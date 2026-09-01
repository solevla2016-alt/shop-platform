"""Product schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    image_url: str | None = Field(default=None, max_length=500)
    price: int = Field(gt=0)
    is_active: bool = True
    category_id: int = Field(gt=0)
    sku: str = Field(min_length=1, max_length=50)
    size: str | None = Field(default=None, max_length=50)

    @field_validator("name", "sku", "size", mode="before")
    @classmethod
    def strip_strings(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    image_url: str | None = Field(default=None, max_length=500)
    price: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    category_id: int | None = Field(default=None, gt=0)
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    size: str | None = Field(default=None, max_length=50)

    @field_validator("name", "sku", "size", mode="before")
    @classmethod
    def strip_strings(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


ProductOut = ProductResponse


class PaginatedProducts(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    size: int
    pages: int
