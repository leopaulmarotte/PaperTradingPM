#!/usr/bin/env python3
"""
Polymarket Market Metadata Sync Worker

Fetches market metadata from the Polymarket Gamma API and stores it in MongoDB.
Designed for resilience:
- Saves results incrementally as they're fetched (batch by batch)
- Resumes from last sync point using cursor/offset tracking
- Handles interruptions gracefully

Usage:
    python sync_markets.py

Environment Variables:
    MONGODB_URI: MongoDB connection string
    SYNC_INTERVAL_MINUTES: Minutes between syncs (default: 5)
    FULL_SYNC_INTERVAL_HOURS: Hours between full syncs (default: 24)
    BATCH_SIZE: Markets per API request (default: 500)
    LOG_LEVEL: Logging level (default: INFO)
"""
import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import UpdateOne


# ==================== Configuration ====================

class SyncConfig(BaseSettings):
    """Worker configuration from environment."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # MongoDB
    mongodb_uri: str = Field(default="mongodb://mongodb:27017")
    markets_db_name: str = Field(default="markets_db")
    
    # Sync settings
    sync_interval_minutes: int = Field(default=30)
    full_sync_interval_hours: int = Field(default=24)
    batch_size: int = Field(default=500)
    
    # Polymarket API
    gamma_api_url: str = Field(default="https://gamma-api.polymarket.com")
    
    # Logging
    log_level: str = Field(default="INFO")


config = SyncConfig()


# ==================== Logging Setup ====================

logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("polymarket_sync")


# ==================== Collections ====================

MARKETS_COLLECTION = "markets"
SYNC_STATE_COLLECTION = "sync_state"


# ==================== Polymarket API Client ====================

class GammaAPIClient:
    """Async client for Polymarket Gamma API."""
    
    def __init__(self, base_url: str = config.gamma_api_url):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
            )
        return self._client
    
    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def get_markets(
        self,
        limit: int = 500,
        offset: int = 0,
        **filters,
    ) -> list[dict[str, Any]]:
        """Fetch a batch of markets from Gamma API."""
        client = await self._get_client()
        
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        params.update(filters)
        
        try:
            response = await client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching markets: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            raise


# ==================== Data Transformation ====================

def parse_json_string(value: Any) -> Any:
    """Parse JSON-encoded string fields from Gamma API."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def transform_market(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform raw Gamma API response to MongoDB document."""
    
    # Parse JSON string fields
    outcomes = parse_json_string(raw.get("outcomes", "[]"))
    outcome_prices = parse_json_string(raw.get("outcomePrices", "[]"))
    clob_token_ids = parse_json_string(raw.get("clobTokenIds", "[]"))
    tags = parse_json_string(raw.get("tags", "[]"))
    rewards = parse_json_string(raw.get("rewards", "{}"))
    
    return {
        "slug": raw.get("slug", ""),
        "condition_id": raw.get("conditionId"),
        "gamma_id": raw.get("id"),
        "question": raw.get("question", ""),
        "description": raw.get("description"),
        
        "outcomes": outcomes if isinstance(outcomes, list) else [],
        "outcome_prices": outcome_prices if isinstance(outcome_prices, list) else [],
        "clob_token_ids": clob_token_ids if isinstance(clob_token_ids, list) else [],
        
        "volume_num": safe_float(raw.get("volumeNum"), 0.0),
        "volume_24hr": safe_float(raw.get("volume24hr"), 0.0),
        "volume_7d": safe_float(raw.get("volume7d"), 0.0),
        "liquidity_num": safe_float(raw.get("liquidityNum"), 0.0),
        
        "best_bid": safe_float(raw.get("bestBid")),
        "best_ask": safe_float(raw.get("bestAsk")),
        "spread": safe_float(raw.get("spread")),
        
        "closed": raw.get("closed", False) in (True, "true", 1),
        "active": raw.get("active", True) in (True, "true", 1),
        "archived": raw.get("archived", False) in (True, "true", 1),
        
        "end_date_iso": raw.get("endDateIso"),
        "end_date": raw.get("endDateIso"),
        "start_date_iso": raw.get("startDateIso"),
        "created_at": raw.get("createdAt"),
        
        "image": raw.get("image"),
        "icon": raw.get("icon"),
        "tags": tags if isinstance(tags, list) else [],
        "rewards": rewards if isinstance(rewards, dict) else {},
        
        "event_slug": raw.get("eventSlug"),
        "group_slug": raw.get("groupSlug"),
    }


# ==================== MongoDB Operations ====================

async def upsert_markets_batch(
    collection,
    markets: list[dict[str, Any]],
) -> tuple[int, int]:
    """Upsert a batch of markets. Returns (upserted, modified) counts."""
    if not markets:
        return 0, 0
    
    now = datetime.now(timezone.utc)
    operations = []
    
    for raw_market in markets:
        doc = transform_market(raw_market)
        doc["last_synced_at"] = now
        
        operations.append(UpdateOne(
            {"slug": doc["slug"]},
            {
                "$set": doc,
                "$setOnInsert": {"first_synced_at": now},
            },
            upsert=True,
        ))
    
    result = await collection.bulk_write(operations, ordered=False)
    return result.upserted_count, result.modified_count


async def create_indexes(collection):
    """Create indexes for efficient querying."""
    indexes = [
        {"keys": [("slug", 1)], "unique": True},
        {"keys": [("condition_id", 1)]},
        {"keys": [("closed", 1), ("active", 1)]},
        {"keys": [("volume_num", -1)]},
        {"keys": [("volume_24hr", -1)]},
        {"keys": [("liquidity_num", -1)]},
        {"keys": [("last_synced_at", -1)]},
        {"keys": [("question", "text")]},
    ]
    
    for idx in indexes:
        try:
            await collection.create_index(**idx)
        except Exception as e:
            logger.debug(f"Index exists or error: {e}")


# ==================== Sync State Management ====================

class SyncState:
    """Manages sync state for resumable syncs."""
    
    def __init__(self, collection):
        self.collection = collection
    
    async def get_state(self, sync_id: str) -> Optional[dict]:
        """Get current sync state."""
        return await self.collection.find_one({"_id": sync_id})
    
    async def save_state(
        self,
        sync_id: str,
        offset: int,
        total_fetched: int,
        total_upserted: int,
        total_modified: int,
        is_complete: bool = False,
        filters: Optional[dict] = None,
    ):
        """Save sync progress."""
        now = datetime.now(timezone.utc)
        await self.collection.update_one(
            {"_id": sync_id},
            {
                "$set": {
                    "offset": offset,
                    "total_fetched": total_fetched,
                    "total_upserted": total_upserted,
                    "total_modified": total_modified,
                    "is_complete": is_complete,
                    "filters": filters or {},
                    "updated_at": now,
                },
                "$setOnInsert": {"started_at": now},
            },
            upsert=True,
        )
    
    async def clear_state(self, sync_id: str):
        """Clear sync state (for starting fresh)."""
        await self.collection.delete_one({"_id": sync_id})
    
    async def get_last_full_sync(self) -> Optional[datetime]:
        """Get timestamp of last completed full sync."""
        doc = await self.collection.find_one(
            {"_id": "full_sync", "is_complete": True}
        )
        return doc.get("updated_at") if doc else None


# ==================== Main Sync Worker ====================

class MarketSyncWorker:
    """Polymarket market metadata sync worker."""
    
    def __init__(self):
        self.api = GammaAPIClient()
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.running = False
        self.db = None
        self.markets_col = None
        self.sync_state: Optional[SyncState] = None
    
    async def connect(self):
        """Connect to MongoDB."""
        self.mongo_client = AsyncIOMotorClient(config.mongodb_uri)
        
        # Test connection
        await self.mongo_client.admin.command("ping")
        logger.info(f"Connected to MongoDB")
        
        self.db = self.mongo_client[config.markets_db_name]
        self.markets_col = self.db[MARKETS_COLLECTION]
        self.sync_state = SyncState(self.db[SYNC_STATE_COLLECTION])
        
        # Create indexes
        await create_indexes(self.markets_col)
    
    async def disconnect(self):
        """Disconnect from MongoDB and close API client."""
        if self.mongo_client:
            self.mongo_client.close()
        await self.api.close()
        logger.info("Disconnected")
    
    async def sync_markets_incremental(
        self,
        sync_id: str,
        filters: Optional[dict] = None,
        resume: bool = True,
    ) -> dict[str, Any]:
        """
        Sync markets with incremental saves.
        
        Saves each batch to MongoDB as it's fetched.
        Can resume from last offset if interrupted.
        """
        filters = filters or {}
        
        # Check for existing incomplete sync to resume
        offset = 0
        total_fetched = 0
        total_upserted = 0
        total_modified = 0
        
        if resume:
            existing_state = await self.sync_state.get_state(sync_id)
            if existing_state and not existing_state.get("is_complete"):
                offset = existing_state.get("offset", 0)
                total_fetched = existing_state.get("total_fetched", 0)
                total_upserted = existing_state.get("total_upserted", 0)
                total_modified = existing_state.get("total_modified", 0)
                logger.info(f"Resuming {sync_id} from offset {offset} (fetched: {total_fetched})")
        
        start_time = datetime.now(timezone.utc)
        batch_num = offset // config.batch_size
        
        logger.info(f"Starting sync '{sync_id}' with filters: {filters}")
        
        try:
            while self.running:
                batch_num += 1
                
                # Fetch batch from API
                try:
                    batch = await self.api.get_markets(
                        limit=config.batch_size,
                        offset=offset,
                        **filters,
                    )
                except Exception as e:
                    logger.error(f"API error at offset {offset}: {e}")
                    # Save state before exiting so we can resume
                    await self.sync_state.save_state(
                        sync_id, offset, total_fetched, total_upserted, total_modified,
                        is_complete=False, filters=filters,
                    )
                    raise
                
                if not batch:
                    logger.info(f"No more markets to fetch at offset {offset}")
                    break
                
                # Save batch to MongoDB immediately
                upserted, modified = await upsert_markets_batch(self.markets_col, batch)
                
                total_fetched += len(batch)
                total_upserted += upserted
                total_modified += modified
                offset += len(batch)
                
                logger.info(
                    f"Batch {batch_num}: fetched {len(batch)}, "
                    f"upserted {upserted}, modified {modified} "
                    f"(total: {total_fetched})"
                )
                
                # Save sync state after each batch
                await self.sync_state.save_state(
                    sync_id, offset, total_fetched, total_upserted, total_modified,
                    is_complete=False, filters=filters,
                )
                
                # Check if we got fewer than requested (end of data)
                if len(batch) < config.batch_size:
                    logger.info("Reached end of available markets")
                    break
                
                # Small delay to be nice to the API
                await asyncio.sleep(0.2)
            
            # Mark sync as complete
            await self.sync_state.save_state(
                sync_id, offset, total_fetched, total_upserted, total_modified,
                is_complete=True, filters=filters,
            )
            
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            stats = {
                "sync_id": sync_id,
                "total_fetched": total_fetched,
                "total_upserted": total_upserted,
                "total_modified": total_modified,
                "elapsed_seconds": round(elapsed, 2),
                "complete": True,
            }
            
            logger.info(
                f"Sync '{sync_id}' complete: {total_fetched} fetched, "
                f"{total_upserted} new, {total_modified} updated "
                f"in {stats['elapsed_seconds']}s"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Sync '{sync_id}' failed: {e}")
            return {
                "sync_id": sync_id,
                "total_fetched": total_fetched,
                "total_upserted": total_upserted,
                "total_modified": total_modified,
                "complete": False,
                "error": str(e),
            }
    
    async def full_sync(self) -> dict[str, Any]:
        """Run a full sync of all markets."""
        logger.info("=" * 50)
        logger.info("Starting FULL SYNC")
        logger.info("=" * 50)
        
        # Clear previous full sync state to start fresh
        await self.sync_state.clear_state("full_sync")
        
        return await self.sync_markets_incremental(
            sync_id="full_sync",
            filters={},
            resume=False,
        )
    
    async def incremental_sync(self) -> dict[str, Any]:
        """Run an incremental sync (active markets only)."""
        logger.info("Starting incremental sync (active markets)")
        
        # Clear previous incremental state
        await self.sync_state.clear_state("incremental_sync")
        
        return await self.sync_markets_incremental(
            sync_id="incremental_sync",
            filters={"closed": "false", "active": "true"},
            resume=False,
        )
    
    async def should_full_sync(self) -> bool:
        """Determine if a full sync is needed."""
        last_full = await self.sync_state.get_last_full_sync()
        
        if last_full is None:
            return True
        
        # Ensure last_full is timezone-aware (MongoDB may return naive datetime)
        if last_full.tzinfo is None:
            last_full = last_full.replace(tzinfo=timezone.utc)

        elapsed_hours = (
            datetime.now(timezone.utc) - last_full
        ).total_seconds() / 3600
        
        return elapsed_hours >= config.full_sync_interval_hours
    
    async def run(self):
        """Main worker loop."""
        self.running = True
        
        # Check for interrupted sync to resume
        for sync_id in ["full_sync", "incremental_sync"]:
            state = await self.sync_state.get_state(sync_id)
            if state and not state.get("is_complete"):
                logger.info(f"Found interrupted sync '{sync_id}', resuming...")
                await self.sync_markets_incremental(
                    sync_id=sync_id,
                    filters=state.get("filters", {}),
                    resume=True,
                )
        
        # Initial sync if needed
        if await self.should_full_sync():
            await self.full_sync()
        else:
            await self.incremental_sync()
        
        # Main loop
        while self.running:
            try:
                # Wait for next sync interval
                logger.info(f"Sleeping {config.sync_interval_minutes} minutes until next sync...")
                await asyncio.sleep(config.sync_interval_minutes * 60)
                
                if not self.running:
                    break
                
                # Determine sync type
                if await self.should_full_sync():
                    await self.full_sync()
                else:
                    await self.incremental_sync()
                
            except asyncio.CancelledError:
                logger.info("Worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self.running = False


# ==================== Main Entry Point ====================

async def main():
    """Main entry point."""
    worker = MarketSyncWorker()
    
    # Signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig):
        logger.info(f"Received signal {sig.name}")
        worker.stop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: shutdown_handler(s))
    
    try:
        await worker.connect()
        await worker.run()
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)
    finally:
        await worker.disconnect()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Polymarket Market Metadata Sync Worker")
    logger.info(f"Batch size: {config.batch_size}")
    logger.info(f"Sync interval: {config.sync_interval_minutes} minutes")
    logger.info(f"Full sync interval: {config.full_sync_interval_hours} hours")
    logger.info("=" * 60)
    
    asyncio.run(main())
