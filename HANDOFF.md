# PaperTradingPM - Project Handoff Document

**Last Updated:** December 23, 2025  
**Purpose:** Complete context for AI assistants continuing development

---

## 🎯 Project Goal

Build a **Polymarket paper trading dashboard/app** that allows users to:
- Browse real Polymarket prediction markets
- Execute simulated (paper) trades
- Track portfolio performance over time
- Access real-time market data

The user wants a **professional-grade application** with proper architecture, not a quick prototype.

---

## 👥 Team Structure & Responsibilities

| Person | Responsibility |
|--------|----------------|
| **User (kmlst)** | Backend architecture, FastAPI, MongoDB, Workers |
| **Teammate** | Frontend (Streamlit) - production version |
| **Teammate** | Redis integration, live orderbook streaming |

**Important:** The frontend in `/frontend/` is **only for debugging/testing the backend**. A teammate will build the production frontend separately. Don't over-invest in frontend polish.

---

## 🏗️ Architecture Overview

### Tech Stack
- **Backend:** FastAPI (Python 3.11)
- **Database:** MongoDB (multi-database architecture)
- **Cache/Live Data:** Redis (for future orderbook streaming)
- **Frontend (debug):** Streamlit
- **Containerization:** Docker Compose

### Data Flow
```
Polymarket APIs ──► Workers ──► MongoDB ──► FastAPI Backend ──► Streamlit/Frontend
                                                  │
                                            Redis (live data)
```

---

## 📁 Repository Structure

```
PaperTradingPM/
├── backend/                    # FastAPI application
│   └── app/
│       ├── main.py            # App entry, lifespan, router mounting
│       ├── config.py          # Pydantic Settings from env
│       ├── core/              # Security (JWT), rate limiting (TODO)
│       ├── database/          # MongoDB connections & multi-DB setup
│       │   ├── connections.py # Motor async client singleton
│       │   ├── registry.py    # DB sync & index creation
│       │   └── databases/     # Per-database configs
│       │       ├── auth_db.py
│       │       ├── trading_db.py
│       │       ├── markets_db.py
│       │       └── system_db.py
│       ├── models/            # Pydantic models for MongoDB docs
│       ├── schemas/           # Request/response schemas
│       ├── services/          # Business logic layer
│       │   ├── auth_service.py
│       │   ├── market_service.py    # Lazy-loading from Polymarket
│       │   ├── polymarket_api.py    # Async httpx client for PM APIs
│       │   └── portfolio_service.py
│       ├── routers/           # FastAPI route handlers
│       │   ├── auth.py        # Login, register, JWT tokens
│       │   ├── markets.py     # Market browsing with filters
│       │   ├── portfolios.py  # Portfolio CRUD
│       │   ├── health.py      # Health checks
│       │   └── ws.py          # WebSocket (placeholder)
│       ├── dependencies/      # FastAPI Depends() functions
│       │   ├── auth.py        # get_current_user
│       │   └── roles.py       # require_role(UserRole.ADMIN)
│       └── polymarket_example.py  # Reference: how to query PM APIs
│
├── frontend/                   # Streamlit DEBUG app (not production)
│   ├── app.py                 # Basic test UI for backend
│   ├── Dockerfile
│   └── requirements.txt
│
├── workers/                    # Background workers (separate containers)
│   ├── polymarket_sync/       # Market metadata sync worker
│   │   ├── sync_markets.py    # Main worker script
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── live_data_worker/      # Placeholder for orderbook streaming
│       └── ...                # (Teammate will implement)
│
├── worker/                     # OLD location - deprecated placeholder
├── scripts/                    # Utility scripts (empty)
├── docker-compose.yml
└── .env
```

---

## 🗄️ Database Architecture

### Multi-Database Design (User's Explicit Choice)

The user wanted **separate MongoDB databases** for different concerns, not collections in a single DB:

| Database | Purpose | Collections |
|----------|---------|-------------|
| `auth_db` | Authentication | `users` |
| `trading_db` | Trading data | `portfolios`, `trades`, `positions` |
| `markets_db` | Polymarket data | `markets`, `price_history`, `open_interest`, `sync_state` |
| `system_db` | System config | `rate_limits`, `settings` |

### Database Registry Pattern
The `database/registry.py` syncs metadata across all DBs on startup and creates indexes.

---

## 🔐 Authentication System

### JWT Token Authentication
- **Library:** python-jose for JWT, passlib[bcrypt] for passwords
- **Token expiry:** 30 minutes (configurable)
- **Token delivery:** Query parameter `?token=xxx` (user's preference for Streamlit compatibility, not headers)

### User Roles (Enum)
```python
class UserRole(str, Enum):
    USER = "user"           # Basic access
    PREMIUM_USER = "premium_user"  # Extended features (future)
    ADMIN = "admin"         # Full access
```

### Rate Limiting
- **Priority:** Login endpoint rate limiting is most important
- **Implementation:** Planned with Redis, currently TODO placeholders
- **Config in settings:** login attempts, lockout duration, global limits

---

## 🔄 Workers Organization

### Worker Philosophy
- Each worker has its **own folder, Dockerfile, and requirements.txt**
- Workers are **separate Docker containers**
- Named descriptively (not just "worker")

### Current Workers

#### 1. `polymarket_sync` (Market Metadata Sync)
**Location:** `workers/polymarket_sync/sync_markets.py`

**Features:**
- **Batch size:** 500 markets per API request
- **Incremental saves:** Each batch saved immediately (important because full sync takes hours)
- **Resumable:** Tracks progress in `sync_state` collection, can resume after interruption
- **Two sync modes:**
  - Full sync: All markets (every 24 hours)
  - Incremental sync: Active markets only (every 5 minutes)

**Why these choices:**
- User emphasized that fetching all markets takes hours
- Must save as it fetches, not wait until complete
- Must handle restarts/crashes gracefully

#### 2. `live_data_worker` (Placeholder)
**Location:** `workers/live_data_worker/`
- Reserved for teammate to implement
- Will stream orderbook data to Redis
- WebSocket router in backend is prepared but placeholder

---

## 📊 Polymarket API Integration

### Three APIs Used (All Public, No Auth)

| API | Base URL | Purpose |
|-----|----------|---------|
| **Gamma** | gamma-api.polymarket.com | Market metadata (question, volume, liquidity, etc.) |
| **CLOB** | clob.polymarket.com | Price history, orderbooks |
| **Data** | data-api.polymarket.com | Open interest, holders, positions |

### Key Data Structures

**Market metadata fields from Gamma API:**
- `slug` - URL-friendly identifier (primary key)
- `conditionId` - On-chain condition ID
- `clobTokenIds` - Token IDs for each outcome (JSON string that needs parsing!)
- `outcomes` - ["Yes", "No"] etc. (JSON string that needs parsing!)
- `outcomePrices` - Current prices (JSON string)
- `volume24hr`, `volumeNum`, `liquidityNum` - Numeric metrics
- `closed`, `active` - Status booleans

**Important:** Many fields come as JSON-encoded strings from the API and need parsing.

### Reference File
`backend/app/polymarket_example.py` - User-provided file showing how to query all PM APIs. Use this as the source of truth for API behavior.

---

## 🌐 Backend API Endpoints

### Auth (`/auth`)
- `POST /auth/register` - Create user
- `POST /auth/token` - Login (OAuth2 form)
- `GET /auth/me` - Current user profile

### Markets (`/markets`)
- `GET /markets` - List with filters (search, volume, liquidity, active/closed, pagination)
- `GET /markets/top` - Top markets by volume
- `GET /markets/stats` - Sync statistics
- `GET /markets/by-slug/{slug}` - Single market (lazy-loads from API if not cached)
- `GET /markets/by-slug/{slug}/prices` - Price history
- `POST /markets/open-interest` - Batch OI lookup
- `POST /markets/admin/refresh` - Manual sync trigger (admin only)

### Portfolios (`/portfolios`)
- `GET /portfolios` - List user's portfolios
- `POST /portfolios` - Create portfolio
- `GET /portfolios/{id}` - Portfolio details

### Health (`/health`)
- `GET /health` - System status, DB connections

### WebSocket (`/ws`)
- `/ws/live` - Placeholder for real-time data

---

## 🎨 Design Decisions & User Preferences

### 1. Dependency Injection
User asked about safety for concurrent users - confirmed that FastAPI's DI creates new service instances per request, so it's safe.

### 2. Lazy Loading Strategy
Markets are fetched from Polymarket API **on-demand** if not in cache, then stored in MongoDB. Worker keeps cache fresh in background.

### 3. No API Prefix
Routes are mounted directly (`/markets`, `/auth`) not under `/api/v1`. Keep it simple.

### 4. Token in Query Params
User prefers `?token=xxx` over Authorization headers for Streamlit compatibility.

### 5. French Comments OK
User writes some comments in French - that's fine, don't "fix" them.

---

## 🚧 TODO / Incomplete Items

| Item | Status | Notes |
|------|--------|-------|
| Rate limiting (Redis) | TODO placeholder | `core/rate_limit.py` has stubs |
| WebSocket live data | Placeholder | Waiting for teammate's Redis worker |
| Trade execution | Basic service exists | Needs order matching logic |
| Portfolio positions | Schema exists | Needs position tracking on trades |
| Premium user features | Not started | Role exists but no differentiation |

---

## 🐳 Docker Setup

```bash
# Start everything
docker compose up --build

# Services:
# - frontend:        http://localhost:8501 (Streamlit debug UI)
# - backend:         http://localhost:8000 (FastAPI + Swagger at /docs)
# - mongodb:         localhost:27017
# - redis:           localhost:6379
# - polymarket-sync: Background worker (no port)
```

### Environment Variables (.env)
```
MONGO_URI=mongodb://mongodb:27017
REDIS_HOST=redis
REDIS_PORT=6379
```

---

## ⚠️ Known Issues / Gotchas

1. **JSON string parsing:** Polymarket returns arrays as JSON strings - must parse with `json.loads()` or `eval()`

2. **Empty price history:** CLOB API returns `[]` for markets with no trade history - this is normal

3. **Volume field names:** API uses `volume24hr`, `volumeNum` - we normalize to `volume_24hr`, `volume_num` in DB

4. **Text search:** MongoDB text index on `question` field for market search

5. **Sync state collection:** `markets_db.sync_state` tracks worker progress for resumability

---

## 💬 User Communication Style

- Prefers concise, technical responses
- Appreciates architecture discussions
- Values clean separation of concerns
- Wants professional-grade code, not prototypes
- OK with TODO placeholders for teammate work
- Uses French occasionally

---

## 📝 Files to Reference

When continuing development, these are the key files to understand:

1. `backend/app/main.py` - App structure, router mounting
2. `backend/app/services/market_service.py` - Lazy loading logic
3. `backend/app/services/polymarket_api.py` - API client
4. `workers/polymarket_sync/sync_markets.py` - Worker implementation
5. `backend/app/polymarket_example.py` - API reference (user provided)
6. `backend/app/database/databases/markets_db.py` - Collection structure

---

*This document captures the full context from the development conversation. Use it to continue development without losing architectural decisions or user preferences.*
