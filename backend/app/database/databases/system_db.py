"""
System database configuration.
Cross-database registry and system-wide metadata.
"""

DB_NAME = "system_db"


class Collections:
    """Collection names in system_db."""
    DB_REGISTRY = "db_registry"
    METADATA = "_metadata"


# Manifest for registry
DB_MANIFEST = {
    "db_name": DB_NAME,
    "purpose": "Cross-database registry and system metadata",
    "collections": [Collections.DB_REGISTRY, Collections.METADATA],
    "access_level": "system",
}
