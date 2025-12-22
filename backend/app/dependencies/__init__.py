"""
Dependencies for dependency injection in routes.
"""
from app.dependencies.auth import get_current_user, get_current_active_user
from app.dependencies.roles import require_roles, require_admin

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_roles",
    "require_admin",
]
