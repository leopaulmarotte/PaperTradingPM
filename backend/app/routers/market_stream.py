from fastapi import APIRouter, Query
import os
import json
import redis


# from app.services.redis_stream_service import MarketMessageTransformer


router = APIRouter(prefix="/market-stream", tags=["Market Stream"])

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "polymarket:market_stream")
REDIS_JSON_KEY = os.getenv("REDIS_JSON_KEY", "polymarket:messages_json")
REDIS_PAUSE_KEY = os.getenv("REDIS_PAUSE_KEY", "polymarket:worker_paused")

_redis_pub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
_redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@router.post("/start")
async def start_stream(asset_id: str = Query(..., description="Asset ID to stream")):
    try:
        # Clear pause flag
        _redis_client.delete(REDIS_PAUSE_KEY)
        # Publish asset_ids to control channel
        _redis_pub.publish("live-data-control", json.dumps({"asset_ids": asset_id.split(',')}))
        return {
            "status": "started",
            "asset_id": asset_id,
            "message": f"Streaming started for asset {asset_id}"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/stop")
async def stop_stream():
    try:
        # Set pause flag
        _redis_client.set(REDIS_PAUSE_KEY, "1")
        # Publish stop
        _redis_pub.publish("live-data-control", json.dumps({"stop": True}))
        return {"status": "stopped", "message": "Stop command sent and data cleared"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/messages")
async def get_messages():
    try:
        data = _redis_client.get(REDIS_JSON_KEY)
        messages = json.loads(data) if data else []
        return {"status": "ok", "count": len(messages), "messages": messages}
    except Exception as e:
        return {"status": "error", "message": str(e), "messages": []}



@router.get("/latest")
async def get_latest_message():
    try:
        msgs = _redis_client.xrevrange(REDIS_STREAM_KEY, count=1)
        if msgs:
            entry_id, fields = msgs[0]
            return {"status": "ok", "message": json.loads(fields.get("data", "{}"))}
        return {"status": "no_data", "message": None}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# from app.services.redis_stream_service import MarketMessageTransformer


# @router.get("/messages-test")
# async def get_messages():
#     try:
#         data = _redis_client.get(REDIS_JSON_KEY)
#         messages = json.loads(data) if data else []

#         messages = MarketMessageTransformer.normalize_messages(messages)

#         return {
#             "status": "ok",
#             "count": len(messages),
#             "messages": messages,
#         }

#     except Exception as e:
#         return {
#             "status": "error",
#             "message": str(e),
#             "messages": [],
#         }
