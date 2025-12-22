"""
Markets router for Polymarket data access.
"""
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.connections import get_mongo_client
from app.database.databases import markets_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.market import MarketResponse, PriceHistoryResponse, MarketSearchResponse
from app.services.market_service import MarketService

router = APIRouter(prefix="/markets", tags=["Markets"])


async def get_market_service() -> MarketService:
    """Dependency to get MarketService instance."""
    client = await get_mongo_client()
    db = client[markets_db.DB_NAME]
    return MarketService(db)


@router.get(
    "/search",
    response_model=MarketSearchResponse,
    summary="Search markets",
)
async def search_markets(
    current_user: Annotated[User, Depends(get_current_active_user)],
    q: str = Query(..., min_length=1, description="Search query"),
    market_service: MarketService = Depends(get_market_service),
):
    """
    Search for markets on Polymarket.
    
    This endpoint queries the Polymarket API directly (results are not cached).
    
    Requires valid token as query parameter: `?token=xxx`
    """
    results = await market_service.search_markets(q)
    
    return MarketSearchResponse(
        results=results,
        total=len(results),
        query=q,
    )


@router.get(
    "/{market_id}",
    response_model=MarketResponse,
    summary="Get market by ID",
)
async def get_market(
    market_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    market_service: MarketService = Depends(get_market_service),
):
    """
    Get market details by slug or condition_id.
    
    This endpoint lazy-loads data from Polymarket API if not already cached.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    market = await market_service.get_market(market_id)
    
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market '{market_id}' not found",
        )
    
    return market


@router.get(
    "/{market_id}/prices",
    response_model=PriceHistoryResponse,
    summary="Get price history",
)
async def get_price_history(
    market_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    outcome: Optional[str] = Query(None, description="Filter by specific outcome"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    market_service: MarketService = Depends(get_market_service),
):
    """
    Get price history for a market.
    
    This endpoint lazy-loads price data from Polymarket API if not already cached.
    
    - **outcome**: Optional filter for specific outcome (e.g., "Yes", "No")
    - **start_date**: Optional start date for the range
    - **end_date**: Optional end date for the range
    
    Requires valid token as query parameter: `?token=xxx`
    """
    prices = await market_service.get_price_history(
        market_id=market_id,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
    )
    
    if not prices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market '{market_id}' not found or no price history available",
        )
    
    return prices
