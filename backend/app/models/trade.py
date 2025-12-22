"""
Trade model for trading database.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TradeSide(str, Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class Trade(BaseModel):
    """
    Trade document model for MongoDB trading_db.trades collection.
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId as string")
    portfolio_id: str = Field(..., description="Parent portfolio ID")
    market_id: str = Field(..., description="Polymarket market identifier (condition_id or slug)")
    outcome: str = Field(..., description="Outcome being traded (e.g., 'Yes', 'No', 'Trump')")
    side: TradeSide = Field(..., description="Buy or sell")
    quantity: float = Field(..., gt=0, description="Number of shares/contracts")
    price: float = Field(..., ge=0, le=1, description="Price per share (0-1 for prediction markets)")
    trade_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the trade occurred (can be backdated for backtesting)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this record was created"
    )
    notes: Optional[str] = Field(None, description="Optional trade notes")

    class Config:
        populate_by_name = True
        use_enum_values = True

    @property
    def total_value(self) -> float:
        """Calculate total trade value."""
        return self.quantity * self.price
