"""
Global test fixtures for PaperTradingPM.

This module provides shared fixtures for all tests including:
- Mock MongoDB (mongomock)
- Mock Redis (fakeredis)
- Test user factories
- Fixture loading utilities with fresh timestamps
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# =============================================================================
# Fixture Loading Utilities
# =============================================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str, subdir: str = "polymarket_responses") -> dict:
    """
    Load a JSON fixture file.
    
    Args:
        filename: Name of the JSON file
        subdir: Subdirectory under fixtures/
        
    Returns:
        Parsed JSON data
    """
    filepath = FIXTURES_DIR / subdir / filename
    with open(filepath) as f:
        return json.load(f)


def load_fixture_with_fresh_timestamps(
    filename: str,
    subdir: str = "polymarket_responses",
    timestamp_fields: list[str] | None = None
) -> dict:
    """
    Load a JSON fixture and replace timestamp fields with current time.
    
    This prevents cache staleness issues in tests that validate timestamps.
    
    Args:
        filename: Name of the JSON file
        subdir: Subdirectory under fixtures/
        timestamp_fields: List of fields to refresh (defaults to common timestamp fields)
        
    Returns:
        Parsed JSON with fresh timestamps
    """
    if timestamp_fields is None:
        timestamp_fields = [
            "cached_at",
            "last_synced_at",
            "fetched_at",
            "first_synced_at",
            "created_at",
            "updated_at"
        ]
    
    data = load_fixture(filename, subdir)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    for field in timestamp_fields:
        if field in data:
            data[field] = now
    
    return data


# =============================================================================
# MongoDB Fixtures (mongomock)
# =============================================================================

@pytest.fixture
def mock_mongo_client():
    """
    Create a mock MongoDB client using mongomock.
    
    This provides an in-memory MongoDB that behaves like the real thing
    for testing purposes.
    """
    try:
        import mongomock
        client = mongomock.MongoClient()
        yield client
        client.close()
    except ImportError:
        pytest.skip("mongomock not installed")


@pytest_asyncio.fixture
async def mock_async_mongo_client():
    """
    Create an async mock MongoDB client using mongomock-motor.
    """
    try:
        from mongomock_motor import AsyncMongoMockClient
        client = AsyncMongoMockClient()
        yield client
        client.close()
    except ImportError:
        pytest.skip("mongomock-motor not installed")


@pytest_asyncio.fixture
async def mock_auth_db(mock_async_mongo_client):
    """Provide mock auth_db database."""
    db = mock_async_mongo_client["auth_db"]
    # Create indexes like the real app
    await db.users.create_index("email", unique=True)
    yield db


@pytest_asyncio.fixture
async def mock_trading_db(mock_async_mongo_client):
    """Provide mock trading_db database."""
    db = mock_async_mongo_client["trading_db"]
    await db.portfolios.create_index("user_id")
    await db.trades.create_index([("portfolio_id", 1), ("trade_timestamp", -1)])
    yield db


@pytest_asyncio.fixture
async def mock_markets_db(mock_async_mongo_client):
    """Provide mock markets_db database."""
    db = mock_async_mongo_client["markets_db"]
    await db.markets.create_index("slug", unique=True)
    await db.markets.create_index("condition_id", unique=True)
    await db.markets.create_index("active")
    await db.markets.create_index("closed")
    yield db


# =============================================================================
# Redis Fixtures (fakeredis)
# =============================================================================

@pytest.fixture
def mock_redis():
    """
    Create a mock Redis client using fakeredis.
    """
    try:
        import fakeredis
        redis_client = fakeredis.FakeRedis(decode_responses=True)
        yield redis_client
        redis_client.flushall()
        redis_client.close()
    except ImportError:
        pytest.skip("fakeredis not installed")


@pytest_asyncio.fixture
async def mock_async_redis():
    """
    Create an async mock Redis client using fakeredis.
    """
    try:
        import fakeredis.aioredis
        redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield redis_client
        await redis_client.flushall()
        await redis_client.close()
    except ImportError:
        pytest.skip("fakeredis with aioredis not installed")


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def test_user_data() -> dict:
    """Basic test user data for registration."""
    return {
        "email": "testuser@example.com",
        "password": "SecurePassword123!"
    }


@pytest.fixture
def test_user_credentials() -> dict:
    """OAuth2 form credentials for login."""
    return {
        "username": "testuser@example.com",
        "password": "SecurePassword123!"
    }


@pytest.fixture
def test_admin_data() -> dict:
    """Admin user data."""
    return {
        "email": "admin@example.com",
        "password": "AdminPassword123!",
        "roles": ["admin"]
    }


@pytest.fixture
def mock_user() -> dict:
    """A complete mock user document as stored in MongoDB."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "id": "507f1f77bcf86cd799439011",
        "email": "testuser@example.com",
        "hashed_password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qOZ3q7K9V6X6Hy",
        "roles": ["user"],
        "status": "active",
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def mock_jwt_token() -> str:
    """A mock JWT token for testing protected routes."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MDdmMWY3N2JjZjg2Y2Q3OTk0MzkwMTEiLCJyb2xlcyI6WyJ1c2VyIl0sImV4cCI6OTk5OTk5OTk5OX0.mock_signature"


# =============================================================================
# Portfolio Fixtures
# =============================================================================

@pytest.fixture
def mock_portfolio() -> dict:
    """A mock portfolio document."""
    return {
        "_id": "507f1f77bcf86cd799439022",
        "id": "507f1f77bcf86cd799439022",
        "user_id": "507f1f77bcf86cd799439011",
        "name": "Test Portfolio",
        "description": "A test portfolio for unit testing",
        "initial_balance": 10000.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }


@pytest.fixture
def mock_trade() -> dict:
    """A mock trade document."""
    return {
        "_id": "507f1f77bcf86cd799439033",
        "id": "507f1f77bcf86cd799439033",
        "portfolio_id": "507f1f77bcf86cd799439022",
        "market_id": "fed-decision-in-october",
        "outcome": "Yes",
        "side": "BUY",
        "quantity": 100.0,
        "price": 0.65,
        "trade_timestamp": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Test trade"
    }


# =============================================================================
# Market Fixtures
# =============================================================================

@pytest.fixture
def market_fixture_fed_october() -> dict:
    """
    Load fed-decision-in-october fixture with fresh timestamps.
    
    This is a CLOSED market - useful for testing resolved market behavior.
    """
    return load_fixture_with_fresh_timestamps("market_fed_decision_october.json")


@pytest.fixture
def market_fixture_fed_june() -> dict:
    """
    Load fed-decision-in-june fixture with fresh timestamps.
    
    This is a CLOSED market - useful for testing resolved market behavior.
    """
    return load_fixture_with_fresh_timestamps("market_fed_decision_june.json")


@pytest.fixture
def price_history_fixture_fed_october() -> dict:
    """Load price history for fed-october with fresh timestamps."""
    return load_fixture_with_fresh_timestamps("price_history_fed_october.json")


@pytest.fixture
def active_markets_fixture() -> list[dict]:
    """Load sample active markets fixture."""
    data = load_fixture("active_markets_sample.json")
    # Refresh timestamps for each market
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for market in data.get("markets", []):
        if "last_synced_at" in market:
            market["last_synced_at"] = now
    return data


# =============================================================================
# FastAPI Test Client Fixtures
# =============================================================================

@pytest.fixture
def app():
    """
    Create FastAPI app for testing.
    
    Note: This imports the actual app and should be used with mocked
    database connections.
    """
    from app.main import app
    return app


@pytest.fixture
def client(app) -> Generator:
    """
    Create a TestClient for the FastAPI app.
    
    Use this for synchronous endpoint testing.
    """
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def async_client(app):
    """
    Create an async test client.
    
    Use this for testing async endpoints.
    """
    from httpx import AsyncClient, ASGITransport
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


# =============================================================================
# Authenticated Client Fixtures
# =============================================================================

@pytest.fixture
def authenticated_client(client, mock_jwt_token) -> TestClient:
    """
    A test client with authentication token pre-configured.
    
    Note: Requires mocking the token validation in individual tests.
    """
    # Store token for use in requests
    client.token = mock_jwt_token
    return client


def make_authenticated_request(client: TestClient, method: str, url: str, token: str, **kwargs):
    """
    Helper to make authenticated requests with token as query param.
    
    Args:
        client: TestClient instance
        method: HTTP method (get, post, put, delete)
        url: Endpoint URL
        token: JWT token
        **kwargs: Additional arguments for the request
        
    Returns:
        Response object
    """
    # Add token to query params
    separator = "&" if "?" in url else "?"
    authenticated_url = f"{url}{separator}token={token}"
    
    request_method = getattr(client, method.lower())
    return request_method(authenticated_url, **kwargs)


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def freeze_time():
    """
    Fixture to freeze time for deterministic timestamp testing.
    
    Usage:
        def test_something(freeze_time):
            with freeze_time("2024-10-15T12:00:00Z"):
                # datetime.now() returns frozen time
                ...
    """
    from unittest.mock import patch
    from datetime import datetime
    
    class TimeFreezer:
        def __call__(self, iso_string: str):
            frozen = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return patch("datetime.datetime", wraps=datetime, **{
                "now.return_value": frozen,
                "utcnow.return_value": frozen.replace(tzinfo=None)
            })
    
    return TimeFreezer()


@pytest.fixture
def assert_datetime_recent():
    """
    Fixture providing a helper to assert a datetime is recent.
    
    Usage:
        def test_something(assert_datetime_recent):
            assert_datetime_recent(response["created_at"], max_age_seconds=60)
    """
    def _assert_recent(datetime_str: str, max_age_seconds: int = 60):
        if datetime_str.endswith("Z"):
            datetime_str = datetime_str.replace("Z", "+00:00")
        
        dt = datetime.fromisoformat(datetime_str)
        now = datetime.now(timezone.utc)
        age = (now - dt).total_seconds()
        
        assert age < max_age_seconds, f"Datetime {datetime_str} is {age}s old, expected < {max_age_seconds}s"
        assert age >= 0, f"Datetime {datetime_str} is in the future"
    
    return _assert_recent
