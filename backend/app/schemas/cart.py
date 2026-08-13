"""Cart schemas."""

from typing import List

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    """Cart item payload."""

    product_id: int
    quantity: int = Field(default=1, ge=1, le=1000)


class CartAdd(BaseModel):
    """Add one or multiple products to cart."""

    items: List[CartItemAdd] = Field(min_length=1)


class CartItemOut(BaseModel):
    """Cart item response."""

    product_id: int
    name: str
    price: int
    quantity: int
    subtotal: int


class CartOut(BaseModel):
    """Cart response."""

    items: List[CartItemOut]
    total: int


class CartTotalOut(BaseModel):
    """Cart total response."""

    total: int