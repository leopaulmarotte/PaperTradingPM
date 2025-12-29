"""
Frontend test fixtures and mocks.

Mocks Streamlit session_state and API client for isolated testing.
"""
import pytest
from unittest.mock import MagicMock, patch


class MockSessionState(dict):
    """Mock st.session_state that behaves like both dict and attribute access."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default state
        self.update({
            "is_authenticated": False,
            "user_id": None,
            "token": None,
            "selected_market": None,
            "trades_df": None,
            "nav_page": "Trading",
            "nav_override": None,
            "trading_view": "list",
            "trading_page": 1,
        })
    
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'SessionState' has no attribute '{name}'")
    
    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def mock_session_state():
    """Provide a mock session state for testing."""
    return MockSessionState()


@pytest.fixture
def authenticated_session_state():
    """Provide an authenticated mock session state."""
    state = MockSessionState()
    state.update({
        "is_authenticated": True,
        "user_id": "user-123",
        "token": "test-jwt-token",
    })
    return state


@pytest.fixture
def mock_streamlit(mock_session_state):
    """Patch streamlit module with mocks."""
    with patch.dict("sys.modules", {"streamlit": MagicMock()}):
        import sys
        st_mock = sys.modules["streamlit"]
        st_mock.session_state = mock_session_state
        yield st_mock


@pytest.fixture
def mock_api_responses():
    """Common API response fixtures."""
    return {
        "health_ok": {"status": 200, "data": {"status": "ok"}},
        "login_success": {
            "status": 200,
            "data": {
                "access_token": "jwt-token-abc123",
                "token_type": "bearer",
                "user_id": "user-123",
            },
        },
        "login_invalid": {
            "status": 401,
            "data": {"detail": "Invalid credentials"},
        },
        "user_profile": {
            "status": 200,
            "data": {
                "id": "user-123",
                "email": "test@example.com",
                "created_at": "2025-01-01T00:00:00Z",
            },
        },
        "markets_list": {
            "status": 200,
            "data": {
                "items": [
                    {
                        "slug": "fed-decision-october",
                        "question": "Will the Fed cut rates in October?",
                        "active": False,
                        "closed": True,
                    },
                    {
                        "slug": "fed-decision-june",
                        "question": "Will the Fed raise rates in June?",
                        "active": False,
                        "closed": True,
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 20,
            },
        },
        "market_detail": {
            "status": 200,
            "data": {
                "slug": "fed-decision-october",
                "question": "Will the Fed cut rates in October?",
                "description": "Market for Fed decision",
                "active": False,
                "closed": True,
                "outcomes": ["Yes", "No"],
            },
        },
        "connection_error": {"status": 0, "error": "Cannot connect to backend"},
    }


@pytest.fixture
def sample_market():
    """Sample market data for testing."""
    return {
        "slug": "fed-decision-october",
        "question": "Will the Fed cut rates in October?",
        "name": "Fed October Decision",
        "title": "Federal Reserve Rate Decision",
        "description": "Market about Fed rate decision",
        "active": False,
        "closed": True,
        "outcomes": ["Yes", "No"],
        "end_date_iso": "2024-10-31T23:59:59Z",
    }


@pytest.fixture
def sample_portfolio():
    """Sample portfolio data for testing."""
    return {
        "id": "portfolio-123",
        "user_id": "user-123",
        "name": "Main Portfolio",
        "balance": 10000.0,
        "positions": [
            {
                "market_id": "fed-decision-october",
                "outcome": "Yes",
                "quantity": 100,
                "avg_price": 0.55,
            }
        ],
        "created_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_trades():
    """Sample trades list for testing."""
    return [
        {
            "id": "trade-1",
            "market_id": "fed-decision-october",
            "side": "buy",
            "outcome": "Yes",
            "quantity": 50,
            "price": 0.50,
            "timestamp": "2025-01-15T10:00:00Z",
        },
        {
            "id": "trade-2",
            "market_id": "fed-decision-october",
            "side": "buy",
            "outcome": "Yes",
            "quantity": 50,
            "price": 0.60,
            "timestamp": "2025-01-16T14:30:00Z",
        },
    ]
