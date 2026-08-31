import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import auth, products, cart, orders, categories, uploads
from app.core.config import settings
from app.core.exceptions import (
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    TooManyRequestsError,
)
from app.db.session import get_db


logger = logging.getLogger(__name__)


FRONTEND_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "frontend",
    )
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    settings.ensure_upload_dirs()
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="API для магазина живых растений",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# STATIC FILES
# ============================================================

if os.path.exists(FRONTEND_DIR):
    js_dir = os.path.join(FRONTEND_DIR, "js")
    css_dir = os.path.join(FRONTEND_DIR, "css")
    images_dir = os.path.join(FRONTEND_DIR, "images")

    if os.path.exists(js_dir):
        app.mount(
            "/js",
            StaticFiles(directory=js_dir),
            name="js",
        )

    if os.path.exists(css_dir):
        app.mount(
            "/css",
            StaticFiles(directory=css_dir),
            name="css",
        )

    if os.path.exists(images_dir):
        app.mount(
            "/images",
            StaticFiles(directory=images_dir),
            name="images",
        )


# Загруженные изображения раздаются по /uploads отдельно:
# локально — напрямую из FastAPI, в Docker — через nginx.
settings.ensure_upload_dirs()

if os.path.exists(settings.uploads_path):
    app.mount(
        "/uploads",
        StaticFiles(directory=settings.uploads_path),
        name="uploads",
    )


@app.get("/")
async def read_root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "message": f"index.html не найден в {FRONTEND_DIR}"
    }


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)


# ============================================================
# EXCEPTION HANDLERS
# ============================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    """
    Обработка ошибок Pydantic/FastAPI валидации.

    ВАЖНО:
    jsonable_encoder необходим, потому что Pydantic v2
    может помещать ValueError в поле ctx.
    Обычный JSONResponse(exc.errors()) в таком случае
    вызывает:

        TypeError:
        Object of type ValueError is not JSON serializable
    """

    errors = jsonable_encoder(exc.errors())

    logger.warning(
        "Validation error for %s %s: %s",
        request.method,
        request.url.path,
        errors,
    )

    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "Ошибка валидации",
            "details": errors,
        },
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(
    request: Request,
    exc: UnauthorizedError,
):
    return JSONResponse(
        status_code=401,
        content={
            "code": 401,
            "message": str(exc),
        },
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(
    request: Request,
    exc: NotFoundError,
):
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "message": str(exc),
        },
    )


@app.exception_handler(BadRequestError)
async def bad_request_handler(
    request: Request,
    exc: BadRequestError,
):
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": str(exc),
        },
    )


@app.exception_handler(ConflictError)
async def conflict_handler(
    request: Request,
    exc: ConflictError,
):
    return JSONResponse(
        status_code=409,
        content={
            "code": 409,
            "message": str(exc),
        },
    )


@app.exception_handler(ForbiddenError)
async def forbidden_handler(
    request: Request,
    exc: ForbiddenError,
):
    return JSONResponse(
        status_code=403,
        content={
            "code": 403,
            "message": str(exc),
        },
    )


@app.exception_handler(TooManyRequestsError)
async def too_many_requests_handler(
    request: Request,
    exc: TooManyRequestsError,
):
    return JSONResponse(
        status_code=429,
        content={
            "code": 429,
            "message": str(exc),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.error(
        "Unhandled exception: %s",
        exc,
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "Внутренняя ошибка сервера",
        },
    )


# ============================================================
# API ROUTES
# ============================================================

app.include_router(
    auth.router,
    prefix=f"{settings.api_v1_prefix}/auth",
)

app.include_router(
    products.router,
    prefix=f"{settings.api_v1_prefix}/products",
)

app.include_router(
    cart.router,
    prefix=f"{settings.api_v1_prefix}/cart",
)

app.include_router(
    orders.router,
    prefix=f"{settings.api_v1_prefix}/orders",
)

app.include_router(
    categories.router,
    prefix=f"{settings.api_v1_prefix}/categories",
)

app.include_router(
    uploads.router,
    prefix=f"{settings.api_v1_prefix}/uploads",
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
):
    try:
        await db.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as exc:
        logger.error(
            "Health check failed: %s",
            exc,
            exc_info=True,
        )

        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "error": "Database unavailable",
            },
        )


# ============================================================
# PASSWORD RESET PAGE
# ============================================================

@app.get("/reset-password")
async def reset_password_page():
    """
    Страница сброса пароля.

    Токен передаётся frontend через:
    /reset-password?token=...
    """

    index_path = os.path.join(
        FRONTEND_DIR,
        "index.html",
    )

    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "message": "index.html not found"
    }