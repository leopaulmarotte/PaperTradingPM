"""
Request and response schemas for API endpoints.
"""
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    TokenPayload,
)
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioWithPositions,
    Position,
)
from app.schemas.trade import TradeCreate, TradeResponse, TradeHistory
from app.schemas.market import MarketResponse, PriceHistoryResponse

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
    "TokenPayload",
    # User
    "UserResponse",
    "UserUpdate",
    # Portfolio
    "PortfolioCreate",
    "PortfolioUpdate",
    "PortfolioResponse",
    "PortfolioWithPositions",
    "Position",
    # Trade
    "TradeCreate",
    "TradeResponse",
    "TradeHistory",
    # Market
    "MarketResponse",
    "PriceHistoryResponse",
]
