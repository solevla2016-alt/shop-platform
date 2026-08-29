from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProductCategory(str, Enum):
    INDOOR = "indoor"
    GARDEN = "garden"
    SHRUB = "shrub"
    TREE = "tree"
    SUCCULENT = "succulent"
    OTHER = "other"


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    price: int = Field(..., gt=0, description="Цена в копейках/центах")
    is_active: bool = Field(default=True)
    category: ProductCategory = ProductCategory.OTHER
    sku: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Z0-9\-]+$')
    size: str | None = Field(None, max_length=50)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = Field(None, max_length=500)
    price: int | None = Field(None, gt=0)
    is_active: bool | None = None
    category: ProductCategory | None = None
    sku: str | None = Field(None, min_length=1, max_length=50, pattern=r'^[A-Z0-9\-]+$')
    size: str | None = Field(None, max_length=50)


class ProductResponse(BaseModel):
    id: int
    name: str
    description: str | None
    image_url: str | None
    price: int
    is_active: bool
    category: ProductCategory
    sku: str
    size: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Алиас для обратной совместимости
ProductOut = ProductResponse


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1, le=100)
    pages: int = Field(..., ge=0)
