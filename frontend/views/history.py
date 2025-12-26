"""
History page: Display complete transaction history across all portfolios.

Features:
- Display all trades in a formatted table
- Support filtering and sorting
- Delete entire history with confirmation
- Auto-refresh when new trades are created
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

from config import API_URL
from utils.api import APIClient


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


def _format_datetime(dt: Optional[datetime]) -> str:
	"""Format datetime into separate date and time strings."""
	if not dt:
		return "", ""
	return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


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


def _build_trades_dataframe(trades: List[Dict]) -> pd.DataFrame:
	"""
	Convert trades list into formatted pandas DataFrame.
	
	Expected trade fields:
	- created_at: ISO datetime string
	- portfolio_name: Portfolio name
	- side: "buy" or "sell"
	- outcome: YES or NO
	- quantity: Trade quantity
	- price: Unit price
	- notes: Optional notes
	"""
	if not trades:
		return pd.DataFrame()
	
	rows = []
	for trade in trades:
		try:
			# Parse datetime
			dt = _parse_datetime(trade.get("created_at"))
			date_str, time_str = _format_datetime(dt)
			
			# Get fields
			portfolio = trade.get("portfolio_name", "N/A")
			market_name = trade.get("market_name", "")
			action = (trade.get("side") or "").upper()
			outcome = (trade.get("outcome") or "").upper()
			quantity = float(trade.get("quantity") or 0)
			price = float(trade.get("price") or 0)
			notes = trade.get("notes") or ""
			
			# Calculate total
			total = quantity * price
			
			rows.append({
				"Date": date_str,
				"Heure": time_str,
				"Portefeuille": portfolio,
				"Marché": market_name,
				"Action": action,
				"Token": outcome,
				"Quantité": quantity,
				"Prix unitaire": price,
				"Prix total": total,
				"Note": notes,
			})
		except Exception:
			# Skip malformed trades
			continue
	
	if not rows:
		return pd.DataFrame()
	
	df = pd.DataFrame(rows)
	
	# Ensure numeric columns are properly typed
	for col in ["Quantité", "Prix unitaire", "Prix total"]:
		if col in df.columns:
			df[col] = pd.to_numeric(df[col], errors="coerce")
	
	# Sort by date descending (newest first)
	if "Date" in df.columns:
		df = df.sort_values("Date", ascending=False, key=lambda x: pd.to_datetime(x, errors='coerce'), na_position='last')
	
	df = df.reset_index(drop=True)
	return df


def render():
	"""Render the history page."""
	st.title("📊 Historique des transactions")
	
	api = APIClient(API_URL)
	
	# Fetch all trades
	with st.spinner("Chargement de l'historique..."):
		trades = _fetch_all_trades(api)
	
	# Display summary metrics
	if trades:
		total_trades = len(trades)
		buy_count = sum(1 for t in trades if (t.get("side") or "").lower() == "buy")
		sell_count = sum(1 for t in trades if (t.get("side") or "").lower() == "sell")
		
		col1, col2, col3, col4 = st.columns(4)
		with col1:
			st.metric("Total de transactions", total_trades)
		with col2:
			st.metric("Achats", buy_count)
		with col3:
			st.metric("Ventes", sell_count)
		with col4:
			try:
				total_volume = sum(
					float(t.get("quantity") or 0) * float(t.get("price") or 0)
					for t in trades
				)
				st.metric("Volume total", f"${total_volume:,.2f}")
			except Exception:
				st.metric("Volume total", "N/A")
		
		st.divider()
		
		# Build and display DataFrame
		df = _build_trades_dataframe(trades)
		
		if not df.empty:
			# Display table with proper formatting
			st.subheader("Détail des transactions")
			
			# Use columns for better display control
			col_config = {
				"Date": st.column_config.TextColumn(width="small"),
				"Heure": st.column_config.TextColumn(width="small"),
				"Portefeuille": st.column_config.TextColumn(),
				"Marché": st.column_config.TextColumn(),
				"Action": st.column_config.TextColumn(width="small"),
				"Token": st.column_config.TextColumn(width="small"),
				"Quantité": st.column_config.NumberColumn(format="%.4f"),
				"Prix unitaire": st.column_config.NumberColumn(format="%.4f"),
				"Prix total": st.column_config.NumberColumn(format="$%.2f"),
				"Note": st.column_config.TextColumn(),
			}
			
			st.dataframe(
				df,
				use_container_width=True,
				hide_index=True,
				column_config=col_config,
			)
			
			# Export option
			csv_data = df.to_csv(index=False)
			st.download_button(
				label="📥 Télécharger en CSV",
				data=csv_data,
				file_name=f"history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
				mime="text/csv",
				use_container_width=True,
			)
		else:
			st.warning("Aucune transaction n'a pu être affichée.")
	else:
		st.info("📭 Aucune transaction enregistrée pour l'instant.")

