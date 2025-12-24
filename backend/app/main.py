"""
PaperTradingPM Backend - FastAPI Application

A paper trading platform for Polymarket with real-time data streaming and portfolio tracking.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.connections import get_mongo_client, close_connections
from app.database.registry import sync_registry, create_indexes
from app.routers import auth, health, markets, portfolios, ws, market_stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Startup:
    - Initialize database connections
    - Sync database registry
    - Create indexes
    
    Shutdown:
    - Close all database connections
    """

    print("Starting up PaperTradingPM Backend...")
    
    try:
        # Initialize MongoDB and sync registry
        client = await get_mongo_client()
        await sync_registry(client)
        await create_indexes(client)
        print("✓ Database registry synced and indexes created")
    except Exception as e:
        print(f"⚠ Database initialization warning: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down PaperTradingPM Backend...")
    await close_connections()
    print("✓ Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="PaperTradingPM API",
    description="""
## Polymarket Paper Trading Platform API

A paper trading application for Polymarket prediction markets.

### Features
- **Authentication**: JWT-based auth with role-based access control
- **Portfolios**: Create and manage paper trading portfolios
- **Trades**: Execute paper trades with backtesting support
- **Markets**: Browse and search Polymarket markets with lazy-loaded caching
- **Live Data**: Real-time orderbook and price updates via WebSocket

### Authentication
All protected endpoints require a JWT token passed as a query parameter:
```
GET /portfolios?token=your_jwt_token
```

Obtain a token via `POST /auth/login`.

### WebSocket
Connect to `/ws/live?token=xxx` for real-time market data.
    """,
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",  # Streamlit default
        "http://streamlit_frontend:8501",  # Docker network
        "http://localhost:3000",  # Development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(markets.router)
app.include_router(portfolios.router)
app.include_router(market_stream.router)
app.include_router(ws.router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "PaperTradingPM API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
