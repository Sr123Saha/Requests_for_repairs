import sqlite3
import os
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime


DB_NAME = "climate_repair.db"


def get_connection():
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(
            f"Файл базы данных '{DB_NAME}' не найден. "
            f"Сначала запустите 'test.py' для создания БД."
        )
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Учет заявок на ремонт климатического оборудования")
        self.geometry("900x500")

        self.current_user = None

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for FrameClass in (LoginFrame, MainMenuFrame, RequestsListFrame, NewRequestFrame, StatsFrame):
            frame = FrameClass(parent=container, controller=self)
            self.frames[FrameClass.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LoginFrame")

    def show_frame(self, name: str):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()


class LoginFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        tk.Label(self, text="Авторизация", font=("Arial", 18, "bold")).pack(pady=20)

        form = tk.Frame(self)
        form.pack(pady=10)

        tk.Label(form, text="Логин:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form, text="Пароль:").grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.login_var = tk.StringVar()
        self.password_var = tk.StringVar()

        tk.Entry(form, textvariable=self.login_var).grid(row=0, column=1, padx=5, pady=5)
        tk.Entry(form, textvariable=self.password_var, show="*").grid(row=1, column=1, padx=5, pady=5)

        tk.Button(self, text="Войти", command=self.handle_login).pack(pady=10)

    def handle_login(self):
        login = self.login_var.get().strip()
        password = self.password_var.get().strip()

        if not login or not password:
            messagebox.showwarning("Авторизация", "Введите логин и пароль.")
            return

        try:
            conn = get_connection()
        except FileNotFoundError as exc:
            messagebox.showerror("Ошибка БД", str(exc))
            return

        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, fio, user_type
                FROM users
                WHERE login = ? AND password = ?
                """,
                (login, password),
            )
            row = cur.fetchone()

        if row is None:
            messagebox.showerror("Авторизация", "Неверный логин или пароль.")
            return

        self.controller.current_user = {
            "user_id": row["user_id"],
            "fio": row["fio"],
            "user_type": row["user_type"],
        }
        messagebox.showinfo("Авторизация", f"Добро пожаловать, {row['fio']}!")
        self.controller.show_frame("MainMenuFrame")


class MainMenuFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        self.label_user = tk.Label(self, text="", font=("Arial", 12))
        self.label_user.pack(pady=10)

        tk.Label(self, text="Главное меню", font=("Arial", 18, "bold")).pack(pady=10)

        btns = tk.Frame(self)
        btns.pack(pady=10)

        tk.Button(btns, text="Список заявок", width=20,
                  command=lambda: controller.show_frame("RequestsListFrame")).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(btns, text="Новая заявка", width=20,
                  command=lambda: controller.show_frame("NewRequestFrame")).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(btns, text="Статистика", width=20,
                  command=lambda: controller.show_frame("StatsFrame")).grid(row=0, column=2, padx=5, pady=5)

        tk.Button(self, text="Выход из приложения", command=self.quit).pack(pady=10)

    def on_show(self):
        user = self.controller.current_user
        if user:
            self.label_user.config(
                text=f"Пользователь: {user['fio']} ({user['user_type']})"
            )


class RequestsListFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        header = tk.Frame(self)
        header.pack(fill="x")

        tk.Label(header, text="Список заявок", font=("Arial", 16, "bold")).pack(side="left", padx=10, pady=10)
        tk.Button(header, text="Назад", command=lambda: controller.show_frame("MainMenuFrame")).pack(
            side="right", padx=10, pady=10
        )

        columns = ("id", "number", "date", "type", "model", "status", "client")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("number", text="Номер")
        self.tree.heading("date", text="Дата")
        self.tree.heading("type", text="Тип")
        self.tree.heading("model", text="Модель")
        self.tree.heading("status", text="Статус")
        self.tree.heading("client", text="Клиент")

        self.tree.column("id", width=40)
        self.tree.column("number", width=120)
        self.tree.column("date", width=100)
        self.tree.column("type", width=120)
        self.tree.column("model", width=180)
        self.tree.column("status", width=140)
        self.tree.column("client", width=180)

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

    def on_show(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        try:
            conn = get_connection()
        except FileNotFoundError as exc:
            messagebox.showerror("Ошибка БД", str(exc))
            return

        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    r.request_id,
                    r.request_number,
                    r.start_date,
                    r.climate_tech_type,
                    r.climate_tech_model,
                    r.request_status,
                    u.fio AS client_fio
                FROM requests r
                LEFT JOIN users u ON r.client_id = u.user_id
                ORDER BY r.start_date DESC, r.request_id DESC
                """
            )
            rows = cur.fetchall()

        for r in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    r["request_id"],
                    r["request_number"],
                    r["start_date"],
                    r["climate_tech_type"],
                    r["climate_tech_model"],
                    r["request_status"],
                    r["client_fio"],
                ),
            )


class NewRequestFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        header = tk.Frame(self)
        header.pack(fill="x")

        tk.Label(header, text="Новая заявка", font=("Arial", 16, "bold")).pack(side="left", padx=10, pady=10)
        tk.Button(header, text="Назад", command=lambda: controller.show_frame("MainMenuFrame")).pack(
            side="right", padx=10, pady=10
        )

        form = tk.Frame(self)
        form.pack(pady=10, padx=10, fill="x")

        tk.Label(form, text="Заказчик:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form, text="Дата (ГГГГ-ММ-ДД):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form, text="Тип оборудования:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form, text="Модель:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        tk.Label(form, text="Описание проблемы:").grid(row=4, column=0, sticky="ne", padx=5, pady=5)

        self.client_cb = ttk.Combobox(form, state="readonly")
        self.client_cb.grid(row=0, column=1, sticky="we", padx=5, pady=5)

        self.date_var = tk.StringVar()
        self.type_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.problem_text = tk.Text(form, height=5, width=40)

        tk.Entry(form, textvariable=self.date_var).grid(row=1, column=1, sticky="we", padx=5, pady=5)
        tk.Entry(form, textvariable=self.type_var).grid(row=2, column=1, sticky="we", padx=5, pady=5)
        tk.Entry(form, textvariable=self.model_var).grid(row=3, column=1, sticky="we", padx=5, pady=5)
        self.problem_text.grid(row=4, column=1, sticky="we", padx=5, pady=5)

        form.columnconfigure(1, weight=1)

        tk.Button(self, text="Сохранить заявку", command=self.save_request).pack(pady=10)

    def on_show(self):
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.type_var.set("")
        self.model_var.set("")
        self.problem_text.delete("1.0", tk.END)

        try:
            conn = get_connection()
        except FileNotFoundError as exc:
            messagebox.showerror("Ошибка БД", str(exc))
            return

        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, fio
                FROM users
                WHERE user_type = 'Заказчик'
                ORDER BY fio
                """
            )
            rows = cur.fetchall()

        self.clients = rows
        self.client_cb["values"] = [f"{r['user_id']}: {r['fio']}" for r in rows]
        if rows:
            self.client_cb.current(0)

    def save_request(self):
        if not self.clients:
            messagebox.showwarning("Новая заявка", "В системе нет ни одного заказчика.")
            return

        if not self.client_cb.get():
            messagebox.showwarning("Новая заявка", "Выберите заказчика.")
            return

        date_val = self.date_var.get().strip()
        ctype = self.type_var.get().strip()
        model = self.model_var.get().strip()
        problem = self.problem_text.get("1.0", tk.END).strip()

        if not date_val or not ctype or not model or not problem:
            messagebox.showwarning("Новая заявка", "Заполните все поля.")
            return

        try:
            datetime.strptime(date_val, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Новая заявка", "Дата должна быть в формате ГГГГ-ММ-ДД.")
            return

        client_index = self.client_cb.current()
        client_id = self.clients[client_index]["user_id"]

        try:
            conn = get_connection()
        except FileNotFoundError as exc:
            messagebox.showerror("Ошибка БД", str(exc))
            return

        with conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO requests (
                    start_date,
                    climate_tech_type,
                    climate_tech_model,
                    problem_description,
                    request_status,
                    client_id
                )
                VALUES (?, ?, ?, ?, 'Новая заявка', ?)
                """,
                (date_val, ctype, model, problem, client_id),
            )
            request_id = cur.lastrowid
            cur.execute(
                "SELECT request_number FROM requests WHERE request_id = ?",
                (request_id,),
            )
            row = cur.fetchone()

        messagebox.showinfo(
            "Новая заявка",
            f"Заявка успешно создана.\nID: {request_id}\nНомер: {row['request_number']}",
        )
        self.controller.show_frame("RequestsListFrame")


class StatsFrame(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent)
        self.controller = controller

        header = tk.Frame(self)
        header.pack(fill="x")

        tk.Label(header, text="Статистика", font=("Arial", 16, "bold")).pack(side="left", padx=10, pady=10)
        tk.Button(header, text="Назад", command=lambda: controller.show_frame("MainMenuFrame")).pack(
            side="right", padx=10, pady=10
        )

        self.text = tk.Text(self, height=15)
        self.text.pack(fill="both", expand=True, padx=10, pady=10)
        self.text.config(state="disabled")

    def on_show(self):
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)

        try:
            conn = get_connection()
        except FileNotFoundError as exc:
            messagebox.showerror("Ошибка БД", str(exc))
            self.text.insert("1.0", "Ошибка подключения к базе данных.")
            self.text.config(state="disabled")
            return

        with conn:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM requests
                WHERE request_status = 'Завершена'
                """
            )
            finished_count = cur.fetchone()["cnt"]

            cur.execute(
                """
                SELECT
                    AVG(
                        JULIANDAY(completion_date) - JULIANDAY(start_date)
                    ) AS avg_days
                FROM requests
                WHERE request_status = 'Завершена'
                      AND completion_date IS NOT NULL
                """
            )
            avg_row = cur.fetchone()
            avg_days = avg_row["avg_days"]

            cur.execute(
                """
                SELECT climate_tech_type, COUNT(*) AS cnt
                FROM requests
                GROUP BY climate_tech_type
                ORDER BY cnt DESC
                """
            )
            type_rows = cur.fetchall()

        self.text.insert("end", f"Количество выполненных заявок: {finished_count}\n")
        if avg_days is not None:
            self.text.insert("end", f"Среднее время выполнения заявки: {avg_days:.2f} дня(дней)\n")
        else:
            self.text.insert(
                "end",
                "Недостаточно данных для расчета среднего времени выполнения заявок.\n",
            )

        self.text.insert("end", "\nКоличество заявок по типам оборудования:\n")
        if not type_rows:
            self.text.insert("end", "Заявок пока нет.\n")
        else:
            for r in type_rows:
                self.text.insert("end", f"- {r['climate_tech_type']}: {r['cnt']}\n")

        self.text.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()



