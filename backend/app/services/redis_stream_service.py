# # """
# # Service for reading from Redis streams (WebSocket market data).
# # """
# # import json
# # import os
# # from typing import Any, Optional

# # import redis


# # class RedisStreamService:
# #     """Service to read from Redis market data streams."""
    
# #     def __init__(self):
# #         self.redis_client = redis.Redis(
# #             host=os.getenv("REDIS_HOST", "redis"),
# #             port=int(os.getenv("REDIS_PORT", 6379)),
# #             decode_responses=True,
# #         )
# #         self.stream_key = "polymarket:market_stream"
    
# #     def test_connection(self) -> bool:
# #         """Test Redis connection."""
# #         try:
# #             self.redis_client.ping()
# #             return True
# #         except Exception:
# #             return False
    
# #     def get_recent_messages(self, count: int = 50) -> list[dict[str, Any]]:
# #         """
# #         Get the most recent messages from the stream.
        
# #         Args:
# #             count: Number of messages to retrieve (default: 50)
            
# #         Returns:
# #             List of message dicts with timestamp and data
# #         """
# #         try:
# #             # XREVRANGE gets messages in reverse order (most recent first)
# #             messages = self.redis_client.xrevrange(
# #                 self.stream_key,
# #                 count=count,
# #             )
            
# #             result = []
# #             for entry_id, fields in messages:
# #                 try:
# #                     data = json.loads(fields.get("data", "{}"))
# #                     timestamp = fields.get("timestamp", "")
                    
# #                     result.append({
# #                         "id": entry_id,
# #                         "timestamp": timestamp,
# #                         "data": data,
# #                     })
# #                 except (json.JSONDecodeError, ValueError):
# #                     continue
            
# #             return result
# #         except Exception as e:
# #             raise RuntimeError(f"Failed to read from Redis stream: {e}")
    
# #     def get_messages_by_asset(self, asset_id: str, count: int = 50) -> list[dict[str, Any]]:
# #         """
# #         Get messages filtered by asset_id.
        
# #         Args:
# #             asset_id: Asset ID to filter by
# #             count: Maximum messages to retrieve before filtering
            
# #         Returns:
# #             List of messages containing the specified asset_id
# #         """
# #         try:
# #             # Get more messages than needed since we'll filter
# #             fetch_count = min(count * 5, 1000)
# #             messages = self.redis_client.xrevrange(
# #                 self.stream_key,
# #                 count=fetch_count,
# #             )
            
# #             result = []
# #             for entry_id, fields in messages:
# #                 try:
# #                     data = json.loads(fields.get("data", "{}"))
# #                     timestamp = fields.get("timestamp", "")
                    
# #                     # Check if this message contains the asset_id
# #                     if self._message_contains_asset(data, asset_id):
# #                         result.append({
# #                             "id": entry_id,
# #                             "timestamp": timestamp,
# #                             "data": data,
# #                         })
                    
# #                     # Stop if we have enough messages
# #                     if len(result) >= count:
# #                         break
                        
# #                 except (json.JSONDecodeError, ValueError):
# #                     continue
            
# #             return result
# #         except Exception as e:
# #             raise RuntimeError(f"Failed to read from Redis stream: {e}")
    
# #     @staticmethod
# #     def _message_contains_asset(data: dict, asset_id: str) -> bool:
# #         """Check if a message contains a specific asset_id."""
# #         # Direct asset_id field
# #         if data.get("asset_id") == asset_id:
# #             return True
# #         if data.get("assetId") == asset_id:
# #             return True
        
# #         # assets_ids list
# #         assets_ids = data.get("assets_ids", [])
# #         if isinstance(assets_ids, list) and asset_id in assets_ids:
# #             return True
        
# #         # price_changes list
# #         price_changes = data.get("price_changes", [])
# #         if isinstance(price_changes, list):
# #             for change in price_changes:
# #                 if isinstance(change, dict):
# #                     if change.get("asset_id") == asset_id or change.get("assetId") == asset_id:
# #                         return True
        
# #         return False

    
# #     # def get_messages_since(self, last_id: str = "0", count: int = 50) -> list[dict[str, Any]]:
# #     #     """
# #     #     Get messages after a specific stream ID.
        
# #     #     Args:
# #     #         last_id: Stream ID to start from (default: "0" for beginning)
# #     #         count: Max messages to retrieve
            
# #     #     Returns:
# #     #         List of message dicts
# #     #     """
# #     #     try:
# #     #         messages = self.redis_client.xrange(
# #     #             self.stream_key,
# #     #             min=f"({last_id}",  # Exclusive lower bound
# #     #             count=count,
# #     #         )
            
# #     #         result = []
# #     #         for entry_id, fields in messages:
# #     #             try:
# #     #                 data = json.loads(fields.get("data", "{}"))
# #     #                 timestamp = fields.get("timestamp", "")
                    
# #     #                 result.append({
# #     #                     "id": entry_id,
# #     #                     "timestamp": timestamp,
# #     #                     "data": data,
# #     #                 })
# #     #             except (json.JSONDecodeError, ValueError):
# #     #                 continue
            
# #     #         return result
# #     #     except Exception as e:
# #     #         raise RuntimeError(f"Failed to read from Redis stream: {e}")
    
# #     # def get_stream_info(self) -> dict[str, Any]:
# #     #     """Get stream statistics."""
# #     #     try:
# #     #         info = self.redis_client.xinfo_stream(self.stream_key)
# #     #         return {
# #     #             "length": info.get("length", 0),
# #     #             "first_entry_id": info.get("first-entry", [None])[0],
# #     #             "last_entry_id": info.get("last-entry", [None])[0],
# #     #         }
# #     #     except Exception as e:
# #     #         return {"error": str(e)}



# from typing import Dict, Any, List


# class MarketMessageTransformer:
#     """
#     Normalize raw Polymarket WebSocket messages
#     into a more analysis-friendly format.
#     """

#     # ---------- single message ----------

#     @staticmethod
#     def normalize_message(message: Dict[str, Any]) -> Dict[str, Any]:
#         if not isinstance(message, dict):
#             return message

#         bids = message.get("bids")
#         if isinstance(bids, list):
#             message["bids"] = {
#                 str(bid["price"]): str(bid["size"])
#                 for bid in bids
#                 if isinstance(bid, dict)
#                 and "price" in bid
#                 and "size" in bid
#             }




#         asks = message.get("asks")
#         if isinstance(asks, list):
#             message["asks"] = {
#                 str(ask["price"]): str(ask["size"])
#                 for ask in asks
#                 if isinstance(ask, dict)
#                 and "price" in ask
#                 and "size" in ask
#             }



#         price_changes = message.get("price_changes")
#         if isinstance(price_changes, list):
#             message["price_changes"] = [
#                 MarketMessageTransformer.normalize_price_change(pc)
#                 for pc in price_changes
#                 if isinstance(pc, dict)
#             ]

#         return message

#     # ---------- single price change ----------

#     @staticmethod
#     def normalize_price_change(change: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Normalize a single price change:
#         BUY  -> bid
#         SELL -> ask
#         """
#         side = change.get("side")

#         if side == "BUY":
#             change["bid"] = {
#                 "price": change.get("price"),
#                 "size": change.get("size"),
#             }
#         elif side == "SELL":
#             change["ask"] = {
#                 "price": change.get("price"),
#                 "size": change.get("size"),
#             }

#         return change

#     # ---------- list of Redis messages ----------

#     @classmethod
#     def normalize_messages(cls, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#         """
#         Normalize a list of Redis JSON messages.
#         Expected format:
#         { "timestamp": "...", "message": {...} }
#         """
#         normalized = []

#         for item in messages:
#             msg = item.get("message")
#             if isinstance(msg, dict):
#                 item["message"] = cls.normalize_message(msg)
#             normalized.append(item)

#         return normalized
