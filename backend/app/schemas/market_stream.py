from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class StreamStartResponse(BaseModel):
    """Response when starting a market stream."""
    status: str = Field(..., description="Status of the stream start")
    asset_id: str = Field(..., description="Asset ID(s) being streamed")
    message: str = Field(..., description="Status message")
    started_by: str = Field(..., description="User ID who started the stream")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "started",
                "asset_id": "123,456",
                "message": "Streaming started for asset 123,456",
                "started_by": "user123"
            }
        }


class StreamStopResponse(BaseModel):
    """Response when stopping a market stream."""
    status: str = Field(..., description="Status of the stream stop")
    message: str = Field(..., description="Status message")
    stopped_by: str = Field(..., description="User ID who stopped the stream")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "stopped",
                "message": "Stop command sent and data cleared",
                "stopped_by": "user123"
            }
        }


class OrderbookLevel(BaseModel):
    """Single price level in an orderbook."""
    price: float = Field(..., description="Price at this level")
    quantity: float = Field(..., description="Quantity at this level")


class TokenOrderbook(BaseModel):
    """Orderbook for a single token (YES/NO)."""
    bids: Dict[str, float] = Field(default_factory=dict, description="Bid levels {price: quantity}")
    asks: Dict[str, float] = Field(default_factory=dict, description="Ask levels {price: quantity}")


class OrderbookResponse(BaseModel):
    """Response containing streamed orderbook messages."""
    status: str = Field(..., description="Status of the request")
    count: int = Field(..., description="Number of messages")
    messages: Dict[str, TokenOrderbook] = Field(default_factory=dict, description="Orderbook snapshots by token ID")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "count": 2,
                "messages": {
                    "123": {
                        "bids": {"0.45": 100.0, "0.44": 200.0},
                        "asks": {"0.55": 150.0, "0.56": 250.0}
                    },
                    "456": {
                        "bids": {"0.50": 80.0},
                        "asks": {"0.60": 120.0}
                    }
                }
            }
        }


class LatestMessageResponse(BaseModel):
    """Response containing the latest streamed message."""
    status: str = Field(..., description="Status of the request")
    message: Optional[Dict[str, Any]] = Field(None, description="Latest message data")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "message": {
                    "123": {
                        "bids": {"0.45": 100.0},
                        "asks": {"0.55": 150.0}
                    }
                }
            }
        }
