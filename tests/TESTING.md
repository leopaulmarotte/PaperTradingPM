# Testing Guide

This document describes the test structure, fixtures, and rationale for the PaperTradingPM test suite.

## Running Tests

Tests run in a dedicated Docker service with access to all project code.

```bash
# Run all unit tests
docker compose run --rm test /tests -m "not integration" -v

# Run specific test file
docker compose run --rm test /tests/backend/test_services.py -v

# Run tests matching a pattern
docker compose run --rm test /tests -k "test_password" -v

# Integration tests (requires services running)
docker compose up -d mongodb redis backend
docker compose run --rm test /tests -m integration -v

# With coverage report
docker compose run --rm test /tests --cov=app --cov-report=term-missing

# HTML coverage report
docker compose run --rm test /tests --cov=app --cov-report=html
```

## Test Structure

```
tests/
├── pytest.ini                    # Config: asyncio_mode=auto, markers
├── conftest.py                   # Global fixtures (fresh timestamps, mock DB/Redis)
├── fixtures/
│   ├── polymarket_responses/     # Real API response samples
│   │   ├── market_fed_decision_october.json
│   │   ├── market_fed_decision_june.json
│   │   ├── price_history_fed_october.json
│   │   ├── active_markets_sample.json
│   │   └── README.md
│   └── test_data/
│       ├── users.json            # Sample user documents
│       └── portfolios.json       # Sample portfolio documents
├── backend/
│   ├── conftest.py               # Backend fixtures (mock services, auth bypass)
│   ├── test_health.py            # Health endpoint tests
│   ├── test_websocket.py         # WS connection, subscription, ping/pong
│   ├── test_database.py          # Connection, indexes, registry tests
│   └── test_services.py          # Password hashing, MarketService unit tests
├── workers/
│   ├── test_polymarket_sync.py   # Batch fetching, transform_market, resume
│   └── test_live_data_worker.py  # Redis streams, pause flag
├── frontend/
│   ├── conftest.py               # Mock session_state, API responses
│   └── test_formatters.py        # Number, currency, date formatting
└── integration/
    ├── conftest.py               # Live API fixtures (URLs, timeouts)
    ├── test_polymarket_api_live.py   # Real Polymarket API tests
    └── test_full_trading_flow.py     # End-to-end backend tests
```

## Test Categories

### Unit Tests (`-m "not integration"`)

Fast, isolated tests that mock external dependencies:

| File | Coverage |
|------|----------|
| `test_health.py` | Health endpoint responses |
| `test_services.py` | Password hashing, `MarketService` methods |
| `test_database.py` | Connection setup, index creation, registry |
| `test_websocket.py` | WebSocket message handling, subscriptions |
| `test_formatters.py` | Number, currency, date formatting utilities |
| `test_polymarket_sync.py` | Batch processing, data transformation |
| `test_live_data_worker.py` | Redis stream operations |

### Integration Tests (`-m integration`)

Tests that require running services:

| File | Requirements |
|------|--------------|
| `test_polymarket_api_live.py` | Internet access (calls real Polymarket APIs) |
| `test_full_trading_flow.py` | `mongodb`, `redis`, `backend` containers |

## Fixtures

### Mock Database (mongomock)

Uses `mongomock` and `mongomock-motor` to simulate MongoDB without a real database:

```python
@pytest.fixture
def mock_mongo_client():
    """Provides an in-memory MongoDB client."""
    client = mongomock.MongoClient()
    yield client
    client.close()
```

### Mock Redis (fakeredis)

Uses `fakeredis` to simulate Redis:

```python
@pytest.fixture
def mock_redis():
    """Provides an in-memory Redis client."""
    return fakeredis.FakeRedis(decode_responses=True)
```

### Fresh Timestamps

Market fixtures use a helper to update timestamps, preventing cache staleness:

```python
def load_fixture_with_fresh_timestamps(fixture_path: str) -> dict:
    """Load fixture and update timestamp fields to current time."""
    with open(fixture_path) as f:
        data = json.load(f)
    
    now = datetime.utcnow()
    if "updated_at" in data:
        data["updated_at"] = now.isoformat()
    # ... update other timestamp fields
    
    return data
```

### Polymarket Response Fixtures

Real API responses captured for deterministic testing:

| Fixture | Source | Notes |
|---------|--------|-------|
| `market_fed_decision_october.json` | Gamma API | Closed/resolved market |
| `market_fed_decision_june.json` | Gamma API | Closed/resolved market |
| `price_history_fed_october.json` | CLOB API | Historical price data |
| `active_markets_sample.json` | Gamma API | Sample of active markets |

**Why closed markets?** Resolved markets have stable data that won't change, making assertions reliable.

## Key Testing Decisions

| Decision | Rationale |
|----------|-----------|
| **mongomock + mongomock-motor** | Isolated MongoDB testing without requiring a running database |
| **fakeredis** | Mock Redis for cache and stream tests without external dependency |
| **Fresh timestamps on fixtures** | Prevents cache staleness issues in tests |
| **Closed markets as fixtures** | Resolved markets don't change, providing stable test data |
| **Unit tests for pure functions** | Test services, formatters, and helpers without FastAPI mocking overhead |
| **Integration tests separated** | Endpoint tests that need real services are marked and run separately |
| **Test service in Docker** | Ensures consistent environment matching production |

## Configuration (pytest.ini)

```ini
[pytest]
asyncio_mode = auto
markers =
    integration: marks tests as integration tests (require running services)
    slow: marks tests as slow (deselect with '-m "not slow"')
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

## Coverage Goals

Current coverage focuses on:

- ✅ Service layer business logic
- ✅ Utility functions (formatters, helpers)
- ✅ Database connection and indexing
- ✅ Basic endpoint responses

### Areas Needing More Coverage

- ⚠️ Edge cases: market state transitions (active → closed)
- ⚠️ Trade execution failures (insufficient balance, closed market)
- ⚠️ Concurrent request handling
- ⚠️ Worker failure and recovery scenarios
- ⚠️ Rate limiting (when implemented)

## Adding New Tests

### Unit Test Template

```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    """Tests for MyFeature functionality."""
    
    def test_happy_path(self):
        """Test normal operation."""
        result = my_function(valid_input)
        assert result == expected_output
    
    def test_edge_case(self):
        """Test boundary condition."""
        result = my_function(edge_input)
        assert result == edge_expected
    
    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError):
            my_function(invalid_input)
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
class TestEndToEndFlow:
    """Integration tests requiring running services."""
    
    @pytest.fixture(autouse=True)
    def setup(self, live_backend_url):
        self.base_url = live_backend_url
    
    async def test_full_flow(self, http_client):
        """Test complete user journey."""
        # Register
        response = await http_client.post(f"{self.base_url}/auth/register", ...)
        assert response.status_code == 201
        
        # Login
        response = await http_client.post(f"{self.base_url}/auth/token", ...)
        token = response.json()["access_token"]
        
        # Use protected endpoint
        response = await http_client.get(
            f"{self.base_url}/portfolios",
            params={"token": token}
        )
        assert response.status_code == 200
```

## Troubleshooting

### Tests hang or timeout

- Check if integration tests are accidentally running without services
- Verify `asyncio_mode = auto` is set in `pytest.ini`

### Import errors

- Ensure you're running tests via Docker: `docker compose run --rm test`
- The test container mounts the project code at `/app` and `/tests`

### Fixture not found

- Check fixture scope (function, class, module, session)
- Verify fixture is in the correct `conftest.py` (tests/ for global, tests/backend/ for backend-specific)

### Mock not working

- Patch at the location where the object is used, not where it's defined
- Example: `@patch('app.services.market_service.PolymarketAPI')` not `@patch('app.services.polymarket_api.PolymarketAPI')`
