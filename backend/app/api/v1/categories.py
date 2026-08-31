"""Category endpoints."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_admin_user
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.db.session import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(tags=["Categories"])

@router.get("", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()

@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    category = Category(**payload.model_dump()); db.add(category)
    try: await db.commit(); await db.refresh(category)
    except IntegrityError as exc:
        await db.rollback(); raise ConflictError("Категория с таким названием или slug уже существует") from exc
    return category

@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, payload: CategoryUpdate, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    category = await db.get(Category, category_id)
    if category is None: raise NotFoundError("Категория не найдена")
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(category, field, value)
    try: await db.commit(); await db.refresh(category)
    except IntegrityError as exc:
        await db.rollback(); raise ConflictError("Категория с таким названием уже существует") from exc
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    category = await db.get(Category, category_id)
    if category is None: raise NotFoundError("Категория не найдена")
    has_products = await db.scalar(select(Product.id).where(Product.category_id == category_id).limit(1))
    if has_products is not None: raise BadRequestError("Нельзя удалить категорию, в которой есть товары")
    await db.delete(category); await db.commit()
    return None
