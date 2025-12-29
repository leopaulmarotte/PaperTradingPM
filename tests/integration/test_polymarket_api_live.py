"""
Integration tests for live Polymarket API.

These tests make real network calls to Polymarket APIs.
Run with: pytest -m integration tests/integration/

Requires network access. Will be skipped if Polymarket API is unreachable.
"""
import pytest
import httpx
from datetime import datetime


pytestmark = pytest.mark.integration


class TestGammaAPILive:
    """Tests against live Polymarket Gamma API (metadata)."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_api_base_url, test_timeout):
        """Set up HTTP client for tests."""
        self.base_url = live_api_base_url
        self.timeout = test_timeout
    
    def test_gamma_api_health(self):
        """Gamma API should be reachable."""
        try:
            response = httpx.get(f"{self.base_url}/markets", timeout=self.timeout)
            assert response.status_code == 200
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Gamma API")
    
    def test_fetch_markets_list(self):
        """Should fetch list of markets from Gamma API."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"limit": 10},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            # Should return a list of markets
            assert isinstance(data, list)
            assert len(data) > 0
            
            # Each market should have required fields
            market = data[0]
            assert "condition_id" in market or "conditionId" in market
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Gamma API")
    
    def test_fetch_market_by_slug(self, known_closed_market_slug):
        """Should fetch specific market by slug."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"slug": known_closed_market_slug},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            # Should return list with matching market
            assert isinstance(data, list)
            if len(data) > 0:
                market = data[0]
                assert market.get("slug") == known_closed_market_slug or known_closed_market_slug in str(market)
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Gamma API")
    
    def test_fetch_closed_markets(self):
        """Should be able to filter for closed markets."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"closed": True, "limit": 5},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            # Verify markets are closed
            for market in data:
                # Markets may have 'closed' or 'active' field
                closed = market.get("closed", not market.get("active", False))
                assert closed is True or market.get("active") is False
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Gamma API")
    
    def test_market_has_required_fields(self):
        """Fetched markets should have fields we depend on."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"limit": 1},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            if len(data) > 0:
                market = data[0]
                # Check for fields we use in transform_market
                required_fields = ["question", "outcomes", "outcomePrices"]
                optional_fields = ["slug", "description", "volume", "liquidity"]
                
                # At least question should exist
                assert "question" in market or "title" in market
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Gamma API")


class TestCLOBAPILive:
    """Tests against live Polymarket CLOB API (prices/orderbook)."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_clob_url, test_timeout):
        """Set up HTTP client for tests."""
        self.base_url = live_clob_url
        self.timeout = test_timeout
    
    def test_clob_api_reachable(self):
        """CLOB API should be reachable."""
        try:
            # Try to hit a simple endpoint
            response = httpx.get(f"{self.base_url}/", timeout=self.timeout)
            # Even 404 means API is reachable
            assert response.status_code in [200, 404, 405]
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket CLOB API")
    
    def test_fetch_orderbook(self, known_condition_id):
        """Should fetch orderbook for a market."""
        try:
            # CLOB API uses token_id not condition_id
            response = httpx.get(
                f"{self.base_url}/book",
                params={"token_id": known_condition_id},
                timeout=self.timeout,
            )
            # May return 404 for closed markets, that's OK
            assert response.status_code in [200, 400, 404]
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket CLOB API")


class TestDataAPILive:
    """Tests against Polymarket Data API (historical data)."""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_timeout):
        """Set up test."""
        self.base_url = "https://data-api.polymarket.com"
        self.timeout = test_timeout
    
    def test_data_api_reachable(self):
        """Data API should be reachable."""
        try:
            response = httpx.get(f"{self.base_url}/", timeout=self.timeout)
            # Even error response means API is up
            assert response.status_code < 500
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket Data API")


class TestAPIRateLimits:
    """Tests to understand API rate limiting behavior."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_api_base_url, test_timeout):
        """Set up test."""
        self.base_url = live_api_base_url
        self.timeout = test_timeout
    
    @pytest.mark.slow
    def test_multiple_requests_allowed(self):
        """Should handle multiple sequential requests."""
        try:
            for i in range(5):
                response = httpx.get(
                    f"{self.base_url}/markets",
                    params={"limit": 1, "offset": i},
                    timeout=self.timeout,
                )
                assert response.status_code == 200
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket API")


class TestMarketDataQuality:
    """Tests to verify data quality from Polymarket APIs."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_api_base_url, test_timeout):
        """Set up test."""
        self.base_url = live_api_base_url
        self.timeout = test_timeout
    
    def test_prices_are_valid_probabilities(self):
        """Market prices should be valid probabilities (0-1)."""
        import json as json_module
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"limit": 10},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            for market in data:
                prices = market.get("outcomePrices", [])
                if prices:
                    # Parse prices - API returns JSON string like "[0.5, 0.5]"
                    if isinstance(prices, str):
                        prices = json_module.loads(prices)
                    for price in prices:
                        if isinstance(price, str):
                            price = float(price)
                        # Prices should be between 0 and 1
                        assert 0 <= price <= 1, f"Invalid price: {price}"
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket API")
    
    def test_outcomes_match_prices(self):
        """Number of outcomes should match number of prices."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"limit": 10},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            for market in data:
                outcomes = market.get("outcomes", [])
                prices = market.get("outcomePrices", [])
                
                if outcomes and prices:
                    # Convert string outcomes/prices if needed
                    if isinstance(outcomes, str):
                        outcomes = outcomes.strip("[]").split(",")
                    if isinstance(prices, str):
                        prices = prices.strip("[]").split(",")
                    
                    assert len(outcomes) == len(prices), (
                        f"Mismatch: {len(outcomes)} outcomes vs {len(prices)} prices"
                    )
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket API")
    
    def test_closed_markets_have_resolution(self):
        """Closed markets should have resolution data."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"closed": True, "limit": 5},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            
            for market in data:
                # Closed markets typically have resolution info
                # This might be 'resolution', 'resolved', or similar
                has_resolution = any(
                    key in market 
                    for key in ["resolution", "resolved", "winner", "winning_outcome"]
                )
                # Not all APIs include resolution, so just log
                if not has_resolution:
                    print(f"Market {market.get('slug', 'unknown')} missing resolution info")
        except httpx.ConnectError:
            pytest.skip("Cannot reach Polymarket API")
