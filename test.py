import sqlite3
import os
from datetime import datetime


def create_database(db_name='climate_repair.db'):
    """
    Создает базу данных для учета заявок на ремонт климатического оборудования.
    """
    if os.path.exists(db_name):
        os.remove(db_name)
        print(f"Удалена старая база данных: {db_name}")

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    print(f"Создаю базу данных: {db_name}")

    cursor.execute("PRAGMA foreign_keys = ON;")

    print("Создаю таблицу 'users'...")
    cursor.execute(
        '''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fio TEXT NOT NULL,
            phone TEXT,
            login TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL CHECK (
                user_type IN ('Администратор', 'Менеджер', 'Специалист', 'Оператор', 'Заказчик', 'Менеджер по качеству')
            ),
            is_active INTEGER DEFAULT 1,
            registration_date TEXT DEFAULT (DATE('now')),
            email TEXT,
            address TEXT,
            notes TEXT
        )
        '''
    )

    print("Создаю таблицу 'requests'...")
    cursor.execute(
        '''
        CREATE TABLE requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_number TEXT UNIQUE,
            start_date TEXT NOT NULL,
            climate_tech_type TEXT NOT NULL,
            climate_tech_model TEXT NOT NULL,
            problem_description TEXT NOT NULL,
            request_status TEXT NOT NULL DEFAULT 'Новая заявка' CHECK (
                request_status IN ('Новая заявка', 'В процессе ремонта', 'Ожидание комплектующих',
                                    'Готова к выдаче', 'Завершена', 'Отменена')
            ),
            priority TEXT DEFAULT 'Средний' CHECK (priority IN ('Низкий', 'Средний', 'Высокий', 'Критичный')),
            completion_date TEXT,
            repair_parts TEXT,
            estimated_time INTEGER,

            master_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
            client_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            quality_manager_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,

            deadline_extension TEXT,
            extension_reason TEXT,
            customer_agreement INTEGER DEFAULT 0,

            qr_code_generated INTEGER DEFAULT 0,
            qr_code_token TEXT UNIQUE,
            feedback_received INTEGER DEFAULT 0,

            created_at TEXT DEFAULT (DATETIME('now')),
            updated_at TEXT DEFAULT (DATETIME('now'))
        )
        '''
    )

    print("Создаю таблицу 'comments'...")
    cursor.execute(
        '''
        CREATE TABLE comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            message TEXT NOT NULL,
            is_internal INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (DATETIME('now'))
        )
        '''
    )

    print("Создаю таблицу 'reviews'...")
    cursor.execute(
        '''
        CREATE TABLE reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER UNIQUE NOT NULL REFERENCES requests(request_id),
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            feedback TEXT,
            suggestions TEXT,
            review_date TEXT DEFAULT (DATE('now')),
            is_anonymous INTEGER DEFAULT 0
        )
        '''
    )

    print("Создаю таблицу 'spare_parts'...")
    cursor.execute(
        '''
        CREATE TABLE spare_parts (
            part_id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_code TEXT UNIQUE NOT NULL,
            part_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            manufacturer TEXT,
            quantity_in_stock INTEGER DEFAULT 0,
            min_quantity INTEGER DEFAULT 5,
            price REAL,
            unit TEXT DEFAULT 'шт.',
            last_restock_date TEXT
        )
        '''
    )

    print("Создаю таблицу 'request_parts'...")
    cursor.execute(
        '''
        CREATE TABLE request_parts (
            request_part_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
            part_id INTEGER NOT NULL REFERENCES spare_parts(part_id),
            quantity_needed INTEGER NOT NULL CHECK (quantity_needed > 0),
            quantity_used INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Требуется' CHECK (
                status IN ('Требуется', 'Заказан', 'Поступил', 'Установлен', 'Отменен')
            ),
            order_date TEXT,
            expected_date TEXT,
            actual_date TEXT,
            notes TEXT
        )
        '''
    )

    print("Создаю таблицу 'request_history'...")
    cursor.execute(
        '''
        CREATE TABLE request_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by INTEGER REFERENCES users(user_id),
            change_reason TEXT,
            changed_at TEXT DEFAULT (DATETIME('now'))
        )
        '''
    )

    print("Создаю таблицу 'specializations'...")
    cursor.execute(
        '''
        CREATE TABLE specializations (
            spec_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            equipment_type TEXT NOT NULL,
            skill_level TEXT CHECK (skill_level IN ('Начальный', 'Средний', 'Эксперт')),
            certification_date TEXT,
            UNIQUE(user_id, equipment_type)
        )
        '''
    )

    print("Создаю таблицу 'notifications'...")
    cursor.execute(
        '''
        CREATE TABLE notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id),
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT CHECK (notification_type IN ('info', 'warning', 'error', 'success')),
            is_read INTEGER DEFAULT 0,
            related_request_id INTEGER REFERENCES requests(request_id),
            created_at TEXT DEFAULT (DATETIME('now'))
        )
        '''
    )

    print("Все таблицы созданы успешно!")

    print("Создаю индексы для ускорения запросов...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_login ON users(login);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(request_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_client ON requests(client_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_master ON requests(master_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_date ON requests(start_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_tech_type ON requests(climate_tech_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_request ON comments(request_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_date ON comments(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requestparts_status ON request_parts(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requestparts_request ON request_parts(request_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_number ON requests(request_number);")

    print("Индексы созданы успешно!")

    print("Создаю триггеры для автоматизации...")
    cursor.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS update_requests_timestamp 
        AFTER UPDATE ON requests
        BEGIN
            UPDATE requests 
            SET updated_at = DATETIME('now') 
            WHERE request_id = NEW.request_id;
        END;
        '''
    )

    cursor.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS track_status_changes 
        AFTER UPDATE OF request_status ON requests
        BEGIN
            INSERT INTO request_history (request_id, old_status, new_status, changed_by)
            VALUES (NEW.request_id, OLD.request_status, NEW.request_status, NEW.master_id);
        END;
        '''
    )

    cursor.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS generate_request_number 
        AFTER INSERT ON requests
        BEGIN
            UPDATE requests 
            SET request_number = 'REQ-' || strftime('%Y%m', 'now') || '-' || printf('%04d', NEW.request_id)
            WHERE request_id = NEW.request_id;
        END;
        '''
    )

    cursor.execute(
        '''
        CREATE TRIGGER IF NOT EXISTS check_min_quantity 
        AFTER UPDATE OF quantity_in_stock ON spare_parts
        WHEN NEW.quantity_in_stock <= NEW.min_quantity
        BEGIN
            INSERT INTO notifications (user_id, title, message, notification_type)
            VALUES (
                1,
                'Низкий запас комплектующих',
                'Комплектующее ' || NEW.part_name || ' (' || NEW.part_code || ') почти закончилось. Осталось: ' || NEW.quantity_in_stock || ' шт.',
                'warning'
            );
        END;
        '''
    )

    print("Триггеры созданы успешно!")

    print("Добавляю тестовые данные...")
    test_users = [
        (1, 'Широков Василий Матвеевич', '89210563128', 'login1', 'pass1', 'Менеджер'),
        (2, 'Кудрявцева Ева Ивановна', '89535078985', 'login2', 'pass2', 'Специалист'),
        (3, 'Гончарова Ульяна Ярославовна', '89210673849', 'login3', 'pass3', 'Специалист'),
        (4, 'Гусева Виктория Данииловна', '89990563748', 'login4', 'pass4', 'Оператор'),
        (5, 'Баранов Артём Юрьевич', '89994563847', 'login5', 'pass5', 'Оператор'),
        (6, 'Овчинников Фёдор Никитич', '89219567849', 'login6', 'pass6', 'Заказчик'),
        (7, 'Петров Никита Артёмович', '89219567841', 'login7', 'pass7', 'Заказчик'),
        (8, 'Ковалева Софья Владимировна', '89219567842', 'login8', 'pass8', 'Заказчик'),
        (9, 'Кузнецов Сергей Матвеевич', '89219567843', 'login9', 'pass9', 'Заказчик'),
        (10, 'Беспалова Екатерина Даниэльевна', '89219567844', 'login10', 'pass10', 'Специалист'),
        (11, 'Менеджер Качества Тестовый', '89001234567', 'quality1', 'qpass1', 'Менеджер по качеству'),
    ]
    cursor.executemany(
        '''
        INSERT OR IGNORE INTO users (user_id, fio, phone, login, password, user_type) 
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        test_users,
    )

    test_parts = [
        ('FILT-001', 'Фильтр воздушный', 'Фильтр для кондиционера', 'Фильтр', 'TCL', 25, 10, 1200.50),
        ('COMP-002', 'Компрессор', 'Компрессор 1.5 кВт', 'Компрессор', 'Daikin', 5, 3, 8500.00),
        ('FAN-003', 'Вентилятор', 'Вентилятор охлаждения', 'Вентилятор', 'Electrolux', 15, 5, 3200.00),
        ('PCB-004', 'Плата управления', 'Основная плата управления', 'Электроника', 'Xiaomi', 8, 4, 4500.00),
        ('SENS-005', 'Датчик температуры', 'Термодатчик', 'Датчик', 'Polaris', 30, 15, 850.00),
    ]
    cursor.executemany(
        '''
        INSERT INTO spare_parts (part_code, part_name, description, category, manufacturer, 
                                quantity_in_stock, min_quantity, price) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        test_parts,
    )

    test_specializations = [
        (2, 'Кондиционер', 'Эксперт', '2022-05-15'),
        (2, 'Увлажнитель воздуха', 'Средний', '2023-01-20'),
        (3, 'Кондиционер', 'Средний', '2022-08-10'),
        (3, 'Сушилка для рук', 'Начальный', '2023-03-05'),
        (10, 'Кондиционер', 'Эксперт', '2021-11-30'),
        (10, 'Увлажнитель воздуха', 'Эксперт', '2022-06-25'),
    ]
    cursor.executemany(
        '''
        INSERT INTO specializations (user_id, equipment_type, skill_level, certification_date)
        VALUES (?, ?, ?, ?)
        ''',
        test_specializations,
    )

    print("Тестовые данные добавлены!")

    print("\nПроверяю структуру базы данных...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("\nСозданные таблицы:")
    for index, table in enumerate(tables, 1):
        print(f"  {index}. {table[0]}")

    print("\nСтруктура таблицы 'users':")
    cursor.execute("PRAGMA table_info(users);")
    for col in cursor.fetchall():
        print(f"  - {col[1]} ({col[2]})")

    conn.commit()
    conn.close()

    file_size = os.path.getsize(db_name) / 1024

    print("\n" + "=" * 50)
    print("БАЗА ДАННЫХ УСПЕШНО СОЗДАНА!")
    print(f"Файл: {db_name}")
    print(f"Размер: {file_size:.2f} КБ")
    print(f"Создана: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    return db_name


def test_database_connection(db_name='climate_repair.db'):
    """
    Тестирует подключение к базе данных и показывает простую статистику.
    """
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        print(f"\nТЕСТИРУЮ ПОДКЛЮЧЕНИЕ К БАЗЕ: {db_name}")

        tables = ['users', 'requests', 'spare_parts', 'specializations']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} записей")

        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        print(f"Внешние ключи: {'ВКЛЮЧЕНЫ' if fk_status else 'ВЫКЛЮЧЕНЫ'}")

        cursor.execute(
            '''
            SELECT user_id, fio, user_type 
            FROM users 
            WHERE user_type = 'Специалист'
            '''
        )
        print("\nСпециалисты в системе:")
        for row in cursor.fetchall():
            print(f"    ID: {row[0]}, ФИО: {row[1]}, Должность: {row[2]}")

        conn.close()
        print("\nТестирование завершено успешно!")
    except Exception as exc:
        print(f"Ошибка при тестировании: {exc}")


def export_schema_to_file(db_name='climate_repair.db', output_file='database_schema.sql'):
    """
    Экспортирует схему базы данных в SQL файл.
    """
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        with open(output_file, 'w', encoding='utf-8') as file:
            file.write("-- ============================================\n")
            file.write("-- СХЕМА БАЗЫ ДАННЫХ: climate_repair.db\n")
            file.write(f"-- Экспортировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write("-- ============================================\n\n")

            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
            for row in cursor.fetchall():
                file.write(row[0] + ";\n\n")

            cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
            for row in cursor.fetchall():
                file.write(row[0] + ";\n")

            cursor.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL;")
            for row in cursor.fetchall():
                file.write(row[0] + ";\n")

        conn.close()
        print(f"Схема экспортирована в файл: {output_file}")
    except Exception as exc:
        print(f"Ошибка при экспорте: {exc}")


def main():
    """
    Основная функция для создания и тестирования базы данных.
    """
    print("=" * 60)
    print("СОЗДАНИЕ БАЗЫ ДАННЫХ ДЛЯ УЧЕТА ЗАЯВОК НА РЕМОНТ")
    print("=" * 60)

    db_name = create_database()
    test_database_connection(db_name)
    export_schema_to_file(db_name)

    print("\n" + "=" * 60)
    print("ЧТО ДАЛЬШЕ:")
    print("1. База данных готова к импорту ваших данных")
    print("2. Файл 'climate_repair.db' можно использовать в приложении")
    print("3. Файл 'database_schema.sql' содержит полную схему")
    print("4. Для импорта данных используйте pandas или sqlite3")
    print("=" * 60)


if __name__ == "__main__":
    main()