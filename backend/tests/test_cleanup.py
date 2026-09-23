from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.core.cleanup import (
    cleanup_abandoned_carts,
    cleanup_expired_refresh_tokens,
    cleanup_expired_reset_tokens,
    cleanup_orphan_uploads,
    cleanup_revoked_refresh_tokens,
    cleanup_used_reset_tokens,
    run_cleanup,
)
from app.models.cart import Cart, CartItem
from app.models.password_reset_token import PasswordResetToken
from app.models.product import Product
from app.models.refresh_token import RefreshToken
from app.models.user import User


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _reset_tokens_count(db) -> int:
    result = await db.execute(select(PasswordResetToken.id))
    return len(result.all())


async def _refresh_tokens_count(db) -> int:
    result = await db.execute(select(RefreshToken.id))
    return len(result.all())


async def _clear_tables(db) -> None:
    await db.execute(delete(CartItem))
    await db.execute(delete(Cart))
    await db.execute(delete(RefreshToken))
    await db.execute(delete(PasswordResetToken))
    await db.commit()


@pytest.mark.asyncio
async def test_cleanup_expired_reset_tokens(
    db_session,
    regular_user: User,
):
    await _clear_tables(db_session)

    expired = PasswordResetToken(
        user_id=regular_user.id,
        token_hash="expired-hash",
        expires_at=utcnow() - timedelta(minutes=5),
    )
    db_session.add(expired)
    await db_session.commit()

    deleted = await cleanup_expired_reset_tokens(db_session)
    await db_session.commit()

    assert deleted == 1
    assert await _reset_tokens_count(db_session) == 0


@pytest.mark.asyncio
async def test_cleanup_keeps_valid_reset_token(
    db_session,
    regular_user: User,
):
    await _clear_tables(db_session)

    valid = PasswordResetToken(
        user_id=regular_user.id,
        token_hash="valid-hash",
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db_session.add(valid)
    await db_session.commit()

    deleted = await cleanup_expired_reset_tokens(db_session)
    await db_session.commit()

    assert deleted == 0
    assert await _reset_tokens_count(db_session) == 1


@pytest.mark.asyncio
async def test_cleanup_used_reset_tokens(
    db_session,
    regular_user: User,
):
    await _clear_tables(db_session)

    used_old = PasswordResetToken(
        user_id=regular_user.id,
        token_hash="used-old",
        is_used=True,
        created_at=utcnow() - timedelta(days=60),
        expires_at=utcnow() + timedelta(minutes=15),
    )
    used_recent = PasswordResetToken(
        user_id=regular_user.id,
        token_hash="used-recent",
        is_used=True,
        created_at=utcnow() - timedelta(days=2),
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db_session.add_all([used_old, used_recent])
    await db_session.commit()

    deleted = await cleanup_used_reset_tokens(db_session)
    await db_session.commit()

    assert deleted == 1
    remaining = (await db_session.execute(
        select(PasswordResetToken.token_hash).where(
            PasswordResetToken.user_id == regular_user.id
        )
    )).scalars().all()
    assert remaining == ["used-recent"]


@pytest.mark.asyncio
async def test_cleanup_expired_refresh_tokens(
    db_session,
    regular_user: User,
):
    await _clear_tables(db_session)

    expired = RefreshToken(
        user_id=regular_user.id,
        jti="expired-jti",
        expires_at=utcnow() - timedelta(minutes=5),
    )
    db_session.add(expired)
    await db_session.commit()

    deleted = await cleanup_expired_refresh_tokens(db_session)
    await db_session.commit()

    assert deleted == 1
    assert await _refresh_tokens_count(db_session) == 0


@pytest.mark.asyncio
async def test_cleanup_revoked_refresh_tokens(
    db_session,
    regular_user: User,
):
    await _clear_tables(db_session)

    revoked_old = RefreshToken(
        user_id=regular_user.id,
        jti="revoked-old",
        expires_at=utcnow() + timedelta(minutes=5),
        revoked_at=utcnow() - timedelta(days=60),
    )
    revoked_recent = RefreshToken(
        user_id=regular_user.id,
        jti="revoked-recent",
        expires_at=utcnow() + timedelta(minutes=5),
        revoked_at=utcnow() - timedelta(hours=1),
    )
    db_session.add_all([revoked_old, revoked_recent])
    await db_session.commit()

    deleted = await cleanup_revoked_refresh_tokens(db_session)
    await db_session.commit()

    assert deleted == 1
    remaining = (await db_session.execute(
        select(RefreshToken.jti).where(
            RefreshToken.user_id == regular_user.id
        )
    )).scalars().all()
    assert remaining == ["revoked-recent"]


@pytest.mark.asyncio
async def test_cleanup_abandoned_cart_deletes_items(
    db_session,
    regular_user: User,
    test_product: Product,
):
    await _clear_tables(db_session)

    cutoff = utcnow() - timedelta(days=45)
    recent = utcnow() - timedelta(hours=2)

    old_cart = Cart(user_id=regular_user.id, updated_at=cutoff)
    db_session.add(old_cart)
    await db_session.commit()
    db_session.add(
        CartItem(cart_id=old_cart.id, product_id=test_product.id, quantity=2)
    )

    other_user = User(
        email=(f"other_{regular_user.id}@example.com"),
        phone=f"+7999{regular_user.id + 5:07d}",
        full_name="Other",
        password_hash="x",
    )
    db_session.add(other_user)
    await db_session.commit()
    fresh_cart = Cart(user_id=other_user.id, updated_at=recent)
    db_session.add(fresh_cart)
    await db_session.commit()

    deleted = await cleanup_abandoned_carts(db_session)
    await db_session.commit()

    assert deleted == 1
    carts = (await db_session.execute(select(Cart.id))).scalars().all()
    assert carts == [fresh_cart.id]
    items = (await db_session.execute(select(CartItem.id))).scalars().all()
    assert items == []


@pytest.mark.asyncio
async def test_cleanup_orphan_uploads(
    db_session,
    test_product: Product,
    tmp_path,
    monkeypatch,
):
    from app.core.config import settings

    upload_root = tmp_path / "uploads"
    products_dir = upload_root / "products"
    products_dir.mkdir(parents=True)

    kept_file = products_dir / "kept.jpg"
    orphan_file = products_dir / "orphan.jpg"
    kept_file.write_bytes(b"img")
    orphan_file.write_bytes(b"img")

    monkeypatch.setattr(settings, "upload_dir", str(upload_root))

    test_product.image_url = "/uploads/products/kept.jpg"
    await db_session.commit()

    deleted = await cleanup_orphan_uploads(db_session)

    assert deleted == 1
    assert kept_file.exists()
    assert not orphan_file.exists()


@pytest.mark.asyncio
async def test_run_cleanup_reports_counts(db_session):
    stats = await run_cleanup(db_session)
    assert isinstance(stats, dict)
    assert set(stats) == {
        "reset_tokens_expired",
        "reset_tokens_used",
        "refresh_tokens_expired",
        "refresh_tokens_revoked",
        "carts_abandoned",
        "orphan_uploads",
    }
    assert all(isinstance(value, int) for value in stats.values())
