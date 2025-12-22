"""
Database connection management for MongoDB and Redis.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis
from typing import Optional

from app.config import get_settings

# Global connection instances
_mongo_client: Optional[AsyncIOMotorClient] = None
_redis_client: Optional[Redis] = None


async def get_mongo_client() -> AsyncIOMotorClient:
    """Get or create MongoDB client."""
    global _mongo_client
    if _mongo_client is None:
        settings = get_settings()
        _mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    return _mongo_client


async def get_redis_client() -> Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
    return _redis_client


async def close_connections():
    """Close all database connections."""
    global _mongo_client, _redis_client
    
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


async def get_database(db_name: str) -> AsyncIOMotorDatabase:
    """Get a specific MongoDB database by name."""
    client = await get_mongo_client()
    return client[db_name]
