"""
Markets database configuration.
Stores Polymarket data cache with dynamic collections per market slug.
"""
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

DB_NAME = "markets_db"


class Collections:
    """Collection names in markets_db."""
    REGISTRY = "_registry"
    METADATA = "_metadata"
    
    @staticmethod
    def market(slug: str) -> str:
        """Generate collection name for a market slug."""
        # Sanitize slug for collection name (replace problematic chars)
        safe_slug = slug.replace(" ", "-").replace("/", "-").lower()
        return f"market:{safe_slug}"


async def ensure_market_collection(
    db: AsyncIOMotorDatabase, 
    slug: str, 
    market_info: dict
) -> str:
    """
    Create market collection and register it if not exists.
    
    Args:
        db: Markets database instance
        slug: Market slug identifier
        market_info: Market metadata (condition_id, question, outcomes, etc.)
    
    Returns:
        Collection name for the market
    """
    collection_name = Collections.market(slug)
    
    # Check if already registered
    existing = await db[Collections.REGISTRY].find_one({"_id": slug})
    if existing:
        # Update last_fetched_at
        await db[Collections.REGISTRY].update_one(
            {"_id": slug},
            {"$set": {"last_fetched_at": datetime.now(timezone.utc)}}
        )
        return collection_name
    
    # Register new market collection
    await db[Collections.REGISTRY].insert_one({
        "_id": slug,
        "collection_name": collection_name,
        "condition_id": market_info.get("condition_id"),
        "question": market_info.get("question"),
        "outcomes": market_info.get("outcomes", []),
        "created_at": datetime.now(timezone.utc),
        "last_fetched_at": datetime.now(timezone.utc),
    })
    
    return collection_name


async def get_registered_markets(db: AsyncIOMotorDatabase) -> list[dict]:
    """Get all registered market slugs from the registry."""
    cursor = db[Collections.REGISTRY].find({})
    return await cursor.to_list(length=None)


# Manifest for registry
DB_MANIFEST = {
    "db_name": DB_NAME,
    "purpose": "Polymarket data cache with dynamic per-market collections",
    "collections": [Collections.REGISTRY, Collections.METADATA],
    "access_level": "standard",
    "dynamic_collections": True,
}
