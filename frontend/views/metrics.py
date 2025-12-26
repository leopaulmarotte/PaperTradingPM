"""
Metrics View - Professional portfolio performance visualization with Plotly charts
"""
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta

from config import API_URL
from utils.api import APIClient
from utils.styles import COLORS
from utils.formatters import (
    format_currency,
    format_percent,
    format_date,
    get_pnl_color,
)


def _create_pnl_chart(pnl_history: list) -> go.Figure:
    """Create P&L evolution chart."""
    fig = go.Figure()
    
    if not pnl_history:
        # Empty state
        fig.add_annotation(
            text="Pas encore de données de performance",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
    else:
        dates = []
        values = []
        for point in pnl_history:
            try:
                date_str = point.get("date") or point.get("timestamp")
                if date_str:
                    if isinstance(date_str, str):
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromtimestamp(date_str)
                    dates.append(dt)
                    values.append(point.get("pnl", 0) or point.get("value", 0))
            except:
                continue
        
        if dates and values:
            # Determine colors based on values
            colors = [COLORS["accent_green"] if v >= 0 else COLORS["accent_red"] for v in values]
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name='P&L',
                line=dict(color=COLORS["accent_blue"], width=2),
                marker=dict(size=6, color=colors),
                fill='tozeroy',
                fillcolor='rgba(88, 166, 255, 0.1)'
            ))
            
            # Zero line
            fig.add_hline(
                y=0,
                line_dash="dash",
                line_color=COLORS["text_secondary"],
                opacity=0.5
            )
    
    fig.update_layout(
        title=None,
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=350,
        margin=dict(l=50, r=20, t=30, b=50),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
            title=None
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
            tickprefix='$',
            title=None
        ),
        hovermode='x unified',
        showlegend=False
    )
    
    return fig


def _create_drawdown_chart(drawdown_history: list) -> go.Figure:
    """Create drawdown chart."""
    fig = go.Figure()
    
    if not drawdown_history:
        fig.add_annotation(
            text="Pas de données de drawdown",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
    else:
        dates = []
        values = []
        for point in drawdown_history:
            try:
                date_str = point.get("date") or point.get("timestamp")
                if date_str:
                    if isinstance(date_str, str):
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromtimestamp(date_str)
                    dates.append(dt)
                    values.append(point.get("drawdown", 0) * 100)  # Convert to percentage
            except:
                continue
        
        if dates and values:
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines',
                name='Drawdown',
                line=dict(color=COLORS["accent_red"], width=2),
                fill='tozeroy',
                fillcolor='rgba(248, 81, 73, 0.2)'
            ))
    
    fig.update_layout(
        title=None,
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=250,
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
            ticksuffix='%',
            title=None,
            autorange='reversed'  # Drawdown goes down
        ),
        showlegend=False
    )
    
    return fig


def _create_trade_distribution_chart(trades_by_outcome: dict) -> go.Figure:
    """Create pie chart of trades by outcome."""
    fig = go.Figure()
    
    if not trades_by_outcome:
        fig.add_annotation(
            text="Pas de trades",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
    else:
        labels = list(trades_by_outcome.keys())
        values = list(trades_by_outcome.values())
        
        colors = []
        for label in labels:
            if label.upper() == "YES":
                colors.append(COLORS["accent_green"])
            elif label.upper() == "NO":
                colors.append(COLORS["accent_red"])
            else:
                colors.append(COLORS["accent_blue"])
        
        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(colors=colors),
            textinfo='label+percent',
            textfont=dict(color=COLORS["text_primary"]),
            hovertemplate='%{label}: %{value} trades<extra></extra>'
        ))
    
    fig.update_layout(
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
        annotations=[dict(
            text='Trades',
            x=0.5, y=0.5,
            font=dict(size=14, color=COLORS["text_secondary"]),
            showarrow=False
        )]
    )
    
    return fig


def _create_returns_chart(returns_history: list) -> go.Figure:
    """Create daily/period returns bar chart."""
    fig = go.Figure()
    
    if not returns_history:
        fig.add_annotation(
            text="Pas de données de rendements",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
    else:
        dates = []
        returns = []
        colors = []
        
        for point in returns_history:
            try:
                date_str = point.get("date") or point.get("timestamp")
                ret = point.get("return", 0) or point.get("pct_change", 0)
                if date_str:
                    if isinstance(date_str, str):
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromtimestamp(date_str)
                    dates.append(dt)
                    returns.append(ret * 100)  # Convert to percentage
                    colors.append(COLORS["accent_green"] if ret >= 0 else COLORS["accent_red"])
            except:
                continue
        
        if dates and returns:
            fig.add_trace(go.Bar(
                x=dates,
                y=returns,
                marker_color=colors,
                hovertemplate='%{x|%d/%m/%Y}: %{y:.2f}%<extra></extra>'
            ))
    
    fig.update_layout(
        title=None,
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=250,
        margin=dict(l=50, r=20, t=20, b=50),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
            ticksuffix='%',
            zeroline=True,
            zerolinecolor=COLORS["text_secondary"]
        ),
        showlegend=False
    )
    
    return fig


def _render_metric_card(label: str, value: str, description: str = "", positive: bool = None) -> str:
    """Generate HTML for a metric card."""
    if positive is True:
        value_color = COLORS["accent_green"]
    elif positive is False:
        value_color = COLORS["accent_red"]
    else:
        value_color = COLORS["text_primary"]
    
    return f"""
    <div style="background: {COLORS['bg_secondary']}; padding: 20px; border-radius: 12px; border: 1px solid {COLORS['border']}; text-align: center;">
        <div style="color: {COLORS['text_secondary']}; font-size: 13px; margin-bottom: 8px; text-transform: uppercase;">{label}</div>
        <div style="color: {value_color}; font-size: 28px; font-weight: bold;">{value}</div>
        {f'<div style="color: {COLORS["text_secondary"]}; font-size: 11px; margin-top: 8px;">{description}</div>' if description else ''}
    </div>
    """


def render():
    """Main render function for Metrics view."""
    api = APIClient(API_URL)
    
    st.markdown("## 📈 Performance du portefeuille")
    
    # Portfolio selection
    portfolios_resp = api.list_portfolios()
    if portfolios_resp["status"] != 200:
        st.error("Impossible de charger les portefeuilles")
        return
    
    portfolios = portfolios_resp.get("data", [])
    if not portfolios:
        st.warning("Aucun portefeuille trouvé. Créez-en un dans la section Portfolio.")
        return
    
    # Build portfolio options
    portfolio_ids = []
    portfolio_by_id = {}
    for p in portfolios:
        pid = p.get("_id") or p.get("id")
        if pid:
            pid = str(pid)
            portfolio_ids.append(pid)
            portfolio_by_id[pid] = p
    
    # Check if we were redirected with a specific portfolio
    preselect_id = st.session_state.get("metrics_portfolio_id")
    default_idx = 0
    if preselect_id and str(preselect_id) in portfolio_ids:
        default_idx = portfolio_ids.index(str(preselect_id))
    
    selected_portfolio_id = st.selectbox(
        "Sélectionner un portefeuille",
        options=portfolio_ids,
        index=default_idx,
        format_func=lambda pid: portfolio_by_id[pid].get("name", pid)
    )
    
    # Fetch portfolio details and metrics
    portfolio_resp = api.get_portfolio(selected_portfolio_id)
    metrics_resp = api.get_portfolio_metrics(selected_portfolio_id)
    
    if portfolio_resp["status"] != 200:
        st.error("Impossible de charger le portefeuille")
        return
    
    portfolio = portfolio_resp.get("data", {})
    
    # Metrics may not exist yet
    metrics = {}
    if metrics_resp["status"] == 200:
        metrics = metrics_resp.get("data", {})
    
    # Portfolio summary header
    st.markdown("---")
    
    # Calculate portfolio value breakdown
    cash_balance = portfolio.get("cash_balance", 0)
    
    # Fetch trades to calculate token positions AND cost basis
    trades_resp = api.get_trades(selected_portfolio_id, page=1, page_size=100)
    positions = {}  # {(market_id, outcome): {"qty": float, "cost": float, "market_id": str}}
    
    if trades_resp.get("status") == 200:
        trades_data = trades_resp.get("data", {})
        trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else trades_data
        for t in trades:
            market_id = t.get("market_id", "")
            outcome = (t.get("outcome") or "").strip().lower()
            side = t.get("side", "buy")
            qty = t.get("quantity", 0) or 0
            price = t.get("price", 0) or 0
            
            key = (market_id, outcome)
            if key not in positions:
                positions[key] = {"qty": 0, "cost": 0, "market_id": market_id, "outcome": outcome}
            
            if side == "buy":
                positions[key]["qty"] += qty
                positions[key]["cost"] += qty * price  # Add cost basis
            else:
                # When selling, reduce cost proportionally
                if positions[key]["qty"] > 0:
                    avg_cost = positions[key]["cost"] / positions[key]["qty"]
                    positions[key]["qty"] -= qty
                    positions[key]["cost"] -= qty * avg_cost
    
    # Calculate values for YES and NO tokens (current value and cost basis)
    yes_value = 0.0
    no_value = 0.0
    yes_cost = 0.0
    no_cost = 0.0
    
    # Group positions by market and fetch prices
    markets_prices = {}  # {market_id: {outcome: price}}
    
    for (market_id, outcome), pos in positions.items():
        qty = pos["qty"]
        cost = pos["cost"]
        if qty <= 0:
            continue
        
        # Fetch market price if not cached
        if market_id not in markets_prices:
            market_resp = api.get_market(market_id)
            if market_resp.get("status") != 200:
                market_resp = api.get_market_by_condition(market_id)
            
            if market_resp.get("status") == 200:
                mdata = market_resp.get("data", {})
                outcomes_list = mdata.get("outcomes") or []
                prices_list = mdata.get("outcome_prices") or []
                markets_prices[market_id] = {}
                for o, p in zip(outcomes_list, prices_list):
                    try:
                        markets_prices[market_id][o.strip().lower()] = float(p)
                    except:
                        markets_prices[market_id][o.strip().lower()] = 0.5
            else:
                markets_prices[market_id] = {}
        
        # Get price for this outcome
        price = markets_prices.get(market_id, {}).get(outcome, 0.5)
        token_value = qty * price
        
        if outcome == "yes":
            yes_value += token_value
            yes_cost += cost
        elif outcome == "no":
            no_value += token_value
            no_cost += cost
        else:
            # Other outcomes - add to YES for simplicity or create separate category
            yes_value += token_value
            yes_cost += cost
    
    # Calculate performance percentages
    yes_perf = ((yes_value - yes_cost) / yes_cost * 100) if yes_cost > 0 else 0
    no_perf = ((no_value - no_cost) / no_cost * 100) if no_cost > 0 else 0
    
    total_portfolio_value = cash_balance + yes_value + no_value
    
    # Key metrics row - now 5 columns for detailed breakdown
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(
            _render_metric_card("💰 Cash", format_currency(cash_balance), "Liquidités disponibles"),
            unsafe_allow_html=True
        )
    
    with col2:
        yes_perf_str = f"{'+' if yes_perf >= 0 else ''}{yes_perf:.1f}%"
        yes_desc = f"Coût: {format_currency(yes_cost)} | Perf: {yes_perf_str}" if yes_cost > 0 else "Valeur au prix actuel"
        st.markdown(
            _render_metric_card("🟢 Tokens YES", format_currency(yes_value), yes_desc, yes_perf >= 0 if yes_cost > 0 else None),
            unsafe_allow_html=True
        )
    
    with col3:
        no_perf_str = f"{'+' if no_perf >= 0 else ''}{no_perf:.1f}%"
        no_desc = f"Coût: {format_currency(no_cost)} | Perf: {no_perf_str}" if no_cost > 0 else "Valeur au prix actuel"
        st.markdown(
            _render_metric_card("🔴 Tokens NO", format_currency(no_value), no_desc, no_perf >= 0 if no_cost > 0 else None),
            unsafe_allow_html=True
        )
    
    with col4:
        st.markdown(
            _render_metric_card("📊 Valeur Totale", format_currency(total_portfolio_value), "Cash + Tokens"),
            unsafe_allow_html=True
        )
    
    with col5:
        pnl = metrics.get("total_pnl", 0) or metrics.get("pnl", 0)
        pnl_pct = metrics.get("total_return", 0) or metrics.get("return_pct", 0)
        positive = pnl >= 0 if pnl else None
        pnl_str = f"{'+' if pnl >= 0 else ''}{format_currency(pnl)}"
        desc = f"{'+' if pnl_pct >= 0 else ''}{pnl_pct:.2f}%" if pnl_pct else ""
        st.markdown(
            _render_metric_card("📈 P&L Total", pnl_str, desc, positive),
            unsafe_allow_html=True
        )
    
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    # Second row: Sharpe ratio and max drawdown
    col_sharpe, col_dd, _, _ = st.columns(4)
    
    with col_sharpe:
        sharpe = metrics.get("sharpe_ratio", 0)
        sharpe_positive = sharpe > 1 if sharpe else None
        st.markdown(
            _render_metric_card("Ratio de Sharpe", f"{sharpe:.2f}" if sharpe else "—", "Risk-adjusted return", sharpe_positive),
            unsafe_allow_html=True
        )
    
    with col_dd:
        max_dd = metrics.get("max_drawdown", 0)
        dd_str = f"{max_dd * 100:.1f}%" if max_dd else "—"
        st.markdown(
            _render_metric_card("Drawdown Max", dd_str, "Peak-to-trough decline", False if max_dd and max_dd < -0.1 else None),
            unsafe_allow_html=True
        )
    
    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
    
    # Charts section
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 📊 Évolution du P&L")
        pnl_history = metrics.get("pnl_history", []) or metrics.get("equity_curve", [])
        fig_pnl = _create_pnl_chart(pnl_history)
        st.plotly_chart(fig_pnl, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("### 📉 Drawdown")
        drawdown_history = metrics.get("drawdown_history", [])
        fig_dd = _create_drawdown_chart(drawdown_history)
        st.plotly_chart(fig_dd, use_container_width=True, config={'displayModeBar': False})
    
    with col_right:
        st.markdown("### 🎯 Distribution des trades")
        trades_by_outcome = metrics.get("trades_by_outcome", {})
        
        # If no breakdown in metrics, compute from trades we already fetched
        if not trades_by_outcome:
            # Use trades already fetched earlier for position calculation
            if trades_resp.get("status") == 200:
                trades_data = trades_resp.get("data", {})
                all_trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else trades_data
                trades_by_outcome = {}
                for t in all_trades:
                    outcome = t.get("outcome", "Unknown")
                    trades_by_outcome[outcome] = trades_by_outcome.get(outcome, 0) + 1
        
        fig_pie = _create_trade_distribution_chart(trades_by_outcome)
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        
        # Additional stats
        st.markdown("### 📋 Statistiques")
        
        total_trades = metrics.get("total_trades") or 0
        win_rate = metrics.get("win_rate") or 0
        avg_trade = metrics.get("avg_trade_pnl") or 0
        best_trade = metrics.get("best_trade") or 0
        worst_trade = metrics.get("worst_trade") or 0
        
        # Ensure numeric types
        win_rate = float(win_rate) if win_rate else 0.0
        avg_trade = float(avg_trade) if avg_trade else 0.0
        best_trade = float(best_trade) if best_trade else 0.0
        worst_trade = float(worst_trade) if worst_trade else 0.0
        
        stats_html = f"""
        <div style="background: {COLORS['bg_secondary']}; padding: 16px; border-radius: 8px; border: 1px solid {COLORS['border']};">
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {COLORS['border']};">
                <span style="color: {COLORS['text_secondary']};">Nombre de trades</span>
                <span style="color: {COLORS['text_primary']}; font-weight: bold;">{total_trades}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {COLORS['border']};">
                <span style="color: {COLORS['text_secondary']};">Win Rate</span>
                <span style="color: {COLORS['accent_green'] if win_rate >= 0.5 else COLORS['accent_red']}; font-weight: bold;">{win_rate * 100:.1f}%</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {COLORS['border']};">
                <span style="color: {COLORS['text_secondary']};">P&L moyen/trade</span>
                <span style="color: {get_pnl_color(avg_trade)}; font-weight: bold;">{format_currency(avg_trade)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid {COLORS['border']};">
                <span style="color: {COLORS['text_secondary']};">Meilleur trade</span>
                <span style="color: {COLORS['accent_green']}; font-weight: bold;">{format_currency(best_trade)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: {COLORS['text_secondary']};">Pire trade</span>
                <span style="color: {COLORS['accent_red']}; font-weight: bold;">{format_currency(worst_trade)}</span>
            </div>
        </div>
        """
        st.markdown(stats_html, unsafe_allow_html=True)
    
    # Back to portfolio button
    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
    if st.button("← Retour au Portfolio"):
        st.session_state.pop("metrics_portfolio_id", None)
        st.session_state.nav_override = "Portfolio"
        st.rerun()
