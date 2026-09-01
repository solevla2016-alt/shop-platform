"""Product endpoints."""

import math
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user, optional_current_user
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.db.session import get_db
from app.models.category import Category
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
    page: int
    size: int
    name: str | None
    category_id: int | None
    min_price: int | None
    max_price: int | None
    sort_by: Literal["price", "created_at", "name"]
    sort_order: Literal["asc", "desc"]
    include_inactive: bool


async def get_product_list_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    name: Annotated[
        str | None,
        Query(min_length=1, max_length=255),
    ] = None,
    category_id: Annotated[
        int | None,
        Query(ge=1),
    ] = None,
    min_price: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
    max_price: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
    sort_by: Annotated[
        Literal["price", "created_at", "name"],
        Query(),
    ] = "created_at",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(),
    ] = "desc",
    include_inactive: bool = False,
) -> ProductListParams:
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise BadRequestError(
            "min_price cannot be greater than max_price"
        )

    return ProductListParams(
        page=page,
        size=size,
        name=name,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        include_inactive=include_inactive,
    )


@router.get(
    "",
    response_model=PaginatedProducts,
)
async def list_products(
    params: Annotated[
        ProductListParams,
        Depends(get_product_list_params),
    ],
    user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = []

    if not (
        user
        and user.is_admin
        and params.include_inactive
    ):
        filters.append(Product.is_active.is_(True))

    if params.name:
        filters.append(
            Product.name.ilike(
                f"%{params.name}%"
            )
        )

    if params.category_id is not None:
        filters.append(
            Product.category_id == params.category_id
        )

    if params.min_price is not None:
        filters.append(
            Product.price >= params.min_price
        )

    if params.max_price is not None:
        filters.append(
            Product.price <= params.max_price
        )

    count_query = (
        select(func.count())
        .select_from(Product)
        .where(*filters)
    )

    total = await db.scalar(count_query) or 0

    pages = (
        math.ceil(total / params.size)
        if total
        else 0
    )

    sort_column = getattr(
        Product,
        params.sort_by,
    )

    order = (
        sort_column.desc()
        if params.sort_order == "desc"
        else sort_column.asc()
    )

    result = await db.scalars(
        select(Product)
        .where(*filters)
        .order_by(
            order,
            Product.id.desc(),
        )
        .offset(
            (params.page - 1) * params.size
        )
        .limit(params.size)
    )

    return PaginatedProducts(
        items=result.all(),
        total=total,
        page=params.page,
        size=params.size,
        pages=pages,
    )


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    # Проверяем категорию явно.
    # Это важно для SQLite-тестов: foreign key constraint
    # может быть отключён, поэтому IntegrityError здесь
    # не гарантирован.
    category = await db.get(
        Category,
        payload.category_id,
    )

    if category is None:
        raise BadRequestError(
            "Указанная категория не существует"
        )

    product = Product(
        **payload.model_dump()
    )

    db.add(product)

    try:
        await db.commit()
        await db.refresh(product)

    except IntegrityError as exc:
        await db.rollback()

        if "sku" in str(exc.orig).lower():
            raise ConflictError(
                "Товар с таким SKU уже существует"
            ) from exc

        raise BadRequestError(
            "Не удалось создать товар"
        ) from exc

    return product


@router.get(
    "/{product_id}",
    response_model=ProductOut,
)
async def get_product(
    product_id: int,
    user: User | None = Depends(optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(
        Product,
        product_id,
    )

    if product is None:
        raise NotFoundError()

    if (
        not product.is_active
        and not (
            user
            and user.is_admin
        )
    ):
        raise NotFoundError()

    return product


async def update_product_by_payload(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession,
):
    product = await db.get(
        Product,
        product_id,
    )

    if product is None:
        raise NotFoundError()

    update_data = payload.model_dump(
        exclude_unset=True
    )

    # Если category_id передан при обновлении,
    # проверяем существование категории явно.
    if "category_id" in update_data:
        category = await db.get(
            Category,
            update_data["category_id"],
        )

        if category is None:
            raise BadRequestError(
                "Указанная категория не существует"
            )

    for field, value in update_data.items():
        setattr(
            product,
            field,
            value,
        )

    try:
        await db.commit()
        await db.refresh(product)

    except IntegrityError as exc:
        await db.rollback()

        if "sku" in str(exc.orig).lower():
            raise ConflictError(
                "Товар с таким SKU уже существует"
            ) from exc

        raise BadRequestError(
            "Не удалось обновить товар"
        ) from exc

    return product


@router.put(
    "/{product_id}",
    response_model=ProductOut,
)
async def update_product_put(
    product_id: int,
    payload: ProductUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_product_by_payload(
        product_id,
        payload,
        db,
    )


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
)
async def update_product_patch(
    product_id: int,
    payload: ProductUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_product_by_payload(
        product_id,
        payload,
        db,
    )


@router.delete(
    "/{product_id}",
    response_model=ProductOut,
)
async def delete_product(
    product_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(
        Product,
        product_id,
    )

    if product is None:
        raise NotFoundError()

    product.is_active = False

    await db.commit()
    await db.refresh(product)

    return product

