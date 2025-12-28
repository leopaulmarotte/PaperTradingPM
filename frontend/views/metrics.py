"""
Metrics Page - Mark-to-Market P&L Analysis.

Displays continuous mark-to-market P&L for a portfolio and individual positions.
Supports both direct access (dropdown selection) and indirect access (from Portfolio page).
"""
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict, Optional

from utils.api import APIClient
from utils.styles import COLORS
from config import API_URL

from utils.display_figure import (_create_portfolio_pnl_chart,
                                  _create_position_pnl_chart)

from utils.helper import (_format_position_label,
                          _get_pnl_color)



def render():
    """Render the Metrics page."""
    
    # Simple CSS for KPI cards only
    st.markdown("""
    <style>
    .kpi-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        flex: 1;
        border: 1px solid rgba(99, 102, 241, 0.2);
    }
    .kpi-label {
        color: #888;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin-top: 0.25rem;
    }
    .kpi-positive { color: #3BB950; }
    .kpi-negative { color: #F85149; }
    .kpi-neutral { color: #E8E8E8; }
    </style>
    """, unsafe_allow_html=True)
    
    # Page title (same style as other pages)
    st.title("Métriques")
    
    api = APIClient(API_URL)
    
    # =========================================================================
    # PORTFOLIO SELECTION
    # =========================================================================
    
    # Check if coming from Portfolio page with pre-selected portfolio
    preselected_portfolio_id = st.session_state.get("metrics_portfolio_id")
    
    # Load all portfolios
    resp = api.list_portfolios()
    if resp.get("status") != 200:
        st.error("Impossible de charger les portfolios")
        return
    
    portfolios = resp.get("data") or []
    if isinstance(portfolios, dict):
        portfolios = list(portfolios.values())
    
    if not portfolios:
        st.info("Aucun portfolio trouvé. Créez un portfolio depuis la page Portfolios.")
        return
    
    # Build dropdown options
    portfolio_options = {p["id"]: f"{p['name']} (Balance: ${p.get('initial_balance', 0):,.0f})" for p in portfolios}
    portfolio_ids = list(portfolio_options.keys())
    
    # Determine default selection
    default_index = 0
    if preselected_portfolio_id and preselected_portfolio_id in portfolio_ids:
        default_index = portfolio_ids.index(preselected_portfolio_id)
    
    # Portfolio selector (full width, no resolution selector)
    selected_id = st.selectbox(
        "📁 Sélectionner un portfolio",
        options=portfolio_ids,
        format_func=lambda x: portfolio_options[x],
        index=default_index,
        key="metrics_portfolio_selector"
    )
    
    # Use 10 min resolution for granular P&L charts (matches Polymarket price history)
    resolution = 10
    
    # Clear pre-selection after use
    if preselected_portfolio_id:
        st.session_state.pop("metrics_portfolio_id", None)
    
    if not selected_id:
        st.warning("Veuillez sélectionner un portfolio")
        return
    
    # =========================================================================
    # LOAD MTM DATA
    # =========================================================================
    
    with st.spinner("Chargement des données mark-to-market..."):
        mtm_resp = api.get_portfolio_mtm(selected_id, resolution=resolution)
    
    if mtm_resp.get("status") != 200:
        st.error("Impossible de charger les données MTM")
        if mtm_resp.get("data"):
            st.json(mtm_resp.get("data"))
        return
    
    mtm_data = mtm_resp.get("data", {})
    
    if not mtm_data:
        st.warning("Aucune donnée disponible pour ce portfolio")
        return
    
    # =========================================================================
    # KEY METRICS DISPLAY
    # =========================================================================
    
    total_pnl = mtm_data.get("total_pnl", 0)
    total_pnl_percent = mtm_data.get("total_pnl_percent", 0)
    initial_balance = mtm_data.get("initial_balance", 0)
    total_value = mtm_data.get("total_value", 0)
    
    pnl_class = "kpi-positive" if total_pnl >= 0 else "kpi-negative"
    pnl_sign = "+" if total_pnl >= 0 else ""
    
    st.markdown(f"""
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-label">P&L Total</div>
            <div class="kpi-value {pnl_class}">{pnl_sign}${total_pnl:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Performance</div>
            <div class="kpi-value {pnl_class}">{pnl_sign}{total_pnl_percent:.2f}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Valeur Actuelle</div>
            <div class="kpi-value kpi-neutral">${total_value:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Capital Initial</div>
            <div class="kpi-value kpi-neutral">${initial_balance:,.2f}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # =========================================================================
    # GRAPH 1: GLOBAL PORTFOLIO PNL
    # =========================================================================
    
    st.subheader("P&L Global du Portfolio")
    
    pnl_series = mtm_data.get("pnl_series", [])
    
    if pnl_series:
        fig_portfolio = _create_portfolio_pnl_chart(pnl_series)
        st.plotly_chart(fig_portfolio, use_container_width=True, key="portfolio_pnl_chart")
        
        # Show data points count and time span
        if len(pnl_series) >= 2:
            first_ts = pnl_series[0].get("timestamp", "")
            last_ts = pnl_series[-1].get("timestamp", "")
            try:
                from datetime import datetime
                t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                span = t1 - t0
                days = span.days
                hours = span.seconds // 3600
                if days > 0:
                    span_str = f"{days}j {hours}h"
                else:
                    span_str = f"{hours}h {(span.seconds % 3600) // 60}min"
                st.caption(f"📊 {len(pnl_series)} points de données • Période: {span_str}")
            except:
                st.caption(f"📊 {len(pnl_series)} points de données")
        else:
            st.caption(f"📊 {len(pnl_series)} points de données")
    else:
        st.info("Aucun trade exécuté - le P&L est constant à $0")
    
    # =========================================================================
    # GRAPH 2: POSITION-LEVEL PNL
    # =========================================================================
    
    st.divider()
    st.subheader("P&L par Position")
    
    all_positions = mtm_data.get("positions", [])
    
    # Filter to only show positions with non-zero quantity
    positions = [p for p in all_positions if p.get("current_quantity", 0) != 0]
    
    if not positions:
        st.info("Aucune position active (quantité > 0)")
    else:
        # Build position dropdown with P&L displayed
        position_labels = [_format_position_label(p) for p in positions]
        
        selected_position_idx = st.selectbox(
            "Sélectionner une position",
            options=range(len(positions)),
            format_func=lambda i: position_labels[i],
            key="position_selector"
        )
        
        if selected_position_idx is not None:
            selected_position = positions[selected_position_idx]
            
            # Simple metrics in columns
            pos_pnl = selected_position.get("total_pnl", 0)
            pos_qty = selected_position.get("current_quantity", 0)
            pos_avg_price = selected_position.get("average_entry_price", 0)
            pos_current_price = selected_position.get("current_price", 0)
            first_trade_at = selected_position.get("first_trade_at")
            
            # Display opening date if available
            if first_trade_at:
                try:
                    if isinstance(first_trade_at, str):
                        from datetime import datetime
                        first_trade_dt = datetime.fromisoformat(first_trade_at.replace("Z", "+00:00"))
                    else:
                        first_trade_dt = first_trade_at
                    st.caption(f"📅 Position ouverte le {first_trade_dt.strftime('%d/%m/%Y à %H:%M')}")
                except:
                    pass
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Quantité", f"{pos_qty:.2f}")
            with col2:
                st.metric("Prix d'entrée", f"${pos_avg_price:.4f}")
            with col3:
                st.metric("Prix actuel", f"${pos_current_price:.4f}")
            with col4:
                pnl_delta = f"{pos_pnl:+.2f}"
                st.metric("P&L", f"${pos_pnl:.2f}", delta=pnl_delta)
            
            # Position P&L chart
            fig_position = _create_position_pnl_chart(selected_position)
            st.plotly_chart(fig_position, use_container_width=True, key="position_pnl_chart")
