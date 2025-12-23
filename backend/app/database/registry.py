"""
Database registry management.
Ensures all databases and collections are registered on startup.
"""
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

from app.database.databases import auth_db, trading_db, markets_db, system_db

# All database manifests
ALL_DB_MANIFESTS = [
    auth_db.DB_MANIFEST,
    trading_db.DB_MANIFEST,
    markets_db.DB_MANIFEST,
    system_db.DB_MANIFEST,
]


async def sync_registry(client: AsyncIOMotorClient) -> None:
    """
    Synchronize the database registry on application startup.
    Ensures all databases are registered in system_db.db_registry.
    """
    sys_db = client[system_db.DB_NAME]
    registry_collection = sys_db[system_db.Collections.DB_REGISTRY]
    
    for manifest in ALL_DB_MANIFESTS:
        db_name = manifest["db_name"]
        
        # Upsert database entry
        await registry_collection.update_one(
            {"_id": db_name},
            {
                "$set": {
                    "purpose": manifest["purpose"],
                    "collections": manifest["collections"],
                    "access_level": manifest["access_level"],
                    "schema_version": "1.0",
                    "updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        
        # Ensure _metadata collection exists in each database
        db = client[db_name]
        metadata_collection = db["_metadata"]
        await metadata_collection.update_one(
            {"_id": "db_metadata"},
            {
                "$set": {
                    "db_name": db_name,
                    "last_updated_at": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )


async def create_indexes(client: AsyncIOMotorClient) -> None:
    """Create necessary indexes for all databases."""
    
    # Auth DB indexes
    auth_users = client[auth_db.DB_NAME][auth_db.Collections.USERS]
    await auth_users.create_index("email", unique=True)
    
    # Trading DB indexes
    trading = client[trading_db.DB_NAME]
    await trading[trading_db.Collections.PORTFOLIOS].create_index("user_id")
    await trading[trading_db.Collections.TRADES].create_index("portfolio_id")
    await trading[trading_db.Collections.TRADES].create_index(
        [("portfolio_id", 1), ("trade_timestamp", -1)]
    )
    
    # Markets DB indexes
    await markets_db.create_market_indexes(client[markets_db.DB_NAME])
    
    # Markets DB indexes
    markets = client[markets_db.DB_NAME]
    await markets[markets_db.Collections.REGISTRY].create_index("condition_id")
