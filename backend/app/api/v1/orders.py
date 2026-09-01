"""Order endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_admin_user, get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.user import User
from app.schemas.order import (
    CheckoutRequest,
    OrderOut,
    OrderStatusUpdate,
    PaymentRequest,
)


router = APIRouter(tags=["Orders"])


async def load_order(order_id: int, db: AsyncSession) -> Order | None:
    return await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )


@router.post("/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    payload: CheckoutRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cart = await db.scalar(
        select(Cart)
        .options(
            selectinload(Cart.items).joinedload(CartItem.product)
        )
        .where(Cart.user_id == user.id)
    )

    if not cart or not cart.items:
        raise BadRequestError("Cart is empty")

    selected_ids = (
        set(payload.product_ids)
        if payload is not None and payload.product_ids is not None
        else None
    )

    order_items = []
    total = 0
    checked_out: list[CartItem] = []

    for item in cart.items:
        if selected_ids is not None and item.product_id not in selected_ids:
            continue

        product = item.product

        if product is None or not product.is_active:
            raise BadRequestError("One of cart products is unavailable")

        subtotal = product.price * item.quantity
        total += subtotal

        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                price=product.price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
        )
        checked_out.append(item)

    if not order_items:
        raise BadRequestError("Нет выбранных товаров для заказа")

    delivery_method = (
        payload.delivery_method if payload is not None else None
    )
    delivery_cost = payload.delivery_cost if payload is not None else 0
    delivery_address = (
        payload.delivery_address if payload is not None else None
    )
    recipient_name = (
        payload.recipient_name if payload is not None else None
    )

    if delivery_method == "delivery":
        if not delivery_address or not recipient_name:
            raise BadRequestError(
                "Для доставки укажите адрес и ФИО получателя"
            )

    if delivery_method == "pickup":
        delivery_address = None
        delivery_cost = 0

    order = Order(
        user_id=user.id,
        status="pending_payment",
        total_amount=total + delivery_cost,
        items=order_items,
        delivery_method=delivery_method,
        delivery_cost=delivery_cost,
        delivery_address=delivery_address,
        recipient_name=recipient_name,
    )
    db.add(order)

    checked_out_ids = [item.product_id for item in checked_out]
    await db.execute(
        delete(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id.in_(checked_out_ids),
        )
    )

    try:
        await db.commit()
        await db.refresh(order)
    except Exception:
        await db.rollback()
        raise

    return await load_order(order.id, db)


@router.post("/{order_id}/pay", response_model=OrderOut)
async def pay_order(
    order_id: int,
    payload: PaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None or (
        order.user_id != user.id and not user.is_admin
    ):
        raise NotFoundError()

    if order.status == "paid":
        raise BadRequestError("Order is already paid")

    if order.status == "cancelled":
        raise BadRequestError("Order is cancelled")

    order.status = "paid"
    order.payment_method = payload.payment_method
    order.paid_at = datetime.now(timezone.utc)
    await db.commit()

    return await load_order(order.id, db)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None or (
        order.user_id != user.id and not user.is_admin
    ):
        raise NotFoundError()

    if order.status == "paid":
        raise BadRequestError("Cannot cancel paid order")

    if order.status == "cancelled":
        raise BadRequestError("Order is already cancelled")

    order.status = "cancelled"
    await db.commit()

    return await load_order(order.id, db)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    return result.all()


@router.get("/admin/all", response_model=list[OrderOut])
async def admin_list_orders(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return result.all()


@router.patch("/admin/{order_id}/status", response_model=OrderOut)
async def admin_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None:
        raise NotFoundError("Заказ не найден")

    order.status = payload.status

    if payload.status == "paid" and order.paid_at is None:
        order.paid_at = datetime.now(timezone.utc)

    if payload.status != "paid":
        order.paid_at = None
        order.payment_method = None

    await db.commit()

    return await load_order(order.id, db)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None or (
        order.user_id != user.id and not user.is_admin
    ):
        raise NotFoundError()

    return order
