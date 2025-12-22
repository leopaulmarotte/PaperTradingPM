"""
Market service for lazy-loading Polymarket data.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.databases import markets_db
from app.services.polymarket_api import PolymarketAPI
from app.schemas.market import MarketResponse, PriceHistoryResponse


class MarketService:
    """Service for market data with lazy-loading from Polymarket API."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with markets database."""
        self.db = db
        self.registry = db[markets_db.Collections.REGISTRY]
        self.polymarket = PolymarketAPI()
    
    async def get_market(self, market_id: str) -> Optional[MarketResponse]:
        """
        Get market by ID (slug or condition_id).
        Lazy-loads from Polymarket API if not cached.
        
        Args:
            market_id: Market slug or condition_id
            
        Returns:
            MarketResponse or None if not found
        """
        # Try to find in registry first (by slug or condition_id)
        registry_entry = await self.registry.find_one({
            "$or": [{"_id": market_id}, {"condition_id": market_id}]
        })
        
        if registry_entry:
            # Market is cached, load from collection
            collection_name = registry_entry["collection_name"]
            info_doc = await self.db[collection_name].find_one({"_id": "info"})
            
            if info_doc:
                return self._doc_to_response(info_doc, registry_entry)
        
        # Not cached - fetch from Polymarket API
        market_data = await self.polymarket.get_market(market_id)
        
        if not market_data:
            return None
        
        # Cache the market
        await self._cache_market(market_data)
        
        return self._market_data_to_response(market_data)
    
    async def get_price_history(
        self,
        market_id: str,
        outcome: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[PriceHistoryResponse]:
        """
        Get price history for a market.
        Lazy-loads from Polymarket API if not cached.
        
        Args:
            market_id: Market slug or condition_id
            outcome: Optional specific outcome to filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            PriceHistoryResponse or None if market not found
        """
        # Ensure market is cached
        market = await self.get_market(market_id)
        if not market:
            return None
        
        # Find registry entry to get collection name
        registry_entry = await self.registry.find_one({
            "$or": [{"_id": market_id}, {"condition_id": market_id}]
        })
        
        if not registry_entry:
            return None
        
        collection_name = registry_entry["collection_name"]
        
        # Get prices document
        prices_doc = await self.db[collection_name].find_one({"_id": "prices"})
        
        if not prices_doc or not prices_doc.get("history"):
            # Try to fetch from API
            price_data = await self.polymarket.get_price_history(
                market_id, start_date, end_date
            )
            
            if price_data:
                await self._cache_prices(collection_name, price_data)
                prices_doc = {"history": price_data}
        
        # Filter and return
        history = prices_doc.get("history", [])
        
        # Apply filters
        filtered = history
        if outcome:
            filtered = [p for p in filtered if p.get("outcome") == outcome]
        if start_date:
            filtered = [p for p in filtered if p.get("timestamp", datetime.min) >= start_date]
        if end_date:
            filtered = [p for p in filtered if p.get("timestamp", datetime.max) <= end_date]
        
        return PriceHistoryResponse(
            market_id=market_id,
            outcome=outcome,
            prices=filtered,
            start_date=start_date,
            end_date=end_date,
            total_points=len(filtered),
        )
    
    async def search_markets(self, query: str) -> list[dict]:
        """
        Search markets via Polymarket API.
        Does not cache search results.
        
        Args:
            query: Search query string
            
        Returns:
            List of market search results
        """
        return await self.polymarket.search_markets(query)
    
    # ==================== Caching Methods ====================
    
    async def _cache_market(self, market_data: dict) -> str:
        """Cache market data in MongoDB."""
        slug = market_data.get("slug") or market_data.get("condition_id", "unknown")
        
        # Ensure collection exists and is registered
        collection_name = await markets_db.ensure_market_collection(
            self.db, slug, market_data
        )
        
        # Store market info
        info_doc = {
            "_id": "info",
            "slug": slug,
            "condition_id": market_data.get("condition_id"),
            "question": market_data.get("question"),
            "description": market_data.get("description"),
            "outcomes": market_data.get("outcomes", []),
            "end_date": market_data.get("end_date"),
            "status": market_data.get("status", "active"),
            "resolution": market_data.get("resolution"),
            "metadata": {k: v for k, v in market_data.items() 
                        if k not in ["slug", "condition_id", "question", 
                                    "description", "outcomes", "end_date",
                                    "status", "resolution"]},
            "first_fetched_at": datetime.now(timezone.utc),
            "last_updated_at": datetime.now(timezone.utc),
        }
        
        await self.db[collection_name].update_one(
            {"_id": "info"},
            {"$set": info_doc},
            upsert=True,
        )
        
        return collection_name
    
    async def _cache_prices(self, collection_name: str, price_data: list[dict]) -> None:
        """Cache price history in MongoDB."""
        # Append to existing history (avoid duplicates by timestamp+outcome)
        existing = await self.db[collection_name].find_one({"_id": "prices"})
        existing_history = existing.get("history", []) if existing else []
        
        # Create set of existing (timestamp, outcome) for dedup
        existing_keys = {
            (p.get("timestamp"), p.get("outcome")) 
            for p in existing_history
        }
        
        # Add new prices that don't exist
        for price in price_data:
            key = (price.get("timestamp"), price.get("outcome"))
            if key not in existing_keys:
                existing_history.append(price)
        
        # Sort by timestamp
        existing_history.sort(key=lambda x: x.get("timestamp", datetime.min))
        
        await self.db[collection_name].update_one(
            {"_id": "prices"},
            {"$set": {"history": existing_history}},
            upsert=True,
        )
    
    # ==================== Helper Methods ====================
    
    def _doc_to_response(self, info_doc: dict, registry_entry: dict) -> MarketResponse:
        """Convert cached documents to MarketResponse."""
        return MarketResponse(
            slug=info_doc.get("slug") or registry_entry["_id"],
            condition_id=info_doc.get("condition_id"),
            question=info_doc.get("question", ""),
            description=info_doc.get("description"),
            outcomes=info_doc.get("outcomes", []),
            end_date=info_doc.get("end_date"),
            status=info_doc.get("status", "active"),
            resolution=info_doc.get("resolution"),
            current_prices=None,  # TODO: Get from Redis live data
            metadata=info_doc.get("metadata", {}),
        )
    
    def _market_data_to_response(self, market_data: dict) -> MarketResponse:
        """Convert API market data to MarketResponse."""
        return MarketResponse(
            slug=market_data.get("slug") or market_data.get("condition_id", ""),
            condition_id=market_data.get("condition_id"),
            question=market_data.get("question", ""),
            description=market_data.get("description"),
            outcomes=market_data.get("outcomes", []),
            end_date=market_data.get("end_date"),
            status=market_data.get("status", "active"),
            resolution=market_data.get("resolution"),
            current_prices=market_data.get("current_prices"),
            metadata={k: v for k, v in market_data.items() 
                     if k not in ["slug", "condition_id", "question", 
                                 "description", "outcomes", "end_date",
                                 "status", "resolution", "current_prices"]},
        )
