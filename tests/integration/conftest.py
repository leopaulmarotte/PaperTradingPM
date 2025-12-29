"""
Integration test fixtures.

These tests require actual network access and running services.
Mark with @pytest.mark.integration to skip in normal test runs.
"""
import pytest
import os


@pytest.fixture
def live_api_base_url():
    """Get base URL for live Polymarket API tests."""
    return os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")


@pytest.fixture
def live_clob_url():
    """Get base URL for live CLOB API tests."""
    return os.getenv("POLYMARKET_CLOB_URL", "https://clob.polymarket.com")


@pytest.fixture
def live_backend_url():
    """Get base URL for live backend tests (if running)."""
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture
def known_closed_market_slug():
    """Return a known closed market slug for stable testing."""
    return "will-the-federal-reserve-cut-the-benchmark-interest-rate-before-november-1-2024"


@pytest.fixture
def known_condition_id():
    """Return a known condition ID for testing."""
    # Fed October decision market condition ID
    return "0xa8e5a4d7b4b68b0b56c7c4e4c3e4a3f2d1c0b9a8"


@pytest.fixture
def test_timeout():
    """Timeout for network requests in integration tests."""
    return 30


@pytest.fixture
def skip_if_no_network():
    """Skip test if no network access."""
    import socket
    try:
        socket.create_connection(("gamma-api.polymarket.com", 443), timeout=5)
    except (socket.timeout, socket.error):
        pytest.skip("No network access to Polymarket API")
