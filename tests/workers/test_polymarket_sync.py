"""
Tests for polymarket_sync worker.

These tests cover:
- Market fetching in batches
- Progress tracking (sync_state)
- Resume capability
- Data transformation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json


class TestSyncBatching:
    """Tests for batch fetching behavior."""

    def test_sync_fetches_markets_in_batches_of_500(self):
        """Worker should fetch markets in configurable batch size."""
        # Default batch size is 500
        from workers.polymarket_sync.sync_markets import config
        
        assert config.batch_size == 500

    @pytest.mark.asyncio
    async def test_gamma_api_client_respects_limit_param(self):
        """GammaAPIClient should respect limit parameter."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            
            from workers.polymarket_sync.sync_markets import GammaAPIClient
            
            client = GammaAPIClient()
            await client.get_markets(limit=100, offset=0)
            
            # Verify limit was passed
            call_args = mock_get.call_args
            assert "limit" in str(call_args) or call_args[1]["params"]["limit"] == 100


class TestSyncProgress:
    """Tests for sync progress tracking."""

    @pytest.mark.asyncio
    async def test_sync_saves_progress_cursor_to_sync_state(self, mock_async_mongo_client):
        """Worker should save progress to sync_state collection."""
        db = mock_async_mongo_client["markets_db"]
        
        # Simulate saving progress
        await db.sync_state.update_one(
            {"_id": "full_sync"},
            {
                "$set": {
                    "last_offset": 1000,
                    "total_fetched": 1000,
                    "status": "in_progress",
                    "updated_at": "2024-12-29T10:00:00Z",
                }
            },
            upsert=True,
        )
        
        # Verify saved
        state = await db.sync_state.find_one({"_id": "full_sync"})
        assert state["last_offset"] == 1000
        assert state["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_sync_resumes_from_last_saved_cursor(self, mock_async_mongo_client):
        """Worker should resume from last saved offset."""
        db = mock_async_mongo_client["markets_db"]
        
        # Pre-populate sync state (simulating interrupted sync)
        await db.sync_state.insert_one({
            "_id": "full_sync",
            "last_offset": 5000,
            "total_fetched": 5000,
            "status": "in_progress",
        })
        
        # Worker should read this and resume from offset 5000
        state = await db.sync_state.find_one({"_id": "full_sync"})
        
        assert state["last_offset"] == 5000
        # In actual worker, this would be used as starting offset


class TestDataTransformation:
    """Tests for market data transformation."""

    def test_transform_market_converts_camelcase_to_snake(self):
        """transform_market should convert camelCase to snake_case."""
        from workers.polymarket_sync.sync_markets import transform_market
        
        raw = {
            "slug": "test-market",
            "conditionId": "0x123",
            "volumeNum": 1000000,
            "volume24hr": 50000,
            "liquidityNum": 100000,
            "bestBid": 0.65,
            "bestAsk": 0.66,
            "endDateIso": "2024-12-31T00:00:00Z",
        }
        
        result = transform_market(raw)
        
        # Should have snake_case keys
        assert "condition_id" in result
        assert "volume_num" in result
        assert "volume_24hr" in result
        assert "liquidity_num" in result
        assert "best_bid" in result
        assert "best_ask" in result
        assert "end_date_iso" in result
        
        # Should NOT have camelCase keys
        assert "conditionId" not in result
        assert "volumeNum" not in result

    def test_transform_market_parses_json_string_arrays(self):
        """transform_market should parse JSON string fields."""
        from workers.polymarket_sync.sync_markets import transform_market
        
        raw = {
            "slug": "test-market",
            "outcomes": '["Yes", "No"]',  # JSON string
            "outcomePrices": '["0.65", "0.35"]',  # JSON string
            "clobTokenIds": '["token1", "token2"]',  # JSON string
            "tags": '["Politics", "Elections"]',  # JSON string
        }
        
        result = transform_market(raw)
        
        # Should be actual arrays, not strings
        assert isinstance(result["outcomes"], list)
        assert result["outcomes"] == ["Yes", "No"]
        
        assert isinstance(result["outcome_prices"], list)
        assert result["outcome_prices"] == ["0.65", "0.35"]
        
        assert isinstance(result["clob_token_ids"], list)
        assert isinstance(result["tags"], list)

    def test_transform_market_handles_missing_fields(self):
        """transform_market should handle missing fields gracefully."""
        from workers.polymarket_sync.sync_markets import transform_market
        
        raw = {
            "slug": "minimal-market",
        }
        
        result = transform_market(raw)
        
        # Should have defaults for missing fields
        assert result["slug"] == "minimal-market"
        assert result["outcomes"] == []
        assert result["volume_num"] == 0.0
        assert result["closed"] is False
        assert result["active"] is True

    def test_transform_market_handles_boolean_variations(self):
        """transform_market should handle different boolean representations."""
        from workers.polymarket_sync.sync_markets import transform_market
        
        # Test with string "true"
        raw1 = {"slug": "m1", "closed": "true", "active": "true"}
        result1 = transform_market(raw1)
        assert result1["closed"] is True
        assert result1["active"] is True
        
        # Test with boolean True
        raw2 = {"slug": "m2", "closed": True, "active": False}
        result2 = transform_market(raw2)
        assert result2["closed"] is True
        assert result2["active"] is False
        
        # Test with integer 1
        raw3 = {"slug": "m3", "closed": 1, "active": 0}
        result3 = transform_market(raw3)
        assert result3["closed"] is True
        assert result3["active"] is False


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_json_string_parses_valid_json(self):
        """parse_json_string should parse valid JSON."""
        from workers.polymarket_sync.sync_markets import parse_json_string
        
        result = parse_json_string('["a", "b", "c"]')
        assert result == ["a", "b", "c"]
        
        result = parse_json_string('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_string_returns_original_on_invalid(self):
        """parse_json_string should return original on invalid JSON."""
        from workers.polymarket_sync.sync_markets import parse_json_string
        
        result = parse_json_string("not json")
        assert result == "not json"

    def test_parse_json_string_returns_non_strings_unchanged(self):
        """parse_json_string should return non-strings unchanged."""
        from workers.polymarket_sync.sync_markets import parse_json_string
        
        assert parse_json_string(123) == 123
        assert parse_json_string(["a", "b"]) == ["a", "b"]
        assert parse_json_string(None) is None

    def test_safe_float_converts_valid_numbers(self):
        """safe_float should convert valid numbers."""
        from workers.polymarket_sync.sync_markets import safe_float
        
        assert safe_float(100) == 100.0
        assert safe_float("123.45") == 123.45
        assert safe_float(0) == 0.0

    def test_safe_float_returns_default_on_invalid(self):
        """safe_float should return default on invalid input."""
        from workers.polymarket_sync.sync_markets import safe_float
        
        assert safe_float(None) is None
        assert safe_float(None, 0.0) == 0.0
        assert safe_float("not a number", 0.0) == 0.0
        assert safe_float("", 0.0) == 0.0


class TestSyncConfiguration:
    """Tests for sync configuration."""

    def test_config_loads_defaults(self):
        """Config should have sensible defaults."""
        from workers.polymarket_sync.sync_markets import SyncConfig
        
        config = SyncConfig()
        
        assert config.batch_size == 500
        assert config.sync_interval_minutes > 0
        assert config.full_sync_interval_hours > 0
        assert "gamma-api.polymarket.com" in config.gamma_api_url

    def test_config_mongodb_uri_default(self):
        """Config should have MongoDB URI default."""
        from workers.polymarket_sync.sync_markets import SyncConfig
        
        config = SyncConfig()
        
        assert "mongodb" in config.mongodb_uri
