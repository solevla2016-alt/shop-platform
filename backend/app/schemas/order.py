"""Order schemas."""
from datetime import datetime
from typing import Literal
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
    user_id: int
    status: str
    payment_method: str | None = None
    total_amount: int
    delivery_method: str | None = None
    delivery_cost: int = 0
    delivery_address: str | None = None
    recipient_name: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]

class PaymentRequest(BaseModel):
    payment_method: Literal["card", "sbp", "cash"]

class OrderStatusUpdate(BaseModel):
    status: Literal["pending_payment", "paid", "cancelled"]

class CheckoutRequest(BaseModel):
    product_ids: list[int] | None = None
    delivery_method: Literal["pickup", "delivery"] | None = None
    delivery_cost: int = Field(default=0, ge=0)
    delivery_address: str | None = Field(default=None, max_length=500)
    recipient_name: str | None = Field(default=None, max_length=255)
