"""
Database definitions and collection constants.
"""
from app.database.databases import auth_db, trading_db, markets_db, system_db

__all__ = ["auth_db", "trading_db", "markets_db", "system_db"]
