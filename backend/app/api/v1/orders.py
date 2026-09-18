"""Order endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_admin_user, get_current_user
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    CheckoutRequest,
    OrderOut,
    OrderQrInfo,
    OrderStatusUpdate,
    PaymentRequest,
    ShippingStatusUpdate,
)


router = APIRouter(tags=["Orders"])

SHIPPING_STATUS_TEXT = {
    "sorting": "На сортировке",
    "ready": "Готов к отправке",
    "shipped": "Отправлен",
}


def format_rubles(amount_kopecks: int) -> str:
    rubles = amount_kopecks / 100
    return f"{rubles:,.2f}".replace(",", " ")


async def load_order(order_id: int, db: AsyncSession) -> Order | None:
    return await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )


async def decrement_stock(
    order: Order,
    db: AsyncSession,
) -> None:
    for item in order.items:
        result = await db.execute(
            update(Product)
            .where(
                Product.id == item.product_id,
                Product.stock_quantity >= item.quantity,
            )
            .values(
                stock_quantity=Product.stock_quantity - item.quantity
            )
        )
        if result.rowcount != 1:
            await db.rollback()
            raise BadRequestError(
                f"Недостаточно товара «{item.product_name}» на складе"
            )


async def restore_stock(
    order: Order,
    db: AsyncSession,
) -> None:
    for item in order.items:
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(
                stock_quantity=Product.stock_quantity + item.quantity
            )
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

        if product.stock_quantity < item.quantity:
            raise BadRequestError(
                f"Недостаточно товара «{product.name}» на складе: "
                f"в наличии {product.stock_quantity}"
            )

        subtotal = product.price * item.quantity
        total += subtotal

        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku,
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

    await decrement_stock(order, db)

    order.status = "paid"
    order.payment_method = payload.payment_method
    order.shipping_status = order.shipping_status or "sorting"
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

    was_paid = order.status == "paid"
    will_be_paid = payload.status == "paid"

    if not was_paid and will_be_paid:
        await decrement_stock(order, db)
    elif was_paid and not will_be_paid:
        await restore_stock(order, db)

    order.status = payload.status

    if will_be_paid and order.paid_at is None:
        order.paid_at = datetime.now(timezone.utc)
        order.shipping_status = order.shipping_status or "sorting"

    if not will_be_paid:
        order.paid_at = None
        order.payment_method = None

    await db.commit()

    return await load_order(order.id, db)


@router.get("/admin/processed", response_model=list[OrderOut])
async def admin_processed_orders(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status == "paid")
        .order_by(Order.created_at.desc())
    )
    return result.all()


@router.patch(
    "/admin/{order_id}/shipping-status",
    response_model=OrderOut,
)
async def admin_update_shipping_status(
    order_id: int,
    payload: ShippingStatusUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None:
        raise NotFoundError("Заказ не найден")

    if order.status != "paid":
        raise BadRequestError(
            "Изменить статус отгрузки можно только у оплаченного заказа"
        )

    order.shipping_status = payload.shipping_status
    await db.commit()

    return await load_order(order.id, db)


@router.get("/{order_id}/qr-info", response_model=OrderQrInfo)
async def get_order_qr_info(
    order_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await load_order(order_id, db)

    if order is None or (
        order.user_id != user.id and not user.is_admin
    ):
        raise NotFoundError()

    if order.status == "cancelled":
        raise BadRequestError("Заказ отменён")

    settings = get_settings()
    phone_raw = settings.sbp_phone
    phone_digits = "".join(ch for ch in phone_raw if ch.isdigit())

    if len(phone_digits) == 11:
        phone_display = (
            f"+7 {phone_digits[1:4]} {phone_digits[4:7]}-"
            f"{phone_digits[7:9]}-{phone_digits[9:11]}"
        )
    else:
        phone_display = phone_raw

    amount = round(order.total_amount / 100, 2)

    payload = (
        "СБП по номеру телефона\n"
        f"Получатель: {phone_display}\n"
        f"Банк получателя: {settings.sbp_bank_name}\n"
        f"Сумма: {format_rubles(order.total_amount)} ₽\n"
        f"Назначение: Оплата заказа №{order.id}"
    )

    return OrderQrInfo(
        order_id=order.id,
        phone=phone_display,
        bank_name=settings.sbp_bank_name,
        amount=amount,
        payload=payload,
    )


@router.get("/admin/{order_id}", response_model=OrderOut)
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
