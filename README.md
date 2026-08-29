# 🌿 Green Garden E-commerce API 

Современная fullstack e-commerce платформа для продажи комнатных растений, садовых цветов и кустарников.

** Демо:** http://111.88.155.227:8080

##  О проекте

**Green Garden** — это полнофункциональный интернет-магазин с:
- ️ Каталогом товаров с фильтрацией и поиском
-  Корзиной и оформлением заказов
-  Личным кабинетом пользователя
-  Админ-панелью для управления товарами
-  JWT-аутентификацией и безопасностью

##  Технологический стек

- **Python 3.12** + **FastAPI** (асинхронный веб-фреймворк)
- **PostgreSQL** (реляционная база данных)
- **SQLAlchemy 2.0** (асинхронная ORM)
- **Alembic** (управление миграциями БД)
- **Pydantic** (валидация данных и сериализация)
- **JWT** (аутентификация: access + refresh токены)
- **Docker & Docker Compose** (контейнеризация)
- **Pytest + pytest-cov** (тестирование с покрытием ≥ 75%)
- **GitHub Actions** (CI/CD: линтинг flake8 и запуск тестов)


##  Быстрый старт

### Способ 1: Docker (рекомендуется)

**Требования:** Docker и Docker Compose

# 1. Клонируйте репозиторий
git clone https://github.com/solevla2016-alt/shop-platform.git
cd shop-platform

# 2. Создайте файл окружения
cp .env.example .env

# 3. Отредактируйте .env (укажите свои параметры БД и SECRET_KEY)

# 4. Запустите проект
docker compose up --build

# 5. Откройте в браузере:

**Фронтенд**: http://localhost:8080

**API документация (Swagger)**: http://localhost:8080/docs

###  Способ 2: Локальная разработка

**Требования:** Python 3.12+, PostgreSQL 16

# 1. Клонируйте репозиторий
git clone https://github.com/solevla2016-alt/shop-platform.git
cd shop-platform/backend

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt -r requirements-dev.txt

# 4. Создайте файл .env (скопируйте из .env.example)
cp .env.example .env

# 5. Примените миграции
alembic upgrade head

# 6. Создайте админа (опционально)
python -m app.scripts.create_admin

# 7. Запустите сервер
uvicorn app.main:app --reload

**Backend будет доступен на** http://localhost:8000




##  Структура проекта

```text
shop-platform/
├── backend/
│   ├── app/                    # Основной код приложения
│   │   ├── api/                # API endpoints
│   │   │   ├── v1/
│   │   │   │   ├── auth.py     # Регистрация и авторизация
│   │   │   │   ├── products.py # Каталог товаров
│   │   │   │   ├── cart.py     # Корзина
│   │   │   │   └── orders.py   # Заказы
│   │   │   ── deps.py         # Зависимости (аутентификация)
│   │   ├── core/               # Конфигурация и безопасность
│   │   │   ├── config.py       # Настройки приложения
│   │   │   ├── security.py     # JWT и хеширование паролей
│   │   │   └── exceptions.py   # Кастомные исключения
│   │   ├── db/                 # Подключение к БД
│   │   ├── models/             # SQLAlchemy модели
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── cart.py
│   │   │   └── order.py
│   │   ├── schemas/            # Pydantic схемы для валидации
│   │   └── main.py             # Точка входа FastAPI
│   ├── alembic/                # Миграции базы данных
│   ├── frontend/               # Статический фронтенд (HTML/CSS/JS)
│   ├── tests/                  # Тесты (pytest)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic.ini
├── .github/workflows/          # CI/CD пайплайны
├── docker-compose.yml          # Конфигурация Docker Compose
├── .env.example                # Пример переменных окружения
└── README.md                   # Этот файл
```

Основной функционал
Для пользователей:
✅ Регистрация и авторизация (email/телефон + пароль)
✅ Просмотр каталога товаров с фильтрацией по категориям
✅ Поиск товаров по названию и описанию
✅ Корзина (добавление, удаление, изменение количества)
✅ Оформление заказа с выбором способа оплаты
✅ История заказов в личном кабинете
Для администраторов:
✅ CRUD товаров (создание, чтение, обновление, удаление)
✅ Управление статусами заказов
✅ Просмотр всех заказов системы
Технические особенности:
🔐 JWT-аутентификация (access + refresh токены)
🔒 Хеширование паролей (bcrypt)
🛡️ Rate limiting на endpoints авторизации
✅ Покрытие тестами ≥ 75%
🐳 Docker-контейнеризация
🔄 CI/CD через GitHub Actions (автоматические тесты и линтинг)
📱 Адаптивный дизайн (работает на мобильных устройствах)


 Переменные окружения
Создайте файл .env в корне проекта (скопируйте из .env.example):

# База данных
POSTGRES_USER=shop
POSTGRES_PASSWORD=shop_password
POSTGRES_DB=shop
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Безопасность
SECRET_KEY=your-secret-key-here-min-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=14

# Rate limiting
RATE_LIMIT_AUTH_REQUESTS=10000
RATE_LIMIT_AUTH_WINDOW_SECONDS=60

# Админ по умолчанию
ADMIN_EMAIL=admin@example.com
ADMIN_PHONE=+79990000000
ADMIN_PASSWORD=AdminPass123!
ADMIN_FULL_NAME=Admin Admin

Тестирование

cd backend

# Запуск всех тестов
pytest

# Запуск с отчётом о покрытии
pytest --cov=app --cov-report=term-missing

# Запуск с HTML-отчётом
pytest --cov=app --cov-report=html

Требование ТЗ: покрытие тестами ≥ 75% ✅

# API Документация
После запуска проекта откройте:
Swagger UI: http://localhost:8080/docs
ReDoc: http://localhost:8080/redoc

# Основные endpoints:

 **Метод** **Путь** **Описание** 

**POST**   **/api/v1/auth/register** **Регистрация пользователя**

**POST**   **/api/v1/auth/login**      **Авторизация**

**GET**    **/api/v1/products**        **Список товаров**

**POST**   **/api/v1/cart/items**      **Добавить в корзину**

**GET**    **/api/v1/cart**            **Получить корзину**

**POST**  **/api/v1/orders**          **Оформить заказ**

#  Production-деплой

Проект развёрнут на Яндекс Облаке:

URL: http://111.88.155.227:8080

# Демо-доступ:

Email: admin@example.com

Пароль: AdminPass$

# Автор

[Ольга Стасенко]

GitHub: @solevla2016-alt

Email: [solevla2016@gmail.com] 

