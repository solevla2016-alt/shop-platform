from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    price: int
    quantity: int
    subtotal: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    payment_method: Optional[str] = None
    total_amount: int
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut]


class PaymentRequest(BaseModel):
    payment_method: str = Field(..., description="card, sbp, or cash")