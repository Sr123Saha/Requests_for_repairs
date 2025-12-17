
"""
Скрипт для импорта данных из CSV файлов в базу данных
"""
import os
import sqlite3
import csv
from datetime import datetime

DB_NAME = "climate_repair.db"

CSV_USERS = "TZ_no_zip/2 неделя/Ресурсы/Кондиционеры_данные/Пользователи/inputDataUsers.csv"
CSV_REQUESTS = "TZ_no_zip/2 неделя/Ресурсы/Кондиционеры_данные/Заявки/inputDataRequests.csv"
CSV_COMMENTS = "TZ_no_zip/2 неделя/Ресурсы/Кондиционеры_данные/Комментарии/inputDataComments.csv"


def get_connection():
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(
            f"База данных '{DB_NAME}' не найдена. Сначала запустите 'test.py'"
        )
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def import_users(conn):
    """Импорт пользователей из CSV"""
    if not os.path.exists(CSV_USERS):
        print(f"Файл {CSV_USERS} не найден, пропускаем импорт пользователей")
        return
    
    print("Импорт пользователей...")
    cur = conn.cursor()
    
    with open(CSV_USERS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        imported = 0
        skipped = 0
        
        for row in reader:
            user_id = int(row['userID'])
            fio = row['fio'].strip()
            phone = row['phone'].strip()
            login = row['login'].strip()
            password = row['password'].strip()
            user_type = row['type'].strip()
            
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, fio, phone, login, password, user_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, fio, phone, login, password, user_type))
                imported += 1
            except sqlite3.IntegrityError as e:
                print(f"  Пропущен пользователь ID {user_id}: {e}")
                skipped += 1
    
    conn.commit()
    print(f"  Импортировано пользователей: {imported}, пропущено: {skipped}")


def import_requests(conn):
    """Импорт заявок из CSV"""
    if not os.path.exists(CSV_REQUESTS):
        print(f"Файл {CSV_REQUESTS} не найден, пропускаем импорт заявок")
        return
    
    print("Импорт заявок...")
    cur = conn.cursor()
    
    with open(CSV_REQUESTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        imported = 0
        skipped = 0
        
        for row in reader:
            request_id = int(row['requestID'])
            start_date = row['startDate'].strip()
            climate_type = row['climateTechType'].strip()
            climate_model = row['climateTechModel'].strip()
            problem = row['problemDescryption'].strip()
            status = row['requestStatus'].strip()
            completion_date = row['completionDate'].strip() if row['completionDate'].strip() != 'null' else None
            repair_parts = row['repairParts'].strip() if row['repairParts'].strip() else None
            master_id = int(row['masterID']) if row['masterID'].strip() and row['masterID'].strip() != 'null' else None
            client_id = int(row['clientID'])

            status_map = {
                'В процессе ремонта': 'В процессе ремонта',
                'Готова к выдаче': 'Готова к выдаче',
                'Новая заявка': 'Новая заявка',
            }
            request_status = status_map.get(status, 'Новая заявка')
            
            try:

                cur.execute("SELECT user_id FROM users WHERE user_id = ?", (client_id,))
                if not cur.fetchone():
                    print(f"  Пропущена заявка ID {request_id}: клиент {client_id} не найден")
                    skipped += 1
                    continue
                
                # Проверяем существование мастера (если указан)
                if master_id:
                    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (master_id,))
                    if not cur.fetchone():
                        master_id = None
                
                cur.execute("""
                    INSERT OR REPLACE INTO requests 
                    (request_id, start_date, climate_tech_type, climate_tech_model,
                    problem_description, request_status, completion_date,
                    repair_parts, master_id, client_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (request_id, start_date, climate_type, climate_model, problem,
                    request_status, completion_date, repair_parts, master_id, client_id))

                cur.execute("""
                    UPDATE requests 
                    SET request_number = 'REQ-' || strftime('%Y%m', start_date) || '-' || printf('%04d', request_id)
                    WHERE request_id = ? AND request_number IS NULL
                """, (request_id,))
                
                imported += 1
            except Exception as e:
                print(f"  Ошибка при импорте заявки ID {request_id}: {e}")
                skipped += 1
    
    conn.commit()
    print(f"  Импортировано заявок: {imported}, пропущено: {skipped}")


def import_comments(conn):
    """Импорт комментариев из CSV"""
    if not os.path.exists(CSV_COMMENTS):
        print(f"Файл {CSV_COMMENTS} не найден, пропускаем импорт комментариев")
        return
    
    print("Импорт комментариев...")
    cur = conn.cursor()
    
    with open(CSV_COMMENTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        imported = 0
        skipped = 0
        
        for row in reader:
            comment_id = int(row['commentID'])
            message = row['message'].strip()
            master_id = int(row['masterID'])
            request_id = int(row['requestID'])
            
            try:

                cur.execute("SELECT request_id FROM requests WHERE request_id = ?", (request_id,))
                if not cur.fetchone():
                    print(f"  Пропущен комментарий ID {comment_id}: заявка {request_id} не найдена")
                    skipped += 1
                    continue
                
                cur.execute("SELECT user_id FROM users WHERE user_id = ?", (master_id,))
                if not cur.fetchone():
                    print(f"  Пропущен комментарий ID {comment_id}: пользователь {master_id} не найден")
                    skipped += 1
                    continue
                
                cur.execute("""
                    INSERT OR REPLACE INTO comments 
                    (comment_id, request_id, user_id, message)
                    VALUES (?, ?, ?, ?)
                """, (comment_id, request_id, master_id, message))
                
                imported += 1
            except Exception as e:
                print(f"  Ошибка при импорте комментария ID {comment_id}: {e}")
                skipped += 1
    
    conn.commit()
    print(f"  Импортировано комментариев: {imported}, пропущено: {skipped}")


def main():
    print("=" * 60)
    print("ИМПОРТ ДАННЫХ ИЗ CSV В БАЗУ ДАННЫХ")
    print("=" * 60)
    
    try:
        conn = get_connection()
        
        print("\nНачинаем импорт...\n")
        
        import_users(conn)
        print()
        
        import_requests(conn)
        print()
        
        import_comments(conn)
        print()
        

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM requests")
        requests_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM comments")
        comments_count = cur.fetchone()[0]
        
        print("=" * 60)
        print("ИТОГО В БАЗЕ ДАННЫХ:")
        print(f"  Пользователей: {users_count}")
        print(f"  Заявок: {requests_count}")
        print(f"  Комментариев: {comments_count}")
        print("=" * 60)
        
        conn.close()
        print("\nИмпорт завершён успешно!")
        
    except FileNotFoundError as e:
        print(f"\nОШИБКА: {e}")
        print("\nСначала запустите: python test.py")
    except Exception as e:
        print(f"\nОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


