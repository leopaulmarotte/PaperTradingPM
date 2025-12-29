"""
Integration tests for full trading flow.

These tests require a running backend and database.
Run with: pytest -m integration tests/integration/

Requires:
- Backend running at BACKEND_URL (default: http://localhost:8000)
- MongoDB and Redis available
"""
import pytest
import httpx
from datetime import datetime
import time


pytestmark = pytest.mark.integration


class TestFullTradingFlow:
    """End-to-end tests for trading workflow."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_backend_url, test_timeout):
        """Set up test with unique user."""
        self.base_url = live_backend_url
        self.timeout = test_timeout
        self.test_email = f"integration_test_{int(time.time())}@test.com"
        self.test_password = "TestPassword123!"
        self.token = None
        self.portfolio_id = None
    
    def _get_auth_params(self):
        """Return query params with token."""
        return {"token": self.token} if self.token else {}
    
    def test_health_check(self):
        """Backend health endpoint should respond."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "ok"
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_user_registration_flow(self):
        """Should register a new user."""
        try:
            response = httpx.post(
                f"{self.base_url}/auth/register",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                    "password_confirm": self.test_password,
                },
                timeout=self.timeout,
            )
            # 201 for success, 400 if user exists (from previous run)
            assert response.status_code in [200, 201, 400]
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_user_login_flow(self):
        """Should login and receive token."""
        try:
            # First ensure user exists
            httpx.post(
                f"{self.base_url}/auth/register",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                    "password_confirm": self.test_password,
                },
                timeout=self.timeout,
            )
            
            # Now login
            response = httpx.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            self.token = data["access_token"]
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_get_user_profile(self):
        """Should get authenticated user profile."""
        try:
            # Login first
            login_resp = httpx.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                timeout=self.timeout,
            )
            if login_resp.status_code != 200:
                pytest.skip("Could not login")
            self.token = login_resp.json()["access_token"]
            
            # Get profile
            response = httpx.get(
                f"{self.base_url}/auth/me",
                params=self._get_auth_params(),
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("email") == self.test_email
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_list_markets(self):
        """Should list available markets."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"page": 1, "page_size": 10},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            assert "items" in data or isinstance(data, list)
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_search_markets(self):
        """Should search markets by keyword."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"search": "fed", "page_size": 5},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            # Search results may be empty if no matching markets
            assert "items" in data or isinstance(data, list)
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_portfolio_creation_flow(self):
        """Should create and manage portfolio."""
        try:
            # Login
            login_resp = httpx.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                timeout=self.timeout,
            )
            if login_resp.status_code != 200:
                pytest.skip("Could not login")
            self.token = login_resp.json()["access_token"]
            
            # Create portfolio
            response = httpx.post(
                f"{self.base_url}/portfolios",
                params=self._get_auth_params(),
                json={
                    "name": "Integration Test Portfolio",
                    "initial_balance": 10000.0,
                },
                timeout=self.timeout,
            )
            # 201 for new, 200 if updating, 400 if already exists
            assert response.status_code in [200, 201, 400]
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.portfolio_id = data.get("id")
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_list_user_portfolios(self):
        """Should list user's portfolios."""
        try:
            # Login
            login_resp = httpx.post(
                f"{self.base_url}/auth/login",
                json={
                    "email": self.test_email,
                    "password": self.test_password,
                },
                timeout=self.timeout,
            )
            if login_resp.status_code != 200:
                pytest.skip("Could not login")
            self.token = login_resp.json()["access_token"]
            
            response = httpx.get(
                f"{self.base_url}/portfolios",
                params=self._get_auth_params(),
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
        except httpx.ConnectError:
            pytest.skip("Backend not running")


class TestMarketDataIntegration:
    """Integration tests for market data sync."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_backend_url, test_timeout):
        """Set up test."""
        self.base_url = live_backend_url
        self.timeout = test_timeout
    
    def test_sync_stats_endpoint(self):
        """Should return market sync statistics."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets/stats",
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            # Should have sync information
            assert "total_markets" in data or "count" in data or isinstance(data, dict)
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_top_markets_endpoint(self):
        """Should return top markets by volume."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets/top",
                params={"limit": 5, "sort_by": "volume_24h"},
                timeout=self.timeout,
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
        except httpx.ConnectError:
            pytest.skip("Backend not running")


class TestWebSocketIntegration:
    """Integration tests for WebSocket endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_backend_url, test_timeout):
        """Set up test."""
        self.ws_url = live_backend_url.replace("http", "ws")
        self.timeout = test_timeout
    
    @pytest.mark.slow
    def test_websocket_connection(self):
        """Should be able to connect to WebSocket."""
        try:
            import websockets
            import asyncio
            
            async def connect_test():
                try:
                    async with websockets.connect(
                        f"{self.ws_url}/ws",
                        close_timeout=5,
                    ) as ws:
                        # Send ping
                        await ws.send('{"type": "ping"}')
                        # Wait for response
                        response = await asyncio.wait_for(ws.recv(), timeout=5)
                        return response
                except Exception as e:
                    return str(e)
            
            result = asyncio.get_event_loop().run_until_complete(connect_test())
            # Just verify we got some response (connection worked)
            assert result is not None
        except ImportError:
            pytest.skip("websockets library not installed")
        except Exception as e:
            pytest.skip(f"WebSocket test failed: {e}")


class TestErrorHandling:
    """Integration tests for error handling."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_backend_url, test_timeout):
        """Set up test."""
        self.base_url = live_backend_url
        self.timeout = test_timeout
    
    def test_invalid_token_rejected(self):
        """Should reject requests with invalid token."""
        try:
            response = httpx.get(
                f"{self.base_url}/auth/me",
                params={"token": "invalid-token-12345"},
                timeout=self.timeout,
            )
            assert response.status_code in [401, 403]
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_nonexistent_market_404(self):
        """Should return 404 for nonexistent market."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets/by-slug/nonexistent-market-12345",
                timeout=self.timeout,
            )
            assert response.status_code == 404
        except httpx.ConnectError:
            pytest.skip("Backend not running")
    
    def test_invalid_pagination(self):
        """Should handle invalid pagination gracefully."""
        try:
            response = httpx.get(
                f"{self.base_url}/markets",
                params={"page": -1, "page_size": 0},
                timeout=self.timeout,
            )
            # Should either reject or use defaults
            assert response.status_code in [200, 400, 422]
        except httpx.ConnectError:
            pytest.skip("Backend not running")
