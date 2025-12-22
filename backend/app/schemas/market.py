"""
Market request/response schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketResponse(BaseModel):
    """Market information response."""
    slug: str = Field(..., description="Market slug identifier")
    condition_id: Optional[str] = Field(None, description="Polymarket condition ID")
    question: str = Field(..., description="Market question")
    description: Optional[str] = Field(None, description="Market description")
    outcomes: list[str] = Field(..., description="Possible outcomes")
    end_date: Optional[datetime] = Field(None, description="Market end date")
    status: str = Field(..., description="Market status")
    resolution: Optional[str] = Field(None, description="Resolved outcome if applicable")
    
    # Current prices per outcome (if available)
    current_prices: Optional[dict[str, float]] = Field(
        None,
        description="Current price for each outcome"
    )
    
    # Flexible metadata
    metadata: dict[str, Any] = Field(default={}, description="Additional metadata")


class PriceHistoryResponse(BaseModel):
    """Price history response for a market."""
    market_id: str = Field(..., description="Market identifier")
    outcome: Optional[str] = Field(None, description="Specific outcome (if filtered)")
    prices: list[dict] = Field(
        ...,
        description="Price points with timestamp, outcome, price, volume"
    )
    start_date: Optional[datetime] = Field(None, description="Query start date")
    end_date: Optional[datetime] = Field(None, description="Query end date")
    total_points: int = Field(..., description="Number of price points returned")


class MarketSearchResult(BaseModel):
    """Market search result item."""
    slug: str
    condition_id: Optional[str] = None
    question: str
    outcomes: list[str] = []
    status: str
    end_date: Optional[datetime] = None


class MarketSearchResponse(BaseModel):
    """Market search response."""
    results: list[MarketSearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total matching markets")
    query: str = Field(..., description="Search query used")
