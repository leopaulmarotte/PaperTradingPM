"""
Market request/response schemas.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ==================== Market Metadata Responses ====================

class MarketSummary(BaseModel):
    """Compact market summary for list responses."""
    slug: str = Field(..., description="Market slug identifier")
    question: str = Field(..., description="Market question")
    outcomes: list[str] = Field(default=[], description="Possible outcomes")
    outcome_prices: list[str] = Field(default=[], description="Current prices per outcome")
    volume_24h: Optional[float] = Field(None, description="24-hour volume")
    volume_total: Optional[float] = Field(None, description="Total volume")
    liquidity: Optional[float] = Field(None, description="Current liquidity")
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    closed: bool = Field(default=False)
    active: bool = Field(default=True)
    end_date: Optional[datetime] = Field(None, description="Market end date")


class MarketDetailResponse(BaseModel):
    """Full market details response."""
    slug: str
    condition_id: Optional[str] = None
    question: str
    description: Optional[str] = None
    
    outcomes: list[str] = []
    outcome_prices: list[str] = []
    clob_token_ids: list[str] = []
    
    volume_24h: Optional[float] = None
    volume_7d: Optional[float] = None
    volume_total: Optional[float] = None
    liquidity: Optional[float] = None
    
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    
    closed: bool = False
    active: bool = True
    end_date: Optional[datetime] = None
    
    image: Optional[str] = None
    icon: Optional[str] = None
    tags: list[str] = []
    rewards: dict = {}
    
    last_synced_at: Optional[datetime] = None


# ==================== Market List / Filter ====================

class MarketListResponse(BaseModel):
    """Paginated market list response."""
    markets: list[MarketSummary] = Field(..., description="List of markets")
    total: int = Field(..., description="Total matching markets")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total pages")
    has_next: bool = Field(..., description="Whether next page exists")
    has_prev: bool = Field(..., description="Whether previous page exists")


class MarketFilterParams(BaseModel):
    """Market filter parameters for queries."""
    # Text search
    search: Optional[str] = Field(None, description="Text search in question/description")
    
    # Status filters
    active: Optional[bool] = Field(None, description="Filter by active status")
    closed: Optional[bool] = Field(None, description="Filter by closed status")
    
    # Volume filters
    volume_min: Optional[float] = Field(None, ge=0, description="Minimum total volume")
    volume_max: Optional[float] = Field(None, ge=0, description="Maximum total volume")
    
    # Liquidity filters
    liquidity_min: Optional[float] = Field(None, ge=0, description="Minimum liquidity")
    liquidity_max: Optional[float] = Field(None, ge=0, description="Maximum liquidity")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page")
    
    # Sorting
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_desc: bool = Field(default=True, description="Sort descending")


# ==================== Price History ====================

class PriceHistoryResponse(BaseModel):
    """Price history for a market outcome."""
    slug: str = Field(..., description="Market slug")
    outcome: str = Field(..., description="Outcome name")
    outcome_index: int = Field(..., description="Outcome index")
    token_id: str = Field(..., description="CLOB token ID")
    
    history: list[dict] = Field(default=[], description="Price points [{t: timestamp, p: price}]")
    total_points: int = 0
    
    cached_at: Optional[datetime] = None


# ==================== Open Interest ====================

class OpenInterestResponse(BaseModel):
    """Open interest for a market."""
    slug: str
    condition_id: str
    value: float
    fetched_at: Optional[datetime] = None


# ==================== Sync Statistics ====================

class SyncStatsResponse(BaseModel):
    """Market database sync statistics."""
    total_markets: int = Field(..., description="Total cached markets")
    active_markets: int = Field(..., description="Active markets count")
    closed_markets: int = Field(..., description="Closed markets count")
    oldest_sync: Optional[datetime] = Field(None, description="Oldest sync timestamp")
    newest_sync: Optional[datetime] = Field(None, description="Most recent sync timestamp")


# ==================== Legacy compatibility ====================

MarketResponse = MarketDetailResponse
