"""
Trade request/response schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.trade import TradeSide


class TradeCreate(BaseModel):
    """Create trade request."""
    market_id: str = Field(..., description="Polymarket market identifier")
    outcome: str = Field(..., description="Outcome to trade (e.g., 'Yes', 'No')")
    side: TradeSide = Field(..., description="Buy or sell")
    quantity: float = Field(..., gt=0, description="Number of shares")
    price: float = Field(..., ge=0, le=1, description="Price per share (0-1)")
    trade_timestamp: Optional[datetime] = Field(
        None,
        description="Trade timestamp (defaults to now, can be backdated for backtesting)"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class TradeResponse(BaseModel):
    """Trade response."""
    id: str = Field(..., description="Trade ID")
    portfolio_id: str = Field(..., description="Portfolio ID")
    market_id: str = Field(..., description="Market identifier")
    outcome: str = Field(..., description="Traded outcome")
    side: str = Field(..., description="Buy or sell")
    quantity: float = Field(..., description="Quantity traded")
    price: float = Field(..., description="Trade price")
    total_value: float = Field(..., description="Total trade value")
    trade_timestamp: datetime = Field(..., description="When trade occurred")
    created_at: datetime = Field(..., description="Record creation time")
    notes: Optional[str] = Field(None, description="Trade notes")
    
    # Optional enrichment from market data
    market_question: Optional[str] = Field(None, description="Market question for display")


class TradeHistory(BaseModel):
    """Paginated trade history response."""
    trades: list[TradeResponse] = Field(..., description="List of trades")
    total: int = Field(..., description="Total number of trades")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether more pages exist")
