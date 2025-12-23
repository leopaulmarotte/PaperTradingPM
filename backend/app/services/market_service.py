"""
Market service for lazy-loading Polymarket data.

Provides:
- Market metadata retrieval with lazy-loading from Gamma API
- Price history fetching with caching
- Open interest data
- Market filtering and pagination for Streamlit
"""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.database.databases import markets_db
from app.models.market import MarketMetadata, PriceHistory, OpenInterest
from app.services.polymarket_api import get_polymarket_api
from app.schemas.market import (
    MarketSummary,
    MarketDetailResponse,
    MarketListResponse,
    MarketFilterParams,
    PriceHistoryResponse,
    OpenInterestResponse,
)


class MarketService:
    """Service for market data with lazy-loading from Polymarket API."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with markets database."""
        self.db = db
        self.markets_col = db[markets_db.Collections.MARKETS]
        self.price_history_col = db[markets_db.Collections.PRICE_HISTORY]
        self.open_interest_col = db[markets_db.Collections.OPEN_INTEREST]
    
    # ==================== Market Metadata ====================
    
    async def get_market_by_slug(
        self,
        slug: str,
        force_refresh: bool = False,
    ) -> Optional[MarketDetailResponse]:
        """
        Get market by slug with lazy-loading.
        
        Args:
            slug: Market slug identifier
            force_refresh: Force fetch from API even if cached
            
        Returns:
            MarketDetailResponse or None
        """
        # Check cache first
        if not force_refresh:
            doc = await self.markets_col.find_one({"slug": slug})
            if doc:
                return self._doc_to_detail_response(doc)
        
        # Fetch from Polymarket API
        api = await get_polymarket_api()
        market_data = await api.get_market_by_slug(slug)
        
        if not market_data:
            return None
        
        # Cache and return
        await self._cache_market(market_data)
        return self._market_data_to_detail_response(market_data)
    
    async def get_market_by_condition_id(
        self,
        condition_id: str,
        force_refresh: bool = False,
    ) -> Optional[MarketDetailResponse]:
        """
        Get market by condition ID with lazy-loading.
        
        Args:
            condition_id: On-chain condition ID
            force_refresh: Force fetch from API even if cached
            
        Returns:
            MarketDetailResponse or None
        """
        # Check cache first
        if not force_refresh:
            doc = await self.markets_col.find_one({"condition_id": condition_id})
            if doc:
                return self._doc_to_detail_response(doc)
        
        # Fetch from Polymarket API
        api = await get_polymarket_api()
        market_data = await api.get_market_by_condition_id(condition_id)
        
        if not market_data:
            return None
        
        # Cache and return
        await self._cache_market(market_data)
        return self._market_data_to_detail_response(market_data)
    
    async def list_markets(
        self,
        filters: MarketFilterParams,
    ) -> MarketListResponse:
        """
        List markets with filtering and pagination.
        Queries cached data in MongoDB.
        
        Args:
            filters: Filter and pagination parameters
            
        Returns:
            MarketListResponse with paginated results
        """
        # Build query
        query: dict[str, Any] = {}
        
        if filters.closed is not None:
            query["closed"] = filters.closed
        if filters.active is not None:
            query["active"] = filters.active
        if filters.search:
            query["$text"] = {"$search": filters.search}
        if filters.volume_min is not None:
            query["volume_num"] = {"$gte": filters.volume_min}
        if filters.volume_max is not None:
            query.setdefault("volume_num", {})["$lte"] = filters.volume_max
        if filters.liquidity_min is not None:
            query["liquidity_num"] = {"$gte": filters.liquidity_min}
        if filters.liquidity_max is not None:
            query.setdefault("liquidity_num", {})["$lte"] = filters.liquidity_max
        
        # Determine sort
        sort_field_map = {
            "volume_24h": "volume_24hr",
            "volume": "volume_num",
            "liquidity": "liquidity_num",
            "end_date": "end_date_iso",
        }
        sort_field = filters.sort_by or "volume_num"
        # Map friendly name to DB field if needed
        sort_field = sort_field_map.get(sort_field, sort_field)
        sort_dir = -1 if filters.sort_desc else 1
        
        # Get total count
        total = await self.markets_col.count_documents(query)
        
        # Calculate pagination
        skip = (filters.page - 1) * filters.page_size
        total_pages = (total + filters.page_size - 1) // filters.page_size
        
        # Fetch results
        cursor = self.markets_col.find(query).sort(
            sort_field, sort_dir
        ).skip(skip).limit(filters.page_size)
        
        docs = await cursor.to_list(length=filters.page_size)
        
        markets = [self._doc_to_summary(doc) for doc in docs]
        
        return MarketListResponse(
            markets=markets,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
            has_next=filters.page < total_pages,
            has_prev=filters.page > 1,
        )
    
    async def get_top_markets(
        self,
        limit: int = 20,
        sort_by: str = "volume_24h",
        active_only: bool = True,
    ) -> list[MarketSummary]:
        """
        Get top markets by volume or liquidity.
        
        Args:
            limit: Number of markets to return
            sort_by: Field to sort by (volume_24h, liquidity, etc.)
            active_only: Only return active markets
            
        Returns:
            List of MarketSummary
        """
        query: dict[str, Any] = {}
        if active_only:
            query["closed"] = False
            query["active"] = True
        
        # Map friendly names to DB fields
        sort_field_map = {
            "volume_24h": "volume_24hr",
            "volume": "volume_num",
            "liquidity": "liquidity_num",
            "end_date": "end_date_iso",
        }
        sort_field = sort_field_map.get(sort_by, sort_by)
        
        cursor = self.markets_col.find(query).sort(
            sort_field, -1
        ).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [self._doc_to_summary(doc) for doc in docs]
    
    # ==================== Price History ====================
    
    async def get_price_history(
        self,
        slug: str,
        outcome_index: int = 0,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Optional[PriceHistoryResponse]:
        """
        Get price history for a market outcome.
        Lazy-loads from CLOB API if not cached.
        
        Args:
            slug: Market slug
            outcome_index: Outcome index (0 or 1 for binary markets)
            start_ts: Start Unix timestamp filter
            end_ts: End Unix timestamp filter
            force_refresh: Force fetch from API
            
        Returns:
            PriceHistoryResponse or None
        """
        # Get market to find token ID
        market_doc = await self.markets_col.find_one({"slug": slug})
        if not market_doc:
            # Try to lazy-load market first
            market = await self.get_market_by_slug(slug)
            if not market:
                return None
            market_doc = await self.markets_col.find_one({"slug": slug})
        
        clob_token_ids = market_doc.get("clob_token_ids", [])
        outcomes = market_doc.get("outcomes", [])
        
        if outcome_index >= len(clob_token_ids):
            return None
        
        token_id = clob_token_ids[outcome_index]
        outcome_name = outcomes[outcome_index] if outcome_index < len(outcomes) else f"Outcome {outcome_index}"
        
        # Check cache
        cache_key = f"{slug}:{token_id}"
        if not force_refresh:
            cached = await self.price_history_col.find_one({"_id": cache_key})
            if cached and cached.get("history"):
                history = self._filter_history(cached["history"], start_ts, end_ts)
                return PriceHistoryResponse(
                    slug=slug,
                    outcome=outcome_name,
                    outcome_index=outcome_index,
                    token_id=token_id,
                    history=history,
                    total_points=len(history),
                    cached_at=cached.get("fetched_at"),
                )
        
        # Fetch from CLOB API
        api = await get_polymarket_api()
        raw_history = await api.get_price_history(
            token_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        
        # Cache the history
        now = datetime.now(timezone.utc)
        await self.price_history_col.update_one(
            {"_id": cache_key},
            {
                "$set": {
                    "slug": slug,
                    "token_id": token_id,
                    "outcome_index": outcome_index,
                    "history": raw_history,
                    "fetched_at": now,
                }
            },
            upsert=True,
        )
        
        history = self._filter_history(raw_history, start_ts, end_ts)
        
        return PriceHistoryResponse(
            slug=slug,
            outcome=outcome_name,
            outcome_index=outcome_index,
            token_id=token_id,
            history=history,
            total_points=len(history),
            cached_at=now,
        )
    
    # ==================== Open Interest ====================
    
    async def get_open_interest(
        self,
        slugs: list[str],
        force_refresh: bool = False,
    ) -> list[OpenInterestResponse]:
        """
        Get open interest for multiple markets.
        
        Args:
            slugs: List of market slugs
            force_refresh: Force fetch from API
            
        Returns:
            List of OpenInterestResponse
        """
        # Get condition IDs for the slugs
        cursor = self.markets_col.find(
            {"slug": {"$in": slugs}},
            {"slug": 1, "condition_id": 1}
        )
        slug_to_cond = {doc["slug"]: doc["condition_id"] async for doc in cursor}
        
        condition_ids = list(slug_to_cond.values())
        if not condition_ids:
            return []
        
        # Check cache
        results: list[OpenInterestResponse] = []
        to_fetch: list[str] = []
        
        if not force_refresh:
            async for doc in self.open_interest_col.find({"condition_id": {"$in": condition_ids}}):
                cond_id = doc["condition_id"]
                slug = next((s for s, c in slug_to_cond.items() if c == cond_id), None)
                if slug:
                    results.append(OpenInterestResponse(
                        slug=slug,
                        condition_id=cond_id,
                        value=doc["value"],
                        fetched_at=doc.get("fetched_at"),
                    ))
                    condition_ids.remove(cond_id)
            
            to_fetch = condition_ids
        else:
            to_fetch = condition_ids
        
        if to_fetch:
            # Fetch from Data API
            api = await get_polymarket_api()
            oi_data = await api.get_open_interest(to_fetch)
            
            # Cache and add to results
            now = datetime.now(timezone.utc)
            for item in oi_data:
                cond_id = item["market"]
                value = item["value"]
                slug = next((s for s, c in slug_to_cond.items() if c == cond_id), None)
                
                if slug:
                    await self.open_interest_col.update_one(
                        {"condition_id": cond_id},
                        {
                            "$set": {
                                "slug": slug,
                                "condition_id": cond_id,
                                "value": value,
                                "fetched_at": now,
                            }
                        },
                        upsert=True,
                    )
                    
                    results.append(OpenInterestResponse(
                        slug=slug,
                        condition_id=cond_id,
                        value=value,
                        fetched_at=now,
                    ))
        
        return results
    
    # ==================== Bulk Operations (for Worker) ====================
    
    async def bulk_upsert_markets(
        self,
        markets: list[dict[str, Any]],
    ) -> int:
        """
        Bulk upsert market metadata.
        Used by the worker for periodic refresh.
        
        Args:
            markets: List of raw market data from Gamma API
            
        Returns:
            Number of markets upserted
        """
        if not markets:
            return 0
        
        operations = []
        now = datetime.now(timezone.utc)
        
        for market_data in markets:
            market = MarketMetadata.from_gamma_response(market_data)
            doc = market.to_mongo_doc()
            doc["last_synced_at"] = now
            
            operations.append(UpdateOne(
                {"slug": market.slug},
                {
                    "$set": doc,
                    "$setOnInsert": {"first_synced_at": now},
                },
                upsert=True,
            ))
        
        if operations:
            result = await self.markets_col.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        
        return 0
    
    async def get_sync_stats(self) -> dict[str, Any]:
        """Get market sync statistics."""
        total = await self.markets_col.count_documents({})
        active = await self.markets_col.count_documents({"closed": False, "active": True})
        closed = await self.markets_col.count_documents({"closed": True})
        
        # Get oldest and newest sync times
        pipeline = [
            {"$group": {
                "_id": None,
                "oldest_sync": {"$min": "$last_synced_at"},
                "newest_sync": {"$max": "$last_synced_at"},
            }}
        ]
        agg_result = await self.markets_col.aggregate(pipeline).to_list(1)
        sync_times = agg_result[0] if agg_result else {}
        
        return {
            "total_markets": total,
            "active_markets": active,
            "closed_markets": closed,
            "oldest_sync": sync_times.get("oldest_sync"),
            "newest_sync": sync_times.get("newest_sync"),
        }
    
    # ==================== Private Helpers ====================
    
    async def _cache_market(self, market_data: dict[str, Any]) -> None:
        """Cache a single market to MongoDB."""
        market = MarketMetadata.from_gamma_response(market_data)
        doc = market.to_mongo_doc()
        doc["last_synced_at"] = datetime.now(timezone.utc)
        
        await self.markets_col.update_one(
            {"slug": market.slug},
            {
                "$set": doc,
                "$setOnInsert": {"first_synced_at": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
    
    def _filter_history(
        self,
        history: list[dict],
        start_ts: Optional[int],
        end_ts: Optional[int],
    ) -> list[dict]:
        """Filter price history by timestamp range."""
        if not start_ts and not end_ts:
            return history
        
        filtered = []
        for point in history:
            ts = point.get("t", 0)
            if start_ts and ts < start_ts:
                continue
            if end_ts and ts > end_ts:
                continue
            filtered.append(point)
        
        return filtered
    
    def _doc_to_summary(self, doc: dict) -> MarketSummary:
        """Convert MongoDB doc to MarketSummary."""
        return MarketSummary(
            slug=doc.get("slug", ""),
            question=doc.get("question", ""),
            outcomes=doc.get("outcomes", []),
            outcome_prices=doc.get("outcome_prices", []),
            volume_24h=doc.get("volume_24hr"),
            volume_total=doc.get("volume_num"),
            liquidity=doc.get("liquidity_num"),
            best_bid=doc.get("best_bid"),
            best_ask=doc.get("best_ask"),
            spread=doc.get("spread"),
            closed=doc.get("closed", False),
            active=doc.get("active", True),
            end_date=doc.get("end_date_iso"),
        )
    
    def _doc_to_detail_response(self, doc: dict) -> MarketDetailResponse:
        """Convert MongoDB doc to MarketDetailResponse."""
        return MarketDetailResponse(
            slug=doc.get("slug", ""),
            condition_id=doc.get("condition_id"),
            question=doc.get("question", ""),
            description=doc.get("description"),
            outcomes=doc.get("outcomes", []),
            outcome_prices=doc.get("outcome_prices", []),
            clob_token_ids=doc.get("clob_token_ids", []),
            volume_24h=doc.get("volume_24hr"),
            volume_7d=doc.get("volume_7d"),
            volume_total=doc.get("volume_num"),
            liquidity=doc.get("liquidity_num"),
            best_bid=doc.get("best_bid"),
            best_ask=doc.get("best_ask"),
            spread=doc.get("spread"),
            closed=doc.get("closed", False),
            active=doc.get("active", True),
            end_date=doc.get("end_date_iso"),
            image=doc.get("image"),
            icon=doc.get("icon"),
            tags=doc.get("tags", []),
            rewards=doc.get("rewards", {}),
            last_synced_at=doc.get("last_synced_at"),
        )
    
    def _market_data_to_detail_response(self, data: dict) -> MarketDetailResponse:
        """Convert raw API data to MarketDetailResponse."""
        market = MarketMetadata.from_gamma_response(data)
        return MarketDetailResponse(
            slug=market.slug,
            condition_id=market.condition_id,
            question=market.question,
            description=market.description,
            outcomes=market.outcomes,
            outcome_prices=market.outcome_prices,
            clob_token_ids=market.clob_token_ids,
            volume_24h=market.volume_24hr,
            volume_7d=market.volume_7d,
            volume_total=market.volume_num,
            liquidity=market.liquidity_num,
            best_bid=market.best_bid,
            best_ask=market.best_ask,
            spread=market.spread,
            closed=market.closed,
            active=market.active,
            end_date=market.end_date_iso,
            image=market.image,
            icon=market.icon,
            tags=market.tags,
            rewards=market.rewards,
            last_synced_at=None,
        )
