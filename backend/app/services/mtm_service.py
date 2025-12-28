"""
Mark-to-Market P&L Service.

Computes TRUE, FINANCIALLY CORRECT P&L using a stateful position model
with continuous mark-to-market valuation based on market price time series.

Key principles:
- VWAP average entry price
- Position state tracking (quantity, avg_entry_price, realized_pnl)
- Unrealized P&L updates with every market price tick
- Time axis comes from MARKET PRICES, not trade timestamps
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import math

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.databases import trading_db, markets_db
from app.services.polymarket_api import get_polymarket_api


@dataclass
class PositionState:
    """
    Stateful position model for a single market/outcome.
    
    Maintains:
    - quantity: Current position size
    - average_entry_price: VWAP of entry (only updated on buys)
    - realized_pnl: Cumulative realized P&L from closed trades
    """
    market_id: str
    outcome: str
    quantity: float = 0.0
    average_entry_price: float = 0.0
    realized_pnl: float = 0.0
    total_cost: float = 0.0  # For VWAP calculation
    
    def apply_trade(self, side: str, qty: float, price: float) -> float:
        """
        Apply a trade to update position state.
        Returns the realized P&L from this trade (0 for buys).
        
        Rules:
        1) BUY (increase position):
           - quantity increases
           - average_entry_price is recomputed using VWAP
           - realized_pnl unchanged
           
        2) SELL (reduce position):
           - quantity decreases
           - realized_pnl increases
           - average_entry_price DOES NOT change
        """
        trade_pnl = 0.0
        
        if side == "buy":
            # VWAP calculation for average entry price
            new_qty = self.quantity + qty
            if new_qty > 0:
                # new_avg = (old_qty * old_avg + trade_qty * trade_price) / new_qty
                self.total_cost = self.quantity * self.average_entry_price + qty * price
                self.average_entry_price = self.total_cost / new_qty
            self.quantity = new_qty
            
        else:  # sell
            if self.quantity > 0:
                # Realized P&L = sold_qty * (sell_price - average_entry_price)
                sell_qty = min(qty, self.quantity)
                trade_pnl = sell_qty * (price - self.average_entry_price)
                self.realized_pnl += trade_pnl
                
                # Reduce position (avg_entry_price stays the same!)
                self.quantity -= sell_qty
                self.total_cost = self.quantity * self.average_entry_price
                
                # Full liquidation
                if self.quantity <= 0.0001:
                    self.quantity = 0.0
                    self.average_entry_price = 0.0
                    self.total_cost = 0.0
        
        return trade_pnl
    
    def unrealized_pnl(self, market_price: float) -> float:
        """
        Calculate unrealized P&L at a given market price.
        
        unrealized_pnl = quantity * (market_price - average_entry_price)
        """
        if self.quantity <= 0 or self.average_entry_price <= 0:
            return 0.0
        return self.quantity * (market_price - self.average_entry_price)
    
    def total_pnl(self, market_price: float) -> float:
        """Total P&L = realized + unrealized."""
        return self.realized_pnl + self.unrealized_pnl(market_price)


@dataclass
class PnLSnapshot:
    """Single P&L snapshot at a point in time."""
    timestamp: datetime
    portfolio_value: float
    cash_balance: float
    position_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_pnl_percent: float


@dataclass
class PositionPnLSeries:
    """P&L time series for a single position."""
    market_id: str
    outcome: str
    market_question: Optional[str]
    current_quantity: float
    average_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    # First trade timestamp for this position
    first_trade_at: Optional[datetime] = None
    # Time series data
    timestamps: List[datetime] = field(default_factory=list)
    prices: List[float] = field(default_factory=list)
    unrealized_pnls: List[float] = field(default_factory=list)
    total_pnls: List[float] = field(default_factory=list)


@dataclass 
class MarkToMarketResult:
    """Complete mark-to-market result."""
    portfolio_id: str
    as_of: datetime
    initial_balance: float
    cash_balance: float
    total_value: float
    total_pnl: float
    total_pnl_percent: float
    
    # Metrics
    sharpe_ratio: Optional[float]
    volatility: Optional[float]
    max_drawdown: Optional[float]
    win_rate: Optional[float]
    total_trades: int
    avg_trade_pnl: Optional[float]
    best_trade: Optional[float]
    worst_trade: Optional[float]
    
    # Portfolio P&L time series (from market prices)
    pnl_series: List[PnLSnapshot] = field(default_factory=list)
    
    # Position-level P&L series
    positions: List[PositionPnLSeries] = field(default_factory=list)


class MarkToMarketService:
    """
    Service for computing mark-to-market P&L.
    
    Uses market price time series as the x-axis, NOT trade timestamps.
    """
    
    def __init__(self, trading_db_instance: AsyncIOMotorDatabase, markets_db_instance: AsyncIOMotorDatabase):
        self.trading_db = trading_db_instance
        self.markets_db = markets_db_instance
        self.portfolios = trading_db_instance[trading_db.Collections.PORTFOLIOS]
        self.trades = trading_db_instance[trading_db.Collections.TRADES]
        self.markets_col = markets_db_instance[markets_db.Collections.MARKETS]
        self.price_history_col = markets_db_instance[markets_db.Collections.PRICE_HISTORY]
    
    async def _get_current_market_price(self, market_id: str, outcome: str) -> Optional[float]:
        """
        Get current market price from the market document (outcome_prices).
        This is more reliable than the last point in price_history.
        """
        try:
            market_doc = await self.markets_col.find_one({"slug": market_id})
            if not market_doc:
                return None
            
            outcomes = market_doc.get("outcomes", [])
            outcome_prices = market_doc.get("outcome_prices", [])
            
            for i, o in enumerate(outcomes):
                if o == outcome and i < len(outcome_prices):
                    try:
                        return float(outcome_prices[i])
                    except (ValueError, TypeError):
                        return None
            return None
        except Exception:
            return None
    
    async def calculate_mtm(
        self,
        portfolio_id: str,
        user_id: str,
        resolution_minutes: int = 60,  # Default: hourly snapshots
    ) -> Optional[MarkToMarketResult]:
        """
        Calculate mark-to-market P&L for a portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            user_id: User ID (for authorization)
            resolution_minutes: Time resolution for P&L snapshots
            
        Returns:
            MarkToMarketResult with continuous P&L series
        """
        # 1. Get portfolio
        try:
            portfolio = await self.portfolios.find_one({
                "_id": ObjectId(portfolio_id),
                "user_id": user_id,
            })
        except Exception:
            return None
        
        if not portfolio:
            return None
        
        initial_balance = portfolio["initial_balance"]
        portfolio_created = portfolio["created_at"]
        if portfolio_created.tzinfo is None:
            portfolio_created = portfolio_created.replace(tzinfo=timezone.utc)
        
        # 2. Get all trades sorted by timestamp
        cursor = self.trades.find({"portfolio_id": portfolio_id}).sort("trade_timestamp", 1)
        trades = await cursor.to_list(length=None)
        
        if not trades:
            # No trades - return initial state
            now = datetime.now(timezone.utc)
            return MarkToMarketResult(
                portfolio_id=portfolio_id,
                as_of=now,
                initial_balance=initial_balance,
                cash_balance=initial_balance,
                total_value=initial_balance,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                sharpe_ratio=None,
                volatility=None,
                max_drawdown=None,
                win_rate=None,
                total_trades=0,
                avg_trade_pnl=None,
                best_trade=None,
                worst_trade=None,
                pnl_series=[PnLSnapshot(
                    timestamp=now,
                    portfolio_value=initial_balance,
                    cash_balance=initial_balance,
                    position_value=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    total_pnl=0.0,
                    total_pnl_percent=0.0,
                )],
                positions=[],
            )
        
        # 3. Identify all unique positions (market_id, outcome)
        position_keys = set()
        for trade in trades:
            position_keys.add((trade["market_id"], trade["outcome"]))
        
        # 4. Fetch price history for each position
        price_histories: Dict[Tuple[str, str], List[Tuple[datetime, float]]] = {}
        market_questions: Dict[str, str] = {}
        
        for market_id, outcome in position_keys:
            prices = await self._get_price_history_for_position(market_id, outcome)
            price_histories[(market_id, outcome)] = prices
            
            # Get market question (market_id is slug)
            market_doc = await self.markets_col.find_one({"slug": market_id})
            if market_doc:
                market_questions[market_id] = market_doc.get("question", market_id)
            else:
                market_questions[market_id] = market_id
        
        # 5. Build unified time axis from all price histories
        all_timestamps = set()
        for prices in price_histories.values():
            for ts, _ in prices:
                all_timestamps.add(ts)
        
        # Also add trade timestamps to ensure we capture state changes
        for trade in trades:
            ts = trade["trade_timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            all_timestamps.add(ts)
        
        # Add "now" as final timestamp
        now = datetime.now(timezone.utc)
        all_timestamps.add(now)
        
        # Collect trade timestamps (these are critical and must be preserved)
        trade_timestamps = set()
        for trade in trades:
            ts = trade["trade_timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            trade_timestamps.add(ts)
        
        # Sort timestamps
        sorted_timestamps = sorted(all_timestamps)
        
        # 6. Downsample to desired resolution, but ALWAYS keep trade timestamps
        if resolution_minutes > 0:
            sorted_timestamps = self._downsample_timestamps(
                sorted_timestamps, resolution_minutes, must_keep=trade_timestamps
            )
        
        # 7. Build position states and process trades
        position_states: Dict[Tuple[str, str], PositionState] = {}
        for market_id, outcome in position_keys:
            position_states[(market_id, outcome)] = PositionState(
                market_id=market_id,
                outcome=outcome,
            )
        
        # Index trades by timestamp for efficient lookup
        trades_by_time = {}
        for trade in trades:
            ts = trade["trade_timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts not in trades_by_time:
                trades_by_time[ts] = []
            trades_by_time[ts].append(trade)
        
        # Track trade P&Ls for statistics
        trade_pnls = []
        cash_balance = initial_balance
        
        # 8. Walk through time and compute P&L at each point
        pnl_series: List[PnLSnapshot] = []
        position_series: Dict[Tuple[str, str], PositionPnLSeries] = {}
        
        # Calculate first trade timestamp for each position
        first_trade_timestamps: Dict[Tuple[str, str], datetime] = {}
        for trade in trades:
            key = (trade["market_id"], trade["outcome"])
            ts = trade["trade_timestamp"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if key not in first_trade_timestamps or ts < first_trade_timestamps[key]:
                first_trade_timestamps[key] = ts
        
        # Initialize position series
        for key in position_keys:
            market_id, outcome = key
            position_series[key] = PositionPnLSeries(
                market_id=market_id,
                outcome=outcome,
                market_question=market_questions.get(market_id),
                current_quantity=0.0,
                average_entry_price=0.0,
                current_price=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                total_pnl=0.0,
                first_trade_at=first_trade_timestamps.get(key),
            )
        
        # Build price lookup for each position (timestamp -> price)
        price_lookup: Dict[Tuple[str, str], Dict[datetime, float]] = {}
        for key, prices in price_histories.items():
            price_lookup[key] = {ts: p for ts, p in prices}
        
        # Last known prices for interpolation - initialize with first trade prices
        last_known_prices: Dict[Tuple[str, str], float] = {}
        for trade in trades:
            key = (trade["market_id"], trade["outcome"])
            # Use the first trade price as initial known price
            if key not in last_known_prices:
                last_known_prices[key] = trade["price"]
        
        for ts in sorted_timestamps:
            # Apply any trades at this timestamp
            if ts in trades_by_time:
                for trade in trades_by_time[ts]:
                    key = (trade["market_id"], trade["outcome"])
                    state = position_states[key]
                    
                    # Update cash
                    trade_value = trade["quantity"] * trade["price"]
                    if trade["side"] == "buy":
                        cash_balance -= trade_value
                    else:
                        cash_balance += trade_value
                    
                    # Apply to position state
                    pnl = state.apply_trade(
                        trade["side"],
                        trade["quantity"],
                        trade["price"],
                    )
                    if pnl != 0:
                        trade_pnls.append(pnl)
                    
                    # Update last known price from trade
                    last_known_prices[key] = trade["price"]
            
            # Get current prices for all positions
            total_position_value = 0.0
            total_unrealized = 0.0
            total_realized = sum(s.realized_pnl for s in position_states.values())
            
            # Check if this is the last timestamp (now) - use live market prices
            is_final_timestamp = (ts == sorted_timestamps[-1])
            
            for key, state in position_states.items():
                market_id, outcome = key
                
                # For final timestamp, use live market price from outcome_prices
                if is_final_timestamp:
                    live_price = await self._get_current_market_price(market_id, outcome)
                    if live_price is not None:
                        price = live_price
                    else:
                        price = self._get_price_at_time(
                            ts, price_lookup.get(key, {}), last_known_prices.get(key, 0.0)
                        )
                else:
                    # Get price at this timestamp from history
                    price = self._get_price_at_time(
                        ts, price_lookup.get(key, {}), last_known_prices.get(key, 0.0)
                    )
                last_known_prices[key] = price
                
                if state.quantity > 0:
                    position_value = state.quantity * price
                    unrealized = state.unrealized_pnl(price)
                    total_position_value += position_value
                    total_unrealized += unrealized
                    
                    # Update position series
                    series = position_series[key]
                    series.timestamps.append(ts)
                    series.prices.append(price)
                    series.unrealized_pnls.append(unrealized)
                    series.total_pnls.append(state.total_pnl(price))
            
            # Compute portfolio snapshot
            portfolio_value = cash_balance + total_position_value
            total_pnl = portfolio_value - initial_balance
            total_pnl_percent = (total_pnl / initial_balance * 100) if initial_balance > 0 else 0
            
            pnl_series.append(PnLSnapshot(
                timestamp=ts,
                portfolio_value=portfolio_value,
                cash_balance=cash_balance,
                position_value=total_position_value,
                unrealized_pnl=total_unrealized,
                realized_pnl=total_realized,
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
            ))
        
        # 9. Finalize position series with current state using LIVE market prices
        # Use outcome_prices from market doc for consistency with Portfolio page
        for key, state in position_states.items():
            market_id, outcome = key
            series = position_series[key]
            
            # Get current price from market doc (same source as Portfolio page)
            current_price = await self._get_current_market_price(market_id, outcome)
            if current_price is None:
                current_price = last_known_prices.get(key, 0.0)
            
            series.current_quantity = state.quantity
            series.average_entry_price = state.average_entry_price
            series.current_price = current_price
            series.realized_pnl = state.realized_pnl
            series.unrealized_pnl = state.unrealized_pnl(current_price)
            series.total_pnl = state.total_pnl(current_price)
        
        # 10. Recalculate final snapshot with live market prices for consistency
        if pnl_series:
            final_position_value = 0.0
            final_unrealized = 0.0
            final_realized = sum(s.realized_pnl for s in position_states.values())
            
            for key, state in position_states.items():
                market_id, outcome = key
                current_price = await self._get_current_market_price(market_id, outcome)
                if current_price is None:
                    current_price = last_known_prices.get(key, 0.0)
                
                if state.quantity > 0:
                    final_position_value += state.quantity * current_price
                    final_unrealized += state.unrealized_pnl(current_price)
            
            final_portfolio_value = cash_balance + final_position_value
            final_pnl = final_portfolio_value - initial_balance
            final_pnl_percent = (final_pnl / initial_balance * 100) if initial_balance > 0 else 0
            
            # Update last snapshot with corrected values
            pnl_series[-1] = PnLSnapshot(
                timestamp=now,
                portfolio_value=final_portfolio_value,
                cash_balance=cash_balance,
                position_value=final_position_value,
                unrealized_pnl=final_unrealized,
                realized_pnl=final_realized,
                total_pnl=final_pnl,
                total_pnl_percent=final_pnl_percent,
            )
        
        # 11. Calculate metrics
        sharpe_ratio, volatility, max_drawdown = self._calculate_risk_metrics(pnl_series)
        
        win_rate = None
        avg_trade_pnl = None
        best_trade = None
        worst_trade = None
        
        if trade_pnls:
            winning = len([p for p in trade_pnls if p > 0])
            win_rate = winning / len(trade_pnls)
            avg_trade_pnl = sum(trade_pnls) / len(trade_pnls)
            best_trade = max(trade_pnls)
            worst_trade = min(trade_pnls)
        
        # Get final values
        final_snapshot = pnl_series[-1] if pnl_series else None
        
        return MarkToMarketResult(
            portfolio_id=portfolio_id,
            as_of=now,
            initial_balance=initial_balance,
            cash_balance=final_snapshot.cash_balance if final_snapshot else initial_balance,
            total_value=final_snapshot.portfolio_value if final_snapshot else initial_balance,
            total_pnl=final_snapshot.total_pnl if final_snapshot else 0.0,
            total_pnl_percent=final_snapshot.total_pnl_percent if final_snapshot else 0.0,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(trades),
            avg_trade_pnl=avg_trade_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade,
            pnl_series=pnl_series,
            positions=[s for s in position_series.values() if s.current_quantity > 0 or s.realized_pnl != 0],
        )
    
    async def _get_price_history_for_position(
        self, market_id: str, outcome: str
    ) -> List[Tuple[datetime, float]]:
        """
        Get price history for a position.
        
        Args:
            market_id: Slug of the market (trades store slug as market_id)
            outcome: Outcome name (e.g., "Yes", "No", team name, etc.)
            
        Returns:
            List of (timestamp, price) tuples sorted by time
        """
        # Find market document by slug (trades store slug as market_id)
        market_doc = await self.markets_col.find_one({"slug": market_id})
        
        if not market_doc:
            # Fallback: try condition_id in case of legacy data
            market_doc = await self.markets_col.find_one({"condition_id": market_id})
        
        if not market_doc:
            return []
        
        slug = market_doc.get("slug", "")
        outcomes = market_doc.get("outcomes", [])
        clob_token_ids = market_doc.get("clob_token_ids", [])
        
        if not clob_token_ids:
            return []
        
        # Find outcome index
        outcome_index = 0
        for i, o in enumerate(outcomes):
            if o == outcome:
                outcome_index = i
                break
        
        if outcome_index >= len(clob_token_ids):
            return []
        
        token_id = clob_token_ids[outcome_index]
        cache_key = f"{slug}:{token_id}"
        
        # Get cached price history
        cached = await self.price_history_col.find_one({"_id": cache_key})
        
        if not cached or not cached.get("history"):
            # Try to fetch fresh with high fidelity (1 minute intervals)
            try:
                api = await get_polymarket_api()
                history = await api.get_price_history(token_id, fidelity=1)
                if history:
                    # Cache it
                    await self.price_history_col.update_one(
                        {"_id": cache_key},
                        {
                            "$set": {
                                "slug": slug,
                                "token_id": token_id,
                                "history": history,
                                "fetched_at": datetime.now(timezone.utc),
                            }
                        },
                        upsert=True,
                    )
                    # Convert to list of tuples
                    result = []
                    for point in history:
                        ts = datetime.fromtimestamp(point["t"], tz=timezone.utc)
                        price = point["p"]
                        result.append((ts, price))
                    return sorted(result, key=lambda x: x[0])
            except Exception:
                pass
            return []
        
        # Convert cached history to list of tuples
        result = []
        for point in cached["history"]:
            ts = datetime.fromtimestamp(point["t"], tz=timezone.utc)
            price = point["p"]
            result.append((ts, price))
        
        return sorted(result, key=lambda x: x[0])
    
    def _get_price_at_time(
        self,
        target_time: datetime,
        price_dict: Dict[datetime, float],
        last_known: float,
    ) -> float:
        """
        Get price at a specific time, using last known price for interpolation.
        """
        if target_time in price_dict:
            return price_dict[target_time]
        
        # Find closest price before this time
        closest_price = last_known
        closest_time = None
        
        for ts, price in price_dict.items():
            if ts <= target_time:
                if closest_time is None or ts > closest_time:
                    closest_time = ts
                    closest_price = price
        
        return closest_price if closest_price > 0 else last_known
    
    def _downsample_timestamps(
        self, timestamps: List[datetime], resolution_minutes: int, must_keep: set = None
    ) -> List[datetime]:
        """
        Downsample timestamps to desired resolution.
        
        Args:
            timestamps: Sorted list of timestamps
            resolution_minutes: Minimum time between kept timestamps
            must_keep: Set of timestamps that must always be kept (e.g., trade timestamps)
        """
        if not timestamps or resolution_minutes <= 0:
            return timestamps
        
        must_keep = must_keep or set()
        result = []
        last_kept = None
        delta = timedelta(minutes=resolution_minutes)
        
        for ts in timestamps:
            # Always keep must_keep timestamps (trade timestamps)
            if ts in must_keep:
                result.append(ts)
                last_kept = ts
            elif last_kept is None or (ts - last_kept) >= delta:
                result.append(ts)
                last_kept = ts
        
        # Always include the last timestamp
        if timestamps and timestamps[-1] not in result:
            result.append(timestamps[-1])
        
        return sorted(set(result))  # Remove duplicates and sort
    
    def _calculate_risk_metrics(
        self, pnl_series: List[PnLSnapshot]
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculate Sharpe ratio, volatility, and max drawdown.
        """
        if len(pnl_series) < 2:
            return None, None, None
        
        # Calculate returns
        returns = []
        for i in range(1, len(pnl_series)):
            prev_val = pnl_series[i-1].portfolio_value
            curr_val = pnl_series[i].portfolio_value
            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                returns.append(ret)
        
        if not returns:
            return None, None, None
        
        # Volatility
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = math.sqrt(variance) if variance >= 0 else 0
        
        # Sharpe ratio (annualized, assuming hourly data -> 8760 hours/year)
        # Adjust based on actual resolution
        sharpe_ratio = None
        if volatility > 0:
            # Assume hourly resolution for simplicity
            annualized_return = mean_return * 8760
            annualized_vol = volatility * math.sqrt(8760)
            sharpe_ratio = annualized_return / annualized_vol
        
        # Max drawdown
        max_drawdown = 0.0
        peak = pnl_series[0].portfolio_value
        
        for snapshot in pnl_series:
            if snapshot.portfolio_value > peak:
                peak = snapshot.portfolio_value
            
            if peak > 0:
                drawdown = (snapshot.portfolio_value - peak) / peak
                if drawdown < max_drawdown:
                    max_drawdown = drawdown
        
        return sharpe_ratio, volatility, max_drawdown


# Factory function
async def get_mtm_service() -> MarkToMarketService:
    """Get MTM service instance with database connections."""
    from app.database.connections import get_mongo_client
    from app.database.databases import trading_db, markets_db
    
    client = await get_mongo_client()
    trading = client[trading_db.DB_NAME]
    markets = client[markets_db.DB_NAME]
    
    return MarkToMarketService(trading, markets)
