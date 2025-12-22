"""
Trading database configuration.
Stores user portfolios and paper trades.
"""

DB_NAME = "trading_db"


class Collections:
    """Collection names in trading_db."""
    PORTFOLIOS = "portfolios"
    TRADES = "trades"
    METADATA = "_metadata"


# Manifest for registry
DB_MANIFEST = {
    "db_name": DB_NAME,
    "purpose": "User portfolios and paper trading data",
    "collections": [Collections.PORTFOLIOS, Collections.TRADES, Collections.METADATA],
    "access_level": "standard",
}
