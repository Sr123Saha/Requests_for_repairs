import os
import io
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file,
    abort,
    flash,
)
import qrcode


DB_NAME = "climate_repair.db"

# Ссылка на Google‑форму из ТЗ
FEEDBACK_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSdhZcExx6LSIXxk0ub55mSu-WIh23WYdGG9HY5EZhLDo7P8eA/viewform?usp=sf_link"
)


def get_connection():
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(
            f"Файл базы данных '{DB_NAME}' не найден. "
            f"Сначала запустите 'test.py' для создания БД."
        )
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


app = Flask(__name__)
app.secret_key = "very-secret-key-for-demo"  # для сессий; в реальном проекте вынести в переменные окружения


# =====================  ШАБЛОНЫ  =====================
# Шаблоны теперь в папке templates/


# =====================  ВСПОМОГАТЕЛЬНОЕ  =====================

def login_required(view_func):
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    wrapper.__name__ = view_func.__name__
    return wrapper


def manager_required(view_func):
    """Только для менеджеров и администраторов"""
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        user_type = session.get("user", {}).get("user_type")
        if user_type not in ["Менеджер", "Администратор"]:
            flash("Доступ запрещён. Требуются права менеджера или администратора.", "danger")
            return redirect(url_for("requests_list"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def admin_required(view_func):
    """Только для администраторов"""
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("user", {}).get("user_type") != "Администратор":
            flash("Доступ запрещён. Требуются права администратора.", "danger")
            return redirect(url_for("requests_list"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def can_edit_request(request_id, user):
    """
    Проверка прав на редактирование заявки
    Возвращает (может_редактировать, может_менять_статус, может_менять_всё)
    """
    user_type = user.get("user_type")
    user_id = user.get("user_id")
    
    if user_type == "Администратор" or user_type == "Менеджер":
        return (True, True, True)  # Может всё
    
    try:
        conn = get_connection()
        with conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT client_id, master_id FROM requests WHERE request_id = ?",
                (request_id,)
            )
            row = cur.fetchone()
            if not row:
                return (False, False, False)
            
            client_id = row["client_id"]
            master_id = row["master_id"]
    except:
        return (False, False, False)
    
    if user_type == "Заказчик":
        # Заказчик может редактировать только свои заявки (дату и проблему)
        if client_id == user_id:
            return (True, False, False)
        return (False, False, False)
    
    if user_type == "Специалист":
        # Специалист может менять статус и добавлять комментарии к назначенным заявкам
        if master_id == user_id:
            return (True, True, False)
        return (False, False, False)
    
    if user_type == "Оператор":
        # Оператор может редактировать базовые данные и менять статус
        return (True, True, False)
    
    return (False, False, False)


# =====================  МАРШРУТЫ  =====================

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("requests_list"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        if not login_value or not password:
            flash("Введите логин и пароль.", "warning")
        else:
            try:
                conn = get_connection()
            except FileNotFoundError as exc:
                flash(str(exc), "danger")
                return render_template("login.html", current_user=session.get("user"))

            with conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT user_id, fio, user_type
                    FROM users
                    WHERE login = ? AND password = ?
                    """,
                    (login_value, password),
                )
                row = cur.fetchone()

            if row is None:
                flash("Неверный логин или пароль.", "danger")
            else:
                session["user"] = {
                    "user_id": row["user_id"],
                    "fio": row["fio"],
                    "user_type": row["user_type"],
                }
                flash(f"Добро пожаловать, {row['fio']}!", "success")
                return redirect(url_for("requests_list"))

    return render_template("login.html", current_user=session.get("user"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация нового пользователя. Все получают роль 'Заказчик' по умолчанию."""
    if request.method == "POST":
        fio = request.form.get("fio", "").strip()
        phone = request.form.get("phone", "").strip()  # Необязательное поле
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        password_confirm = request.form.get("password_confirm", "").strip()

        if not (fio and login_value and password):
            flash("Заполните все обязательные поля (ФИО, логин, пароль).", "warning")
        elif password != password_confirm:
            flash("Пароли не совпадают.", "warning")
        else:
            try:
                conn = get_connection()
            except FileNotFoundError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("register"))

            with conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        """
                        INSERT INTO users (fio, phone, login, password, user_type)
                        VALUES (?, ?, ?, ?, 'Заказчик')
                        """,
                        (fio, phone if phone else None, login_value, password),
                    )
                    conn.commit()
                    flash("Регистрация успешна! Теперь вы можете войти в систему.", "success")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    flash("Логин уже используется. Выберите другой логин.", "danger")

    return render_template("register.html", current_user=session.get("user"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


@app.route("/requests")
@login_required
def requests_list():
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return render_template("requests_list.html", 
                                current_user=session.get("user"),
                                requests=[])

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
                r.problem_description,
                r.request_status,
                r.master_id,
                u.fio AS client_fio,
                m.fio AS master_fio,
                m.phone AS master_phone
            FROM requests r
            LEFT JOIN users u ON r.client_id = u.user_id
            LEFT JOIN users m ON r.master_id = m.user_id
            ORDER BY r.start_date DESC, r.request_id DESC
            """
        )
        rows = cur.fetchall()

    current_user = session.get("user", {})
    
    # Цветные бейджи статусов
    status_classes = {
        'Новая заявка': 'bg-secondary',
        'В процессе ремонта': 'bg-warning text-dark',
        'Ожидание комплектующих': 'bg-warning text-dark',
        'Готова к выдаче': 'bg-primary',
        'Завершена': 'bg-success',
        'Отменена': 'bg-danger',
    }
    
    # Формируем список заявок с дополнительной информацией
    requests_list = []
    for r in rows:
        can_edit, can_status, can_all = can_edit_request(r['request_id'], current_user)
        requests_list.append({
            'request_id': r['request_id'],
            'request_number': r['request_number'],
            'start_date': r['start_date'],
            'climate_tech_type': r['climate_tech_type'],
            'climate_tech_model': r['climate_tech_model'],
            'problem_description': r['problem_description'],
            'client_fio': r['client_fio'],
            'request_status': r['request_status'],
            'master_fio': r['master_fio'],
            'master_phone': r['master_phone'],
            'status_class': status_classes.get(r['request_status'], 'bg-info'),
            'can_edit': can_edit
        })
    
    return render_template("requests_list.html", 
                            current_user=current_user,
                            requests=requests_list)


@app.route("/requests/new", methods=["GET", "POST"])
@login_required
def new_request():
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return render_template("new_request.html",
                                current_user=session.get("user"),
                                clients=[],
                                specialists=[],
                                today=datetime.now().strftime("%Y-%m-%d"))

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
        clients = cur.fetchall()

    if request.method == "POST":
        client_id = request.form.get("client_id", "").strip()
        start_date = request.form.get("start_date", "").strip()
        climate_type = request.form.get("climate_tech_type", "").strip()
        climate_model = request.form.get("climate_tech_model", "").strip()
        problem = request.form.get("problem_description", "").strip()
        master_id = request.form.get("master_id", "").strip() or None

        if not (client_id and start_date and climate_type and climate_model and problem):
            flash("Заполните все обязательные поля.", "warning")
        else:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                flash("Дата должна быть в формате ГГГГ-ММ-ДД.", "warning")
            else:
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
                            client_id,
                            master_id
                        )
                        VALUES (?, ?, ?, ?, 'Новая заявка', ?, ?)
                        """,
                        (start_date, climate_type, climate_model, problem, client_id, master_id),
                    )
                    request_id = cur.lastrowid
                    cur.execute(
                        "SELECT request_number FROM requests WHERE request_id = ?",
                        (request_id,),
                    )
                    row = cur.fetchone()

                flash(
                    f"Заявка создана. ID: {request_id}, номер: {row['request_number']}",
                    "success",
                )
                return redirect(url_for("requests_list", created="true"))

    # Получаем список специалистов для назначения
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, fio, phone
            FROM users
            WHERE user_type IN ('Специалист', 'Менеджер') AND is_active = 1
            ORDER BY fio
            """
        )
        specialists = cur.fetchall()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    return render_template("new_request.html",
                            current_user=session.get("user"),
                            clients=clients,
                            specialists=specialists,
                            today=today)


@app.route("/clients/new", methods=["GET", "POST"])
@login_required
def new_client():
    """
    Создание нового заказчика. Доступно только для роли 'Менеджер'.
    """
    current = session.get("user")
    if not current or current.get("user_type") != "Менеджер":
        flash("Доступ к созданию заказчиков разрешён только менеджеру.", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        fio = request.form.get("fio", "").strip()
        phone = request.form.get("phone", "").strip()
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        if not (fio and phone and login_value and password):
            flash("Заполните все поля.", "warning")
        else:
            try:
                conn = get_connection()
            except FileNotFoundError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("requests_list"))

            with conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        """
                        INSERT INTO users (fio, phone, login, password, user_type)
                        VALUES (?, ?, ?, ?, 'Заказчик')
                        """,
                        (fio, phone, login_value, password),
                    )
                    conn.commit()
                    flash("Заказчик успешно создан.", "success")
                    return redirect(url_for("new_request"))
                except sqlite3.IntegrityError:
                    flash("Логин уже используется. Выберите другой логин.", "danger")

    return render_template("new_client.html", current_user=session.get("user"))


@app.route("/requests/<int:request_id>/edit", methods=["GET", "POST"])
@login_required
def edit_request(request_id):
    """Редактирование заявки с проверкой прав доступа"""
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("requests_list"))
    
    current_user = session.get("user", {})
    can_edit, can_status, can_all = can_edit_request(request_id, current_user)
    
    if not can_edit:
        flash("У вас нет прав для редактирования этой заявки.", "danger")
        return redirect(url_for("requests_list"))
    
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 
                r.request_id, r.request_number, r.start_date,
                r.climate_tech_type, r.climate_tech_model,
                r.problem_description, r.request_status,
                r.completion_date, r.master_id, r.client_id,
                u.fio AS client_fio,
                m.fio AS master_fio,
                m.phone AS master_phone
            FROM requests r
            LEFT JOIN users u ON r.client_id = u.user_id
            LEFT JOIN users m ON r.master_id = m.user_id
            WHERE r.request_id = ?
            """,
            (request_id,)
        )
        request_data = cur.fetchone()
        
        if not request_data:
            flash("Заявка не найдена.", "danger")
            return redirect(url_for("requests_list"))
        
        # Получаем список специалистов для назначения
        cur.execute(
            """
            SELECT user_id, fio, phone
            FROM users
            WHERE user_type IN ('Специалист', 'Менеджер') AND is_active = 1
            ORDER BY fio
            """
        )
        specialists = cur.fetchall()
        
        # Получаем список заказчиков (для менеджера)
        cur.execute(
            """
            SELECT user_id, fio
            FROM users
            WHERE user_type = 'Заказчик' AND is_active = 1
            ORDER BY fio
            """
        )
        clients = cur.fetchall()
    
    if request.method == "POST":
        start_date = request.form.get("start_date", "").strip()
        climate_type = request.form.get("climate_tech_type", "").strip()
        climate_model = request.form.get("climate_tech_model", "").strip()
        problem = request.form.get("problem_description", "").strip()
        status = request.form.get("request_status", "").strip()
        completion_date = request.form.get("completion_date", "").strip() or None
        master_id = request.form.get("master_id", "").strip() or None
        client_id = request.form.get("client_id", "").strip() if can_all else None
        
        if not (start_date and climate_type and climate_model and problem):
            flash("Заполните все обязательные поля.", "warning")
        else:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                if completion_date:
                    datetime.strptime(completion_date, "%Y-%m-%d")
            except ValueError:
                flash("Дата должна быть в формате ГГГГ-ММ-ДД.", "warning")
            else:
                with conn:
                    cur = conn.cursor()
                    
                    # Формируем SQL запрос в зависимости от прав
                    if can_all:
                        # Менеджер может менять всё
                        cur.execute(
                            """
                            UPDATE requests SET
                                start_date = ?,
                                climate_tech_type = ?,
                                climate_tech_model = ?,
                                problem_description = ?,
                                request_status = ?,
                                completion_date = ?,
                                master_id = ?,
                                client_id = ?
                            WHERE request_id = ?
                            """,
                            (start_date, climate_type, climate_model, problem,
                            status, completion_date, master_id, client_id or request_data['client_id'],
                            request_id)
                        )
                    elif can_status:
                        # Оператор/Специалист может менять статус и базовые данные
                        cur.execute(
                            """
                            UPDATE requests SET
                                start_date = ?,
                                climate_tech_type = ?,
                                climate_tech_model = ?,
                                problem_description = ?,
                                request_status = ?,
                                completion_date = ?,
                                master_id = ?
                            WHERE request_id = ?
                            """,
                            (start_date, climate_type, climate_model, problem,
                            status, completion_date, master_id, request_id)
                        )
                    else:
                        # Заказчик может менять только дату и проблему
                        cur.execute(
                            """
                            UPDATE requests SET
                                start_date = ?,
                                problem_description = ?
                            WHERE request_id = ?
                            """,
                            (start_date, problem, request_id)
                        )
                
                flash("Заявка успешно обновлена.", "success")
                return redirect(url_for("requests_list", edited="true"))
    
    # Статусы заявок
    statuses = ['Новая заявка', 'В процессе ремонта', 'Ожидание комплектующих', 
                'Готова к выдаче', 'Завершена', 'Отменена']
    
    return render_template("edit_request.html",
                            current_user=current_user,
                            request_data=request_data,
                            specialists=specialists,
                            clients=clients if can_all else [],
                            statuses=statuses,
                            can_all=can_all,
                            can_status=can_status)


@app.route("/stats")
@login_required
def stats():
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return render_template("stats.html",
                                current_user=session.get("user"),
                                finished_count=0,
                                avg_days_str=None,
                                type_rows=[])

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

    avg_days_str = f"{avg_days:.2f}" if avg_days is not None else None
    
    type_list = ""
    if type_rows:
        for r in type_rows:
            type_list += f"<li>{r['climate_tech_type']}: {r['cnt']}</li>"
    else:
        type_list = "<p>Заявок пока нет.</p>"
    
    return render_template("stats.html",
                            current_user=session.get("user"),
                            finished_count=finished_count,
                            avg_days_str=avg_days_str,
                            type_rows=type_rows)


@app.route("/users/manage", methods=["GET", "POST"])
@login_required
@manager_required
def manage_users():
    """Управление пользователями - для администратора и менеджера. Позволяет менять роли и редактировать пользователей."""
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("requests_list"))
    
    current_user_role = session.get("user", {}).get("user_type")
    
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        user_id = request.form.get("user_id", "").strip()
        
        if action == "edit_user":
            # Редактирование пользователя (все поля кроме пароля)
            fio = request.form.get("fio", "").strip()
            phone = request.form.get("phone", "").strip() or None
            login_value = request.form.get("login", "").strip()
            new_role = request.form.get("user_type", "").strip()
            is_active = request.form.get("is_active", "").strip()
            
            if not (user_id and fio and login_value and new_role):
                flash("Заполните все обязательные поля (ФИО, логин, роль).", "warning")
            else:
                try:
                    with conn:
                        cur = conn.cursor()
                        # Проверяем, что пользователь существует
                        cur.execute("SELECT user_id, fio, user_type FROM users WHERE user_id = ?", (user_id,))
                        user = cur.fetchone()
                        if not user:
                            flash("Пользователь не найден.", "danger")
                        else:
                            # Проверяем, не занят ли логин другим пользователем
                            cur.execute("SELECT user_id FROM users WHERE login = ? AND user_id != ?", (login_value, user_id))
                            if cur.fetchone():
                                flash("Логин уже используется другим пользователем.", "danger")
                            else:
                                # Проверяем валидность роли
                                valid_roles = ['Администратор', 'Менеджер', 'Специалист', 'Оператор', 'Заказчик', 'Менеджер по качеству']
                                if new_role not in valid_roles:
                                    flash("Некорректная роль.", "danger")
                                else:
                                    # Обновляем данные пользователя (все кроме пароля)
                                    is_active_value = 1 if is_active == "1" else 0
                                    cur.execute(
                                        """
                                        UPDATE users 
                                        SET fio = ?, phone = ?, login = ?, user_type = ?, is_active = ?
                                        WHERE user_id = ?
                                        """,
                                        (fio, phone, login_value, new_role, is_active_value, user_id)
                                    )
                                    conn.commit()
                                    flash(f"Данные пользователя '{fio}' успешно обновлены.", "success")
                                    return redirect(url_for("manage_users"))
                except Exception as e:
                    flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
    
    # Получаем список всех пользователей
    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, fio, phone, login, user_type, registration_date, is_active
            FROM users
            ORDER BY user_type, fio
            """
        )
        users = cur.fetchall()
    
    roles = ['Администратор', 'Менеджер', 'Специалист', 'Оператор', 'Заказчик', 'Менеджер по качеству']
    
    return render_template("manage_users.html",
                        current_user=session.get("user"),
                        users=users,
                        roles=roles,
                        current_user_role=current_user_role)


@app.route("/qr/<int:request_id>")
@login_required
def qr_for_request(request_id: int):
    """
    Генерация QR‑кода для формы отзыва.
    Для простоты ТЗ генерируем QR на одну и ту же форму,
    можно добавить параметры (request_id, client_id) в URL.
    """
    try:
        conn = get_connection()
    except FileNotFoundError:
        abort(404)

    with conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT request_id FROM requests WHERE request_id = ?",
            (request_id,),
        )
        row = cur.fetchone()

    if row is None:
        abort(404)

    # Можно добавить идентификатор заявки как параметр в ссылку
    url = f"{FEEDBACK_FORM_URL}"

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")


if __name__ == "__main__":
    # Для учебного проекта можно оставить debug=True
    app.run(debug=True)


