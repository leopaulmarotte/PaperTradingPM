"""
Authentication service for user management and login.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security import hash_password, verify_password, create_access_token
from app.core.rate_limit import (
    check_user_lockout,
    increment_failed_login,
    reset_failed_attempts,
    set_user_lockout,
)
from app.config import get_settings
from app.database.databases import auth_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
)


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with auth database."""
        self.db = db
        self.users_collection = db[auth_db.Collections.USERS]
        self.settings = get_settings()
    
    async def register_user(self, request: RegisterRequest) -> RegisterResponse:
        """
        Register a new user.
        
        Args:
            request: Registration request with email and password
            
        Returns:
            RegisterResponse with created user ID
            
        Raises:
            ValueError: If passwords don't match or email exists
        """
        # Validate passwords match
        if not request.passwords_match():
            raise ValueError("Passwords do not match")
        
        # Check if email already exists
        existing = await self.users_collection.find_one({"email": request.email})
        if existing:
            raise ValueError("Email already registered")
        
        # Create user document
        user_doc = {
            "email": request.email,
            "hashed_password": hash_password(request.password),
            "roles": [UserRole.USER.value],
            "status": UserStatus.ACTIVE.value,
            "failed_attempts": 0,
            "locked_until": None,
            "created_at": datetime.now(timezone.utc),
        }
        
        result = await self.users_collection.insert_one(user_doc)
        
        return RegisterResponse(
            user_id=str(result.inserted_id),
            email=request.email,
            message="Registration successful"
        )
    
    async def login(self, request: LoginRequest) -> LoginResponse:
        """
        Authenticate user and return JWT token.
        
        Args:
            request: Login request with email and password
            
        Returns:
            LoginResponse with JWT token
            
        Raises:
            ValueError: If credentials are invalid or account is locked
        """
        # Find user by email
        user_doc = await self.users_collection.find_one({"email": request.email})
        
        if not user_doc:
            raise ValueError("Invalid email or password")
        
        user_id = str(user_doc["_id"])
        
        # Check if user is locked out (TODO: Redis implementation)
        if await check_user_lockout(user_id):
            raise ValueError("Account temporarily locked due to too many failed attempts")
        
        # Check if account is disabled
        if user_doc.get("status") == UserStatus.DISABLED.value:
            raise ValueError("Account is disabled")
        
        # Verify password
        if not verify_password(request.password, user_doc["hashed_password"]):
            # Increment failed attempts (TODO: Redis implementation)
            failed_count = await increment_failed_login(user_id)
            
            # Check if should lock out
            if failed_count >= self.settings.user_lockout_threshold:
                await set_user_lockout(
                    user_id,
                    self.settings.user_lockout_duration_minutes
                )
            
            raise ValueError("Invalid email or password")
        
        # Reset failed attempts on successful login
        await reset_failed_attempts(user_id)
        
        # Generate JWT token
        roles = user_doc.get("roles", [UserRole.USER.value])
        access_token = create_access_token(user_id=user_id, roles=roles)
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
            user_id=user_id,
            roles=roles,
        )
    
    async def refresh_token(self, user_id: str) -> LoginResponse:
        """
        Refresh JWT token for an authenticated user.
        
        Args:
            user_id: Authenticated user ID
            
        Returns:
            LoginResponse with new JWT token
            
        Raises:
            ValueError: If user not found or disabled
        """
        user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user_doc:
            raise ValueError("User not found")
        
        if user_doc.get("status") == UserStatus.DISABLED.value:
            raise ValueError("Account is disabled")
        
        roles = user_doc.get("roles", [UserRole.USER.value])
        access_token = create_access_token(user_id=user_id, roles=roles)
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=self.settings.jwt_access_token_expire_minutes * 60,
            user_id=user_id,
            roles=roles,
        )
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ObjectId as string
            
        Returns:
            User model or None if not found
        """
        try:
            user_doc = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        
        if not user_doc:
            return None
        
        user_doc["_id"] = str(user_doc["_id"])
        return User(**user_doc)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email address
            
        Returns:
            User model or None if not found
        """
        user_doc = await self.users_collection.find_one({"email": email})
        
        if not user_doc:
            return None
        
        user_doc["_id"] = str(user_doc["_id"])
        return User(**user_doc)
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> dict:
        """
        Change user password after verifying current password.
        
        Args:
            user_id: User ID to change password for
            current_password: Current password (for verification)
            new_password: New password to set
            
        Returns:
            dict with message, user_id, and email
            
        Raises:
            ValueError: If current password is incorrect or user not found
        """
        # Get user document
        try:
            user_doc = await self.users_collection.find_one(
                {"_id": ObjectId(user_id)}
            )
        except Exception:
            raise ValueError("Invalid user ID")
        
        if not user_doc:
            raise ValueError("User not found")
        
        # Verify current password
        if not verify_password(current_password, user_doc["hashed_password"]):
            raise ValueError("Current password is incorrect")
        
        # Update password
        new_hashed_password = hash_password(new_password)
        result = await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": new_hashed_password}},
        )
        
        if result.modified_count == 0:
            raise ValueError("Failed to update password")
        
        return {
            "message": "Password changed successfully",
            "user_id": user_id,
            "email": user_doc["email"],
        }
