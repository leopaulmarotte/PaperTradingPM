"""
Authentication router for login, registration, and token refresh.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limit import check_rate_limit
from app.database.connections import get_mongo_client
from app.database.databases import auth_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshResponse,
    UserInfoResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_auth_service() -> AuthService:
    """Dependency to get AuthService instance."""
    client = await get_mongo_client()
    db = client[auth_db.DB_NAME]
    return AuthService(db)


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: Request,
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Register a new user account.
    
    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)
    - **password_confirm**: Must match password
    """
    # TODO: Rate limit registration endpoint
    client_ip = get_client_ip(request)
    if not await check_rate_limit(client_ip, "/auth/register", limit=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )
    
    try:
        return await auth_service.register_user(body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login and get access token",
)
async def login(
    request: Request,
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Authenticate with email and password to receive a JWT token.
    
    The token should be passed as a query parameter `token` to protected endpoints.
    
    **Rate limited**: 5 attempts per minute per IP, account lockout after 10 failures.
    """
    # TODO: Strict rate limit on login endpoint
    client_ip = get_client_ip(request)
    if not await check_rate_limit(client_ip, "/auth/login", limit=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
    
    try:
        return await auth_service.login(body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh access token",
)
async def refresh_token(
    current_user: Annotated[User, Depends(get_current_active_user)],
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Refresh the JWT token for an authenticated user.
    
    Call this endpoint periodically or when performing important actions
    to extend the session.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    try:
        result = await auth_service.refresh_token(current_user.id)
        return TokenRefreshResponse(
            access_token=result.access_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Get current user info",
)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Get information about the currently authenticated user.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "roles": current_user.roles,
        "status": current_user.status,
        "created_at": current_user.created_at,
    }
