import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional


from config import API_URL
from utils.api import APIClient
from utils.styles import COLORS

def _init_state():
    """Initialize session state variables."""
    if "trading_view" not in st.session_state:
        st.session_state.trading_view = "list"
    if "trading_page" not in st.session_state:
        st.session_state.trading_page = 1
    if "selected_market" not in st.session_state:
        st.session_state.selected_market = None

def init_session():
    defaults = {
        "is_authenticated": False,
        "user_id": None,
        "token": None,
        "selected_market": None,
        "trades_df": None,
        "nav_page": "Trading",
        "nav_override": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
            

def _extract_market_name(market: dict) -> str:
	"""Return a readable market name from market dict."""
	try:
		name = market.get("question") or market.get("name") or market.get("title")
		if name:
			return name
		slug = market.get("slug") or ""
		if slug:
			return slug.replace("-", " ").replace("_", " ").title()
		return "Marché"
	except Exception:
		return "Marché"


def _resolve_market_name(api: APIClient, market_id: Optional[str], cache: dict) -> str:
	"""Resolve market name from a market identifier using cache + API."""
	if not market_id:
		return ""
	# Use cache if available
	if market_id in cache:
		return cache[market_id]
	
	# Try slug endpoint first
	resp = api.get_market(market_id)
	if resp.get("status") == 200 and isinstance(resp.get("data"), dict):
		market = resp["data"]
		name = _extract_market_name(market)
		cache[market_id] = name
		return name
	
	# Fallback to condition endpoint
	resp2 = api.get_market_by_condition(market_id)
	if resp2.get("status") == 200 and isinstance(resp2.get("data"), dict):
		market = resp2["data"]
		name = _extract_market_name(market)
		cache[market_id] = name
		return name

	# If unresolved, cache empty to avoid repeated calls
	cache[market_id] = ""
	return ""


def _parse_datetime(date_str: str) -> Optional[datetime]:
	"""Parse ISO format datetime string."""
	try:
		if not date_str:
			return None
		return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
	except Exception:
		return None


def _fetch_all_trades(api: APIClient) -> List[Dict]:
	"""
	Fetch trades from all user portfolios.
	
	Returns:
		List of trade dictionaries with enriched portfolio_name field
	"""
	all_trades = []
	market_name_cache: dict = {}
	
	# Get list of all portfolios
	portfolios_resp = api.list_portfolios()
	if portfolios_resp.get("status") != 200:
		return []
	
	portfolios = portfolios_resp.get("data") or []
	if isinstance(portfolios, dict):
		portfolios = list(portfolios.values())
	
	# Fetch trades for each portfolio
	for portfolio in portfolios:
		if not isinstance(portfolio, dict):
			continue
		
		portfolio_id = portfolio.get("_id") or portfolio.get("id")
		portfolio_name = portfolio.get("name", "Sans nom")
		
		if not portfolio_id:
			continue
		
		trades_resp = api.get_trades(portfolio_id, page=1, page_size=100)
		if trades_resp.get("status") != 200:
			continue
		
		trades_data = trades_resp.get("data")
		if isinstance(trades_data, dict):
			trades = trades_data.get("trades") or []
		elif isinstance(trades_data, list):
			trades = trades_data
		else:
			trades = []
		
		# Add portfolio info and enrich each trade
		for trade in trades:
			if isinstance(trade, dict):
				trade["portfolio_name"] = portfolio_name
				trade["portfolio_id"] = portfolio_id
				# Resolve market name
				mid = trade.get("market_id")
				trade["market_name"] = _resolve_market_name(api, mid, market_name_cache)
				all_trades.append(trade)
	
	return all_trades


def _format_position_label(pos: Dict) -> str:
    """Create a readable label for a position with P&L."""
    market_q = pos.get("market_question") or pos.get("market_id", "Unknown")
    # Truncate if too long
    if len(market_q) > 45:
        market_q = market_q[:42] + "..."
    outcome = pos.get("outcome", "")
    pnl = pos.get("total_pnl", 0)
    pnl_sign = "+" if pnl >= 0 else ""
    return f"{market_q} [{outcome}] • P&L: {pnl_sign}${pnl:.2f}"


def _get_pnl_color(value: float) -> str:
    """Get color based on P&L value."""
    if value > 0:
        return COLORS["accent_green"]
    elif value < 0:
        return COLORS["accent_red"]
    return COLORS["text_secondary"]
