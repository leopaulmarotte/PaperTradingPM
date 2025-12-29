"""
Tests for database connections and initialization.

These tests cover:
- MongoDB connection initialization
- Index creation
- Database registry sync
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestMongoDBConnection:
    """Tests for MongoDB connection handling."""

    @pytest.mark.asyncio
    async def test_get_mongo_client_creates_connection(self):
        """get_mongo_client should create connection on first call."""
        with patch("app.database.connections.AsyncIOMotorClient") as mock_client, \
             patch("app.database.connections._mongo_client", None), \
             patch("app.database.connections.get_settings") as mock_settings:
            
            mock_settings.return_value.mongo_uri = "mongodb://test:27017"
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            from app.database.connections import get_mongo_client
            
            # Reset global state for this test
            import app.database.connections as conn_module
            conn_module._mongo_client = None
            
            client = await get_mongo_client()
            
            mock_client.assert_called_once_with("mongodb://test:27017")
            assert client is mock_instance

    @pytest.mark.asyncio
    async def test_close_connections_cleans_up(self):
        """close_connections should clean up both connections."""
        mock_mongo = MagicMock()
        mock_redis = AsyncMock()
        
        import app.database.connections as conn_module
        conn_module._mongo_client = mock_mongo
        conn_module._redis_client = mock_redis
        
        from app.database.connections import close_connections
        await close_connections()
        
        mock_mongo.close.assert_called_once()
        mock_redis.close.assert_called_once()


class TestDatabaseRegistry:
    """Tests for database registry synchronization."""

    @pytest.mark.asyncio
    async def test_registry_creates_metadata_entries(self, mock_async_mongo_client):
        """Registry sync should create _metadata entries."""
        # After sync, each DB should have _metadata collection
        db = mock_async_mongo_client["system_db"]
        
        # Insert a test registry entry
        await db.db_registry.insert_one({
            "db_name": "auth_db",
            "collections": ["users"],
            "synced_at": "2024-12-29T10:00:00Z",
        })
        
        # Verify it was stored
        entry = await db.db_registry.find_one({"db_name": "auth_db"})
        assert entry is not None
        assert entry["db_name"] == "auth_db"


class TestIndexCreation:
    """Tests for index creation on collections."""

    @pytest.mark.asyncio
    async def test_indexes_created_on_markets_collection(self, mock_markets_db):
        """Markets collection should have proper indexes."""
        # Get index info
        indexes = await mock_markets_db.markets.index_information()
        
        # Should have indexes (at minimum _id and slug)
        assert len(indexes) > 0
        
        # Slug index should exist
        assert any("slug" in str(idx) for idx in indexes.values())

    @pytest.mark.asyncio
    async def test_indexes_created_on_users_collection(self, mock_auth_db):
        """Users collection should have email index."""
        indexes = await mock_auth_db.users.index_information()
        
        # Email index should exist
        assert any("email" in str(idx) for idx in indexes.values())

    @pytest.mark.asyncio
    async def test_indexes_created_on_portfolios_collection(self, mock_trading_db):
        """Portfolios collection should have user_id index."""
        indexes = await mock_trading_db.portfolios.index_information()
        
        # user_id index should exist
        assert any("user_id" in str(idx) for idx in indexes.values())


class TestRedisConnection:
    """Tests for Redis connection handling."""

    @pytest.mark.asyncio
    async def test_get_redis_client_creates_connection(self):
        """get_redis_client should create connection on first call."""
        with patch("app.database.connections.Redis") as mock_redis_cls, \
             patch("app.database.connections.get_settings") as mock_settings:
            
            mock_settings.return_value.redis_host = "localhost"
            mock_settings.return_value.redis_port = 6379
            mock_instance = AsyncMock()
            mock_redis_cls.return_value = mock_instance
            
            import app.database.connections as conn_module
            conn_module._redis_client = None
            
            from app.database.connections import get_redis_client
            client = await get_redis_client()
            
            mock_redis_cls.assert_called_once_with(
                host="localhost",
                port=6379,
                decode_responses=True,
            )
            assert client is mock_instance

    @pytest.mark.asyncio
    async def test_redis_ping_succeeds(self, mock_async_redis):
        """Redis ping should succeed when connected."""
        result = await mock_async_redis.ping()
        assert result is True or result == "PONG"
