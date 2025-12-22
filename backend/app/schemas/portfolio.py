"""
Portfolio request/response schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    """Create portfolio request."""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    initial_balance: float = Field(
        default=10000.0,
        gt=0,
        description="Starting paper money balance"
    )


class PortfolioUpdate(BaseModel):
    """Update portfolio request."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    is_active: Optional[bool] = Field(None, description="Portfolio active status")


class PortfolioResponse(BaseModel):
    """Portfolio response."""
    id: str = Field(..., description="Portfolio ID")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Portfolio name")
    description: Optional[str] = Field(None, description="Portfolio description")
    initial_balance: float = Field(..., description="Starting balance")
    created_at: datetime = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Active status")


class Position(BaseModel):
    """Current position in a market."""
    market_id: str = Field(..., description="Market identifier")
    outcome: str = Field(..., description="Outcome held")
    quantity: float = Field(..., description="Net quantity held")
    average_price: float = Field(..., description="Average entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    unrealized_pnl: Optional[float] = Field(None, description="Unrealized P&L")
    market_question: Optional[str] = Field(None, description="Market question for display")


class PortfolioWithPositions(PortfolioResponse):
    """Portfolio response with calculated positions and metrics."""
    positions: list[Position] = Field(default=[], description="Current positions")
    total_value: float = Field(..., description="Total portfolio value")
    cash_balance: float = Field(..., description="Available cash")
    total_pnl: float = Field(..., description="Total realized + unrealized P&L")
    total_pnl_percent: float = Field(..., description="Total P&L as percentage")


class PortfolioMetrics(BaseModel):
    """Calculated portfolio metrics."""
    portfolio_id: str
    as_of: datetime
    total_value: float
    cash_balance: float
    total_pnl: float
    total_pnl_percent: float
    
    # Advanced metrics (placeholders for future implementation)
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown")
    win_rate: Optional[float] = Field(None, description="Winning trade percentage")
    avg_trade_size: Optional[float] = Field(None, description="Average trade size")
