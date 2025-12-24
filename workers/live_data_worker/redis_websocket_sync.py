#!/usr/bin/env python3
"""
Redis WebSocket Sync Worker

Connects to Polymarket WebSocket, streams market data updates,
and stores them in Redis streams for real-time consumption.

Designed for resilience:
- Reconnects automatically on WebSocket close/error
- Stores data incrementally to Redis stream
- Graceful shutdown handling

Usage:
    python redis_websocket_sync.py

Environment Variables:
    REDIS_HOST: Redis host (default: redis)
    REDIS_PORT: Redis port (default: 6379)
    CLOB_URL: CLOB API URL (not used in this worker but kept for compatibility)
    API_KEY: API key (not used in this worker but kept for compatibility)
    ASSET_IDS: Comma-separated asset IDs to subscribe to
    LOG_LEVEL: Logging level (default: INFO)
    WS_URL: WebSocket URL (default: wss://ws-subscriptions-clob.polymarket.com/ws/market)
    REDIS_STREAM_KEY: Redis stream key (default: polymarket:market_stream)
    STREAM_MAX_LEN: Max entries in Redis stream (default: 10000)
"""

import asyncio
import json
import logging
import signal
import sys
import ssl
from datetime import datetime, timezone
from typing import Optional

import certifi
import redis
import redis.asyncio as aioredis
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from websocket import WebSocketApp, WebSocketException


# ==================== Configuration ====================

class WorkerConfig(BaseSettings):
    """Worker configuration from environment."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Redis
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    
    # WebSocket
    ws_url: str = Field(default="wss://ws-subscriptions-clob.polymarket.com/ws/market")
    asset_ids: str = Field(
        default="92703761682322480664976766247614127878023988651992837287050266308961660624165"
    )
    
    # Redis Stream
    redis_stream_key: str = Field(default="polymarket:market_stream")
    stream_max_len: int = Field(default=10000)
    
    # Compatibility
    clob_url: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    
    # Logging
    log_level: str = Field(default="INFO")


config = WorkerConfig()


# ==================== Logging Setup ====================

logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("redis_websocket_sync")


# ==================== Data Transformation ====================

def transform_market_update(raw: dict) -> dict:
    """Transform raw WebSocket message for storage."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": raw,
    }


# ==================== Redis Stream Manager ====================

class RedisStreamManager:
    """Manages Redis stream connections and operations."""
    
    def __init__(self, host: str, port: int, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        
        # Sync client for blocking operations
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
        )
        
        # Async client for non-blocking operations
        self.async_client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis (async)."""
        self.async_client = await aioredis.from_url(
            f"redis://{self.host}:{self.port}/{self.db}",
            encoding="utf8",
            decode_responses=True,
        )
        
        # Test connection
        await self.async_client.ping()
        logger.info(f"Connected to Redis at {self.host}:{self.port}")
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.async_client:
            await self.async_client.close()
    
    async def add_to_stream(
        self,
        stream_key: str,
        data: dict,
        max_len: int = 10000,
    ) -> str:
        """Add entry to Redis stream."""
        # Flatten dict for XADD
        fields = {
            "data": json.dumps(data.get("data", {})),
            "timestamp": data.get("timestamp", ""),
        }
        
        # XADD with MAXLEN
        entry_id = await self.async_client.xadd(
            stream_key,
            fields,
            maxlen=max_len,
            approximate=True,
        )
        
        return entry_id
    
    def test_connection_sync(self) -> bool:
        """Test Redis connection (sync)."""
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False


# ==================== WebSocket Manager ====================

class PolymarketWebSocketManager:
    """Manages WebSocket connection to Polymarket."""
    
    def __init__(self, redis_manager: RedisStreamManager):
        self.redis_manager = redis_manager
        self.ws: Optional[WebSocketApp] = None
        self.running = False
        self.asset_ids = [
            a.strip() for a in config.asset_ids.split(",") if a.strip()
        ]
    
    def on_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON message: {message}")
            return
        
        # Skip empty or control messages
        if not data or data.get("type") in ("ping", "pong"):
            return
        
        # Store in Redis asynchronously
        try:
            # Use sync client for simplicity (WebSocket callback is not async)
            fields = {
                "data": json.dumps(data),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            self.redis_manager.client.xadd(
                config.redis_stream_key,
                fields,
                maxlen=config.stream_max_len,
                approximate=True,
            )
            
            logger.debug(f"Stored message: {data.get('type', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error storing message in Redis: {e}")
    
    def on_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.warning(
            f"WebSocket closed (code: {close_status_code}, msg: {close_msg})"
        )
    
    def on_open(self, ws):
        """Handle WebSocket open."""
        logger.info(f"WebSocket connected, subscribing to assets: {self.asset_ids}")
        
        # Subscribe to market data for specified assets
        subscribe_msg = {
            "assets_ids": self.asset_ids,
            "type": "market",
        }
        
        try:
            ws.send(json.dumps(subscribe_msg))
            logger.info("Subscription message sent")
        except Exception as e:
            logger.error(f"Error sending subscription: {e}")
    
    def connect(self) -> bool:
        """Connect to WebSocket and start receiving."""
        try:
            logger.info(f"Connecting to WebSocket: {config.ws_url}")
            
            self.ws = WebSocketApp(
                config.ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open,
            )
            
            # Run in foreground (blocking)
            self.ws.run_forever(
                sslopt={
                    "cert_reqs": ssl.CERT_REQUIRED,
                    "ca_certs": certifi.where(),
                }
            )
            
            return True
            
        except WebSocketException as e:
            logger.error(f"WebSocket exception: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from WebSocket."""
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")


# ==================== Main Worker ====================

class RedisWebSocketWorker:
    """Main worker coordinating WebSocket and Redis."""
    
    def __init__(self):
        self.redis_manager = RedisStreamManager(
            config.redis_host,
            config.redis_port,
            config.redis_db,
        )
        self.ws_manager = PolymarketWebSocketManager(self.redis_manager)
        self.running = False
    
    async def initialize(self):
        """Initialize Redis connection."""
        # Test sync connection first
        if not self.redis_manager.test_connection_sync():
            raise RuntimeError("Failed to connect to Redis")
        
        # Initialize async connection
        await self.redis_manager.connect()
    
    async def cleanup(self):
        """Cleanup resources."""
        self.ws_manager.disconnect()
        await self.redis_manager.disconnect()
    
    async def run_with_reconnect(self):
        """Run WebSocket with automatic reconnection."""
        self.running = True
        reconnect_delay = 1  # Start with 1 second delay
        max_reconnect_delay = 60  # Cap at 60 seconds
        
        while self.running:
            try:
                logger.info("Starting WebSocket connection...")
                
                # Run WebSocket (blocking call)
                if not self.ws_manager.connect():
                    raise RuntimeError("WebSocket connection failed")
                
                # Reset delay on successful connection
                reconnect_delay = 1
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Connection error: {e}")
                
                if not self.running:
                    break
                
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
                
                # Exponential backoff
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    async def run(self):
        """Main async entry point."""
        try:
            await self.initialize()
            await self.run_with_reconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)
        finally:
            await self.cleanup()
    
    def stop(self):
        """Stop the worker."""
        logger.info("Stopping worker...")
        self.running = False
        self.ws_manager.disconnect()


# ==================== Main Entry Point ====================

async def main():
    """Main entry point."""
    worker = RedisWebSocketWorker()
    
    # Signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig):
        logger.info(f"Received signal {sig.name}")
        worker.stop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: shutdown_handler(s))
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Redis WebSocket Sync Worker")
    logger.info(f"Redis: {config.redis_host}:{config.redis_port}")
    logger.info(f"WebSocket: {config.ws_url}")
    logger.info(f"Asset IDs: {config.asset_ids}")
    logger.info(f"Stream key: {config.redis_stream_key}")
    logger.info("=" * 60)
    
    asyncio.run(main())
