"""Authentication schemas."""
import re
from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_RE = re.compile(r"^[A-Za-z0-9$%&!:]{8,100}$")
SPECIALS = set("$%&!:")

def validate_password(value: str) -> str:
    if not PASSWORD_RE.fullmatch(value):
        raise ValueError("Пароль должен содержать минимум 8 символов и только латинские буквы, цифры или символы $%&!:")
    if not any(ch.isupper() and ch.isascii() for ch in value):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную латинскую букву")
    if not any(ch in SPECIALS for ch in value):
        raise ValueError("Пароль должен содержать хотя бы один специальный символ: $%&!:")
    return value

class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password(value)
