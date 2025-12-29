"""
Backend-specific test fixtures and configuration.

These fixtures extend the global fixtures with backend-specific helpers
for testing FastAPI routes, services, and database operations.
"""

import sys
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


# =============================================================================
# Database Override Fixtures
# =============================================================================

@pytest.fixture
def mock_get_mongo_client(mock_async_mongo_client):
    """
    Override the get_mongo_client dependency with mock client.
    
    Usage in tests:
        def test_something(mock_get_mongo_client, client):
            with patch("app.database.connections.get_mongo_client", mock_get_mongo_client):
                response = client.get("/some-endpoint")
    """
    async def _mock():
        return mock_async_mongo_client
    return _mock


@pytest.fixture
def mock_get_redis_client(mock_async_redis):
    """Override the get_redis_client dependency with mock client."""
    async def _mock():
        return mock_async_redis
    return _mock


# =============================================================================
# Auth Service Fixtures
# =============================================================================

@pytest.fixture
def mock_auth_service():
    """
    Create a fully mocked AuthService.
    
    All methods are AsyncMock, allowing you to configure return values:
    
        mock_auth_service.register_user.return_value = {...}
    """
    service = MagicMock()
    service.register_user = AsyncMock()
    service.login = AsyncMock()
    service.refresh_token = AsyncMock()
    service.change_password = AsyncMock()
    service.get_user_by_id = AsyncMock()
    service.get_user_by_email = AsyncMock()
    return service


@pytest.fixture
def mock_current_user(mock_user):
    """
    Override get_current_active_user dependency.
    
    Returns the mock_user fixture as the authenticated user.
    """
    from app.models.user import User, UserRole, UserStatus
    
    return User(
        id=mock_user["id"],
        email=mock_user["email"],
        hashed_password=mock_user["hashed_password"],
        roles=[UserRole.USER],
        status=UserStatus.ACTIVE,
        created_at=mock_user["created_at"],
    )


# =============================================================================
# Market Service Fixtures
# =============================================================================

@pytest.fixture
def mock_market_service():
    """Create a fully mocked MarketService."""
    service = MagicMock()
    service.list_markets = AsyncMock()
    service.get_top_markets = AsyncMock()
    service.get_market_by_slug = AsyncMock()
    service.get_price_history = AsyncMock()
    service.get_open_interest = AsyncMock()
    service.get_sync_stats = AsyncMock()
    return service


@pytest.fixture
def mock_polymarket_api():
    """Create a fully mocked PolymarketAPI client."""
    api = MagicMock()
    api.get_markets = AsyncMock()
    api.get_market_by_slug = AsyncMock()
    api.get_prices = AsyncMock()
    api.get_price_history = AsyncMock()
    api.get_open_interest = AsyncMock()
    return api


# =============================================================================
# Portfolio Service Fixtures  
# =============================================================================

@pytest.fixture
def mock_portfolio_service():
    """Create a fully mocked PortfolioService."""
    service = MagicMock()
    service.list_portfolios = AsyncMock()
    service.create_portfolio = AsyncMock()
    service.get_portfolio_with_positions = AsyncMock()
    service.update_portfolio = AsyncMock()
    service.delete_portfolio = AsyncMock()
    service.create_trade = AsyncMock()
    service.get_trades = AsyncMock()
    service.get_positions = AsyncMock()
    return service


# =============================================================================
# App Override Helpers
# =============================================================================

@pytest.fixture
def app_with_mocks(mock_async_mongo_client, mock_async_redis):
    """
    Create the FastAPI app with database connections mocked.
    
    This fixture patches the database connection functions before
    importing the app, ensuring all routes use mock databases.
    """
    with patch("app.database.connections.get_mongo_client") as mock_mongo, \
         patch("app.database.connections.get_redis_client") as mock_redis:
        
        async def get_mongo():
            return mock_async_mongo_client
        
        async def get_redis():
            return mock_async_redis
        
        mock_mongo.side_effect = get_mongo
        mock_redis.side_effect = get_redis
        
        from app.main import app
        yield app


@pytest.fixture
def client_with_mocks(app_with_mocks):
    """TestClient using the mocked app."""
    from fastapi.testclient import TestClient
    
    with TestClient(app_with_mocks) as c:
        yield c


# =============================================================================
# Token Validation Helpers
# =============================================================================

@pytest.fixture
def bypass_auth(mock_current_user):
    """
    Fixture to bypass authentication in tests.
    
    Usage:
        def test_protected_route(client, bypass_auth):
            with bypass_auth:
                response = client.get("/protected?token=any")
    """
    from app.dependencies.auth import get_current_active_user
    
    class AuthBypass:
        def __enter__(self):
            self.patcher = patch(
                "app.dependencies.auth.get_current_active_user",
                return_value=mock_current_user
            )
            self.patcher.start()
            return self
        
        def __exit__(self, *args):
            self.patcher.stop()
    
    return AuthBypass()


@pytest.fixture
def valid_token_header(mock_jwt_token):
    """Return dict with token as query param for requests."""
    return {"token": mock_jwt_token}


# =============================================================================
# Response Assertion Helpers
# =============================================================================

@pytest.fixture
def assert_error_response():
    """Helper to assert error response structure."""
    def _assert(response, status_code: int, detail_contains: str = None):
        assert response.status_code == status_code
        data = response.json()
        assert "detail" in data
        if detail_contains:
            assert detail_contains.lower() in data["detail"].lower()
    return _assert


@pytest.fixture
def assert_pagination_response():
    """Helper to assert paginated response structure."""
    def _assert(response, expected_keys: list[str] = None):
        assert response.status_code == 200
        data = response.json()
        
        # Check pagination fields
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        
        # Check items/markets/etc exists
        if expected_keys:
            for key in expected_keys:
                assert key in data
    return _assert
