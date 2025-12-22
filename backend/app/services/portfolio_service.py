"""
Portfolio service for portfolio and trade management.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.databases import trading_db
from app.models.portfolio import Portfolio
from app.models.trade import Trade, TradeSide
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioWithPositions,
    Position,
    PortfolioMetrics,
)
from app.schemas.trade import TradeCreate, TradeResponse, TradeHistory


class PortfolioService:
    """Service for portfolio and trade operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with trading database."""
        self.db = db
        self.portfolios = db[trading_db.Collections.PORTFOLIOS]
        self.trades = db[trading_db.Collections.TRADES]
    
    # ==================== Portfolio CRUD ====================
    
    async def create_portfolio(
        self, user_id: str, request: PortfolioCreate
    ) -> PortfolioResponse:
        """Create a new portfolio for a user."""
        portfolio_doc = {
            "user_id": user_id,
            "name": request.name,
            "description": request.description,
            "initial_balance": request.initial_balance,
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
        }
        
        result = await self.portfolios.insert_one(portfolio_doc)
        portfolio_doc["_id"] = result.inserted_id
        
        return self._portfolio_to_response(portfolio_doc)
    
    async def get_portfolio(
        self, portfolio_id: str, user_id: str
    ) -> Optional[PortfolioResponse]:
        """Get a portfolio by ID (must belong to user)."""
        try:
            portfolio_doc = await self.portfolios.find_one({
                "_id": ObjectId(portfolio_id),
                "user_id": user_id,
            })
        except Exception:
            return None
        
        if not portfolio_doc:
            return None
        
        return self._portfolio_to_response(portfolio_doc)
    
    async def list_portfolios(self, user_id: str) -> list[PortfolioResponse]:
        """List all portfolios for a user."""
        cursor = self.portfolios.find({"user_id": user_id})
        portfolios = await cursor.to_list(length=100)
        return [self._portfolio_to_response(p) for p in portfolios]
    
    async def update_portfolio(
        self, portfolio_id: str, user_id: str, request: PortfolioUpdate
    ) -> Optional[PortfolioResponse]:
        """Update a portfolio."""
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        
        if not update_data:
            return await self.get_portfolio(portfolio_id, user_id)
        
        try:
            result = await self.portfolios.find_one_and_update(
                {"_id": ObjectId(portfolio_id), "user_id": user_id},
                {"$set": update_data},
                return_document=True,
            )
        except Exception:
            return None
        
        if not result:
            return None
        
        return self._portfolio_to_response(result)
    
    async def delete_portfolio(self, portfolio_id: str, user_id: str) -> bool:
        """Delete a portfolio and its trades."""
        try:
            result = await self.portfolios.delete_one({
                "_id": ObjectId(portfolio_id),
                "user_id": user_id,
            })
            
            if result.deleted_count > 0:
                # Also delete associated trades
                await self.trades.delete_many({"portfolio_id": portfolio_id})
                return True
        except Exception:
            pass
        
        return False
    
    # ==================== Trade Operations ====================
    
    async def add_trade(
        self, portfolio_id: str, user_id: str, request: TradeCreate
    ) -> Optional[TradeResponse]:
        """Add a trade to a portfolio."""
        # Verify portfolio belongs to user
        portfolio = await self.get_portfolio(portfolio_id, user_id)
        if not portfolio:
            return None
        
        trade_doc = {
            "portfolio_id": portfolio_id,
            "market_id": request.market_id,
            "outcome": request.outcome,
            "side": request.side.value if isinstance(request.side, TradeSide) else request.side,
            "quantity": request.quantity,
            "price": request.price,
            "trade_timestamp": request.trade_timestamp or datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "notes": request.notes,
        }
        
        result = await self.trades.insert_one(trade_doc)
        trade_doc["_id"] = result.inserted_id
        
        return self._trade_to_response(trade_doc)
    
    async def get_trades(
        self,
        portfolio_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 50,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> TradeHistory:
        """Get paginated trade history for a portfolio."""
        # Verify portfolio belongs to user
        portfolio = await self.get_portfolio(portfolio_id, user_id)
        if not portfolio:
            return TradeHistory(
                trades=[], total=0, page=page, page_size=page_size, has_more=False
            )
        
        # Build query
        query: dict = {"portfolio_id": portfolio_id}
        
        if start_date or end_date:
            query["trade_timestamp"] = {}
            if start_date:
                query["trade_timestamp"]["$gte"] = start_date
            if end_date:
                query["trade_timestamp"]["$lte"] = end_date
        
        # Get total count
        total = await self.trades.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = self.trades.find(query).sort("trade_timestamp", -1).skip(skip).limit(page_size)
        trades = await cursor.to_list(length=page_size)
        
        return TradeHistory(
            trades=[self._trade_to_response(t) for t in trades],
            total=total,
            page=page,
            page_size=page_size,
            has_more=(skip + len(trades)) < total,
        )
    
    # ==================== Position Calculations ====================
    
    async def get_portfolio_with_positions(
        self, portfolio_id: str, user_id: str
    ) -> Optional[PortfolioWithPositions]:
        """Get portfolio with calculated positions and metrics."""
        portfolio = await self.get_portfolio(portfolio_id, user_id)
        if not portfolio:
            return None
        
        # Get all trades for this portfolio
        cursor = self.trades.find({"portfolio_id": portfolio_id})
        trades = await cursor.to_list(length=None)
        
        # Calculate positions
        positions = self._calculate_positions(trades)
        
        # Calculate totals
        initial_balance = portfolio.initial_balance
        position_value = sum(
            p.quantity * (p.current_price or p.average_price) for p in positions
        )
        cash_spent = sum(
            t["quantity"] * t["price"] * (1 if t["side"] == "buy" else -1)
            for t in trades
        )
        cash_balance = initial_balance - cash_spent
        total_value = cash_balance + position_value
        total_pnl = total_value - initial_balance
        total_pnl_percent = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
        
        return PortfolioWithPositions(
            id=portfolio.id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            description=portfolio.description,
            initial_balance=portfolio.initial_balance,
            created_at=portfolio.created_at,
            is_active=portfolio.is_active,
            positions=positions,
            total_value=total_value,
            cash_balance=cash_balance,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
        )
    
    async def calculate_metrics(
        self, portfolio_id: str, user_id: str, as_of: Optional[datetime] = None
    ) -> Optional[PortfolioMetrics]:
        """Calculate portfolio metrics as of a specific date."""
        portfolio_with_positions = await self.get_portfolio_with_positions(
            portfolio_id, user_id
        )
        
        if not portfolio_with_positions:
            return None
        
        # TODO: Implement advanced metrics (Sharpe ratio, max drawdown, etc.)
        return PortfolioMetrics(
            portfolio_id=portfolio_id,
            as_of=as_of or datetime.now(timezone.utc),
            total_value=portfolio_with_positions.total_value,
            cash_balance=portfolio_with_positions.cash_balance,
            total_pnl=portfolio_with_positions.total_pnl,
            total_pnl_percent=portfolio_with_positions.total_pnl_percent,
            sharpe_ratio=None,  # TODO
            max_drawdown=None,  # TODO
            win_rate=None,  # TODO
            avg_trade_size=None,  # TODO
        )
    
    # ==================== Helper Methods ====================
    
    def _portfolio_to_response(self, doc: dict) -> PortfolioResponse:
        """Convert MongoDB document to PortfolioResponse."""
        return PortfolioResponse(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            name=doc["name"],
            description=doc.get("description"),
            initial_balance=doc["initial_balance"],
            created_at=doc["created_at"],
            is_active=doc.get("is_active", True),
        )
    
    def _trade_to_response(self, doc: dict) -> TradeResponse:
        """Convert MongoDB document to TradeResponse."""
        return TradeResponse(
            id=str(doc["_id"]),
            portfolio_id=doc["portfolio_id"],
            market_id=doc["market_id"],
            outcome=doc["outcome"],
            side=doc["side"],
            quantity=doc["quantity"],
            price=doc["price"],
            total_value=doc["quantity"] * doc["price"],
            trade_timestamp=doc["trade_timestamp"],
            created_at=doc["created_at"],
            notes=doc.get("notes"),
            market_question=None,  # TODO: Enrich from market service
        )
    
    def _calculate_positions(self, trades: list[dict]) -> list[Position]:
        """Calculate current positions from trade history."""
        # Group by market_id and outcome
        position_map: dict[tuple[str, str], dict] = {}
        
        for trade in trades:
            key = (trade["market_id"], trade["outcome"])
            
            if key not in position_map:
                position_map[key] = {
                    "market_id": trade["market_id"],
                    "outcome": trade["outcome"],
                    "quantity": 0,
                    "total_cost": 0,
                }
            
            pos = position_map[key]
            multiplier = 1 if trade["side"] == "buy" else -1
            qty = trade["quantity"] * multiplier
            
            pos["quantity"] += qty
            pos["total_cost"] += trade["quantity"] * trade["price"] * multiplier
        
        # Convert to Position objects
        positions = []
        for pos in position_map.values():
            if abs(pos["quantity"]) > 0.0001:  # Filter out closed positions
                avg_price = pos["total_cost"] / pos["quantity"] if pos["quantity"] != 0 else 0
                positions.append(Position(
                    market_id=pos["market_id"],
                    outcome=pos["outcome"],
                    quantity=pos["quantity"],
                    average_price=abs(avg_price),
                    current_price=None,  # TODO: Get from live data
                    unrealized_pnl=None,  # TODO: Calculate with current price
                    market_question=None,  # TODO: Get from market service
                ))
        
        return positions
