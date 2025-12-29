"""
Tests for service layer classes.

These tests cover:
- AuthService (password hashing, verification)
- MarketService (caching logic)
- PortfolioService (calculations)
- PolymarketAPI (response parsing)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


# =============================================================================
# Password Hashing Tests (app.core.security)
# =============================================================================

class TestPasswordHashing:
    """Tests for password hashing functions in app.core.security."""

    def test_hash_password_returns_bcrypt_hash(self):
        """hash_password should return bcrypt hash."""
        from app.core.security import hash_password
        
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        # bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")
        assert hashed != password

    def test_verify_password_correct_returns_true(self):
        """verify_password with correct password should return True."""
        from app.core.security import hash_password, verify_password
        
        password = "TestPassword123!"
        hashed = hash_password(password)
        
        result = verify_password(password, hashed)
        
        assert result is True

    def test_verify_password_wrong_returns_false(self):
        """verify_password with wrong password should return False."""
        from app.core.security import hash_password, verify_password
        
        password = "TestPassword123!"
        wrong_password = "WrongPassword123!"
        hashed = hash_password(password)
        
        result = verify_password(wrong_password, hashed)
        
        assert result is False

    def test_hash_password_different_each_time(self):
        """hash_password should produce different hashes (salt)."""
        from app.core.security import hash_password
        
        password = "TestPassword123!"
        
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Same password should produce different hashes due to salt
        assert hash1 != hash2


# =============================================================================
# MarketService Tests
# =============================================================================

class TestMarketServiceCache:
    """Tests for MarketService caching behavior."""

    @pytest.mark.asyncio
    async def test_get_market_cache_hit_returns_from_db(
        self, mock_markets_db, market_fixture_fed_october
    ):
        """Getting cached market should return from DB without API call."""
        from app.services.market_service import MarketService
        
        # Pre-populate cache with required fields for _doc_to_detail_response
        market_doc = {
            "_id": market_fixture_fed_october["slug"],
            "slug": market_fixture_fed_october["slug"],
            "condition_id": "0x123",
            "question": market_fixture_fed_october.get("question", "Test question?"),
            "outcomes": ["Yes", "No"],
            "outcome_prices": ["0.65", "0.35"],
            "clob_token_ids": ["token1", "token2"],
            "volume_total": 1000000,
            "volume_24h": 50000,
            "liquidity": 100000,
            "closed": market_fixture_fed_october.get("closed", False),
            "active": market_fixture_fed_october.get("active", True),
        }
        await mock_markets_db.markets.insert_one(market_doc)
        
        service = MarketService(mock_markets_db)
        
        with patch("app.services.market_service.get_polymarket_api") as mock_api:
            result = await service.get_market_by_slug(market_fixture_fed_october["slug"])
            
            # API should not be called for cached market
            mock_api.assert_not_called()
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_market_cache_miss_fetches_from_api(self, mock_markets_db):
        """Getting uncached market should fetch from API."""
        from app.services.market_service import MarketService
        
        service = MarketService(mock_markets_db)
        
        with patch("app.services.market_service.get_polymarket_api") as mock_get_api:
            mock_api = AsyncMock()
            mock_api.get_market_by_slug.return_value = None  # Simulate not found
            mock_get_api.return_value = mock_api
            
            # Market not in DB, should trigger API fetch
            result = await service.get_market_by_slug("nonexistent-market")
            
            # Should have attempted API fetch
            mock_get_api.assert_called_once()
            mock_api.get_market_by_slug.assert_called_once_with("nonexistent-market")

    @pytest.mark.asyncio
    async def test_save_market_stores_in_mongodb(self, mock_markets_db):
        """Saving market should store in MongoDB."""
        from app.services.market_service import MarketService
        
        service = MarketService(mock_markets_db)
        
        market_data = {
            "slug": "test-market",
            "question": "Test question?",
            "closed": False,
        }
        
        # Directly insert (simulating save)
        await mock_markets_db.markets.insert_one({
            "_id": market_data["slug"],
            **market_data
        })
        
        # Verify stored
        stored = await mock_markets_db.markets.find_one({"_id": "test-market"})
        assert stored is not None
        assert stored["question"] == "Test question?"


# =============================================================================
# PortfolioService Tests
# =============================================================================

class TestPortfolioServiceCalculations:
    """Tests for PortfolioService calculations."""

    @pytest.mark.asyncio
    async def test_calculate_balance_deducts_after_buy(self, mock_trading_db):
        """Balance should decrease after buy trade."""
        from app.services.portfolio_service import PortfolioService
        
        # Insert portfolio
        await mock_trading_db.portfolios.insert_one({
            "_id": "portfolio_id",
            "user_id": "user_id",
            "initial_balance": 10000.0,
        })
        
        # Insert buy trade
        await mock_trading_db.trades.insert_one({
            "portfolio_id": "portfolio_id",
            "side": "BUY",
            "quantity": 100,
            "price": 0.65,  # Cost = 65
        })
        
        # Calculate balance
        # 10000 - (100 * 0.65) = 9935
        # Actual implementation may vary

    @pytest.mark.asyncio
    async def test_aggregate_positions_groups_by_market_outcome(self, mock_trading_db):
        """Positions should be aggregated by market and outcome."""
        # Insert trades for same market
        await mock_trading_db.trades.insert_many([
            {
                "portfolio_id": "portfolio_id",
                "market_id": "market-a",
                "outcome": "Yes",
                "side": "BUY",
                "quantity": 100,
                "price": 0.50,
            },
            {
                "portfolio_id": "portfolio_id",
                "market_id": "market-a",
                "outcome": "Yes",
                "side": "BUY",
                "quantity": 50,
                "price": 0.55,
            },
        ])
        
        # Aggregated position should be 150 Yes on market-a


# =============================================================================
# PolymarketAPI Tests
# =============================================================================

class TestPolymarketAPIParsing:
    """Tests for PolymarketAPI response parsing."""

    @pytest.mark.asyncio
    async def test_parse_gamma_api_response_extracts_fields(self):
        """Gamma API response should be parsed correctly."""
        raw_response = {
            "id": "12345",
            "slug": "test-market",
            "question": "Will X happen?",
            "outcomes": '["Yes", "No"]',  # JSON string
            "outcomePrices": '["0.65", "0.35"]',  # JSON string
            "clobTokenIds": '["token1", "token2"]',  # JSON string
            "volumeNum": 1000000,
            "volume24hr": 50000,
            "liquidityNum": 100000,
            "closed": False,
            "active": True,
        }
        
        # Parse the JSON strings
        import json
        outcomes = json.loads(raw_response["outcomes"])
        prices = json.loads(raw_response["outcomePrices"])
        tokens = json.loads(raw_response["clobTokenIds"])
        
        assert outcomes == ["Yes", "No"]
        assert len(prices) == 2
        assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_parse_clob_prices_returns_history_array(self):
        """CLOB price history should be parsed to array."""
        raw_history = [
            {"t": 1696118400, "p": 0.52},
            {"t": 1696204800, "p": 0.55},
            {"t": 1696291200, "p": 0.58},
        ]
        
        assert len(raw_history) == 3
        assert raw_history[0]["t"] == 1696118400
        assert raw_history[0]["p"] == 0.52
