"""
Portfolios router for portfolio and trade management.
"""
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database.connections import get_mongo_client
from app.database.databases import trading_db, markets_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioWithPositions,
    PortfolioMetrics,
    MarkToMarketResponse,
)
from app.schemas.trade import TradeCreate, TradeResponse, TradeHistory
from app.services.portfolio_service import PortfolioService
from app.services.mtm_service import get_mtm_service

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


async def get_portfolio_service() -> PortfolioService:
    """Dependency to get PortfolioService instance."""
    client = await get_mongo_client()
    db = client[trading_db.DB_NAME]
    markets_db_instance = client[markets_db.DB_NAME]
    return PortfolioService(db, markets_db_instance)


# ==================== Portfolio CRUD ====================


@router.get(
    "",
    response_model=list[PortfolioResponse],
    summary="List portfolios",
)
async def list_portfolios(
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    List all portfolios for the current user.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    return await portfolio_service.list_portfolios(current_user.id)


@router.post(
    "",
    response_model=PortfolioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create portfolio",
)
async def create_portfolio(
    body: PortfolioCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Create a new paper trading portfolio.
    
    - **name**: Portfolio name (required)
    - **description**: Optional description
    - **initial_balance**: Starting paper money (default: 10000)
    
    Requires valid token as query parameter: `?token=xxx`
    """
    return await portfolio_service.create_portfolio(current_user.id, body)


@router.get(
    "/{portfolio_id}",
    response_model=PortfolioWithPositions,
    summary="Get portfolio with positions",
)
async def get_portfolio(
    portfolio_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Get a portfolio with calculated positions and P&L.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    portfolio = await portfolio_service.get_portfolio_with_positions(
        portfolio_id, current_user.id
    )
    
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return portfolio


@router.patch(
    "/{portfolio_id}",
    response_model=PortfolioResponse,
    summary="Update portfolio",
)
async def update_portfolio(
    portfolio_id: str,
    body: PortfolioUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Update portfolio details.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    portfolio = await portfolio_service.update_portfolio(
        portfolio_id, current_user.id, body
    )
    
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return portfolio


@router.delete(
    "/{portfolio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete portfolio",
)
async def delete_portfolio(
    portfolio_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Delete a portfolio and all its trades.
    
    **Warning**: This action cannot be undone.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    deleted = await portfolio_service.delete_portfolio(portfolio_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )


# ==================== Trade Operations ====================


@router.post(
    "/{portfolio_id}/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add trade to portfolio",
)
async def add_trade(
    portfolio_id: str,
    body: TradeCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Add a paper trade to a portfolio.
    
    - **market_id**: Polymarket market identifier
    - **outcome**: Outcome being traded (e.g., "Yes", "No")
    - **side**: "buy" or "sell"
    - **quantity**: Number of shares
    - **price**: Price per share (0-1)
    - **trade_timestamp**: Optional, defaults to now (can be backdated for backtesting)
    - **notes**: Optional trade notes
    
    Requires valid token as query parameter: `?token=xxx`
    """
    trade = await portfolio_service.add_trade(portfolio_id, current_user.id, body)
    
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return trade


@router.get(
    "/{portfolio_id}/trades",
    response_model=TradeHistory,
    summary="Get trade history",
)
async def get_trades(
    portfolio_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    start_date: Optional[datetime] = Query(None, description="Filter trades after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter trades before this date"),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Get paginated trade history for a portfolio.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    
    Requires valid token as query parameter: `?token=xxx`
    """
    return await portfolio_service.get_trades(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
    )


# ==================== Metrics ====================


@router.get(
    "/{portfolio_id}/metrics",
    response_model=PortfolioMetrics,
    summary="Calculate portfolio metrics",
)
async def get_portfolio_metrics(
    portfolio_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    as_of: Optional[datetime] = Query(None, description="Calculate metrics as of this date"),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
):
    """
    Calculate portfolio metrics (Sharpe ratio, risk metrics, etc.).
    
    - **as_of**: Optional date to calculate historical metrics
    
    Note: Advanced metrics (Sharpe, drawdown) are placeholders for future implementation.
    
    Requires valid token as query parameter: `?token=xxx`
    """
    metrics = await portfolio_service.calculate_metrics(
        portfolio_id, current_user.id, as_of
    )
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return metrics


@router.get(
    "/{portfolio_id}/mtm",
    response_model=MarkToMarketResponse,
    summary="Get mark-to-market P&L",
)
async def get_mark_to_market(
    portfolio_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    resolution: int = Query(60, ge=1, le=1440, description="Time resolution in minutes (1-1440)"),
):
    """
    Calculate TRUE mark-to-market P&L using continuous market price series.
    
    This endpoint provides:
    - Portfolio P&L time series based on MARKET PRICES (not just trade timestamps)
    - Position-level P&L with VWAP average entry prices
    - Proper realized/unrealized P&L separation
    - Risk metrics (Sharpe, volatility, max drawdown)
    
    The P&L curve will move even when no trades occur, as it reflects
    market price movements (true mark-to-market valuation).
    
    - **resolution**: Time resolution in minutes (default: 60 = hourly)
    
    Requires valid token as query parameter: `?token=xxx`
    """
    mtm_service = await get_mtm_service()
    
    result = await mtm_service.calculate_mtm(
        portfolio_id,
        current_user.id,
        resolution_minutes=resolution,
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    # Convert dataclass to response schema
    return MarkToMarketResponse.from_mtm_result(result)
