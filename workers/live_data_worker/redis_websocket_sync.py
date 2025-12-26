import asyncio
import json
import logging
import ssl
import threading
from datetime import datetime, timezone
from websocket import WebSocketApp
import redis

REDIS_HOST = "redis"
REDIS_PORT = 6379
REDIS_STREAM_KEY = "polymarket:market_stream"
REDIS_JSON_KEY = "polymarket:messages_json"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
STREAM_MAX_LEN = 10000

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("worker")

# ---------------- JSON Manager ----------------
class JSONStorageManager:
    def __init__(self, redis_client: redis.Redis, redis_key: str):
        self.redis_client = redis_client
        self.redis_key = redis_key
        self.lock = threading.Lock()
        if not self.redis_client.exists(redis_key):
            self.redis_client.set(redis_key, json.dumps({}))

    def update_orderbook(self, message: dict):
        """
        Update the orderbook for relevant asset_ids.
        Handles full snapshot (bids/asks) or incremental price_changes.
        """
        with self.lock:
            # Load current orderbook
            data = json.loads(self.redis_client.get(self.redis_key) or "{}")

            # Full snapshot: contains bids/asks
            if "bids" in message or "asks" in message:
                asset_id = message.get("asset_id")
                if asset_id:
                    data[asset_id] = {
                        "bids": {str(bid["price"]): str(bid["size"]) for bid in message.get("bids", []) if "price" in bid and "size" in bid},
                        "asks": {str(ask["price"]): str(ask["size"]) for ask in message.get("asks", []) if "price" in ask and "size" in ask}
                    }

            # Incremental updates: price_changes
            elif "price_changes" in message:
                for change in message["price_changes"]:
                    asset_id = change.get("asset_id")
                    if not asset_id:
                        continue

                    # Ensure asset exists
                    if asset_id not in data:
                        data[asset_id] = {"bids": {}, "asks": {}}

                    side = change.get("side", "").upper()
                    price = str(change.get("price"))
                    size = str(change.get("size"))

                    # Map side to bids/asks
                    if side == "BUY":
                        data[asset_id]["bids"][price] = size
                    elif side == "SELL":
                        data[asset_id]["asks"][price] = size

            # Save updated orderbook
            self.redis_client.set(self.redis_key, json.dumps(data))

    def clear(self):
        """Clear the JSON orderbook."""
        with self.lock:
            self.redis_client.set(self.redis_key, json.dumps({}))








# ---------------- WebSocket Manager ----------------
class PolymarketWebSocketManager:
    def __init__(self, redis_client: redis.Redis, json_manager: JSONStorageManager):
        self.redis_client = redis_client
        self.json_manager = json_manager
        self.ws: WebSocketApp | None = None
        self.asset_ids: list[str] = []
        self.paused = False
        self._control_thread: threading.Thread | None = None

    # def on_message(self, ws, message: str):
    #     try:
    #         payload = json.loads(message)
    #     except:
    #         return
    #     items = payload if isinstance(payload, list) else [payload]
    #     for item in items:
    #         if not item or item.get("type") in ("ping", "pong"):
    #             continue
    #         try:
    #             self.redis_client.xadd(
    #                 REDIS_STREAM_KEY,
    #                 {"data": json.dumps(item), "timestamp": datetime.now(timezone.utc).isoformat()},
    #                 maxlen=STREAM_MAX_LEN, approximate=True
    #             )
    #             self.json_manager.add_message(item)
    #         except Exception as e:
    #             logger.error(f"Failed to store message: {e}")





    def on_message(self, ws, message: str):
        try:
            payload = json.loads(message)
        except:
            return

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not item or item.get("type") in ("ping", "pong"):
                continue

            try:
                # Store in Redis Stream (historique limité)
                self.redis_client.xadd(
                    REDIS_STREAM_KEY,
                    {"data": json.dumps(item), "timestamp": datetime.now(timezone.utc).isoformat()},
                    maxlen=STREAM_MAX_LEN, approximate=True
                )
                # Update JSON snapshot orderbook
                self.json_manager.update_orderbook(item)
            except Exception as e:
                logger.error(f"Failed to store/update message: {e}")







    def on_open(self, ws):
        if self.asset_ids:
            ws.send(json.dumps({"assets_ids": self.asset_ids, "type": "market"}))

    def connect(self) -> bool:
        try:
            self.ws = WebSocketApp(
                WS_URL,
                on_message=self.on_message,
                on_error=lambda ws, err: logger.error(f"WS error: {err}"),
                on_close=lambda ws, code, msg: logger.warning(f"WS closed {code} {msg}"),
                on_open=self.on_open
            )
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_REQUIRED})
            return True
        except Exception as e:
            logger.error(f"Failed WS connect: {e}")
            return False

    def disconnect(self):
        if self.ws:
            try: self.ws.close()
            except: pass

    def start_control_listener(self, channel="live-data-control"):
        if self._control_thread and self._control_thread.is_alive():
            return

        def _listen():
            pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to control channel '{channel}'")
            for message in pubsub.listen():
                if not message or not message.get("data"):
                    continue
                data = message["data"]
                try:
                    payload = json.loads(data.decode() if isinstance(data, bytes) else data)
                except: continue

                # Stop request: pause + clear data
                if payload.get("stop"):
                    logger.info("Control stop requested, clearing data")
                    self.paused = True
                    try: self.redis_client.delete(REDIS_STREAM_KEY)
                    except: pass
                    try: self.json_manager.clear()
                    except: pass
                    if self.ws:
                        try: self.ws.close()
                        except: pass
                    continue

                # Start / update asset_ids
                new_ids = payload.get("asset_ids") or payload.get("assets_ids")
                if new_ids:
                    self.asset_ids = [str(a).strip() for a in new_ids if a]
                    self.paused = False
                    if self.ws:
                        try: self.ws.send(json.dumps({"assets_ids": self.asset_ids, "type": "market"}))
                        except: pass

        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        self._control_thread = t

# ---------------- Worker ----------------
class RedisWebSocketWorker:
    def __init__(self):
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self.json_manager = JSONStorageManager(self.redis_client, REDIS_JSON_KEY)
        self.ws_manager = PolymarketWebSocketManager(self.redis_client, self.json_manager)
        self.running = True
        self._paused_logged = False

    async def run_with_reconnect(self):
        reconnect_delay = 1
        max_reconnect_delay = 60
        while self.running:
            if self.ws_manager.paused:
                if not self._paused_logged:
                    logger.info("Worker paused; awaiting asset_ids")
                    self._paused_logged = True
                await asyncio.sleep(2)
                continue
            else:
                if self._paused_logged:
                    logger.info("Worker resuming")
                    self._paused_logged = False

            try:
                if not self.ws_manager.ws or not getattr(self.ws_manager.ws, "sock", None) or not self.ws_manager.ws.sock.connected:
                    logger.info("Connecting WS...")
                    self.ws_manager.connect()
                reconnect_delay = 1
            except Exception as e:
                logger.error(f"WS connection error: {e}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    async def run(self):
        self.ws_manager.start_control_listener()
        await self.run_with_reconnect()

    def stop(self):
        self.running = False
        self.ws_manager.disconnect()

# ---------------- Main ----------------
if __name__ == "__main__":
    worker = RedisWebSocketWorker()
    asyncio.run(worker.run())
