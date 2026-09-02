"""Product database model."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Product(Base):
    """Product model."""

    __tablename__ = "products"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    image_url = Column(
        String(500),
        nullable=True,
    )

    price = Column(
        Integer,
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        index=True,
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=False,
        index=True,
    )

    sku = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    size = Column(
        String(50),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    category_rel = relationship(
        "Category",
        back_populates="products",
    )

    cart_items = relationship(
        "CartItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    order_items = relationship(
        "OrderItem",
        back_populates="product",
    )
