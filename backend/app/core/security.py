"""
Security utilities for password hashing and JWT token management.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain password using bcrypt.
    
    Args:
        plain_password: The plain text password to hash
        
    Returns:
        Hashed password string
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        user_id: Unique user identifier
        roles: List of user roles (e.g., ["user"], ["admin"])
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    expire = datetime.now(timezone.utc) + expires_delta
    
    payload = {
        "sub": user_id,
        "roles": roles,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token string to decode
        
    Returns:
        Decoded payload dictionary with keys: sub, roles, exp, iat
        
    Raises:
        JWTError: If token is invalid or expired
    """
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        raise


def is_token_expired(payload: dict[str, Any]) -> bool:
    """
    Check if a decoded token payload is expired.
    
    Args:
        payload: Decoded JWT payload
        
    Returns:
        True if expired, False otherwise
    """
    exp = payload.get("exp")
    if exp is None:
        return True
    return datetime.now(timezone.utc) > datetime.fromtimestamp(exp, tz=timezone.utc)
