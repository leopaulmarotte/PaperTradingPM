"""
Service for reading from Redis streams (WebSocket market data).
"""
import json
import os
from typing import Any, Optional

import redis


class RedisStreamService:
    """Service to read from Redis market data streams."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
        self.stream_key = "polymarket:market_stream"
    
    def test_connection(self) -> bool:
        """Test Redis connection."""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def get_recent_messages(self, count: int = 50) -> list[dict[str, Any]]:
        """
        Get the most recent messages from the stream.
        
        Args:
            count: Number of messages to retrieve (default: 50)
            
        Returns:
            List of message dicts with timestamp and data
        """
        try:
            # XREVRANGE gets messages in reverse order (most recent first)
            messages = self.redis_client.xrevrange(
                self.stream_key,
                count=count,
            )
            
            result = []
            for entry_id, fields in messages:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    timestamp = fields.get("timestamp", "")
                    
                    result.append({
                        "id": entry_id,
                        "timestamp": timestamp,
                        "data": data,
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
            
            return result
        except Exception as e:
            raise RuntimeError(f"Failed to read from Redis stream: {e}")
    
    def get_messages_since(self, last_id: str = "0", count: int = 50) -> list[dict[str, Any]]:
        """
        Get messages after a specific stream ID.
        
        Args:
            last_id: Stream ID to start from (default: "0" for beginning)
            count: Max messages to retrieve
            
        Returns:
            List of message dicts
        """
        try:
            messages = self.redis_client.xrange(
                self.stream_key,
                min=f"({last_id}",  # Exclusive lower bound
                count=count,
            )
            
            result = []
            for entry_id, fields in messages:
                try:
                    data = json.loads(fields.get("data", "{}"))
                    timestamp = fields.get("timestamp", "")
                    
                    result.append({
                        "id": entry_id,
                        "timestamp": timestamp,
                        "data": data,
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
            
            return result
        except Exception as e:
            raise RuntimeError(f"Failed to read from Redis stream: {e}")
    
    def get_stream_info(self) -> dict[str, Any]:
        """Get stream statistics."""
        try:
            info = self.redis_client.xinfo_stream(self.stream_key)
            return {
                "length": info.get("length", 0),
                "first_entry_id": info.get("first-entry", [None])[0],
                "last_entry_id": info.get("last-entry", [None])[0],
            }
        except Exception as e:
            return {"error": str(e)}
