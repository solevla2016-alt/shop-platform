"""Автоматическая фоновая очистка устаревших данных.

Фоновый цикл запускается из lifespan приложения и периодически
удаляет данные, которые официально больше не нужны:

- просроченные токены сброса пароля;
- использованные токены сброса пароля старше срока хранения;
- просроченные refresh-токены;
- отозванные refresh-токены старше срока хранения;
- заброшенные корзины (без обновлений дольше срока хранения);
- файлы в uploads, на которые не ссылается ни один товар/категория.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.password_reset_token import PasswordResetToken
from app.models.product import Product
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def cleanup_expired_reset_tokens(db: AsyncSession) -> int:
    result = await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < now_utc()
        )
    )
    return result.rowcount or 0


async def cleanup_used_reset_tokens(db: AsyncSession) -> int:
    cutoff = now_utc() - timedelta(days=settings.cleanup_reset_token_days)
    result = await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.is_used.is_(True),
            PasswordResetToken.created_at < cutoff,
        )
    )
    return result.rowcount or 0


async def cleanup_expired_refresh_tokens(db: AsyncSession) -> int:
    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now_utc())
    )
    return result.rowcount or 0


async def cleanup_revoked_refresh_tokens(db: AsyncSession) -> int:
    cutoff = now_utc() - timedelta(days=settings.cleanup_refresh_token_days)
    result = await db.execute(
        delete(RefreshToken).where(
            RefreshToken.revoked_at.is_not(None),
            RefreshToken.revoked_at < cutoff,
        )
    )
    return result.rowcount or 0


async def cleanup_abandoned_carts(db: AsyncSession) -> int:
    cutoff = now_utc() - timedelta(days=settings.cleanup_cart_days)
    old_cart_ids = select(Cart.id).where(Cart.updated_at < cutoff)
    await db.execute(
        delete(CartItem).where(CartItem.cart_id.in_(old_cart_ids))
    )
    result = await db.execute(
        delete(Cart).where(Cart.updated_at < cutoff)
    )
    return result.rowcount or 0


async def cleanup_orphan_uploads(db: AsyncSession) -> int:
    if not settings.cleanup_orphan_uploads:
        return 0

    referenced: set[str] = set()
    for attr in (Product.image_url, Category.image_url):
        rows = await db.execute(select(attr))
        for (value,) in rows.all():
            if value:
                referenced.add(value)

    deleted = 0
    for folder, dir_path in (
        ("categories", settings.categories_upload_dir),
        ("products", settings.products_upload_dir),
    ):
        if not dir_path.exists():
            continue
        for file_path in dir_path.iterdir():
            if not file_path.is_file():
                continue
            url = f"/uploads/{folder}/{file_path.name}"
            if url not in referenced:
                file_path.unlink(missing_ok=True)
                deleted += 1
    return deleted


async def run_cleanup(db: AsyncSession) -> dict[str, int]:
    stats = {
        "reset_tokens_expired": await cleanup_expired_reset_tokens(db),
        "reset_tokens_used": await cleanup_used_reset_tokens(db),
        "refresh_tokens_expired": await cleanup_expired_refresh_tokens(db),
        "refresh_tokens_revoked": await cleanup_revoked_refresh_tokens(db),
        "carts_abandoned": await cleanup_abandoned_carts(db),
        "orphan_uploads": await cleanup_orphan_uploads(db),
    }
    await db.commit()
    return stats


async def cleanup_loop() -> None:
    """Фоновый цикл: первая очистка через 30 секунд после старта."""
    await asyncio.sleep(30)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                stats = await run_cleanup(db)
            if any(stats.values()):
                logger.info("Cleanup finished: %s", stats)
        except Exception:
            logger.exception(
                "Cleanup failed; will retry on next tick"
            )
        await asyncio.sleep(settings.cleanup_interval_minutes * 60)
