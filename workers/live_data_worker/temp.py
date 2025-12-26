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
from pathlib import Path
from typing import Optional

import certifi
import redis
import redis.asyncio as aioredis
import threading
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
        default="92703761682322480664976766247614127878023988651992837287050266308961660624165,48193521645113703700467246669338225849301704920590102230072263970163239985027"
    )
    
    # Redis Stream
    redis_stream_key: str = Field(default="polymarket:market_stream")
    stream_max_len: int = Field(default=10000)
    
    # Redis JSON Storage (shared across containers)
    redis_json_key: str = Field(default="polymarket:messages_json")
    
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


# ==================== JSON Storage Manager ====================

class JSONStorageManager:
    """Manages JSON storage in Redis (shared across containers)."""
    
    def __init__(self, redis_client: redis.Redis, redis_key: str):
        self.redis_client = redis_client
        self.redis_key = redis_key
        self.lock = threading.Lock()
        # Initialize empty list if doesn't exist
        try:
            if not self.redis_client.exists(redis_key):
                self.redis_client.set(redis_key, json.dumps([]))
        except Exception as e:
            logger.error(f"Failed to initialize Redis JSON: {e}")
    
    def add_message(self, message: dict) -> None:
        """Add a message to Redis (thread-safe)."""
        with self.lock:
            try:
                # Get current data
                current_json = self.redis_client.get(self.redis_key)
                if current_json:
                    data = json.loads(current_json)
                else:
                    data = []
                
                # Add new message
                data.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": message
                })
                
                # Save back to Redis
                self.redis_client.set(self.redis_key, json.dumps(data))
            except Exception as e:
                logger.error(f"Failed to add message to Redis: {e}")
    
    def clear(self) -> None:
        """Clear all messages."""
        with self.lock:
            try:
                self.redis_client.set(self.redis_key, json.dumps([]))
            except Exception as e:
                logger.error(f"Failed to clear Redis JSON: {e}")
    
    def get_messages(self) -> list:
        """Get all messages."""
        with self.lock:
            try:
                current_json = self.redis_client.get(self.redis_key)
                return json.loads(current_json) if current_json else []
            except Exception as e:
                logger.error(f"Failed to read messages from Redis: {e}")
                return []


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
    
    def __init__(self, redis_manager: RedisStreamManager, json_manager: JSONStorageManager):
        self.redis_manager = redis_manager
        self.json_manager = json_manager
        self.ws: Optional[WebSocketApp] = None
        self.running = False
        self.asset_ids = [
            a.strip() for a in config.asset_ids.split(",") if a.strip()
        ]

        self._control_thread: Optional[threading.Thread] = None
        self._stop_requested = False
    
    def on_message(self, ws, message: str):
        """Handle WebSocket message - store in Redis stream AND JSON file."""
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("Non-JSON message")
            return
        
        # Handle both list and dict payloads
        items = payload if isinstance(payload, list) else [payload]
        
        for item in items:
            # Skip empty messages and pings
            if not item or (isinstance(item, dict) and item.get("type") in ("ping", "pong")):
                continue
            
            try:
                # Store message directly in Redis stream
                entry_id = self.redis_manager.client.xadd(
                    config.redis_stream_key,
                    {
                        "data": json.dumps(item),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    maxlen=config.stream_max_len,
                    approximate=True,
                )
                logger.debug(f"Added to stream: {entry_id}")
                
                # Also store in JSON file
                self.json_manager.add_message(item)
                logger.debug(f"Added to JSON storage")
                
            except Exception as e:
                logger.error(f"Failed to add to stream/JSON: {e}")


    
    def on_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.warning(
            f"WebSocket closed (code: {close_status_code}, msg: {close_msg})"
        )

        # When the WebSocket connection closes, clear Redis to remove
        # any temporarily-stored market data so other services start
        # from a clean state. Use the synchronous client here because
        # this callback runs in the WebSocket thread.
        try:
            logger.info("Flushing all Redis databases due to WebSocket close")
            try:
                # Flush all databases (be cautious: this removes all keys)
                self.redis_manager.client.flushall()
                logger.info("Redis FLUSHALL completed")
            except Exception as e:
                logger.error(f"Failed to flush Redis sync client: {e}")

            # Also clear the JSON storage key (best-effort)d
            try:
                self.json_manager.clear()
                logger.info("Cleared JSON storage key")
            except Exception as e:
                logger.error(f"Failed to clear JSON storage: {e}")

        except Exception as e:
            logger.error(f"Error during on_close cleanup: {e}")
    
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






    def start_control_listener(self, channel: str = "live-data-control"):
        """Start a background thread subscribing to a Redis pub/sub channel."""
        if self._control_thread and self._control_thread.is_alive():
            return

        def _listen():
            try:
                pubsub = self.redis_manager.client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(channel)
                logger.info(f"Control listener subscribed to Redis channel '{channel}'")

                for message in pubsub.listen():
                    if message is None:
                        continue
                    data = message.get("data")
                    if not data:
                        continue
                    try:
                        payload = json.loads(data.decode()) if isinstance(data, bytes) else json.loads(data)
                    except Exception:
                        logger.debug(f"Control message not JSON: {data}")
                        continue

                    # Handle stop request temporarily
                    if payload.get("stop"):
                        logger.info("Control: stop requested")
                        self.paused = True
                        if self.ws:
                            try:
                                unsubscribe_msg = {"assets_ids": self.asset_ids, "type": "unsubscribe"}
                                self.ws.send(json.dumps(unsubscribe_msg))
                            except:
                                pass
                            try:
                                self.ws.close()
                                logger.info("WebSocket closed by control stop request")
                            except:
                                pass
                        # Do NOT clear asset_ids, keep them to allow automatic reconnect on start
                        continue

                    # Handle new asset_ids to resume streaming
                    new_ids = payload.get("asset_ids") or payload.get("assets_ids")
                    if not new_ids:
                        continue
                    new_ids = [str(a).strip() for a in new_ids if a]
                    if not new_ids:
                        continue

                    if new_ids != self.asset_ids:
                        old_ids = self.asset_ids.copy()
                        self.asset_ids = new_ids
                        self.paused = False  # allow reconnection
                        logger.info(f"Control: updating asset_ids from {old_ids} to {self.asset_ids}")

                        # Send subscription update if WS is connected
                        if self.ws:
                            try:
                                if old_ids:
                                    unsubscribe_msg = {"assets_ids": old_ids, "type": "unsubscribe"}
                                    self.ws.send(json.dumps(unsubscribe_msg))
                                subscribe_msg = {"assets_ids": self.asset_ids, "type": "market"}
                                self.ws.send(json.dumps(subscribe_msg))
                            except Exception as e:
                                logger.error(f"Failed to send subscription update: {e}")

            except Exception as e:
                logger.error(f"Control listener error: {e}")

        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        self._control_thread = t







# ==================== Main Worker ====================

class RedisWebSocketWorker:
    """Main worker coordinating WebSocket and Redis."""
    
    def __init__(self):
        self.redis_manager = RedisStreamManager(
            config.redis_host,
            config.redis_port,
            config.redis_db,
        )
        self.json_manager = JSONStorageManager(
            self.redis_manager.client,
            config.redis_json_key
        )
        self.ws_manager = PolymarketWebSocketManager(self.redis_manager, self.json_manager)
        self.running = False
        # Track whether we've already logged the paused state to avoid spam
        self._paused_logged = False
    
    async def initialize(self):
        """Initialize Redis connection."""
        # Test sync connection first
        if not self.redis_manager.test_connection_sync():
            raise RuntimeError("Failed to connect to Redis")
        
        # Initialize async connection
        await self.redis_manager.connect()
        # If a persistent pause flag is set in Redis, honor it and avoid connecting.
        try:
            pause_flag = self.redis_manager.client.get("polymarket:worker_paused")
            if pause_flag:
                self.ws_manager._stop_requested = True
                logger.info("Worker initialized in paused state (polymarket:worker_paused)")
        except Exception:
            logger.debug("Could not read pause flag from Redis")
        # Start control listener to accept dynamic subscription updates
        try:
            self.ws_manager.start_control_listener()
        except Exception:
            logger.warning("Could not start control listener")
    
    async def cleanup(self):
        """Cleanup resources."""
        self.ws_manager.disconnect()
        await self.redis_manager.disconnect()
    



    async def run_with_reconnect(self):
        """Run WebSocket with automatic reconnection."""
        self.running = True
        reconnect_delay = 1
        max_reconnect_delay = 60

        while self.running:
            paused = getattr(self.ws_manager, "paused", False)

            if paused:
                if not getattr(self, "_paused_logged", False):
                    logger.info("Worker is paused; awaiting new asset_ids to resume")
                    self._paused_logged = True
                await asyncio.sleep(2)
                continue
            else:
                if getattr(self, "_paused_logged", False):
                    logger.info("Worker resuming from paused state")
                    self._paused_logged = False

            try:
                # Connect only if WS is None or disconnected
                if not self.ws_manager.ws or not getattr(self.ws_manager.ws, "sock", None) or not self.ws_manager.ws.sock.connected:
                    logger.info("Starting WebSocket connection...")
                    if not self.ws_manager.connect():
                        raise RuntimeError("WebSocket connection failed")
                reconnect_delay = 1

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if getattr(self.ws_manager, "paused", False):
                    await asyncio.sleep(1)
                    continue
                if not self.running:
                    break
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
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
