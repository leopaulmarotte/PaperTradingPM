import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

APP_NAME = "PolyMarket Trading Simulator"

ORDERBOOK_REFRESH_MS = 1000  # 1 seconde

DEFAULT_MARKETS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD"
]

