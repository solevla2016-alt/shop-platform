"""Order endpoints."""

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.user import User
from app.schemas.order import OrderOut

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "/checkout",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Checkout current cart",
)
async def checkout(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create order from current cart and clear cart."""
    cart = await db.scalar(
        select(Cart)
        .options(selectinload(Cart.items).joinedload(CartItem.product))
        .where(Cart.user_id == user.id)
    )

    if not cart or not cart.items:
        raise BadRequestError("Cart is empty")

    total_amount = 0
    order_items: List[OrderItem] = []

    for cart_item in cart.items:
        product = cart_item.product

        if product is None or not product.is_active:
            raise BadRequestError("One of cart products is unavailable")

        subtotal = product.price * cart_item.quantity
        total_amount += subtotal

        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                price=product.price,
                quantity=cart_item.quantity,
                subtotal=subtotal,
            )
        )

    order = Order(
        user_id=user.id,
        status="created",
        total_amount=total_amount,
        items=order_items,
    )

    db.add(order)

    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    await db.commit()

    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )

    return order


@router.get(
    "",
    response_model=List[OrderOut],
    summary="List user orders",
)
async def list_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return orders of current user."""
    orders = await db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )

    return orders.all()


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    summary="Get order by id",
)
async def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return order by id."""
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )

    if order is None or (order.user_id != user.id and not user.is_admin):
        raise NotFoundError()

    return order