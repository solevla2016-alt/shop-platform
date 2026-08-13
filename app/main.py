from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import auth, cart, products
from app.core.config import get_settings
from app.core.exceptions import AppError

settings = get_settings()

app = FastAPI(
    title="Shop API",
    version="1.0.0",
    description="Backend для сервиса покупки товаров авторизованными пользователями",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.message,
        },
    )


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(products.router, prefix=settings.api_v1_prefix)
app.include_router(cart.router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}