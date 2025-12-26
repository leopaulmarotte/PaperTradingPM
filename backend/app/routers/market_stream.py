"""
Router for market stream data endpoints (from WebSocket -> Redis).
"""
from fastapi import APIRouter, Query, Body
from app.services.redis_stream_service import RedisStreamService
import os
import json
import redis

router = APIRouter(prefix="/market-stream", tags=["Market Stream"])
stream_service = RedisStreamService()
_redis_pub = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", 6379)), decode_responses=True)


@router.get("/recent")
async def get_recent_market_data(
    asset_id: str = Query(..., description="Asset ID to subscribe to and receive data from"),
    count: int = Query(50, ge=1, le=1000, description="Number of recent messages"),
):
    """
    Get recent market data from the WebSocket stream for a specific asset.
    
    Providing an asset_id triggers the WebSocket worker to subscribe to that asset
    and start streaming data to Redis.
    
    **Query Parameters:**
    - `asset_id`: Asset ID to subscribe to (required) - triggers WebSocket streaming
    - `count`: Number of messages to retrieve (default: 50, max: 1000)
    
    **Response:**
    ```json
    [
        {
            "id": "1703430000000-0",
            "timestamp": "2025-12-24T10:00:00.000Z",
            "data": {
                "type": "market",
                "assets_ids": ["..."],
                ...
            }
        }
    ]
    ```
    """
    # Update the worker subscription for this asset
    try:
        _redis_pub.publish(
            "live-data-control",
            json.dumps({"asset_ids": [asset_id]})
        )
    except Exception as e:
        # Log but don't fail - still return messages even if control fails
        print(f"Warning: Failed to update worker subscription: {e}")
    
    # Return messages filtered by asset_id
    return stream_service.get_messages_by_asset(asset_id=asset_id, count=count)








@router.get("/health")
async def health_check():
    """
    Health check for Redis connection.
    """
    if stream_service.test_connection():
        return {
            "status": "ok",
            "message": "Redis stream service is healthy",
        }
    else:
        return {
            "status": "error",
            "message": "Redis connection failed",
        }


