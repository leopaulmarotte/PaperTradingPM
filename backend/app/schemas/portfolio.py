"""
Portfolio request/response schemas.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.services.mtm_service import MarkToMarketResult


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
    cash_balance: float = Field(..., description="Current cash balance")
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


class PnLDataPoint(BaseModel):
    """Single P&L data point for charts."""
    timestamp: datetime
    pnl: float
    cumulative_pnl: float


class PositionPnLHistory(BaseModel):
    """P&L history for a single position."""
    market_id: str
    outcome: str
    market_question: Optional[str] = None
    current_quantity: float
    average_cost: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    pnl_history: list[PnLDataPoint] = []


class PortfolioMetrics(BaseModel):
    """Calculated portfolio metrics."""
    portfolio_id: str
    as_of: datetime
    total_value: float
    cash_balance: float
    initial_balance: float
    total_pnl: float
    total_pnl_percent: float
    
    # Advanced metrics
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio (annualized)")
    volatility: Optional[float] = Field(None, description="Daily volatility")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown percentage")
    win_rate: Optional[float] = Field(None, description="Winning trade percentage")
    total_trades: int = Field(0, description="Total number of trades")
    avg_trade_pnl: Optional[float] = Field(None, description="Average P&L per trade")
    best_trade: Optional[float] = Field(None, description="Best single trade P&L")
    worst_trade: Optional[float] = Field(None, description="Worst single trade P&L")
    
    # Historical data for charts
    pnl_history: list[PnLDataPoint] = Field(default=[], description="Portfolio P&L over time")
    drawdown_history: list[dict] = Field(default=[], description="Drawdown over time")
    
    # Positions breakdown (token-agnostic)
    positions: list[PositionPnLHistory] = Field(default=[], description="P&L by position")


# ==================== Mark-to-Market Schemas ====================


class MTMPnLSnapshot(BaseModel):
    """Single P&L snapshot for mark-to-market time series."""
    timestamp: datetime
    portfolio_value: float
    cash_balance: float
    position_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_pnl_percent: float


class MTMPositionSeries(BaseModel):
    """Position-level P&L time series for mark-to-market."""
    market_id: str
    outcome: str
    market_question: Optional[str] = None
    current_quantity: float
    average_entry_price: float = Field(..., description="VWAP entry price")
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    # Time series data
    timestamps: List[datetime] = Field(default=[], description="Price timestamps")
    prices: List[float] = Field(default=[], description="Market prices over time")
    unrealized_pnls: List[float] = Field(default=[], description="Unrealized P&L over time")
    total_pnls: List[float] = Field(default=[], description="Total P&L over time")


class MarkToMarketResponse(BaseModel):
    """
    Complete mark-to-market response with continuous P&L time series.
    
    The P&L series uses MARKET PRICE timestamps as the x-axis,
    providing true mark-to-market valuation that moves with prices,
    not just at trade events.
    """
    portfolio_id: str
    as_of: datetime
    initial_balance: float
    cash_balance: float
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    
    # Risk metrics
    sharpe_ratio: Optional[float] = None
    volatility: Optional[float] = None
    max_drawdown: Optional[float] = None
    
    # Trade statistics
    win_rate: Optional[float] = None
    total_trades: int = 0
    avg_trade_pnl: Optional[float] = None
    best_trade: Optional[float] = None
    worst_trade: Optional[float] = None
    
    # Mark-to-market P&L time series (from market prices)
    pnl_series: List[MTMPnLSnapshot] = Field(
        default=[],
        description="Portfolio P&L time series based on market prices"
    )
    
    # Position-level P&L series
    positions: List[MTMPositionSeries] = Field(
        default=[],
        description="Position-level P&L with price history"
    )
    
    @classmethod
    def from_mtm_result(cls, result: "MarkToMarketResult") -> "MarkToMarketResponse":
        """Convert MTM service result to response schema."""
        from app.services.mtm_service import MarkToMarketResult
        
        pnl_series = [
            MTMPnLSnapshot(
                timestamp=s.timestamp,
                portfolio_value=s.portfolio_value,
                cash_balance=s.cash_balance,
                position_value=s.position_value,
                unrealized_pnl=s.unrealized_pnl,
                realized_pnl=s.realized_pnl,
                total_pnl=s.total_pnl,
                total_pnl_percent=s.total_pnl_percent,
            )
            for s in result.pnl_series
        ]
        
        positions = [
            MTMPositionSeries(
                market_id=p.market_id,
                outcome=p.outcome,
                market_question=p.market_question,
                current_quantity=p.current_quantity,
                average_entry_price=p.average_entry_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                realized_pnl=p.realized_pnl,
                total_pnl=p.total_pnl,
                timestamps=p.timestamps,
                prices=p.prices,
                unrealized_pnls=p.unrealized_pnls,
                total_pnls=p.total_pnls,
            )
            for p in result.positions
        ]
        
        return cls(
            portfolio_id=result.portfolio_id,
            as_of=result.as_of,
            initial_balance=result.initial_balance,
            cash_balance=result.cash_balance,
            total_value=result.total_value,
            total_pnl=result.total_pnl,
            total_pnl_percent=result.total_pnl_percent,
            sharpe_ratio=result.sharpe_ratio,
            volatility=result.volatility,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            avg_trade_pnl=result.avg_trade_pnl,
            best_trade=result.best_trade,
            worst_trade=result.worst_trade,
            pnl_series=pnl_series,
            positions=positions,
        )
