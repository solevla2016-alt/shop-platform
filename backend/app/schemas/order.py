"""Order schemas."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class OrderItemOut(BaseModel):
    """Order item response."""

    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    price: int
    quantity: int
    subtotal: int


class OrderOut(BaseModel):
    """Order response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total_amount: int
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]