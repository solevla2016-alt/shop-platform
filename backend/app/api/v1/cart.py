"""Cart endpoints."""

from typing import Dict, List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.cart import CartAdd, CartItemOut, CartOut, CartTotalOut

router = APIRouter(tags=["Cart"])


async def get_or_create_cart(user_id: int, db: AsyncSession) -> Cart:
    """Return existing cart or create a new one."""
    cart = await db.scalar(select(Cart).where(Cart.user_id == user_id))

    if cart:
        return cart

    cart = Cart(user_id=user_id)
    db.add(cart)
    await db.flush()

    return cart


async def build_cart_response(cart_id: int, db: AsyncSession) -> CartOut:
    """Build cart response with active products only."""
    cart = await db.scalar(
        select(Cart)
        .options(selectinload(Cart.items).joinedload(CartItem.product))
        .where(Cart.id == cart_id)
    )

    items: List[CartItemOut] = []
    total = 0

    if cart:
        for item in cart.items:
            if item.product and item.product.is_active:
                subtotal = item.product.price * item.quantity
                total += subtotal

                items.append(
                    CartItemOut(
                        product_id=item.product_id,
                        name=item.product.name,
                        price=item.product.price,
                        quantity=item.quantity,
                        subtotal=subtotal,
                    )
                )

    return CartOut(items=items, total=total)


@router.get(
    "",
    response_model=CartOut,
    summary="Get current cart",
)
async def get_cart(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user cart."""
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))

    if not cart:
        return CartOut(items=[], total=0)

    return await build_cart_response(cart.id, db)


@router.get(
    "/total",
    response_model=CartTotalOut,
    summary="Get cart total",
)
async def get_cart_total(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return cart total price."""
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))

    if not cart:
        return CartTotalOut(total=0)

    cart_response = await build_cart_response(cart.id, db)
    return CartTotalOut(total=cart_response.total)


@router.post(
    "/items",
    response_model=CartOut,
    summary="Add one or multiple products to cart",
)
async def add_cart_items(
    payload: CartAdd,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add products to cart."""
    cart = await get_or_create_cart(user.id, db)

    quantities: Dict[int, int] = {}

    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

    for product_id, quantity in quantities.items():
        product = await db.get(Product, product_id)

        if product is None or not product.is_active:
            raise BadRequestError("Product is unavailable")

        existing_item = await db.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product_id,
            )
        )

        if existing_item:
            existing_item.quantity += quantity
        else:
            db.add(
                CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=quantity,
                )
            )

    await db.commit()

    return await build_cart_response(cart.id, db)


@router.delete(
    "/items/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove product from cart",
)
async def remove_cart_item(
    product_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove product from cart."""
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))

    if not cart:
        raise NotFoundError("Cart not found")

    item = await db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product_id,
        )
    )

    if not item:
        raise NotFoundError("Item not found")

    await db.delete(item)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear cart",
)
async def clear_cart(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove all items from cart."""
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))

    if cart:
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
