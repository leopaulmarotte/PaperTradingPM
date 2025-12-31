from pydantic import BaseModel, Field, RootModel
from typing import Dict, Optional


class OrderbookLevel(BaseModel):
    """Single price level in an orderbook (price: quantity)."""
    price: float = Field(..., description="Price point")
    quantity: float = Field(..., description="Quantity available at this price")


class TokenOrderbook(BaseModel):
    """Orderbook data for a single token outcome (YES or NO)."""
    bids: Dict[str, float] = Field(
        default_factory=dict,
        description="Buy orders {price_str: quantity}"
    )
    asks: Dict[str, float] = Field(
        default_factory=dict,
        description="Sell orders {price_str: quantity}"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "bids": {"0.45": 100.0, "0.44": 200.0, "0.43": 150.0},
                "asks": {"0.55": 150.0, "0.56": 250.0, "0.57": 300.0}
            }
        }


class MarketOrderbook(RootModel):
    """Complete orderbook for a market with multiple tokens."""
    root: Dict[str, TokenOrderbook]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, key: str) -> TokenOrderbook:
        return self.root[key]

    def keys(self):
        return self.root.keys()

    def items(self):
        return self.root.items()

    def get(self, key: str, default=None):
        return self.root.get(key, default)

    class Config:
        json_schema_extra = {
            "example": {
                "12345": {
                    "bids": {"0.45": 100.0, "0.44": 200.0},
                    "asks": {"0.55": 150.0, "0.56": 250.0}
                },
                "12346": {
                    "bids": {"0.50": 80.0, "0.49": 120.0},
                    "asks": {"0.60": 100.0, "0.61": 180.0}
                }
            }
        }
