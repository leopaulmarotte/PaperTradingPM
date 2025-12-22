"""
Auth database configuration.
Stores user identity and authentication data.
"""

DB_NAME = "auth_db"


class Collections:
    """Collection names in auth_db."""
    USERS = "users"
    METADATA = "_metadata"


# Manifest for registry
DB_MANIFEST = {
    "db_name": DB_NAME,
    "purpose": "User authentication and identity management",
    "collections": [Collections.USERS, Collections.METADATA],
    "access_level": "restricted",  # Future: admin-only access
}
