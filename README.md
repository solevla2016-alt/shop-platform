# Shop Platform 2.0

Full-stack e-commerce demo:

- FastAPI
- PostgreSQL
- SQLAlchemy async
- Alembic
- JWT access + refresh tokens
- Orders
- Cart
- Pagination, filtering, sorting
- Rate limiting
- Request logging
- Static frontend
- Docker Compose
- GitHub Actions CI

## Quick start

1. Create environment file:

```bash
cp .env.example .env
```

2. Build and start:

```bash
docker compose up --build
```

3. Open:

- Frontend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

Default admin is created from `.env`.

## Local backend development

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload
```

## Tests

```bash
cd backend
pytest
```

## CI

GitHub Actions runs:

```bash
flake8 app tests
pytest
```