from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.cart import CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=List[ProductOut],
    summary="List active products",
)
async def list_products(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    products = await db.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.created_at.desc())
    )
    return products.all()


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create product (admin)",
)
async def create_product(
    payload: ProductCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get product by id",
)
async def get_product(
    product_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if product is None or (not product.is_active and not user.is_admin):
        raise NotFoundError()

    return product


async def update_product_by_payload(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession,
):
    product = await db.get(Product, product_id)

    if product is None:
        raise NotFoundError()

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return product


@router.put(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update product fully (admin)",
)
async def update_product_put(
    product_id: int,
    payload: ProductUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_product_by_payload(product_id, payload, db)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update product partially (admin)",
)
async def update_product_patch(
    product_id: int,
    payload: ProductUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_product_by_payload(product_id, payload, db)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product (admin)",
)
async def delete_product(
    product_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if product is None:
        raise NotFoundError()

    await db.execute(delete(CartItem).where(CartItem.product_id == product_id))
    await db.delete(product)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)