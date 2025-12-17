
"""
Скрипт для запуска веб-приложения с проверкой зависимостей и БД
"""
import os
import sys

def check_dependencies():
    """Проверка установленных зависимостей"""
    required = ['flask', 'qrcode', 'PIL']
    missing = []
    
    for package in required:
        try:
            if package == 'PIL':
                __import__('PIL')
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("=" * 60)
        print("ОШИБКА: Не установлены необходимые пакеты!")
        print("=" * 60)
        print("Выполните команду:")
        print("  pip install -r requirements.txt")
        print("\nОтсутствующие пакеты:", ", ".join(missing))
        print("=" * 60)
        return False
    
    return True

def check_database():
    """Проверка наличия базы данных"""
    db_name = "climate_repair.db"
    if not os.path.exists(db_name):
        print("=" * 60)
        print("ПРЕДУПРЕЖДЕНИЕ: База данных не найдена!")
        print("=" * 60)
        print(f"Файл '{db_name}' отсутствует.")
        print("\nСначала создайте базу данных:")
        print("  python test.py")
        print("=" * 60)
        return False
    
    return True

def main():
    print("Проверка готовности к запуску...")
    
    if not check_dependencies():
        sys.exit(1)
    
    if not check_database():
        response = input("\nПродолжить запуск без БД? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Запуск веб-приложения...")
    print("=" * 60)
    print("Откройте в браузере: http://127.0.0.1:5000/")
    print("\nТестовые логины:")
    print("  login1 / pass1  (Менеджер)")
    print("  login2 / pass2  (Специалист)")
    print("  login6 / pass6  (Заказчик)")
    print("=" * 60)
    print("\nДля остановки нажмите Ctrl+C\n")
    from web_app import app
    app.run(debug=True, host='127.0.0.1', port=5000)

if __name__ == "__main__":
    main()


