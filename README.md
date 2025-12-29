# PaperTradingPM

A Polymarket paper trading platform. Browse real prediction markets, execute simulated trades, track portfolio performance.

---

## Part 1: Running the Application

### Prerequisites

- Docker and Docker Compose (v2+)
- MongoDB Compass (optional, for database inspection)

### Quick Start

**1. Clone and configure**

```bash
git clone <repository-url>
cd PaperTradingPM
```

Create a `.env` file (see `.env.example`):

```
MONGO_URI=mongodb://mongodb:27017
REDIS_HOST=redis
REDIS_PORT=6379
API_KEY=your_polymarket_clob_api_key
CLOB_URL=https://clob.polymarket.com
JWT_SECRET_KEY=CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET
```

**2. Build and start**

```bash
docker compose build
docker compose up
```

**3. Verify**

| Service | URL |
|---------|-----|
| Health check | http://localhost:8000/health |
| API documentation (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:8501 |
| MongoDB | mongodb://localhost:27017 |

After startup, MongoDB should contain four databases: `auth_db`, `trading_db`, `markets_db`, `system_db`.

### Server Deployment Note

The application is designed for local Docker deployment. For server deployment, you need to modify the CORS whitelist in [backend/app/main.py](backend/app/main.py) (around line 84) to include your server's origin:

```python
allow_origins=[
    "http://localhost:8501",
    "http://your-server-ip:8501",  # Add your server
]
```

The frontend automatically uses the `API_URL` environment variable (defaults to `http://localhost:8000`), which is already set correctly in `docker-compose.yml` for inter-container communication.

### MongoDB Data Import/Export

The market sync worker fetches all Polymarket markets on first run, which takes several hours. To skip this, import pre-populated data.

**Export:**
```bash
docker exec mongodb mongodump --out=/dump
docker cp mongodb:/dump ./mongo_backup
```

**Import:**
```bash
docker cp ./mongo_backup mongodb:/dump
docker exec mongodb mongorestore /dump
```

### Running Tests

```bash
pip install -r backend/requirements.txt

# Unit tests (no external dependencies)
pytest tests/ -m "not integration"

# Integration tests (requires running services + network)
pytest tests/ -m integration

# With coverage
pytest tests/ --cov=backend/app --cov-report=html
```

---

## Part 2: Architecture and Implementation

### System Overview

```
Polymarket APIs --> Workers --> MongoDB --> FastAPI Backend --> Frontend
                                                 |
                                               Redis (live data)
```

| Service | Port | Role |
|---------|------|------|
| Frontend (Streamlit) | 8501 | Debug/test UI (not production) |
| Backend (FastAPI) | 8000 | REST API + WebSocket |
| MongoDB | 27017 | Persistent storage |
| Redis | 6379 | Live data cache and pub/sub |
| polymarket-sync | - | Market metadata sync worker |
| live-data-worker | - | Orderbook streaming worker |

### Project Structure

```
PaperTradingPM/
├── backend/app/
│   ├── main.py              # App entry, router mounting
│   ├── config.py            # Pydantic settings
│   ├── core/                # Security (JWT), rate limiting
│   ├── database/            # MongoDB connections, multi-DB setup
│   ├── models/              # Pydantic models for MongoDB documents
│   ├── schemas/             # Request/response schemas
│   ├── services/            # Business logic layer
│   ├── routers/             # API endpoints
│   └── dependencies/        # FastAPI dependency injection
├── frontend/                # Streamlit debug UI
├── workers/
│   ├── polymarket_sync/     # Market metadata sync
│   └── live_data_worker/    # Orderbook streaming to Redis
├── tests/
└── docker-compose.yml
```

### Database Architecture

Four separate MongoDB databases:

| Database | Collections | Purpose |
|----------|-------------|---------|
| `auth_db` | users | Authentication |
| `trading_db` | portfolios, trades, positions | Trading data |
| `markets_db` | markets, price_history, open_interest, sync_state | Polymarket cache |
| `system_db` | rate_limits, settings | System configuration |

### Polymarket API Integration

Three public APIs (no authentication required):

| API | Base URL | Data |
|-----|----------|------|
| Gamma | gamma-api.polymarket.com | Market metadata |
| CLOB | clob.polymarket.com | Price history, orderbooks |
| Data | data-api.polymarket.com | Open interest, positions |

Implementation: [backend/app/services/polymarket_api.py](backend/app/services/polymarket_api.py)

### Market Data Strategy

**Lazy loading**: Markets are fetched from Polymarket on-demand if not in MongoDB, then cached. The sync worker keeps the cache fresh in the background.

**Sync worker** (`workers/polymarket_sync/sync_markets.py`):
- Batch size: 500 markets per API request
- Incremental saves: each batch saved immediately (full sync takes hours)
- Resumable: tracks progress in `sync_state` collection
- Two modes: full sync (every 24h), incremental sync (every 5min, active markets only)

**Live data worker** (`workers/live_data_worker/redis_websocket_sync.py`):
- Connects to Polymarket CLOB WebSocket
- Streams orderbook updates to Redis
- Supports pause/resume via Redis flag

### Authentication

- JWT tokens via python-jose, passwords hashed with bcrypt
- Token expiry: 30 minutes (configurable)
- Token delivery: query parameter (`?token=xxx`) for Streamlit compatibility
- User roles: `user`, `premium_user`, `admin`

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System status |
| `/auth/register` | POST | Create user |
| `/auth/token` | POST | Login (OAuth2 form) |
| `/auth/me` | GET | Current user |
| `/markets` | GET | List with filters |
| `/markets/by-slug/{slug}` | GET | Single market (lazy-loads if needed) |
| `/markets/by-slug/{slug}/prices` | GET | Price history |
| `/portfolios` | GET/POST | List/create |
| `/portfolios/{id}/trades` | GET/POST | Trade history/execution |
| `/market-stream/subscribe` | POST | Subscribe to market updates |
| `/ws/live` | WebSocket | Real-time data |

Authentication for protected endpoints:
```
GET /portfolios?token=your_jwt_token
```

### Known Implementation Notes

- CLOB API returns empty array for markets with no trade history
- Rate limiting placeholders exist in `core/rate_limit.py` ; they are not yet implemented, but should be before deploying to production.
- WebSocket push logic in `routers/ws.py` is a placeholder ; streamlit doesn't support well the async. 

---

## License

MIT License