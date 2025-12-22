"""
Authentication dependencies for route protection.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from jose import JWTError

from app.core.security import decode_token
from app.database.connections import get_mongo_client
from app.database.databases import auth_db
from app.models.user import User, UserStatus
from app.services.auth_service import AuthService


async def get_current_user(
    token: Annotated[str, Query(description="JWT access token")]
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Token is passed as query parameter: ?token=xxx
    
    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 401: If user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    client = await get_mongo_client()
    db = client[auth_db.DB_NAME]
    auth_service = AuthService(db)
    
    user = await auth_service.get_user_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Dependency to ensure the current user is active (not disabled).
    
    Raises:
        HTTPException 403: If user account is disabled
    """
    if current_user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    return current_user


# Type alias for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_active_user)]
