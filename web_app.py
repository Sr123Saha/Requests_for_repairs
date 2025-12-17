import os
import io
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template_string,
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

BASE_HTML = """
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('index') }}">Учёт заявок</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        {% if current_user %}
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('requests_list') }}">Заявки</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('new_request') }}">Новая заявка</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('stats') }}">Статистика</a>
        </li>
        {% if current_user['user_type'] == 'Менеджер' %}
        <li class="nav-item">
          <a class="nav-link" href="{{ url_for('new_client') }}">Новый заказчик</a>
        </li>
        {% endif %}
        {% endif %}
      </ul>
      <span class="navbar-text">
        {% if current_user %}
          {{ current_user['fio'] }} ({{ current_user['user_type'] }}) |
          <a href="{{ url_for('logout') }}" class="btn btn-sm btn-outline-light ms-2">Выход</a>
        {% else %}
          <a href="{{ url_for('login') }}" class="btn btn-sm btn-outline-light">Войти</a>
        {% endif %}
      </span>
    </div>
  </div>
</nav>

<div class="container app-shell">
  <div class="row justify-content-center">
    <div class="col-12 col-lg-11 col-xl-10">
      <div class="card app-card">
        <div class="card-header app-card-header">
          <h5 class="mb-0">{{ title }}</h5>
        </div>
        <div class="card-body bg-white">
          {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
              {% for category, msg in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                  {{ msg }}
                  <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
              {% endfor %}
            {% endif %}
          {% endwith %}

          {{ content|safe }}
        </div>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<div class="toast-container" id="toastContainer"></div>

<script>
  // Функция для показа toast уведомлений
  function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    
    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };
    
    toast.innerHTML = `
      <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 1.5rem;">${icons[type] || icons.info}</span>
        <span style="flex: 1; font-weight: 500;">${message}</span>
        <button onclick="this.parentElement.parentElement.remove()" 
                style="background: none; border: none; font-size: 1.2rem; cursor: pointer; opacity: 0.5;">
          ×
        </button>
      </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 500);
    }, 5000);
  }
  
  // Показываем toast при успешном редактировании (если есть параметр в URL)
  document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const edited = urlParams.get('edited');
    const created = urlParams.get('created');
    
    if (edited === 'true') {
      showToast('Заявка успешно обновлена!', 'success');
    }
    if (created === 'true') {
      showToast('Заявка успешно создана!', 'success');
    }
    
    // Анимация появления элементов
    const cards = document.querySelectorAll('.card, table tbody tr');
    cards.forEach((card, index) => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(20px)';
      setTimeout(() => {
        card.style.transition = 'all 0.5s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      }, index * 50);
    });
    
    // Обработка отправки форм с уведомлением
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
      form.addEventListener('submit', function(e) {
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
          const originalText = submitBtn.innerHTML;
          submitBtn.innerHTML = '⏳ Сохранение...';
          submitBtn.disabled = true;
          
          // Если форма не прошла валидацию, вернём кнопку в исходное состояние
          setTimeout(() => {
            if (!form.checkValidity()) {
              submitBtn.innerHTML = originalText;
              submitBtn.disabled = false;
            }
          }, 100);
        }
      });
    });
    
    // Плавная прокрутка к элементам
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
    
    // Эффект при наведении на кнопки
    document.querySelectorAll('.btn').forEach(btn => {
      btn.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-3px) scale(1.05)';
      });
      btn.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0) scale(1)';
      });
    });
    
    // Валидация форм с визуальной обратной связью
    let changedFields = new Set();
    document.querySelectorAll('input, textarea, select').forEach(input => {
      const initialValue = input.value;
      
      input.addEventListener('change', function() {
        if (this.value !== initialValue) {
          changedFields.add(this.name || this.id);
          this.style.borderColor = '#ffc107';
          this.style.boxShadow = '0 0 0 0.2rem rgba(255, 193, 7, 0.25)';
        } else {
          changedFields.delete(this.name || this.id);
          this.style.borderColor = '';
          this.style.boxShadow = '';
        }
      });
      
      input.addEventListener('blur', function() {
        if (this.checkValidity()) {
          if (this.value !== initialValue) {
            this.style.borderColor = '#28a745';
          }
        } else {
          this.style.borderColor = '#dc3545';
          showToast('Пожалуйста, заполните поле корректно', 'warning');
        }
      });
      
      input.addEventListener('input', function() {
        if (this.checkValidity() && this.value !== initialValue) {
          this.style.borderColor = '#ffc107';
        }
      });
    });
    
    // Показываем уведомление при изменении формы редактирования
    const editForm = document.querySelector('form[action*="edit"]');
    if (editForm) {
      editForm.addEventListener('submit', function(e) {
        if (changedFields.size > 0) {
          showToast(`Изменено полей: ${changedFields.size}. Сохранение...`, 'info');
        }
      });
    }
    
    // Подсветка строк таблицы при наведении
    document.querySelectorAll('table tbody tr').forEach(row => {
      row.addEventListener('mouseenter', function() {
        this.style.backgroundColor = '#f0f4ff';
        this.style.cursor = 'pointer';
      });
      row.addEventListener('mouseleave', function() {
        this.style.backgroundColor = '';
      });
    });
    
    // Анимация появления модальных окон
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
      modal.addEventListener('show.bs.modal', function() {
        this.style.opacity = '0';
        setTimeout(() => {
          this.style.transition = 'opacity 0.3s ease';
          this.style.opacity = '1';
        }, 10);
      });
    });
  });
  
  // Функция для подтверждения действий
  function confirmAction(message, callback) {
    if (confirm(message)) {
      callback();
    }
  }
  
  // Обработка успешного сохранения формы редактирования
  window.addEventListener('pageshow', function(event) {
    if (event.persisted || (performance.navigation.type === 2)) {
      // Страница загружена из кэша (назад/вперёд)
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('edited') === 'true') {
        showToast('Изменения успешно сохранены!', 'success');
      }
    }
  });
</script>
</body>
</html>
"""


def render_page(title: str, content: str, **kwargs):
    return render_template_string(
        BASE_HTML,
        title=title,
        content=content,
        current_user=session.get("user"),
        url_for=url_for,
        **kwargs
    )


# =====================  ВСПОМОГАТЕЛЬНОЕ  =====================

def login_required(view_func):
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    wrapper.__name__ = view_func.__name__
    return wrapper


def manager_required(view_func):
    """Только для менеджеров"""
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("user", {}).get("user_type") != "Менеджер":
            flash("Доступ запрещён. Требуются права менеджера.", "danger")
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
    
    if user_type == "Менеджер":
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
                content = """
                <h1>Авторизация</h1>
                <p class="text-danger">Проблема с базой данных, смотрите сообщение выше.</p>
                """
                return render_page("Авторизация", content)

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

    content = """
    <h1>Авторизация</h1>
    <form method="post" class="mt-3" style="max-width: 400px;">
      <div class="mb-3">
        <label class="form-label">Логин</label>
        <input type="text" name="login" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Пароль</label>
        <input type="password" name="password" class="form-control" required>
      </div>
      <button type="submit" class="btn btn-primary">Войти</button>
    </form>
    """
    return render_page("Авторизация", content)


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
        content = "<h1>Заявки</h1><p>Проблема с базой данных.</p>"
        return render_page("Заявки", content)

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
                u.fio AS client_fio
            FROM requests r
            LEFT JOIN users u ON r.client_id = u.user_id
            ORDER BY r.start_date DESC, r.request_id DESC
            """
        )
        rows = cur.fetchall()

    new_request_url = url_for('new_request')
    
    # Формируем строки таблицы с готовыми URL
    table_rows = []
    for r in rows:
        qr_url = url_for('qr_for_request', request_id=r['request_id'])
        table_rows.append({
            'request_id': r['request_id'],
            'request_number': r['request_number'],
            'start_date': r['start_date'],
            'climate_tech_type': r['climate_tech_type'],
            'climate_tech_model': r['climate_tech_model'],
            'problem_description': r['problem_description'],
            'client_fio': r['client_fio'],
            'request_status': r['request_status'],
            'qr_url': qr_url
        })
    
    content = f"""
    <h1>Список заявок</h1>
    <p><a class="btn btn-success btn-sm" href="{new_request_url}">Новая заявка</a></p>
    <table class="table table-striped table-bordered">
      <thead>
        <tr>
          <th>ID</th>
          <th>Номер</th>
          <th>Дата</th>
          <th>Оборудование</th>
          <th>Проблема</th>
          <th>Клиент</th>
          <th>Статус</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody>
      """
    
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

    for r in table_rows:
        edit_url = url_for('edit_request', request_id=r['request_id'])
        can_edit, can_status, can_all = can_edit_request(r['request_id'], current_user)

        edit_button = ""
        if can_edit:
            edit_button = (
                f'<a href="{edit_url}" '
                f'class="btn btn-outline-warning btn-sm me-1" '
                f'title="Редактировать заявку">✏️ Редактировать</a>'
            )

        status_class = status_classes.get(r['request_status'], 'bg-info')

        content += f"""
        <tr>
          <td>{r['request_id']}</td>
          <td>{r['request_number']}</td>
          <td>{r['start_date']}</td>
          <td>{r['climate_tech_type']} / {r['climate_tech_model']}</td>
          <td>{r['problem_description']}</td>
          <td>{r['client_fio']}</td>
          <td><span class="badge status-badge {status_class}">{r['request_status']}</span></td>
          <td>
            {edit_button}
            <a href="{r['qr_url']}" target="_blank"
               class="btn btn-outline-primary btn-sm" title="QR-код для отзыва">
              📱 QR
            </a>
          </td>
        </tr>
        """
    
    content += """
      </tbody>
    </table>
    """
    
    return render_page("Заявки", content)


@app.route("/requests/new", methods=["GET", "POST"])
@login_required
def new_request():
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        content = "<h1>Новая заявка</h1><p>Проблема с базой данных.</p>"
        return render_page("Новая заявка", content)

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

        if not (client_id and start_date and climate_type and climate_model and problem):
            flash("Заполните все поля.", "warning")
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
                            client_id
                        )
                        VALUES (?, ?, ?, ?, 'Новая заявка', ?)
                        """,
                        (start_date, climate_type, climate_model, problem, client_id),
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

    requests_list_url = url_for('requests_list')
    new_client_url = url_for('new_client')
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Формируем опции для select
    client_options = ""
    for c in clients:
        client_options += f'<option value="{c["user_id"]}">{c["fio"]}</option>'
    
    content = f"""
    <h1>Новая заявка</h1>
    <form method="post" class="mt-3" style="max-width: 600px;">
      <div class="mb-3">
        <label class="form-label">Заказчик</label>
        <select name="client_id" class="form-select" required>
          <option value="">-- выберите заказчика --</option>
          {client_options}
        </select>
        <div class="form-text">
          Не нашли нужного клиента? <a href="{new_client_url}">Создать нового заказчика</a>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Дата</label>
        <input type="date" name="start_date" class="form-control"
               value="{today}" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Тип оборудования</label>
        <input type="text" name="climate_tech_type" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Модель оборудования</label>
        <input type="text" name="climate_tech_model" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Описание проблемы</label>
        <textarea name="problem_description" class="form-control" rows="4" required></textarea>
      </div>
      <button type="submit" class="btn btn-primary">Создать</button>
      <a href="{requests_list_url}" class="btn btn-secondary">Отмена</a>
    </form>
    """
    return render_page("Новая заявка", content)


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

    requests_url = url_for("requests_list")
    content = f"""
    <h1>Новый заказчик</h1>
    <form method="post" class="mt-3" style="max-width: 600px;">
      <div class="mb-3">
        <label class="form-label">ФИО</label>
        <input type="text" name="fio" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Телефон</label>
        <input type="text" name="phone" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Логин</label>
        <input type="text" name="login" class="form-control" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Пароль</label>
        <input type="password" name="password" class="form-control" required>
      </div>
      <button type="submit" class="btn btn-primary">Создать заказчика</button>
      <a href="{requests_url}" class="btn btn-secondary">Отмена</a>
    </form>
    """
    return render_page("Новый заказчик", content)


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
                u.fio AS client_fio
            FROM requests r
            LEFT JOIN users u ON r.client_id = u.user_id
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
            SELECT user_id, fio
            FROM users
            WHERE user_type IN ('Специалист', 'Менеджер')
            ORDER BY fio
            """
        )
        specialists = cur.fetchall()
        
        # Получаем список заказчиков (для менеджера)
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
    
    requests_list_url = url_for('requests_list')
    
    # Формируем опции для select специалистов
    specialist_options = '<option value="">-- не назначен --</option>'
    for s in specialists:
        selected = "selected" if request_data['master_id'] and s['user_id'] == request_data['master_id'] else ""
        specialist_options += f'<option value="{s["user_id"]}" {selected}>{s["fio"]}</option>'
    
    # Формируем опции для select заказчиков (только для менеджера)
    client_options = ""
    if can_all:
        for c in clients:
            selected = "selected" if c['user_id'] == request_data['client_id'] else ""
            client_options += f'<option value="{c["user_id"]}" {selected}>{c["fio"]}</option>'
    
    # Статусы заявок
    statuses = ['Новая заявка', 'В процессе ремонта', 'Ожидание комплектующих', 
                'Готова к выдаче', 'Завершена', 'Отменена']
    status_options = ""
    for s in statuses:
        selected = "selected" if s == request_data['request_status'] else ""
        status_options += f'<option value="{s}" {selected}>{s}</option>'
    
    # Формируем форму в зависимости от прав
    client_field = ""
    if can_all:
        client_field = f"""
      <div class="mb-3">
        <label class="form-label">Заказчик</label>
        <select name="client_id" class="form-select" required>
          {client_options}
        </select>
      </div>
        """
    
    status_field = ""
    if can_status or can_all:
        status_field = f"""
      <div class="mb-3">
        <label class="form-label">Статус</label>
        <select name="request_status" class="form-select" required>
          {status_options}
        </select>
      </div>
      <div class="mb-3">
        <label class="form-label">Дата завершения (ГГГГ-ММ-ДД)</label>
        <input type="date" name="completion_date" class="form-control"
               value="{request_data['completion_date'] or ''}">
      </div>
      <div class="mb-3">
        <label class="form-label">Назначенный специалист</label>
        <select name="master_id" class="form-select">
          {specialist_options}
        </select>
      </div>
        """
    
    equipment_fields = ""
    if can_all or can_status:
        equipment_fields = f"""
      <div class="mb-3">
        <label class="form-label">Тип оборудования</label>
        <input type="text" name="climate_tech_type" class="form-control"
               value="{request_data['climate_tech_type']}" required>
      </div>
      <div class="mb-3">
        <label class="form-label">Модель оборудования</label>
        <input type="text" name="climate_tech_model" class="form-control"
               value="{request_data['climate_tech_model']}" required>
      </div>
        """
    
    content = f"""
    <h1>Редактирование заявки #{request_data['request_number']}</h1>
    <p class="text-muted">Клиент: {request_data['client_fio']}</p>
    <form method="post" class="mt-3" style="max-width: 600px;">
      {client_field}
      <div class="mb-3">
        <label class="form-label">Дата (ГГГГ-ММ-ДД)</label>
        <input type="date" name="start_date" class="form-control"
               value="{request_data['start_date']}" required>
      </div>
      {equipment_fields}
      <div class="mb-3">
        <label class="form-label">Описание проблемы</label>
        <textarea name="problem_description" class="form-control" rows="4" required>{request_data['problem_description']}</textarea>
      </div>
      {status_field}
      <button type="submit" class="btn btn-primary">Сохранить</button>
      <a href="{requests_list_url}" class="btn btn-secondary">Отмена</a>
    </form>
    """
    
    return render_page("Редактирование заявки", content)


@app.route("/stats")
@login_required
def stats():
    try:
        conn = get_connection()
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        content = "<h1>Статистика</h1><p>Проблема с базой данных.</p>"
        return render_page("Статистика", content)

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
    
    content = f"""
    <h1>Статистика</h1>
    <p>Количество выполненных заявок: <strong>{finished_count}</strong></p>
    """
    
    if avg_days_str:
        content += f"""
    <p>Среднее время выполнения заявки: <strong>{avg_days_str} дня(дней)</strong></p>
        """
    else:
        content += """
    <p>Недостаточно данных для расчета среднего времени выполнения заявок.</p>
        """
    
    content += f"""
    <h3 class="mt-4">Количество заявок по типам оборудования</h3>
    <ul>
    {type_list}
    </ul>
    """
    
    return render_page("Статистика", content)


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


