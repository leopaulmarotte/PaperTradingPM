"""
Database module - MongoDB and Redis connections and database definitions.
"""
from app.database.connections import (
    get_mongo_client,
    get_redis_client,
    close_connections,
    get_database,
)
from app.database.databases import auth_db, trading_db, markets_db, system_db

__all__ = [
    "get_mongo_client",
    "get_redis_client", 
    "close_connections",
    "get_database",
    "auth_db",
    "trading_db",
    "markets_db",
    "system_db",
]
