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
    count: int = Query(50, ge=1, le=1000, description="Number of recent messages"),
):
    """
    Get recent market data from the WebSocket stream.
    
    Returns the most recent N messages stored in Redis from the live WebSocket connection.
    
    **Query Parameters:**
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
    return stream_service.get_recent_messages(count=count)


@router.get("/since/{last_id}")
async def get_messages_since(
    last_id: str,  # path parameter (do not use Query for path params)
    count: int = Query(50, ge=1, le=1000),
):
    """
    Get market data messages after a specific stream ID.
    
    Useful for pagination / resuming from a known point.
    
    **Path Parameters:**
    - `last_id`: Stream entry ID (format: timestamp-sequence)
    
    **Query Parameters:**
    - `count`: Number of messages to retrieve
    """
    return stream_service.get_messages_since(last_id=last_id, count=count)


@router.get("/info")
async def get_stream_info():
    """
    Get stream metadata and statistics.
    
    Returns:
    - `length`: Total number of messages in stream
    - `first_entry_id`: ID of oldest message
    - `last_entry_id`: ID of newest message
    """
    return stream_service.get_stream_info()


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


@router.post("/control")
async def publish_control(payload: dict = Body(...)):
    """Publish a control message to the worker via Redis pub/sub.

    Expected body example:
    {
        "asset_ids": ["id1", "id2"]
    }
    """
    try:
        _redis_pub.publish("live-data-control", json.dumps(payload))
        return {"status": "ok", "message": "control published"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
