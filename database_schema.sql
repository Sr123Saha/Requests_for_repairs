CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fio TEXT NOT NULL,
        phone TEXT NOT NULL,
        login TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        user_type TEXT NOT NULL CHECK (
            user_type IN ('Менеджер', 'Специалист', 'Оператор', 'Заказчик', 'Менеджер по качеству')
        ),
        is_active INTEGER DEFAULT 1,
        registration_date TEXT DEFAULT (DATE('now')),
        email TEXT,
        address TEXT,
        notes TEXT
    );

CREATE TABLE sqlite_sequence(name,seq);

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
    );

CREATE TABLE comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        message TEXT NOT NULL,
        is_internal INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (DATETIME('now'))
    );

CREATE TABLE reviews (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER UNIQUE NOT NULL REFERENCES requests(request_id),
        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
        feedback TEXT,
        suggestions TEXT,
        review_date TEXT DEFAULT (DATE('now')),
        is_anonymous INTEGER DEFAULT 0
    );

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
    );

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
    );

CREATE TABLE request_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
        old_status TEXT,
        new_status TEXT NOT NULL,
        changed_by INTEGER REFERENCES users(user_id),
        change_reason TEXT,
        changed_at TEXT DEFAULT (DATETIME('now'))
    );

CREATE TABLE specializations (
        spec_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        equipment_type TEXT NOT NULL,
        skill_level TEXT CHECK (skill_level IN ('Начальный', 'Средний', 'Эксперт')),
        certification_date TEXT,
        UNIQUE(user_id, equipment_type)
    );

CREATE TABLE notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(user_id),
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT CHECK (notification_type IN ('info', 'warning', 'error', 'success')),
        is_read INTEGER DEFAULT 0,
        related_request_id INTEGER REFERENCES requests(request_id),
        created_at TEXT DEFAULT (DATETIME('now'))
    );

CREATE INDEX idx_users_type ON users(user_type);
CREATE INDEX idx_users_login ON users(login);
CREATE INDEX idx_requests_status ON requests(request_status);
CREATE INDEX idx_requests_client ON requests(client_id);
CREATE INDEX idx_requests_master ON requests(master_id);
CREATE INDEX idx_requests_date ON requests(start_date);
CREATE INDEX idx_requests_tech_type ON requests(climate_tech_type);
CREATE INDEX idx_comments_request ON comments(request_id);
CREATE INDEX idx_comments_date ON comments(created_at);
CREATE INDEX idx_requestparts_status ON request_parts(status);
CREATE INDEX idx_requestparts_request ON request_parts(request_id);
CREATE INDEX idx_requests_number ON requests(request_number);


CREATE TRIGGER update_requests_timestamp 
    AFTER UPDATE ON requests
    BEGIN
        UPDATE requests 
        SET updated_at = DATETIME('now') 
        WHERE request_id = NEW.request_id;
    END;
CREATE TRIGGER track_status_changes 
    AFTER UPDATE OF request_status ON requests
    BEGIN
        INSERT INTO request_history (request_id, old_status, new_status, changed_by)
        VALUES (NEW.request_id, OLD.request_status, NEW.request_status, NEW.master_id);
    END;
CREATE TRIGGER generate_request_number 
    AFTER INSERT ON requests
    BEGIN
        UPDATE requests 
        SET request_number = 'REQ-' || strftime('%Y%m', 'now') || '-' || printf('%04d', NEW.request_id)
        WHERE request_id = NEW.request_id;
    END;
CREATE TRIGGER check_min_quantity 
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
