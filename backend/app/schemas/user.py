"""
User request/response schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    """User information response (excludes sensitive data)."""
    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    roles: list[str] = Field(..., description="User roles")
    status: str = Field(..., description="Account status")
    created_at: datetime = Field(..., description="Account creation date")


class UserUpdate(BaseModel):
    """User update request (limited fields)."""
    email: Optional[EmailStr] = Field(None, description="New email address")
    
    # Password change would be a separate endpoint
    # current_password: Optional[str] = None
    # new_password: Optional[str] = None
