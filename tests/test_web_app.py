import os
import sys

import pytest

# Добавляем корень проекта в sys.path, чтобы можно было импортировать web_app
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from web_app import app, DB_NAME


@pytest.fixture(scope="module")
def test_client():
    """
    Тестовый клиент Flask.
    Предполагается, что файл БД climate_repair.db уже существует
    и заполнен начальными данными с помощью test.py.
    """
    # убедимся, что БД существует перед запуском тестов
    assert os.path.exists(DB_NAME), f"База данных {DB_NAME} не найдена, сначала запустите test.py"

    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_redirect_without_login(test_client):
    """
    Проверка: неавторизованный пользователь перенаправляется на страницу логина.
    """
    print("\n[TEST] Проверка редиректа на /login без авторизации")
    resp = test_client.get("/requests", follow_redirects=False)
    # должен быть редирект на /login
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers.get("Location", "")


def test_login_wrong_credentials(test_client):
    """
    Проверка: вход с неверными данными не даёт доступ к заявкам.
    """
    print("\n[TEST] Проверка входа с неверным логином/паролем")
    resp = test_client.post(
        "/login",
        data={"login": "wrong_user", "password": "wrong_pass"},
        follow_redirects=True,
    )
    # Страница логина возвращается с кодом 200, но доступ к /requests не даётся
    assert resp.status_code == 200
    assert "Неверный логин или пароль" in resp.get_data(as_text=True)


def test_login_as_manager_and_open_requests(test_client):
    """
    Проверка: менеджер может войти и увидеть список заявок.
    Логин/пароль берутся из демо-данных (см. run_web.py).
    """
    print("\n[TEST] Проверка входа менеджера и открытия списка заявок")
    resp = test_client.post(
        "/login",
        data={"login": "login1", "password": "pass1"},
        follow_redirects=True,
    )
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # после успешного входа должен открыться список заявок
    assert "Список заявок" in text


def test_stats_page_available_for_authorized_user(test_client):
    """
    Проверка: авторизованный пользователь может открыть страницу статистики.
    """
    print("\n[TEST] Проверка доступа к странице статистики для авторизованного пользователя")
    # сначала залогинимся как менеджер
    test_client.post(
        "/login",
        data={"login": "login1", "password": "pass1"},
        follow_redirects=True,
    )

    resp = test_client.get("/stats")
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Статистика" in text
    # на странице должны быть либо числа, либо сообщение об отсутствии данных
    assert ("Количество выполненных заявок" in text) or ("Недостаточно данных" in text)


def test_login_page_get(test_client):
    """
    Проверка: страница /login открывается по GET и содержит форму авторизации.
    """
    print("\n[TEST] Проверка открытия страницы /login по GET")
    resp = test_client.get("/login")
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Авторизация" in text


def test_access_manage_users_requires_login(test_client):
    """
    Проверка: без входа доступ к /users/manage невозможен (редирект на /login).
    """
    print("\n[TEST] Проверка, что /users/manage без входа редиректит на /login")
    # сначала явно выйдем из системы на всякий случай
    test_client.get("/logout", follow_redirects=True)

    resp = test_client.get("/users/manage", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/login" in resp.headers.get("Location", "")


def test_access_manage_users_only_for_manager(test_client):
    """
    Проверка: менеджер может открыть /users/manage.
    (предполагается, что login1/pass1 имеет роль 'Менеджер').
    """
    print("\n[TEST] Проверка, что менеджер имеет доступ к /users/manage")
    test_client.post(
        "/login",
        data={"login": "login1", "password": "pass1"},
        follow_redirects=True,
    )

    resp = test_client.get("/users/manage")
    text = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Управление пользователями" in text



