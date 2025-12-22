"""
Market model for markets database.
Flexible schema to accommodate various Polymarket data structures.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    """Market lifecycle status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class PricePoint(BaseModel):
    """Single price history data point."""
    timestamp: datetime
    outcome: str
    price: float
    volume: Optional[float] = None


class Market(BaseModel):
    """
    Market document model for MongoDB markets_db.market:{slug} collections.
    
    This is a flexible schema - Polymarket data structure may vary,
    so we use loose typing where appropriate.
    """
    id: Optional[str] = Field(None, alias="_id", description="Document ID within collection")
    slug: Optional[str] = Field(None, description="Market slug identifier")
    condition_id: Optional[str] = Field(None, description="Polymarket condition ID")
    question: Optional[str] = Field(None, description="Market question text")
    description: Optional[str] = Field(None, description="Market description")
    outcomes: list[str] = Field(default=[], description="Possible outcomes")
    end_date: Optional[datetime] = Field(None, description="Market end/resolution date")
    status: MarketStatus = Field(
        default=MarketStatus.ACTIVE,
        description="Market status"
    )
    resolution: Optional[str] = Field(None, description="Resolved outcome if status=resolved")
    
    # Flexible metadata container for additional Polymarket fields
    metadata: dict[str, Any] = Field(
        default={},
        description="Additional metadata from Polymarket API"
    )
    
    first_fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this market was first cached"
    )
    last_updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this market data was last updated"
    )

    class Config:
        populate_by_name = True
        use_enum_values = True


class MarketInfo(BaseModel):
    """
    Market info document stored within market collection.
    Uses _id: "info" as document identifier.
    """
    id: str = Field(default="info", alias="_id")
    slug: str
    condition_id: Optional[str] = None
    question: str
    description: Optional[str] = None
    outcomes: list[str] = []
    end_date: Optional[datetime] = None
    status: MarketStatus = MarketStatus.ACTIVE
    resolution: Optional[str] = None
    metadata: dict[str, Any] = {}
    first_fetched_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        use_enum_values = True


class MarketPrices(BaseModel):
    """
    Price history document stored within market collection.
    Uses _id: "prices" as document identifier.
    """
    id: str = Field(default="prices", alias="_id")
    history: list[PricePoint] = Field(default=[], description="Price history points")
    
    class Config:
        populate_by_name = True
