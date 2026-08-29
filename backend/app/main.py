import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import auth, cart, categories, orders, products
from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
)
from app.db.session import get_db

# Инициализация собственного логгера (исправляет LOG015)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    yield
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.app_name,
    description="API для магазина живых растений",  # Исправлена кодировка (были кракозябры)
    version="1.0.0",
    lifespan=lifespan,
)

# --- Middleware ---

# Исправлен CORS: нельзя использовать allow_origins=["*"] вместе с allow_credentials=True
# Используем настройки из config или безопасный fallback для локальной разработки
allowed_origins = getattr(settings, "allowed_origins", ["http://localhost:3000", "http://localhost:5173"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Сжатие ответов для уменьшения трафика
app.add_middleware(GZipMiddleware, minimum_size=1000)


# --- Обработчики исключений ---

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "Ошибка валидации данных",
            "details": exc.errors(),
        },
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(status_code=401, content={"code": 401, "message": str(exc)})


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"code": 404, "message": str(exc)})


@app.exception_handler(BadRequestError)
async def bad_request_handler(request: Request, exc: BadRequestError):
    return JSONResponse(status_code=400, content={"code": 400, "message": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"code": 409, "message": str(exc)})


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    return JSONResponse(status_code=403, content={"code": 403, "message": str(exc)})


@app.exception_handler(TooManyRequestsError)
async def too_many_requests_handler(request: Request, exc: TooManyRequestsError):
    return JSONResponse(status_code=429, content={"code": 429, "message": str(exc)})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    # Исправлено LOG014: передаем сам объект исключения в exc_info
    logger.error(f"Unhandled exception: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "Внутренняя ошибка сервера"},
    )


# --- Роутеры ---

app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth")
app.include_router(products.router, prefix=f"{settings.api_v1_prefix}/products")
app.include_router(cart.router, prefix=f"{settings.api_v1_prefix}/cart")
app.include_router(orders.router, prefix=f"{settings.api_v1_prefix}/orders")
app.include_router(categories.router, prefix=f"{settings.api_v1_prefix}/categories")


# --- Эндпоинты ---

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):  # noqa: B008
    """Проверка работоспособности приложения и подключения к БД."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:  # noqa: BLE001 (перехват Exception здесь оправдан для health-check)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "error": str(e)},
        )
