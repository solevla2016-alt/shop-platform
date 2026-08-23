"""Product endpoints."""

import math
from dataclasses import dataclass
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    PaginatedProducts,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(tags=["Products"])


@dataclass
class ProductListParams:
    """Query parameters for product list."""

    page: int
    size: int
    name: Optional[str]
    min_price: Optional[int]
    max_price: Optional[int]
    sort_by: Literal["price", "created_at", "name"]
    sort_order: Literal["asc", "desc"]
    include_inactive: bool


async def get_product_list_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    name: Annotated[Optional[str], Query(min_length=1, max_length=255)] = None,
    min_price: Annotated[Optional[int], Query(ge=0)] = None,
    max_price: Annotated[Optional[int], Query(ge=0)] = None,
    sort_by: Annotated[Literal["price", "created_at", "name"], Query()] = "created_at",
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "desc",
    include_inactive: bool = False,
) -> ProductListParams:
    """Validate product list query parameters."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise BadRequestError("min_price cannot be greater than max_price")

    return ProductListParams(
        page=page,
        size=size,
        name=name,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        include_inactive=include_inactive,
    )


@router.get(
    "",
    response_model=PaginatedProducts,
    summary="List products with pagination, filters and sorting",
)
async def list_products(
    params: Annotated[ProductListParams, Depends(get_product_list_params)],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated product list."""
    filters = []

    if not (user.is_admin and params.include_inactive):
        filters.append(Product.is_active.is_(True))

    if params.name:
        filters.append(Product.name.ilike(f"%{params.name}%"))

    if params.min_price is not None:
        filters.append(Product.price >= params.min_price)

    if params.max_price is not None:
        filters.append(Product.price <= params.max_price)

    items_query = select(Product)
    count_query = select(func.count()).select_from(Product)

    if filters:
        items_query = items_query.where(*filters)
        count_query = count_query.where(*filters)

    total = await db.scalar(count_query)
    pages = math.ceil(total / params.size) if total else 0

    sort_column = getattr(Product, params.sort_by)
    sort_expression = (
        sort_column.desc() if params.sort_order == "desc" else sort_column.asc()
    )

    items = await db.scalars(
        items_query.order_by(sort_expression)
        .offset((params.page - 1) * params.size)
        .limit(params.size)
    )

    return PaginatedProducts(
        items=items.all(),
        total=total,
        page=params.page,
        size=params.size,
        pages=pages,
    )


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
    """Create product."""
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
    """Return product by id."""
    product = await db.get(Product, product_id)

    if product is None or (not product.is_active and not user.is_admin):
        raise NotFoundError()

    return product


async def update_product_by_payload(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession,
):
    """Update product fields."""
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
    """Update product with PUT."""
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
    """Update product with PATCH."""
    return await update_product_by_payload(product_id, payload, db)


@router.delete(
    "/{product_id}",
    response_model=ProductOut,
    summary="Soft delete product (admin)",
)
async def delete_product(
    product_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete product by disabling it."""
    product = await db.get(Product, product_id)

    if product is None:
        raise NotFoundError()

    product.is_active = False
    await db.commit()
    await db.refresh(product)

    return product
