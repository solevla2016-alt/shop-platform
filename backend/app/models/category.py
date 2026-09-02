from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(100),
        nullable=False,
        unique=True,
    )

    slug = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    image_url = Column(
        String(500),
        nullable=True,
    )

    icon = Column(
        String(10),
        nullable=True,
    )

    products = relationship(
        "Product",
        back_populates="category_rel",
    )
