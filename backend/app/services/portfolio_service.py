"""
Portfolio service for portfolio and trade management.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import math

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.databases import trading_db, markets_db
from app.models.portfolio import Portfolio
from app.models.trade import Trade, TradeSide
from app.schemas.portfolio import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioWithPositions,
    Position,
    PortfolioMetrics,
    PnLDataPoint,
    PositionPnLHistory,
)
from app.schemas.trade import TradeCreate, TradeResponse, TradeHistory


class PortfolioService:
    """Service for portfolio and trade operations."""
    
    def __init__(self, db: AsyncIOMotorDatabase, markets_db_instance: AsyncIOMotorDatabase = None):
        """Initialize with trading database and optional markets database."""
        self.db = db
        self.portfolios = db[trading_db.Collections.PORTFOLIOS]
        self.trades = db[trading_db.Collections.TRADES]
        self.markets_db = markets_db_instance
        self.markets_col = None
        if markets_db_instance is not None:
            self.markets_col = markets_db_instance[markets_db.Collections.MARKETS]
    
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
        # No trades yet, cash balance equals initial balance
        cash_balance = request.initial_balance
        return self._portfolio_to_response(portfolio_doc, cash_balance)
    
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
        
        cash_balance = await self._calculate_cash_balance(portfolio_id, portfolio_doc["initial_balance"])
        return self._portfolio_to_response(portfolio_doc, cash_balance)
    
    async def list_portfolios(self, user_id: str) -> list[PortfolioResponse]:
        """List all portfolios for a user."""
        cursor = self.portfolios.find({"user_id": user_id})
        portfolios = await cursor.to_list(length=100)
        
        # Calculate cash balance for each portfolio
        responses = []
        for p in portfolios:
            cash_balance = await self._calculate_cash_balance(str(p["_id"]), p["initial_balance"])
            responses.append(self._portfolio_to_response(p, cash_balance))
        
        return responses
    
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
        
        cash_balance = await self._calculate_cash_balance(portfolio_id, result["initial_balance"])
        return self._portfolio_to_response(result, cash_balance)
    
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
    
    async def _get_current_price(self, market_id: str, outcome: str) -> Optional[float]:
        """Get current market price for a position from markets_db."""
        if self.markets_col is None:
            return None
        
        try:
            # market_id is the slug
            market_doc = await self.markets_col.find_one({"slug": market_id})
            if not market_doc:
                return None
            
            outcomes = market_doc.get("outcomes", [])
            outcome_prices = market_doc.get("outcome_prices", [])
            
            # Find outcome index
            for i, o in enumerate(outcomes):
                if o == outcome and i < len(outcome_prices):
                    price_str = outcome_prices[i]
                    try:
                        return float(price_str)
                    except (ValueError, TypeError):
                        return None
            
            return None
        except Exception:
            return None
    
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
        
        # Enrich positions with current market prices
        for pos in positions:
            current_price = await self._get_current_price(pos.market_id, pos.outcome)
            if current_price is not None:
                pos.current_price = current_price
                # Calculate unrealized P&L
                pos.unrealized_pnl = pos.quantity * (current_price - pos.average_price)
        
        # Calculate totals using current market prices
        initial_balance = portfolio.initial_balance
        position_value = sum(
            p.quantity * (p.current_price if p.current_price is not None else p.average_price) 
            for p in positions
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
        """Calculate comprehensive portfolio metrics."""
        portfolio_with_positions = await self.get_portfolio_with_positions(
            portfolio_id, user_id
        )
        
        if not portfolio_with_positions:
            return None
        
        # Get all trades sorted by timestamp
        cursor = self.trades.find({"portfolio_id": portfolio_id}).sort("trade_timestamp", 1)
        trades = await cursor.to_list(length=None)
        
        initial_balance = portfolio_with_positions.initial_balance
        
        # Calculate trade-level P&L and stats
        trade_pnls = []
        positions_data = {}  # {(market_id, outcome): {...}}
        
        for trade in trades:
            market_id = trade["market_id"]
            outcome = trade["outcome"]
            key = (market_id, outcome)
            
            if key not in positions_data:
                positions_data[key] = {
                    "market_id": market_id,
                    "outcome": outcome,
                    "quantity": 0,
                    "total_cost": 0,
                    "realized_pnl": 0,
                    "trades": [],
                }
            
            pos = positions_data[key]
            qty = trade["quantity"]
            price = trade["price"]
            side = trade["side"]
            
            if side == "buy":
                pos["quantity"] += qty
                pos["total_cost"] += qty * price
                pos["trades"].append({
                    "timestamp": trade["trade_timestamp"],
                    "type": "buy",
                    "qty": qty,
                    "price": price,
                    "pnl": 0
                })
            else:  # sell
                # Calculate realized P&L for this sale
                if pos["quantity"] > 0:
                    avg_cost = pos["total_cost"] / pos["quantity"]
                    realized = (price - avg_cost) * qty
                    pos["realized_pnl"] += realized
                    trade_pnls.append(realized)
                    
                    pos["quantity"] -= qty
                    pos["total_cost"] -= qty * avg_cost
                    pos["trades"].append({
                        "timestamp": trade["trade_timestamp"],
                        "type": "sell",
                        "qty": qty,
                        "price": price,
                        "pnl": realized
                    })
        
        # Build P&L history (cumulative portfolio value over time)
        pnl_history = []
        portfolio_value_history = []
        
        if trades:
            # Track positions state at each trade to calculate portfolio value
            position_state = {}  # {(market_id, outcome): {"quantity": x, "last_price": y}}
            cash_balance_running = initial_balance
            
            for trade in trades:
                trade_time = trade["trade_timestamp"]
                qty = trade["quantity"]
                price = trade["price"]
                side = trade["side"]
                market_id = trade["market_id"]
                outcome = trade["outcome"]
                key = (market_id, outcome)
                
                # Initialize position if needed
                if key not in position_state:
                    position_state[key] = {"quantity": 0, "last_price": price}
                
                # Update cash balance and position
                if side == "buy":
                    cash_balance_running -= qty * price
                    position_state[key]["quantity"] += qty
                else:  # sell
                    cash_balance_running += qty * price
                    position_state[key]["quantity"] -= qty
                
                # Update last known price for this position
                position_state[key]["last_price"] = price
                
                # Calculate position value: sum of all positions at their last known price
                position_value = sum(
                    pos["quantity"] * pos["last_price"] 
                    for pos in position_state.values() 
                    if pos["quantity"] > 0
                )
                
                # Total portfolio value = cash + position value
                portfolio_value = cash_balance_running + position_value
                
                # P&L = current value - initial balance
                pnl = portfolio_value - initial_balance
                
                pnl_history.append(PnLDataPoint(
                    timestamp=trade_time,
                    pnl=pnl,
                    cumulative_pnl=pnl
                ))
                portfolio_value_history.append(portfolio_value)
        
        # Calculate drawdown history
        drawdown_history = []
        if portfolio_value_history:
            peak = portfolio_value_history[0]
            for i, value in enumerate(portfolio_value_history):
                if value > peak:
                    peak = value
                drawdown = (value - peak) / peak if peak > 0 else 0
                if pnl_history:
                    drawdown_history.append({
                        "timestamp": pnl_history[i].timestamp.isoformat(),
                        "drawdown": drawdown
                    })
        
        # Calculate max drawdown
        max_drawdown = min([d["drawdown"] for d in drawdown_history]) if drawdown_history else 0
        
        # Calculate win rate
        winning_trades = len([p for p in trade_pnls if p > 0])
        total_trades = len(trade_pnls)
        win_rate = winning_trades / total_trades if total_trades > 0 else None
        
        # Calculate average trade P&L
        avg_trade_pnl = sum(trade_pnls) / len(trade_pnls) if trade_pnls else None
        best_trade = max(trade_pnls) if trade_pnls else None
        worst_trade = min(trade_pnls) if trade_pnls else None
        
        # Calculate volatility and Sharpe ratio
        volatility = None
        sharpe_ratio = None
        
        if len(portfolio_value_history) >= 2:
            # Calculate daily returns
            returns = []
            for i in range(1, len(portfolio_value_history)):
                prev_val = portfolio_value_history[i-1]
                curr_val = portfolio_value_history[i]
                if prev_val > 0:
                    ret = (curr_val - prev_val) / prev_val
                    returns.append(ret)
            
            if returns:
                # Daily volatility
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                volatility = math.sqrt(variance) if variance >= 0 else 0
                
                # Annualized Sharpe (assuming 252 trading days, 0% risk-free rate)
                if volatility > 0:
                    annualized_return = mean_return * 252
                    annualized_vol = volatility * math.sqrt(252)
                    sharpe_ratio = annualized_return / annualized_vol
        
        # Build position P&L summaries (token-agnostic)
        positions_summary = []
        for key, pos_data in positions_data.items():
            if pos_data["quantity"] > 0 or pos_data["realized_pnl"] != 0:
                avg_cost = pos_data["total_cost"] / pos_data["quantity"] if pos_data["quantity"] > 0 else 0
                
                # Build position-level P&L history from trades
                pos_pnl_history = []
                cumulative = 0.0
                for t in pos_data["trades"]:
                    cumulative += t.get("pnl", 0)
                    pos_pnl_history.append(PnLDataPoint(
                        timestamp=t["timestamp"],
                        pnl=t.get("pnl", 0),
                        cumulative_pnl=cumulative
                    ))
                
                positions_summary.append(PositionPnLHistory(
                    market_id=pos_data["market_id"],
                    outcome=pos_data["outcome"],
                    market_question=None,  # Will be enriched by frontend or separate call
                    current_quantity=pos_data["quantity"],
                    average_cost=avg_cost,
                    current_price=None,  # Will be enriched
                    unrealized_pnl=None,  # Will be enriched
                    realized_pnl=pos_data["realized_pnl"],
                    total_pnl=pos_data["realized_pnl"],  # + unrealized when available
                    pnl_history=pos_pnl_history
                ))
        
        return PortfolioMetrics(
            portfolio_id=portfolio_id,
            as_of=as_of or datetime.now(timezone.utc),
            total_value=portfolio_with_positions.total_value,
            cash_balance=portfolio_with_positions.cash_balance,
            initial_balance=initial_balance,
            total_pnl=portfolio_with_positions.total_pnl,
            total_pnl_percent=portfolio_with_positions.total_pnl_percent,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(trades),
            avg_trade_pnl=avg_trade_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade,
            pnl_history=pnl_history,
            drawdown_history=drawdown_history,
            positions=positions_summary
        )
    
    # ==================== Helper Methods ====================
    
    async def _calculate_cash_balance(self, portfolio_id: str, initial_balance: float) -> float:
        """Calculate current cash balance from initial balance and trades."""
        cursor = self.trades.find({"portfolio_id": portfolio_id})
        trades = await cursor.to_list(length=None)
        
        cash_balance = initial_balance
        for trade in trades:
            trade_value = trade["quantity"] * trade["price"]
            if trade["side"] == "buy":
                cash_balance -= trade_value
            else:  # sell
                cash_balance += trade_value
        
        return cash_balance
    
    def _portfolio_to_response(self, doc: dict, cash_balance: float) -> PortfolioResponse:
        """Convert MongoDB document to PortfolioResponse."""
        return PortfolioResponse(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            name=doc["name"],
            description=doc.get("description"),
            initial_balance=doc["initial_balance"],
            cash_balance=cash_balance,
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
