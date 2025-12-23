"""
Market models matching Polymarket API data structures.

Data sources:
- Gamma API: Market metadata (https://gamma-api.polymarket.com)
- CLOB API: Price history (https://clob.polymarket.com)
- Data API: Open interest, holders (https://data-api.polymarket.com)
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    """Market lifecycle status."""
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


# ==================== Market Metadata (from Gamma API) ====================

class MarketMetadata(BaseModel):
    """
    Market metadata document stored in markets_db.markets collection.
    Maps to Polymarket Gamma API response.
    """
    # Core identifiers
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID (slug)")
    gamma_id: str = Field(..., description="Polymarket internal ID")
    slug: str = Field(..., description="URL-friendly identifier")
    condition_id: str = Field(..., description="On-chain condition ID")
    
    # Market info
    question: str = Field(..., description="Market question")
    description: Optional[str] = Field(None, description="Detailed description")
    category: Optional[str] = Field(None, description="Market category")
    
    # Outcomes and tokens
    outcomes: list[str] = Field(default=[], description="Possible outcomes ['Yes', 'No']")
    outcome_prices: list[str] = Field(default=[], description="Current prices per outcome")
    clob_token_ids: list[str] = Field(default=[], description="CLOB token IDs for each outcome")
    
    # Timing
    start_date: Optional[datetime] = Field(None, description="Market start date")
    end_date: Optional[datetime] = Field(None, description="Market end/resolution date")
    created_at: Optional[datetime] = Field(None, description="When market was created on Polymarket")
    
    # Status
    active: bool = Field(default=True, description="Whether market is active")
    closed: bool = Field(default=False, description="Whether market is closed")
    archived: bool = Field(default=False, description="Whether market is archived")
    
    # Volume metrics
    volume_num: float = Field(default=0, description="Total volume in USD")
    volume_24hr: float = Field(default=0, description="24-hour volume")
    volume_7d: float = Field(default=0, description="7-day volume")
    volume_1mo: float = Field(default=0, description="1-month volume")
    
    # Liquidity
    liquidity_num: float = Field(default=0, description="Current liquidity")
    
    # Price info
    best_bid: Optional[float] = Field(None, description="Best bid price")
    best_ask: Optional[float] = Field(None, description="Best ask price")
    spread: Optional[float] = Field(None, description="Bid-ask spread")
    last_trade_price: Optional[float] = Field(None, description="Last trade price")
    
    # Price changes
    one_hour_price_change: Optional[float] = Field(None, description="1-hour price change")
    one_day_price_change: Optional[float] = Field(None, description="24-hour price change")
    one_week_price_change: Optional[float] = Field(None, description="1-week price change")
    
    # Images
    image: Optional[str] = Field(None, description="Market image URL")
    icon: Optional[str] = Field(None, description="Market icon URL")
    
    # Events (parent event info)
    event_slug: Optional[str] = Field(None, description="Parent event slug if part of multi-market")
    event_title: Optional[str] = Field(None, description="Parent event title")
    
    # Metadata tracking
    fetched_at: datetime = Field(default_factory=lambda: datetime.utcnow(), description="When we fetched this data")
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow(), description="Last update time")

    class Config:
        populate_by_name = True
        
    @classmethod
    def from_gamma_response(cls, data: dict) -> "MarketMetadata":
        """Create MarketMetadata from Gamma API response."""
        # Parse JSON string fields
        outcomes = data.get("outcomes", "[]")
        if isinstance(outcomes, str):
            outcomes = eval(outcomes) if outcomes else []
        
        outcome_prices = data.get("outcomePrices", "[]")
        if isinstance(outcome_prices, str):
            outcome_prices = eval(outcome_prices) if outcome_prices else []
        
        clob_token_ids = data.get("clobTokenIds", "[]")
        if isinstance(clob_token_ids, str):
            clob_token_ids = eval(clob_token_ids) if clob_token_ids else []
        
        # Extract event info if present
        events = data.get("events", [])
        event_slug = events[0].get("slug") if events else None
        event_title = events[0].get("title") if events else None
        
        return cls(
            gamma_id=str(data.get("id", "")),
            slug=data.get("slug", ""),
            condition_id=data.get("conditionId", ""),
            question=data.get("question", ""),
            description=data.get("description"),
            category=data.get("category"),
            outcomes=outcomes,
            outcome_prices=outcome_prices,
            clob_token_ids=clob_token_ids,
            start_date=cls._parse_date(data.get("startDate")),
            end_date=cls._parse_date(data.get("endDate")),
            created_at=cls._parse_date(data.get("createdAt")),
            active=data.get("active", True),
            closed=data.get("closed", False),
            archived=data.get("archived", False),
            volume_num=float(data.get("volumeNum", 0) or 0),
            volume_24hr=float(data.get("volume24hr", 0) or 0),
            volume_7d=float(data.get("volume7d", 0) or 0),
            volume_1mo=float(data.get("volume1mo", 0) or 0),
            liquidity_num=float(data.get("liquidityNum", 0) or 0),
            best_bid=float(data["bestBid"]) if data.get("bestBid") is not None else None,
            best_ask=float(data["bestAsk"]) if data.get("bestAsk") is not None else None,
            spread=float(data["spread"]) if data.get("spread") is not None else None,
            last_trade_price=float(data["lastTradePrice"]) if data.get("lastTradePrice") is not None else None,
            one_hour_price_change=data.get("oneHourPriceChange"),
            one_day_price_change=data.get("oneDayPriceChange"),
            one_week_price_change=data.get("oneWeekPriceChange"),
            image=data.get("image"),
            icon=data.get("icon"),
            event_slug=event_slug,
            event_title=event_title,
        )
    
    @staticmethod
    def _parse_date(value: Any) -> Optional[datetime]:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                # Handle ISO format with Z suffix
                if value.endswith("Z"):
                    value = value[:-1] + "+00:00"
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                return None
        return None
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document format."""
        doc = self.model_dump(by_alias=False, exclude_none=False)
        doc["_id"] = self.slug  # Use slug as document ID
        return doc


# ==================== Price History (from CLOB API) ====================

class PricePoint(BaseModel):
    """Single price point from CLOB history."""
    timestamp: int = Field(..., description="Unix timestamp")
    price: float = Field(..., description="Price at timestamp")


class PriceHistory(BaseModel):
    """
    Price history document stored in markets_db.price_history collection.
    One document per token_id.
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID (token_id)")
    token_id: str = Field(..., description="CLOB token ID")
    condition_id: str = Field(..., description="Parent market condition ID")
    slug: str = Field(..., description="Parent market slug")
    outcome: str = Field(..., description="Outcome name (Yes/No)")
    outcome_index: int = Field(..., description="Outcome index (0 or 1)")
    
    # Price history data
    history: list[PricePoint] = Field(default=[], description="Price history points")
    
    # Tracking
    first_fetched_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    last_updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    
    # Range info
    earliest_timestamp: Optional[int] = Field(None, description="Earliest data point timestamp")
    latest_timestamp: Optional[int] = Field(None, description="Latest data point timestamp")

    class Config:
        populate_by_name = True
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document format."""
        doc = self.model_dump(by_alias=False, exclude_none=False)
        doc["_id"] = self.token_id
        # Convert PricePoint objects to dicts
        doc["history"] = [{"t": p.timestamp, "p": p.price} for p in self.history]
        return doc
    
    @classmethod
    def from_mongo_doc(cls, doc: dict) -> "PriceHistory":
        """Create from MongoDB document."""
        history = [
            PricePoint(timestamp=p["t"], price=p["p"]) 
            for p in doc.get("history", [])
        ]
        return cls(
            token_id=doc.get("token_id") or doc.get("_id"),
            condition_id=doc.get("condition_id", ""),
            slug=doc.get("slug", ""),
            outcome=doc.get("outcome", ""),
            outcome_index=doc.get("outcome_index", 0),
            history=history,
            first_fetched_at=doc.get("first_fetched_at"),
            last_updated_at=doc.get("last_updated_at"),
            earliest_timestamp=doc.get("earliest_timestamp"),
            latest_timestamp=doc.get("latest_timestamp"),
        )


# ==================== Open Interest (from Data API) ====================

class OpenInterest(BaseModel):
    """
    Open interest document stored in markets_db.open_interest collection.
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID (condition_id)")
    condition_id: str = Field(..., description="Market condition ID")
    slug: str = Field(..., description="Market slug")
    
    value: float = Field(..., description="Open interest value")
    
    # Tracking
    fetched_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    last_updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    class Config:
        populate_by_name = True
    
    def to_mongo_doc(self) -> dict:
        """Convert to MongoDB document format."""
        doc = self.model_dump(by_alias=False, exclude_none=False)
        doc["_id"] = self.condition_id
        return doc


# ==================== Legacy aliases for backward compatibility ====================

Market = MarketMetadata  # Alias
