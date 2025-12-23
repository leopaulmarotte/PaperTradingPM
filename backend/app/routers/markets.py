"""
Markets router for Polymarket data access.

Endpoints for:
- Listing markets with filters (for Streamlit)
- Getting market details
- Price history
- Open interest
- Sync statistics
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.connections import get_mongo_client
from app.database.databases import markets_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.roles import require_role
from app.models.user import User, UserRole
from app.schemas.market import (
    MarketSummary,
    MarketDetailResponse,
    MarketListResponse,
    MarketFilterParams,
    PriceHistoryResponse,
    OpenInterestResponse,
    SyncStatsResponse,
)
from app.services.market_service import MarketService

router = APIRouter(prefix="/markets", tags=["Markets"])


async def get_market_service() -> MarketService:
    """Dependency to get MarketService instance."""
    client = await get_mongo_client()
    db = client[markets_db.DB_NAME]
    return MarketService(db)


# ==================== List & Filter Endpoints ====================


@router.get(
    "",
    response_model=MarketListResponse,
    summary="List markets with filters",
)
async def list_markets(
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    # Filter parameters
    search: Optional[str] = Query(None, description="Text search in question/description"),
    closed: Optional[bool] = Query(None, description="Filter by closed status"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    volume_min: Optional[float] = Query(None, ge=0, description="Minimum total volume"),
    volume_max: Optional[float] = Query(None, ge=0, description="Maximum total volume"),
    liquidity_min: Optional[float] = Query(None, ge=0, description="Minimum liquidity"),
    liquidity_max: Optional[float] = Query(None, ge=0, description="Maximum liquidity"),
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    # Sorting
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort descending"),
):
    """
    List markets from cached database with filtering and pagination.
    
    Perfect for Streamlit market explorer:
    - Filter by active/closed status
    - Filter by volume/liquidity ranges
    - Text search across questions
    - Paginated results
    
    Note: Only returns cached markets. Use the sync worker to populate the database.
    """
    filters = MarketFilterParams(
        search=search,
        closed=closed,
        active=active,
        volume_min=volume_min,
        volume_max=volume_max,
        liquidity_min=liquidity_min,
        liquidity_max=liquidity_max,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    
    return await market_service.list_markets(filters)


@router.get(
    "/top",
    response_model=list[MarketSummary],
    summary="Get top markets",
)
async def get_top_markets(
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    limit: int = Query(20, ge=1, le=100, description="Number of markets"),
    sort_by: str = Query("volume_24h", description="Sort field: volume_24h, volume, liquidity"),
    active_only: bool = Query(True, description="Only active markets"),
):
    """
    Get top markets by volume or liquidity.
    
    Quick endpoint for dashboard widgets showing top markets.
    """
    return await market_service.get_top_markets(
        limit=limit,
        sort_by=sort_by,
        active_only=active_only,
    )


@router.get(
    "/stats",
    response_model=SyncStatsResponse,
    summary="Get sync statistics",
)
async def get_sync_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
):
    """
    Get market database sync statistics.
    
    Shows total markets, active/closed counts, and sync timestamps.
    """
    stats = await market_service.get_sync_stats()
    return SyncStatsResponse(**stats)


# ==================== Single Market Endpoints ====================


@router.get(
    "/by-slug/{slug:path}",
    response_model=MarketDetailResponse,
    summary="Get market by slug",
)
async def get_market_by_slug(
    slug: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    force_refresh: bool = Query(False, description="Force fetch from Polymarket API"),
):
    """
    Get market details by slug.
    
    Lazy-loads from Polymarket API if not cached.
    Use `force_refresh=true` to always fetch fresh data.
    """
    market = await market_service.get_market_by_slug(slug, force_refresh=force_refresh)
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market with slug '{slug}' not found",
        )
    
    return market


@router.get(
    "/by-condition/{condition_id}",
    response_model=MarketDetailResponse,
    summary="Get market by condition ID",
)
async def get_market_by_condition_id(
    condition_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    force_refresh: bool = Query(False, description="Force fetch from Polymarket API"),
):
    """
    Get market details by on-chain condition ID.
    
    Lazy-loads from Polymarket API if not cached.
    """
    market = await market_service.get_market_by_condition_id(
        condition_id, force_refresh=force_refresh
    )
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market with condition ID '{condition_id}' not found",
        )
    
    return market


# ==================== Price History Endpoints ====================


@router.get(
    "/by-slug/{slug:path}/prices",
    response_model=PriceHistoryResponse,
    summary="Get price history by slug",
)
async def get_price_history(
    slug: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    outcome_index: int = Query(0, ge=0, le=10, description="Outcome index (0=first, 1=second)"),
    start_ts: Optional[int] = Query(None, description="Start Unix timestamp"),
    end_ts: Optional[int] = Query(None, description="End Unix timestamp"),
    force_refresh: bool = Query(False, description="Force fetch from CLOB API"),
):
    """
    Get price history for a market outcome.
    
    Lazy-loads from CLOB API if not cached.
    
    - **outcome_index**: 0 for first outcome (e.g., "Yes"), 1 for second (e.g., "No")
    - **start_ts/end_ts**: Unix timestamps for time range filter
    """
    prices = await market_service.get_price_history(
        slug=slug,
        outcome_index=outcome_index,
        start_ts=start_ts,
        end_ts=end_ts,
        force_refresh=force_refresh,
    )
    
    if not prices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market '{slug}' not found or no price history available",
        )
    
    return prices


# ==================== Open Interest Endpoints ====================


@router.post(
    "/open-interest",
    response_model=list[OpenInterestResponse],
    summary="Get open interest for markets",
)
async def get_open_interest(
    slugs: list[str],
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
    force_refresh: bool = Query(False, description="Force fetch from Data API"),
):
    """
    Get open interest for multiple markets.
    
    POST with list of slugs in request body.
    """
    if not slugs:
        return []
    
    if len(slugs) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 slugs per request",
        )
    
    return await market_service.get_open_interest(slugs, force_refresh=force_refresh)


# ==================== Admin Endpoints ====================


@router.post(
    "/admin/refresh",
    response_model=dict,
    summary="Manually trigger market refresh",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def admin_refresh_markets(
    market_service: MarketService = Depends(get_market_service),
    limit: int = Query(100, ge=1, le=1000, description="Max markets to sync"),
    active_only: bool = Query(True, description="Only sync active markets"),
):
    """
    Manually trigger a market metadata refresh.
    
    Admin only. Fetches markets from Gamma API and updates the cache.
    For production, use the background worker instead.
    """
    from app.services.polymarket_api import get_polymarket_api
    
    api = await get_polymarket_api()
    
    filters = {}
    if active_only:
        filters["closed"] = False
        filters["active"] = True
    
    markets = await api.get_all_markets_paginated(
        batch_size=100,
        max_markets=limit,
        **filters,
    )
    
    count = await market_service.bulk_upsert_markets(markets)
    
    return {
        "message": f"Refreshed {count} markets",
        "fetched": len(markets),
        "upserted": count,
    }
