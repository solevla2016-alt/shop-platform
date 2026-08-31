"""Category schemas."""
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=10)
    @field_validator("name", "slug", mode="before")
    @classmethod
    def strip_values(cls, value):
        return value.strip() if isinstance(value, str) else value

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(default=None, max_length=10)
    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
