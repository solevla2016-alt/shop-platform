from typing import List

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, le=1000)


class CartAdd(BaseModel):
    items: List[CartItemAdd] = Field(min_length=1)


class CartItemOut(BaseModel):
    product_id: int
    name: str
    price: int
    quantity: int
    subtotal: int


class CartOut(BaseModel):
    items: List[CartItemOut]
    total: int


class CartTotalOut(BaseModel):
    total: int