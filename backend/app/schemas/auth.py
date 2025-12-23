"""
Authentication request/response schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole, UserStatus


class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_id: str = Field(..., description="Authenticated user ID")
    roles: list[str] = Field(..., description="User roles")


class RegisterRequest(BaseModel):
    """Registration request body."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        description="User password (min 8 characters)"
    )
    password_confirm: str = Field(..., description="Password confirmation")

    def passwords_match(self) -> bool:
        """Check if password and confirmation match."""
        return self.password == self.password_confirm


class RegisterResponse(BaseModel):
    """Registration response."""
    user_id: str = Field(..., description="Created user ID")
    email: str = Field(..., description="Registered email")
    message: str = Field(
        default="Registration successful",
        description="Success message"
    )


class TokenRefreshRequest(BaseModel):
    """Token refresh request - token comes from query param, this is optional body."""
    pass


class TokenRefreshResponse(BaseModel):
    """Token refresh response."""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenPayload(BaseModel):
    """Decoded JWT token payload."""
    sub: str = Field(..., description="Subject (user ID)")
    roles: list[str] = Field(..., description="User roles")
    exp: datetime = Field(..., description="Expiration time")
    iat: datetime = Field(..., description="Issued at time")


class UserInfoResponse(BaseModel):
    """Current user information response."""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    roles: list[UserRole] = Field(..., description="User roles")
    status: UserStatus = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Account creation timestamp")
