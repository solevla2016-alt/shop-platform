# Shop API

Backend-сервис для покупки товаров авторизованными пользователями.

Стек:

- FastAPI
- PostgreSQL
- SQLAlchemy 2 async
- JWT
- Docker / Docker Compose
- pytest + pytest-cov

## Возможности

- Регистрация пользователей
- Авторизация по email или телефону
- Доступ к списку активных товаров только для авторизованных пользователей
- Администратор может создавать, редактировать и удалять товары
- Авторизованный пользователь может:
  - просматривать корзину
  - добавлять один или несколько товаров в корзину
  - удалять товар из корзины
  - очищать корзину
  - получать общую стоимость корзины

## Формат ошибки unauthorized

При отсутствии токена или невалидном токене API возвращает:

```json
{
  "code": 401,
  "message": "Unauthorized"
}
```

## Основные эндпоинты

| Method | Path | Доступ | Описание |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Регистрация |
| POST | `/api/v1/auth/login` | Public | Авторизация |
| GET | `/api/v1/products` | Authorized | Список активных товаров |
| GET | `/api/v1/products/{id}` | Authorized | Получить товар |
| POST | `/api/v1/products` | Admin | Создать товар |
| PUT/PATCH | `/api/v1/products/{id}` | Admin | Редактировать товар |
| DELETE | `/api/v1/products/{id}` | Admin | Удалить товар |
| GET | `/api/v1/cart` | Authorized | Получить корзину |
| GET | `/api/v1/cart/total` | Authorized | Получить общую стоимость |
| POST | `/api/v1/cart/items` | Authorized | Добавить товары в корзину |
| DELETE | `/api/v1/cart/items/{product_id}` | Authorized | Удалить товар из корзины |
| DELETE | `/api/v1/cart` | Authorized | Очистить корзину |

## Требования к паролю

- минимум 8 символов;
- минимум одна заглавная латинская буква;
- минимум один спецсимвол из `$%&!:`;
- разрешены латинские буквы, цифры и указанные спецсимволы.

> Если нужно запретить цифры, измените `PASSWORD_REGEX` в `app/schemas/user.py` на `^[A-Za-z$%&!:]{8,}$`.

## Требования к телефону

Телефон должен иметь формат:

```text
+7XXXXXXXXXX
```

где после `+7` идёт ровно 10 цифр.

## Установка и запуск через Docker

1. Клонируйте репозиторий:

```bash
git clone <ваш-репозиторий>
cd shop-api
```

2. Создайте `.env`:

```bash
cp .env.example .env
```

3. Запустите сервисы:

```bash
docker compose up --build
```

Приложение будет доступно:

```text
http://localhost:8000
```

Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

ReDoc:

```text
http://localhost:8000/redoc
```

## Создание администратора

Администратор создаётся автоматически при старте контейнера, если в `.env` заданы:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PHONE=+79990000000
ADMIN_PASSWORD=AdminPass$
ADMIN_FULL_NAME=Admin Admin
```

## Локальный запуск без Docker

1. Создайте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Укажите переменные окружения или создайте `.env`.

4. Инициализируйте БД:

```bash
python -m app.scripts.init_db
```

5. Запустите приложение:

```bash
uvicorn app.main:app --reload
```

## Тесты

Запуск тестов:

```bash
pytest
```

Запуск покрытия:

```bash
pytest --cov=app --cov-report=term-missing
```

В проекте настроен минимальный порог покрытия:

```text
75%
```

## Примеры запросов

### Регистрация

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Иванов Иван Иванович",
    "email": "user@example.com",
    "phone": "+79991234567",
    "password": "Password$",
    "password_confirm": "Password$"
  }'
```

### Авторизация

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "user@example.com",
    "password": "Password$"
  }'
```

### Список товаров

```bash
curl http://localhost:8000/api/v1/products \
  -H "Authorization: Bearer <access_token>"
```

### Добавить товары в корзину

```bash
curl -X POST http://localhost:8000/api/v1/cart/items \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 2, "quantity": 1}
    ]
  }'
```

### Получить стоимость корзины

```bash
curl http://localhost:8000/api/v1/cart/total \
  -H "Authorization: Bearer <access_token>"
```