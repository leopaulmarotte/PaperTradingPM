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

from utils.helper import (_resolve_market_name,
						  _extract_market_name,
						  _parse_datetime,
						  _fetch_all_trades)

from utils.formatters import _format_datetime
from utils.display_figure import _build_trades_dataframe


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
				"Timestamp": st.column_config.TextColumn(width="medium"),
				"Portefeuille": st.column_config.TextColumn(width="small"),
				"Marché": st.column_config.TextColumn(width="medium"),
				"Action": st.column_config.TextColumn(width="small"),
				"Token": st.column_config.TextColumn(width="small"),
				"Quantité": st.column_config.NumberColumn(format="%.2f", width="small"),
				"Prix unitaire": st.column_config.NumberColumn(format="%.4f", width="small"),
				"Prix total": st.column_config.NumberColumn(format="$%.2f", width="small"),
				"Note": st.column_config.TextColumn(width="medium"),
			}
			
			st.dataframe(
				df,
				use_container_width=True,
				hide_index=True,
				column_config=col_config,
				height=500,
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

