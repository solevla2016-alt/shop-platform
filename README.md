# 🌿 Green Garden — e-commerce platform

Fullstack интернет-магазин растений на **FastAPI + PostgreSQL + SQLAlchemy + Alembic + vanilla JavaScript + Nginx + Docker Compose**.

Проект подготовлен как коммерчески распространяемый шаблон: секреты не хранятся в репозитории, база создаётся миграциями, категории автоматически заполняются, есть JWT access/refresh, корзина, заказы, админское управление товарами и заказами, восстановление пароля через Resend.

## Возможности

### Покупатель
- регистрация по email и телефону;
- вход по email или телефону;
- JWT access + refresh tokens с ротацией refresh token;
- каталог с поиском, фильтрами, сортировкой и пагинацией;
- корзина;
- оформление заказа;
- демонстрационная оплата: карта / СБП / наличные;
- история заказов;
- отмена неоплаченного заказа;
- восстановление пароля по email.

### Администратор
- создание, изменение и soft-delete товаров;
- управление категориями через API;
- просмотр всех заказов через API;
- изменение статуса заказа;
- просмотр неактивных товаров.

## Важное ограничение

Оплата в текущей версии **демонстрационная**. Реального эквайринга и списания денег нет. Перед запуском реального магазина необходимо подключить платёжного провайдера, настроить юридические документы, доставку, налоги и production-инфраструктуру.

## Стек

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x async
- PostgreSQL 16
- Alembic
- Pydantic v2
- PyJWT
- bcrypt
- Resend HTTP API
- Nginx
- Docker Compose
- Pytest / pytest-cov / flake8
- GitHub Actions

## Быстрый запуск через Docker

Требуются Docker и Docker Compose.

```bash
git clone <your-repository>
cd shop-platform
cp .env.example .env
```

В `.env` обязательно задайте собственный `SECRET_KEY`, пароль PostgreSQL и production-параметры.

Запуск:

```bash
docker compose up --build -d
```

После запуска:

- магазин: `http://localhost:8080`
- Swagger: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- health check: `http://localhost:8080/health`

Миграции, создание администратора и базовых категорий выполняются автоматически контейнером API.

## Локальный запуск backend

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Установка:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Создайте файл `.env` в корне проекта на основе `.env.example`, затем:

```bash
alembic upgrade head
python -m app.scripts.seed_categories
python -m app.scripts.create_admin
uvicorn app.main:app --reload
```

## Переменные окружения

Минимально необходимы:

```env
DATABASE_URL=postgresql+asyncpg://shop:password@localhost:5432/shop
SECRET_KEY=<random-secret-at-least-32-characters>
FRONTEND_URL=http://localhost:8080
CORS_ORIGINS=http://localhost:8080
```

Для восстановления пароля:

```env
RESEND_API_KEY=<resend-api-key>
EMAIL_FROM=Green Garden <noreply@example.com>
PASSWORD_RESET_EXPIRE_MINUTES=15
```

Для автоматического создания администратора:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PHONE=+79990000000
ADMIN_PASSWORD=<strong-password>
ADMIN_FULL_NAME=Store Administrator
```

**Файл `.env` нельзя публиковать или передавать покупателю с реальными секретами.**

## Тесты

```bash
cd backend
pytest -q
```

Покрытие:

```bash
pytest --cov=app --cov-report=term-missing
```

CI запускает линтинг, тесты и Docker build.

## API

Основные маршруты:

| Метод | Endpoint | Назначение |
|---|---|---|
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход |
| POST | `/api/v1/auth/refresh` | Обновление токенов |
| POST | `/api/v1/auth/forgot-password` | Запрос сброса пароля |
| POST | `/api/v1/auth/reset-password` | Смена пароля по одноразовой ссылке |
| GET | `/api/v1/products` | Каталог |
| POST | `/api/v1/products` | Создание товара (admin) |
| PATCH | `/api/v1/products/{id}` | Изменение товара (admin) |
| DELETE | `/api/v1/products/{id}` | Soft-delete товара (admin) |
| GET | `/api/v1/categories` | Категории |
| POST | `/api/v1/cart/items` | Добавление в корзину |
| GET | `/api/v1/cart` | Корзина |
| POST | `/api/v1/orders/checkout` | Создание заказа |
| POST | `/api/v1/orders/{id}/pay` | Демонстрационная оплата |
| POST | `/api/v1/orders/{id}/cancel` | Отмена заказа |
| GET | `/api/v1/orders` | Заказы пользователя |
| GET | `/api/v1/orders/admin/all` | Все заказы (admin) |
| PATCH | `/api/v1/orders/admin/{id}/status` | Изменение статуса (admin) |

## Безопасность

- `.env` исключён из Git;
- access token проверяется как token типа `access`;
- refresh token хранится на сервере по `jti` и ротируется;
- reset token хранится только в виде SHA-256 hash и одноразово помечается использованным;
- пароли хешируются bcrypt;
- auth endpoints ограничены rate limiting;
- validation errors корректно сериализуются;
- публичные ошибки БД не раскрывают внутренние детали;
- PostgreSQL не публикуется наружу через Docker Compose;
- HTML-вывод frontend экранирует пользовательские данные.

## Перед продажей / production

1. Сгенерировать новый `SECRET_KEY`.
2. Задать уникальные PostgreSQL credentials.
3. Настроить домен и HTTPS.
4. Настроить Resend и SPF/DKIM/DMARC.
5. Подключить настоящий платёжный провайдер.
6. Настроить резервное копирование PostgreSQL.
7. Настроить внешний rate limiter/WAF для нескольких API-инстансов.
8. Проверить юридические требования магазина и политики обработки персональных данных.
9. Не использовать демонстрационные admin credentials.

## Лицензирование и продажа

Перед коммерческой продажей добавьте выбранную лицензию, реквизиты правообладателя и условия поддержки. Удалённые из дистрибутива `.git`, `.env`, тестовые базы и локальные кэши не являются частью продукта.
