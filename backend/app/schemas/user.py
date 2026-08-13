"""User schemas."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PHONE_REGEX = re.compile(r"^\+7\d{10}$")
PASSWORD_REGEX = re.compile(r"^[A-Za-z0-9$%&!:]{8,}$")
SPECIAL_CHARS = set("$%&!:")


class UserCreate(BaseModel):
    """Registration payload."""

    full_name: str = Field(min_length=3, max_length=255, examples=["Иванов Иван Иванович"])
    email: EmailStr
    phone: str = Field(examples=["+79991234567"])
    password: str
    password_confirm: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Validate Russian phone format."""
        value = value.strip()
        if not PHONE_REGEX.fullmatch(value):
            raise ValueError("phone must start with +7 and contain 10 digits")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Validate password policy."""
        if not PASSWORD_REGEX.fullmatch(value):
            raise ValueError(
                "password must be at least 8 characters long and contain "
                "only Latin letters, digits or special symbols $%&!:"
            )

        if not any(char.isupper() and char.isascii() for char in value):
            raise ValueError("password must contain at least one uppercase letter")

        if not any(char in SPECIAL_CHARS for char in value):
            raise ValueError("password must contain at least one special symbol: $%&!:")

        return value

    @model_validator(mode="after")
    def validate_password_confirm(self):
        """Ensure password and confirmation match."""
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self


class UserOut(BaseModel):
    """Public user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone: str
    is_admin: bool
    created_at: datetime