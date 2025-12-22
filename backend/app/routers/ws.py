"""
WebSocket router for real-time live data streaming.
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError

from app.core.security import decode_token
from app.database.connections import get_mongo_client
from app.database.databases import auth_db
from app.services.auth_service import AuthService
from app.services.cache import CacheService

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """
    Manages active WebSocket connections.
    """
    
    def __init__(self):
        # Map of user_id -> WebSocket connection
        self.active_connections: dict[str, WebSocket] = {}
        # Map of user_id -> subscribed market_ids
        self.subscriptions: dict[str, set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept connection and register user."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.subscriptions[user_id] = set()
    
    def disconnect(self, user_id: str) -> None:
        """Remove user connection and subscriptions."""
        self.active_connections.pop(user_id, None)
        self.subscriptions.pop(user_id, None)
    
    def subscribe(self, user_id: str, market_ids: list[str]) -> None:
        """Subscribe user to market updates."""
        if user_id in self.subscriptions:
            self.subscriptions[user_id].update(market_ids)
    
    def unsubscribe(self, user_id: str, market_ids: list[str]) -> None:
        """Unsubscribe user from market updates."""
        if user_id in self.subscriptions:
            self.subscriptions[user_id].difference_update(market_ids)
    
    def get_subscribed_users(self, market_id: str) -> list[str]:
        """Get all users subscribed to a market."""
        return [
            user_id for user_id, markets in self.subscriptions.items()
            if market_id in markets
        ]
    
    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """Send message to specific user."""
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception:
                return False
        return False
    
    async def broadcast_to_market(self, market_id: str, message: dict) -> None:
        """Broadcast message to all users subscribed to a market."""
        for user_id in self.get_subscribed_users(market_id):
            await self.send_to_user(user_id, message)


# Global connection manager
manager = ConnectionManager()


async def validate_token(token: str) -> Optional[str]:
    """
    Validate JWT token and return user_id if valid.
    
    Args:
        token: JWT access token
        
    Returns:
        User ID if token is valid, None otherwise
    """
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        # Verify user exists and is active
        client = await get_mongo_client()
        db = client[auth_db.DB_NAME]
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_id(user_id)
        
        if not user or user.status != "active":
            return None
        
        return user_id
        
    except JWTError:
        return None


@router.websocket("/ws/live")
async def websocket_live_data(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time market data.
    
    **Connection**: Connect with `?token=xxx` query parameter.
    
    **Messages from client**:
    ```json
    {"action": "subscribe", "market_ids": ["market-slug-1", "market-slug-2"]}
    {"action": "unsubscribe", "market_ids": ["market-slug-1"]}
    {"action": "ping"}
    ```
    
    **Messages from server**:
    ```json
    {"type": "connected", "user_id": "..."}
    {"type": "subscribed", "market_ids": [...]}
    {"type": "unsubscribed", "market_ids": [...]}
    {"type": "orderbook", "market_id": "...", "outcome": "...", "data": {...}}
    {"type": "price", "market_id": "...", "outcome": "...", "price": ...}
    {"type": "pong"}
    {"type": "error", "message": "..."}
    ```
    
    **Disconnection**: Connection closes on invalid/expired token or explicit close.
    """
    # Validate token before accepting connection
    user_id = await validate_token(token)
    
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Accept connection
    await manager.connect(websocket, user_id)
    
    await websocket.send_json({
        "type": "connected",
        "user_id": user_id,
        "message": "Connected to live data stream",
    })
    
    # Start background task to push live data
    push_task = asyncio.create_task(push_live_data(user_id, websocket))
    
    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "subscribe":
                market_ids = data.get("market_ids", [])
                if market_ids:
                    manager.subscribe(user_id, market_ids)
                    await websocket.send_json({
                        "type": "subscribed",
                        "market_ids": market_ids,
                    })
            
            elif action == "unsubscribe":
                market_ids = data.get("market_ids", [])
                if market_ids:
                    manager.unsubscribe(user_id, market_ids)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "market_ids": market_ids,
                    })
            
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                })
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e),
        })
    finally:
        # Cleanup
        push_task.cancel()
        manager.disconnect(user_id)


async def push_live_data(user_id: str, websocket: WebSocket) -> None:
    """
    Background task to push live data updates to a connected user.
    
    TODO: Implement with Redis pub/sub once worker sets up Redis.
    Currently a placeholder that does nothing.
    """
    cache_service = CacheService()
    
    # TODO: Implement with Redis pub/sub
    # This would subscribe to Redis channels and push updates to the WebSocket
    #
    # async for update in cache_service.subscribe_to_updates(market_ids):
    #     if user_id not in manager.active_connections:
    #         break
    #     
    #     subscribed = manager.subscriptions.get(user_id, set())
    #     if update.get("market_id") in subscribed:
    #         await websocket.send_json({
    #             "type": update.get("type", "update"),
    #             "market_id": update.get("market_id"),
    #             "outcome": update.get("outcome"),
    #             "data": update.get("data"),
    #         })
    
    # Placeholder: keep task alive but do nothing
    try:
        while True:
            await asyncio.sleep(30)  # Heartbeat interval
            
            # Check if user is still connected
            if user_id not in manager.active_connections:
                break
            
            # TODO: Fetch and push live data for subscribed markets
            # subscribed = manager.subscriptions.get(user_id, set())
            # for market_id in subscribed:
            #     prices = await cache_service.get_all_live_prices(market_id)
            #     if prices:
            #         await websocket.send_json({
            #             "type": "prices",
            #             "market_id": market_id,
            #             "data": prices,
            #         })
            
    except asyncio.CancelledError:
        pass
