from fastapi import APIRouter, Depends, HTTPException, Query, status
import os
import json
import redis
from typing import Annotated, Optional
from app.dependencies.auth import get_current_active_user
from app.models.user import User




router = APIRouter(prefix="/market-stream", tags=["Market Stream"])

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "polymarket:market_stream")
REDIS_JSON_KEY = os.getenv("REDIS_JSON_KEY", "polymarket:messages_json")
REDIS_PAUSE_KEY = os.getenv("REDIS_PAUSE_KEY", "polymarket:worker_paused")

_redis_pub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
_redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@router.post(
    "/start/{asset_id}",
    summary="Start live data stream",
)
async def start_stream(
    asset_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Start streaming live data for one or more assets.

    Requires valid token as query parameter: `?token=xxx`
    """
    try:
        # Clear pause flag
        _redis_client.delete(REDIS_PAUSE_KEY)

        # Publish asset_ids to control channel
        _redis_pub.publish(
            "live-data-control",
            json.dumps({"asset_ids": asset_id.split(",")})
        )

        return {
            "status": "started",
            "asset_id": asset_id,
            "message": f"Streaming started for asset {asset_id}",
            "started_by": current_user.id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )






@router.post(
    "/stop",
    summary="Stop live data stream",
)
async def stop_stream(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Stop live data streaming.

    Requires valid token as query parameter: `?token=xxx`
    """
    try:
        # Set pause flag
        _redis_client.set(REDIS_PAUSE_KEY, "1")

        # Publish stop
        _redis_pub.publish(
            "live-data-control",
            json.dumps({"stop": True})
        )

        return {
            "status": "stopped",
            "message": "Stop command sent and data cleared",
            "stopped_by": current_user.id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )




@router.get(
    "/orderbook",
    summary="Get all streamed messages",
)
async def get_messages(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Retrieve all stored streamed messages.

    Requires valid token as query parameter: `?token=xxx`
    """
    try:
        data = _redis_client.get(REDIS_JSON_KEY)
        messages = json.loads(data) if data else []

        return {
            "status": "ok",
            "count": len(messages),
            "messages": messages,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/latest",
    summary="Get latest streamed message",
)
async def get_latest_message(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Retrieve the latest streamed message.

    Requires valid token as query parameter: `?token=xxx`
    """
    try:
        msgs = _redis_client.xrevrange(REDIS_STREAM_KEY, count=1)

        if msgs:
            entry_id, fields = msgs[0]
            return {
                "status": "ok",
                "message": json.loads(fields.get("data", "{}")),
            }

        return {
            "status": "no_data",
            "message": None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
