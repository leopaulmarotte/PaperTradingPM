"""
Markets database configuration.
Stores Polymarket market metadata and price data.

Structure:
- markets: All market metadata from Gamma API (refreshed by worker)
- price_history: Price history per token_id (lazy-loaded)
- open_interest: Open interest snapshots (lazy-loaded)
- _metadata: Database metadata
"""
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

DB_NAME = "markets_db"


class Collections:
    """Collection names in markets_db."""
    MARKETS = "markets"           # Market metadata from Gamma API
    PRICE_HISTORY = "price_history"  # Price history per token
    OPEN_INTEREST = "open_interest"  # Open interest data
    METADATA = "_metadata"
    
    # Index definitions for each collection
    INDEXES = {
        "markets": [
            {"keys": [("slug", 1)], "unique": True},
            {"keys": [("condition_id", 1)], "unique": True},
            {"keys": [("closed", 1)]},
            {"keys": [("active", 1)]},
            {"keys": [("volume_num", -1)]},
            {"keys": [("liquidity_num", -1)]},
            {"keys": [("end_date", 1)]},
            {"keys": [("category", 1)]},
            {"keys": [("question", "text")]},  # Text index for search
        ],
        "price_history": [
            {"keys": [("token_id", 1)]},  # Non-unique, for querying
            {"keys": [("slug", 1)]},
            {"keys": [("fetched_at", 1)]},
        ],
        "open_interest": [
            {"keys": [("condition_id", 1)], "unique": True},
            {"keys": [("last_updated_at", 1)]},
        ],
    }


async def create_market_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes for markets database collections."""
    for collection_name, indexes in Collections.INDEXES.items():
        collection = db[collection_name]
        for index_def in indexes:
            keys = index_def["keys"]
            kwargs = {k: v for k, v in index_def.items() if k != "keys"}
            try:
                await collection.create_index(keys, **kwargs)
            except Exception:
                # Index might already exist with different options
                pass


# Manifest for registry
DB_MANIFEST = {
    "db_name": DB_NAME,
    "purpose": "Polymarket market metadata and price data cache",
    "collections": [
        Collections.MARKETS,
        Collections.PRICE_HISTORY,
        Collections.OPEN_INTEREST,
        Collections.METADATA,
    ],
    "access_level": "standard",
}
