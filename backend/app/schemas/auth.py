"""Authentication schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login by email or phone."""

    identifier: str = Field(min_length=3, description="Email or phone")
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    """Refresh token payload."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
