"""User schemas."""

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


PHONE_REGEX = re.compile(r"^\+7\d{10}$")
PASSWORD_REGEX = re.compile(r"^[A-Za-z0-9$%&!:]{8,}$")
SPECIAL_CHARS = set("$%&!:")


class UserCreate(BaseModel):
    """Registration payload."""

    full_name: str = Field(
        min_length=3,
        max_length=255,
        examples=["Иванов Иван Иванович"],
    )

    email: EmailStr

    phone: str = Field(
        examples=["+79991234567"],
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    password_confirm: str = Field(
        min_length=8,
        max_length=128,
    )

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Normalize and validate full name."""
        value = value.strip()

        if len(value) < 3:
            raise ValueError("Имя должно содержать минимум 3 символа")

        return value

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value) -> str:
        """
        Normalize email before Pydantic validates it as EmailStr.

        IMPORTANT:
        EmailStr in Pydantic v2 is a type annotation and must not be
        instantiated as EmailStr(...).
        """
        if value is None:
            raise ValueError("Email обязателен")

        value = str(value).strip().lower()

        if not value:
            raise ValueError("Email не может быть пустым")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Validate Russian phone format."""
        value = value.strip()

        if not PHONE_REGEX.fullmatch(value):
            raise ValueError(
                "Телефон должен быть в формате +79991234567"
            )

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """Validate password policy."""

        if not PASSWORD_REGEX.fullmatch(value):
            raise ValueError(
                "Пароль должен содержать минимум 8 символов "
                "и только латинские буквы, цифры или символы $%&!:"
            )

        if not any(
            char.isupper() and char.isascii()
            for char in value
        ):
            raise ValueError(
                "Пароль должен содержать хотя бы одну заглавную "
                "латинскую букву"
            )

        if not any(char in SPECIAL_CHARS for char in value):
            raise ValueError(
                "Пароль должен содержать хотя бы один специальный "
                "символ: $%&!:"
            )

        return value

    @field_validator("password_confirm")
    @classmethod
    def validate_password_confirm_field(cls, value: str) -> str:
        """Validate password confirmation field."""
        return value

    @model_validator(mode="after")
    def validate_passwords_match(self):
        """Ensure password and confirmation match."""

        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")

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
