from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func, Enum as SAEnum, text
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum


class ProductCategory(str, enum.Enum):
    INDOOR = "indoor"
    GARDEN = "garden"
    SHRUB = "shrub"
    TREE = "tree"
    SUCCULENT = "succulent"
    OTHER = "other"


class Product(Base):
    __tablename__ = "products"  # ← Обязательно два подчеркивания!

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    price = Column(Integer, nullable=False)

    is_active = Column(Boolean, default=True, server_default=text("true"), nullable=False, index=True)

    category = Column(
        SAEnum(ProductCategory, name="productcategory", create_type=True),
        nullable=False,
        default=ProductCategory.OTHER,
        index=True,
    )

    sku = Column(String(50), unique=True, nullable=False, index=True)
    size = Column(String(50), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cart_items = relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")