"""
Portfolio model for trading database.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Portfolio(BaseModel):
    """
    Portfolio document model for MongoDB trading_db.portfolios collection.
    """
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId as string")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Portfolio name")
    description: Optional[str] = Field(None, description="Optional description")
    initial_balance: float = Field(
        default=10000.0,
        description="Starting paper money balance"
    )
    created_at: datetime = Field(
        default_factory=datetime.now(datetime.UTC),
        description="Portfolio creation timestamp"
    )
    is_active: bool = Field(
        default=True,
        description="Whether portfolio is active"
    )

    class Config:
        populate_by_name = True
