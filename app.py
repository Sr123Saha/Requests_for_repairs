import sqlite3
import os
from datetime import datetime


DB_NAME = "climate_repair.db"


def get_connection():
    """
    Создает подключение к базе данных SQLite.
    Если файл базы данных отсутствует, выводит понятное сообщение.
    """
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(
            f"Файл базы данных '{DB_NAME}' не найден. "
            f"Сначала запустите скрипт 'test.py' для создания базы."
        )

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def input_non_empty(prompt: str) -> str:
    """
    Запрашивает строку у пользователя, пока он не введет непустое значение.
    """
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Поле не может быть пустым. Повторите ввод.")


def show_requests(conn):
    """
    Выводит список заявок с основными полями.
    """
    cursor = conn.cursor()
    cursor.execute(
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

    rows = cursor.fetchall()
    if not rows:
        print("Заявок в системе пока нет.")
        return

    print("\nСписок заявок:")
    print("-" * 80)
    for row in rows:
        print(
            f"ID: {row['request_id']}, "
            f"Номер: {row['request_number'] or '-'}, "
            f"Дата: {row['start_date']}, "
            f"Оборудование: {row['climate_tech_type']} / {row['climate_tech_model']}, "
            f"Клиент: {row['client_fio'] or '-'}, "
            f"Статус: {row['request_status']}"
        )
    print("-" * 80)


def choose_client(conn) -> int:
    """
    Позволяет выбрать существующего клиента по ID.
    Возвращает user_id выбранного клиента.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, fio, phone
        FROM users
        WHERE user_type = 'Заказчик'
        ORDER BY fio
        """
    )
    clients = cursor.fetchall()

    if not clients:
        print("В системе нет ни одного заказчика. Сначала создайте пользователя-заказчика.")
        return -1

    print("\nСписок заказчиков:")
    for row in clients:
        print(f"{row['user_id']}: {row['fio']} ({row['phone']})")

    while True:
        try:
            client_id_str = input("Введите ID заказчика: ").strip()
            client_id = int(client_id_str)
        except ValueError:
            print("Некорректный ID. Введите целое число.")
            continue

        if any(row["user_id"] == client_id for row in clients):
            return client_id

        print("Пользователь с таким ID не найден. Повторите ввод.")


def create_request(conn):
    """
    Создает новую заявку на ремонт.
    Реализует функциональность добавления заявки по ТЗ.
    """
    print("\n=== Создание новой заявки ===")

    client_id = choose_client(conn)
    if client_id == -1:
        return

    start_date_str = input_non_empty(
        "Введите дату начала заявки (ГГГГ-ММ-ДД, пусто = сегодня): "
    )
    if start_date_str.lower() in ("", " "):
        start_date = datetime.now().strftime("%Y-%m-%d")
    else:
        start_date = start_date_str

    climate_type = input_non_empty("Тип оборудования: ")
    climate_model = input_non_empty("Модель оборудования: ")
    problem_description = input_non_empty("Описание проблемы: ")

    valid_statuses = [
        "Новая заявка",
        "В процессе ремонта",
        "Ожидание комплектующих",
        "Готова к выдаче",
        "Завершена",
        "Отменена",
    ]

    print("\nВозможные статусы:")
    for status in valid_statuses:
        print(f"- {status}")

    status = input("Статус (по умолчанию 'Новая заявка'): ").strip()
    if not status:
        status = "Новая заявка"
    if status not in valid_statuses:
        print("Некорректный статус. Будет использован статус 'Новая заявка'.")
        status = "Новая заявка"

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO requests (
            start_date,
            climate_tech_type,
            climate_tech_model,
            problem_description,
            request_status,
            client_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (start_date, climate_type, climate_model, problem_description, status, client_id),
    )
    conn.commit()

    request_id = cursor.lastrowid
    cursor.execute(
        "SELECT request_number FROM requests WHERE request_id = ?",
        (request_id,),
    )
    request_number = cursor.fetchone()[0]

    print(
        f"\nЗаявка успешно создана. ID: {request_id}, "
        f"Номер: {request_number or 'будет сгенерирован триггером'}"
    )


def update_request_status(conn):
    """
    Изменяет статус существующей заявки.
    """
    print("\n=== Изменение статуса заявки ===")
    show_requests(conn)

    try:
        request_id = int(input("Введите ID заявки: ").strip())
    except ValueError:
        print("Некорректный ID заявки.")
        return

    valid_statuses = [
        "Новая заявка",
        "В процессе ремонта",
        "Ожидание комплектующих",
        "Готова к выдаче",
        "Завершена",
        "Отменена",
    ]
    print("\nВозможные статусы:")
    for status in valid_statuses:
        print(f"- {status}")

    new_status = input_non_empty("Введите новый статус: ")
    if new_status not in valid_statuses:
        print("Некорректный статус. Операция отменена.")
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_status FROM requests WHERE request_id = ?",
        (request_id,),
    )
    row = cursor.fetchone()
    if row is None:
        print("Заявка с указанным ID не найдена.")
        return

    cursor.execute(
        """
        UPDATE requests
        SET request_status = ?
        WHERE request_id = ?
        """,
        (new_status, request_id),
    )
    conn.commit()

    print("Статус заявки успешно изменен.")


def add_comment(conn):
    """
    Добавляет комментарий к заявке.
    """
    print("\n=== Добавление комментария к заявке ===")
    show_requests(conn)
    try:
        request_id = int(input("Введите ID заявки: ").strip())
    except ValueError:
        print("Некорректный ID заявки.")
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_id FROM requests WHERE request_id = ?",
        (request_id,),
    )
    if cursor.fetchone() is None:
        print("Заявка с указанным ID не найдена.")
        return

    try:
        user_id = int(input("Введите ID пользователя, оставляющего комментарий: ").strip())
    except ValueError:
        print("Некорректный ID пользователя.")
        return

    cursor.execute(
        "SELECT user_id, fio FROM users WHERE user_id = ?",
        (user_id,),
    )
    user_row = cursor.fetchone()
    if user_row is None:
        print("Пользователь с указанным ID не найден.")
        return

    message = input_non_empty("Текст комментария: ")

    cursor.execute(
        """
        INSERT INTO comments (request_id, user_id, message, is_internal)
        VALUES (?, ?, ?, 0)
        """,
        (request_id, user_id, message),
    )
    conn.commit()

    print(
        f"Комментарий от пользователя '{user_row['fio']}' "
        f"успешно добавлен к заявке ID {request_id}."
    )


def show_statistics(conn):
    """
    Выводит статистику по заявкам:
    - количество выполненных заявок;
    - среднее время выполнения заявки;
    - статистику по типам неисправностей.
    """
    print("\n=== Статистика по заявкам ===")
    cursor = conn.cursor()

    # Количество выполненных заявок
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM requests
        WHERE request_status = 'Завершена'
        """
    )
    finished_count = cursor.fetchone()["cnt"]

    # Среднее время выполнения заявки (в днях)
    cursor.execute(
        """
        SELECT
            AVG(
                JULIANDAY(
                    COALESCE(completion_date, DATE('now'))
                ) - JULIANDAY(start_date)
            ) AS avg_days
        FROM requests
        WHERE request_status = 'Завершена'
                AND completion_date IS NOT NULL
        """
    )
    row = cursor.fetchone()
    avg_days = row["avg_days"]

    # Статистика по типам оборудования и неисправностям
    cursor.execute(
        """
        SELECT
            climate_tech_type,
            COUNT(*) AS cnt
        FROM requests
        GROUP BY climate_tech_type
        ORDER BY cnt DESC
        """
    )
    type_stats = cursor.fetchall()

    print(f"Количество выполненных заявок: {finished_count}")
    if avg_days is not None:
        print(f"Среднее время выполнения заявки: {avg_days:.2f} дня(дней)")
    else:
        print("Недостаточно данных для расчета среднего времени выполнения.")

    print("\nКоличество заявок по типам оборудования:")
    if not type_stats:
        print("Заявок пока нет.")
    else:
        for row in type_stats:
            print(f"- {row['climate_tech_type']}: {row['cnt']}")


def main_menu():
    """
    Простейший консольный интерфейс для работы с модулем.
    Реализует требования ТЗ на уровне прототипа.
    """
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        print(exc)
        return

    while True:
        print("\n=== Модуль учета заявок на ремонт климатического оборудования ===")
        print("1. Показать все заявки")
        print("2. Создать новую заявку")
        print("3. Изменить статус заявки")
        print("4. Добавить комментарий к заявке")
        print("5. Показать статистику")
        print("0. Выход")

        choice = input("Выберите пункт меню: ").strip()

        if choice == "1":
            show_requests(conn)
        elif choice == "2":
            create_request(conn)
        elif choice == "3":
            update_request_status(conn)
        elif choice == "4":
            add_comment(conn)
        elif choice == "5":
            show_statistics(conn)
        elif choice == "0":
            print("Завершение работы.")
            conn.close()
            break
        else:
            print("Некорректный выбор. Повторите ввод.")


if __name__ == "__main__":
    main_menu()
