"""
User model for authentication database.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User role levels."""
    USER = "user"
    PREMIUM_USER = "premium_user"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    DISABLED = "disabled"


class User(BaseModel):
    """
    User document model for MongoDB auth_db.users collection.
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId as string")
    email: EmailStr = Field(..., description="Unique email address")
    hashed_password: str = Field(..., description="Bcrypt hashed password")
    roles: list[UserRole] = Field(
        default=[UserRole.USER],
        description="List of roles assigned to user"
    )
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        description="Account status"
    )
    failed_attempts: int = Field(
        default=0,
        description="Number of consecutive failed login attempts"
    )
    locked_until: Optional[datetime] = Field(
        None,
        description="Account locked until this timestamp"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Account creation timestamp"
    )
    
    # Future: password reset fields
    # password_reset_token: Optional[str] = None
    # reset_token_expires: Optional[datetime] = None

    class Config:
        populate_by_name = True
        use_enum_values = True


class UserInDB(User):
    """User model with additional DB-specific fields."""
    pass
