from py_clob_client.client import ClobClient
import os

host = os.getenv("CLOB_URL")
key = os.getenv("API_KEY")

if not host:
    raise ValueError("CLOB_URL is not set")
if not key:
    raise ValueError("API_KEY is not set")

chain_id: int = 137  # Polygon
POLYMARKET_PROXY_ADDRESS: str = ""

# Initialization of a client that trades directly from an EOA
client = ClobClient(host, key=key, chain_id=chain_id)

print(client.derive_api_key())
