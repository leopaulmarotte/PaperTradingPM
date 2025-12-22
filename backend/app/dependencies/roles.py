"""
Role-based access control dependencies.
"""
from typing import Callable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_active_user
from app.models.user import User, UserRole


def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(user: User = Depends(require_roles(UserRole.ADMIN))):
            ...
    
    Args:
        *allowed_roles: Roles that are allowed to access the route
        
    Returns:
        Dependency function that validates user roles
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        # Convert user roles to UserRole enum for comparison
        user_roles = set()
        for role in current_user.roles:
            try:
                if isinstance(role, str):
                    user_roles.add(UserRole(role))
                else:
                    user_roles.add(role)
            except ValueError:
                continue
        
        # Check if user has any of the allowed roles
        allowed_set = set(allowed_roles)
        if not user_roles.intersection(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        
        return current_user
    
    return role_checker


def require_admin() -> Callable:
    """
    Shortcut dependency for admin-only routes.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(user: User = Depends(require_admin())):
            ...
    """
    return require_roles(UserRole.ADMIN)


def require_premium_or_admin() -> Callable:
    """
    Shortcut dependency for premium user or admin routes.
    
    Usage:
        @router.get("/premium-feature")
        async def premium_route(user: User = Depends(require_premium_or_admin())):
            ...
    """
    return require_roles(UserRole.PREMIUM_USER, UserRole.ADMIN)


def require_any_authenticated() -> Callable:
    """
    Dependency that allows any authenticated user (any role).
    
    Usage:
        @router.get("/any-user")
        async def any_user_route(user: User = Depends(require_any_authenticated())):
            ...
    """
    return require_roles(UserRole.USER, UserRole.PREMIUM_USER, UserRole.ADMIN)
