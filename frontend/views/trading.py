"""
Trading View - Professional card-based market explorer with Plotly charts
"""
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

from config import API_URL
from utils.api import APIClient
from utils.styles import COLORS
from utils.formatters import (
    format_number,
    format_currency,
    format_percent,
    format_date,
    time_until_end,
)


def _init_state():
    """Initialize session state variables."""
    if "trading_view" not in st.session_state:
        st.session_state.trading_view = "list"
    if "trading_page" not in st.session_state:
        st.session_state.trading_page = 1
    if "selected_market" not in st.session_state:
        st.session_state.selected_market = None


def _normalize_outcome(name: str) -> str:
    """Normalize outcome name for matching positions."""
    try:
        return (name or "").strip().lower()
    except Exception:
        return ""


def _display_name(market: dict) -> str:
    """Return a readable market name."""
    name = market.get("question") or market.get("name") or market.get("title")
    if name:
        return name
    slug = market.get("slug") or ""
    if slug:
        return slug.replace("-", " ").replace("_", " ").title()
    return "Marché"


def _create_market_card(market: dict, idx: int) -> str:
    """Generate HTML for a market card."""
    name = _display_name(market)
    # Truncate long names
    display_name = name[:60] + "..." if len(name) > 60 else name
    
    volume = format_number(market.get("volume_24h", 0))
    liquidity = format_number(market.get("liquidity", 0))
    is_closed = market.get("closed", False)
    
    # Get YES price
    prices = market.get("outcome_prices", [])
    yes_price = "—"
    yes_color = COLORS["text_secondary"]
    if prices:
        try:
            yes_val = float(prices[0]) * 100
            yes_price = f"{yes_val:.0f}%"
            # Color based on probability
            if yes_val >= 70:
                yes_color = COLORS["accent_green"]
            elif yes_val <= 30:
                yes_color = COLORS["accent_red"]
            else:
                yes_color = COLORS["accent_blue"]
        except:
            pass
    
    # Status badge
    if is_closed:
        badge = f'<span class="badge-closed">Clôturé</span>'
    else:
        end_date = market.get("end_date")
        time_left = time_until_end(end_date) if end_date else ""
        if time_left:
            badge = f'<span class="badge-active">{time_left}</span>'
        else:
            badge = '<span class="badge-active">Actif</span>'
    
    return f"""
    <div class="market-card" id="card-{idx}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <span style="font-size: 28px; font-weight: bold; color: {yes_color};">{yes_price}</span>
            {badge}
        </div>
        <div style="font-size: 14px; color: {COLORS['text_primary']}; margin-bottom: 12px; line-height: 1.4; min-height: 40px;">
            {display_name}
        </div>
        <div style="display: flex; justify-content: space-between; color: {COLORS['text_secondary']}; font-size: 12px;">
            <span>Vol: ${volume}</span>
            <span>Liq: ${liquidity}</span>
        </div>
    </div>
    """


def _create_price_chart(price_history: list, market_name: str) -> go.Figure:
    """Create a Plotly price history chart."""
    if not price_history:
        # Return empty chart with message
        fig = go.Figure()
        fig.add_annotation(
            text="Pas de données de prix disponibles",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
        fig.update_layout(
            paper_bgcolor=COLORS["bg_secondary"],
            plot_bgcolor=COLORS["bg_secondary"],
            height=300
        )
        return fig
    
    # Extract data
    timestamps = []
    yes_prices = []
    no_prices = []
    
    for point in price_history:
        ts = point.get("timestamp") or point.get("t")
        if ts:
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromtimestamp(ts)
                timestamps.append(dt)
            except:
                continue
        
        # Try different price formats
        yes_p = point.get("yes_price") or point.get("p") or point.get("price")
        if yes_p is not None:
            try:
                yes_prices.append(float(yes_p) * 100)
            except:
                yes_prices.append(None)
        
        no_p = point.get("no_price")
        if no_p is not None:
            try:
                no_prices.append(float(no_p) * 100)
            except:
                no_prices.append(None)
    
    fig = go.Figure()
    
    # YES price line
    if yes_prices and timestamps:
        fig.add_trace(go.Scatter(
            x=timestamps[:len(yes_prices)],
            y=yes_prices,
            mode='lines',
            name='YES',
            line=dict(color=COLORS["accent_green"], width=2),
            fill='tozeroy',
            fillcolor=f'rgba(63, 185, 80, 0.1)'
        ))
    
    # NO price line (if available)
    if no_prices and timestamps and len([p for p in no_prices if p is not None]) > 0:
        fig.add_trace(go.Scatter(
            x=timestamps[:len(no_prices)],
            y=no_prices,
            mode='lines',
            name='NO',
            line=dict(color=COLORS["accent_red"], width=2),
        ))
    
    fig.update_layout(
        title=None,
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=300,
        margin=dict(l=40, r=20, t=20, b=40),
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
            range=[0, 100]
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_secondary"])
        ),
        hovermode='x unified'
    )
    
    return fig



def _display_orderbook(market:dict):
    return 'none yet'




def _render_position_panel(api: APIClient, market: dict):
    """Render position panel for the current market if user has a position."""
    # Get all user portfolios
    portfolios_resp = api.list_portfolios()
    if portfolios_resp.get("status") != 200:
        return
    
    portfolios = portfolios_resp.get("data", [])
    if not portfolios:
        return
    
    market_slug = market.get("slug")
    outcomes = market.get("outcomes", [])
    outcome_prices = market.get("outcome_prices", [])
    
    # Build price map
    price_map = {}
    for outcome, price_str in zip(outcomes, outcome_prices):
        try:
            price_map[outcome] = float(price_str)
        except:
            price_map[outcome] = 0.5
    
    # Market identifiers
    market_keys = [
        market_slug,
        market.get("condition_id"),
        market.get("_id"),
        market.get("id"),
    ]
    market_keys = [str(k) for k in market_keys if k]
    
    # Aggregate positions across all portfolios
    all_positions = []  # List of {portfolio_name, outcome, qty, cost_basis, ...}
    
    for portfolio in portfolios:
        portfolio_id = portfolio.get("_id") or portfolio.get("id")
        portfolio_name = portfolio.get("name", "Sans nom")
        if not portfolio_id:
            continue
        
        trades_resp = api.get_trades(str(portfolio_id), page=1, page_size=100)
        if trades_resp.get("status") != 200:
            continue
        
        trades_data = trades_resp.get("data", {})
        trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else trades_data
        trades = sorted(trades, key=lambda t: t.get("created_at", ""))
        
        # Calculate position per outcome
        position_metrics = {}
        for trade in trades:
            trade_market = str(trade.get("market_id", ""))
            if trade_market not in market_keys:
                continue
            
            outcome_key = _normalize_outcome(trade.get("outcome"))
            if outcome_key not in position_metrics:
                position_metrics[outcome_key] = {"qty": 0, "cost_basis": 0}
            
            qty = float(trade.get("quantity", 0))
            price = float(trade.get("price", 0))
            side = trade.get("side", "").lower()
            
            if side == "buy":
                position_metrics[outcome_key]["qty"] += qty
                position_metrics[outcome_key]["cost_basis"] += qty * price
            elif side == "sell":
                current_qty = position_metrics[outcome_key]["qty"]
                current_cost = position_metrics[outcome_key]["cost_basis"]
                if current_qty > 0:
                    avg_cost = current_cost / current_qty
                    position_metrics[outcome_key]["cost_basis"] -= qty * avg_cost
                position_metrics[outcome_key]["qty"] -= qty
        
        # Add non-zero positions
        for out in outcomes:
            norm_out = _normalize_outcome(out)
            metrics = position_metrics.get(norm_out, {"qty": 0, "cost_basis": 0})
            qty = metrics["qty"]
            if qty > 0:
                cost_basis = metrics["cost_basis"]
                current_price = price_map.get(out, 0.5)
                current_value = qty * current_price
                pnl_dollar = current_value - cost_basis
                pnl_percent = ((current_value - cost_basis) / cost_basis * 100) if cost_basis > 0 else 0
                
                all_positions.append({
                    "portfolio": portfolio_name,
                    "outcome": out,
                    "qty": qty,
                    "avg_entry": cost_basis / qty if qty > 0 else 0,
                    "current_price": current_price,
                    "current_value": current_value,
                    "pnl_dollar": pnl_dollar,
                    "pnl_percent": pnl_percent,
                })
    
    if not all_positions:
        return
    
    st.markdown("### 📊 Vos positions sur ce marché")
    
    for pos in all_positions:
        pnl_sign = "+" if pos["pnl_dollar"] >= 0 else ""
        pnl_color = "#22c55e" if pos["pnl_dollar"] >= 0 else "#ef4444"
        
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e1e2e, #2d2d44); border-radius: 10px; padding: 15px; margin-bottom: 10px; border-left: 4px solid #6366f1;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 600; color: #a0a0a0; font-size: 12px;">📁 {pos["portfolio"]}</span>
                    <span style="font-weight: 700; color: #6366f1; font-size: 16px;">{pos["outcome"]}</span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                    <div style="text-align: center;">
                        <div style="color: #a0a0a0; font-size: 10px; text-transform: uppercase;">Quantité</div>
                        <div style="color: white; font-weight: 600;">{pos["qty"]:.2f}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #a0a0a0; font-size: 10px; text-transform: uppercase;">Prix Entrée</div>
                        <div style="color: white; font-weight: 600;">${pos["avg_entry"]:.4f}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #a0a0a0; font-size: 10px; text-transform: uppercase;">Prix Actuel</div>
                        <div style="color: white; font-weight: 600;">${pos["current_price"]:.4f}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #a0a0a0; font-size: 10px; text-transform: uppercase;">Valeur</div>
                        <div style="color: white; font-weight: 600;">${pos["current_value"]:.2f}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="color: #a0a0a0; font-size: 10px; text-transform: uppercase;">P&L</div>
                        <div style="color: {pnl_color}; font-weight: 700;">{pnl_sign}${pos["pnl_dollar"]:.2f} ({pnl_sign}{pos["pnl_percent"]:.1f}%)</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def _render_market_list(api: APIClient):
    """Render the market explorer with card grid."""
    st.markdown("## 🏛️ Explorer les marchés")
    
    # Search and filters in a clean row
    col_search, col_status, col_sort, col_vol = st.columns([2, 1, 1, 1])
    
    with col_search:
        search = st.text_input(
            "🔍 Rechercher",
            placeholder="Nom du marché...",
            label_visibility="collapsed"
        )
    
    with col_status:
        status_filter = st.selectbox(
            "Statut",
            ["Tous", "Actifs", "Clôturés"],
            index=1,  # Default to active markets
            label_visibility="collapsed"
        )
    
    with col_sort:
        sort_by = st.selectbox(
            "Tri",
            ["volume_24h", "liquidity"],
            format_func=lambda x: "Volume 24h" if x == "volume_24h" else "Liquidité",
            label_visibility="collapsed"
        )
    
    with col_vol:
        volume_min = st.number_input(
            "Vol min",
            min_value=0.0,
            step=1000.0,
            value=0.0,
            label_visibility="collapsed",
            placeholder="Volume min"
        )
    
    # Determine filter parameters
    active = None
    closed = None
    if status_filter == "Actifs":
        active, closed = True, False
    elif status_filter == "Clôturés":
        active, closed = None, True
    
    # Page size selector (smaller, right-aligned)
    col_spacer, col_psize = st.columns([4, 1])
    with col_psize:
        page_size = st.selectbox(
            "Par page",
            [12, 24, 48],
            index=0,
            label_visibility="collapsed"
        )
    
    # Fetch markets
    resp = api.list_markets(
        page=st.session_state.trading_page,
        page_size=page_size,
        search=search or None,
        active=active,
        closed=closed,
        volume_min=volume_min if volume_min > 0 else None,
        sort_by=sort_by,
    )
    
    if resp["status"] != 200:
        err = resp.get("error") or resp.get("data", {}).get("detail", "Impossible de récupérer les marchés")
        st.error(err)
        return
    
    data = resp.get("data") or {}
    markets = data.get("items") or data.get("markets") or (data if isinstance(data, list) else [])
    total = data.get("total", len(markets)) if isinstance(data, dict) else len(markets)
    total_pages = data.get("total_pages", 1) if isinstance(data, dict) else 1
    
    # Results count
    st.markdown(f"<p style='color: {COLORS['text_secondary']}; margin: 10px 0;'>Trouvé <strong style='color: {COLORS['text_primary']};'>{total}</strong> marchés</p>", unsafe_allow_html=True)
    
    if not markets:
        st.info("Aucun marché trouvé avec ces filtres.")
        return
    
    # Render cards in a grid (4 per row)
    cards_per_row = 4
    for row_start in range(0, len(markets), cards_per_row):
        row_markets = markets[row_start:row_start + cards_per_row]
        cols = st.columns(cards_per_row)
        
        for idx, (col, market) in enumerate(zip(cols, row_markets)):
            with col:
                global_idx = row_start + idx
                slug = market.get("slug") or f"market-{global_idx}"
                
                # Card HTML
                card_html = _create_market_card(market, global_idx)
                st.markdown(card_html, unsafe_allow_html=True)
                
                # Button below card
                if st.button("Voir détails", key=f"detail_{slug}_{global_idx}", use_container_width=True):
                    st.session_state.selected_market = slug
                    st.session_state.trading_view = "detail"
                    st.rerun()
    
    # Pagination
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("← Précédent", disabled=st.session_state.trading_page <= 1, use_container_width=True):
            st.session_state.trading_page -= 1
            st.rerun()
    
    with col_info:
        st.markdown(
            f"<p style='text-align: center; color: {COLORS['text_secondary']}; margin-top: 8px;'>Page {st.session_state.trading_page} / {total_pages}</p>",
            unsafe_allow_html=True
        )
    
    with col_next:
        if st.button("Suivant →", disabled=st.session_state.trading_page >= total_pages, use_container_width=True):
            st.session_state.trading_page += 1
            st.rerun()


def _render_market_detail(api: APIClient):
    """Render market detail view with chart and trading panel."""
    slug = st.session_state.get("selected_market")
    if not slug:
        st.warning("Aucun marché sélectionné.")
        return
    
    # Back button
    if st.button("← Retour aux marchés"):
        st.session_state.trading_view = "list"
        # Clear prefill state when going back
        for key in ["prefill_action", "prefill_outcome", "prefill_max_qty", "prefill_use_max", "prefill_portfolio_id"]:
            st.session_state.pop(key, None)
        st.rerun()
    
    # Fetch market data - try by slug first, then by condition_id
    with st.spinner("Chargement..."):
        resp = api.get_market(slug)
        
        # If slug lookup fails, try by condition_id
        if resp["status"] != 200:
            resp = api.get_market_by_condition(slug)
    
    if resp["status"] != 200:
        err = resp.get("error") or resp.get("data", {}).get("detail", "Impossible de charger le marché")
        st.error(f"Marché non trouvé: {slug}")
        st.error(err)
        # Offer to go back
        if st.button("Retourner à la liste des marchés"):
            st.session_state.trading_view = "list"
            st.session_state.selected_market = None
            st.rerun()
        return
    
    market = resp["data"]
    name = _display_name(market)
    st.write(market)
    is_closed = market.get("closed", False)
    
    # Market header
    st.markdown(f"## {name}")
    
    # Status and key metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        status_color = COLORS["accent_red"] if is_closed else COLORS["accent_green"]
        status_text = "Clôturé" if is_closed else "Actif"
        st.markdown(f"<div style='text-align: center;'><span style='color: {status_color}; font-weight: bold;'>● {status_text}</span></div>", unsafe_allow_html=True)
    
    with col2:
        st.metric("Volume 24h", f"${format_number(market.get('volume_24h', 0))}")
    
    with col3:
        st.metric("Liquidité", f"${format_number(market.get('liquidity', 0))}")
    
    with col4:
        end_date = market.get("end_date")
        st.metric("Date de fin", format_date(end_date) if end_date else "—")
    
    with col5:
        if not is_closed and end_date:
            time_left = time_until_end(end_date)
            st.metric("Temps restant", time_left if time_left else "—")
        else:
            st.metric("Temps restant", "—")
    
    # Description
    if market.get("description"):
        with st.expander("📝 Description"):
            st.write(market.get("description"))
    
    st.markdown("---")
    
    # Two columns: Chart + Current prices | Trading panel
    col_chart, col_trade = st.columns([2, 1])
    
    with col_chart:
        # Current prices
        st.markdown("### 📊 Prix actuels")
        outcomes = market.get("outcomes") or []
        prices = market.get("outcome_prices") or []
        
        if outcomes and prices:
            price_cols = st.columns(len(outcomes))
            for i, (outcome, price) in enumerate(zip(outcomes, prices)):
                with price_cols[i]:
                    try:
                        price_pct = float(price) * 100
                        color = COLORS["accent_green"] if outcome.upper() == "YES" else COLORS["accent_red"]
                        st.markdown(
                            f"""
                            <div style='background: {COLORS['bg_secondary']}; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid {COLORS['border']};'>
                                <div style='color: {COLORS['text_secondary']}; font-size: 14px; margin-bottom: 8px;'>{outcome}</div>
                                <div style='color: {color}; font-size: 32px; font-weight: bold;'>{price_pct:.1f}%</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    except:
                        st.write(f"{outcome}: —")
        
        # Price history chart
        st.markdown("### 📈 Historique des prix")
        price_resp = api.get_price_history(slug)
        if price_resp["status"] == 200:
            price_data = price_resp.get("data") or {}
            price_history = price_data.get("history", [])
            fig = _create_price_chart(price_history, name)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Historique des prix non disponible")
        
        # Display position if user has one on this market
        _render_position_panel(api, market)
    
    with col_trade:
        st.markdown("### 🎯 Passer un ordre")
        
        if is_closed:
            st.warning("Ce marché est clôturé. Le trading n'est plus possible.")
        else:
            _render_trade_form(api, market)


def _render_trade_form(api: APIClient, market: dict):
    """Render the compact trading form."""
    # Get portfolios
    portfolios_resp = api.list_portfolios()
    if portfolios_resp["status"] != 200:
        st.error("Impossible de charger les portefeuilles")
        return
    
    portfolios = portfolios_resp.get("data", [])
    if not portfolios:
        st.warning("Créez un portefeuille pour commencer à trader.")
        if st.button("📁 Créer un portefeuille"):
            st.session_state.nav_override = "Portfolio"
            st.rerun()
        return
    
    # Market data
    outcomes = market.get("outcomes", [])
    outcome_prices = market.get("outcome_prices", [])
    market_slug = market.get("slug")
    position_market_id = st.session_state.get("selected_market") or market_slug
    
    if not outcomes or not outcome_prices:
        st.warning("Données de prix non disponibles")
        return
    
    # Create price mapping
    price_map = {}
    for outcome, price_str in zip(outcomes, outcome_prices):
        try:
            price_map[outcome] = float(price_str)
        except:
            price_map[outcome] = 0.5
    
    # Prefill handling
    prefill_portfolio_id = st.session_state.get("prefill_portfolio_id")
    
    # Portfolio selection
    portfolio_ids = []
    portfolio_by_id = {}
    for p in portfolios:
        pid = p.get("_id") or p.get("id")
        if pid is None:
            continue
        pid = str(pid)
        portfolio_ids.append(pid)
        portfolio_by_id[pid] = p
    
    default_idx = 0
    if prefill_portfolio_id and str(prefill_portfolio_id) in portfolio_ids:
        default_idx = portfolio_ids.index(str(prefill_portfolio_id))
    
    # Use regular widgets instead of form for real-time updates
    selected_portfolio_id = st.selectbox(
        "Portefeuille",
        options=portfolio_ids,
        index=default_idx,
        format_func=lambda pid: portfolio_by_id[pid].get("name", pid),
        key="order_portfolio"
    )
    selected_portfolio = portfolio_by_id[selected_portfolio_id]
    
    # Get current cash
    portfolio_detail = api.get_portfolio(selected_portfolio_id)
    current_cash = 0
    if portfolio_detail.get("status") == 200:
        current_cash = portfolio_detail.get("data", {}).get("cash_balance", 0)
    
    st.markdown(
        f"<p style='color: {COLORS['accent_green']}; font-size: 14px;'>💰 ${current_cash:,.2f} disponible</p>",
        unsafe_allow_html=True
    )
    
    # Action and token selection
    col_action, col_token = st.columns(2)
    
    with col_action:
        default_action = st.session_state.get("prefill_action", "BUY")
        action = st.selectbox(
            "Action",
            ["BUY", "SELL"],
            index=1 if default_action == "SELL" else 0,
            format_func=lambda x: "🟢 Acheter" if x == "BUY" else "🔴 Vendre",
            key="order_action"
        )
    
    with col_token:
        prefill_outcome = st.session_state.get("prefill_outcome")
        outcome_index = 0
        if prefill_outcome:
            norm_prefill = _normalize_outcome(prefill_outcome)
            for i, o in enumerate(outcomes):
                if _normalize_outcome(o) == norm_prefill:
                    outcome_index = i
                    break
        outcome = st.selectbox("Token", outcomes, index=outcome_index, key="order_token")
    
    # Get positions for sell validation
    trades_resp = api.get_trades(selected_portfolio_id, page=1, page_size=100)
    current_positions = {}
    if trades_resp.get("status") == 200:
        trades_data = trades_resp.get("data", {})
        trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else trades_data
        for trade in trades:
            key = (trade.get("market_id"), _normalize_outcome(trade.get("outcome")))
            if key not in current_positions:
                current_positions[key] = 0
            qty = trade.get("quantity", 0)
            if trade.get("side") == "buy":
                current_positions[key] += qty
            else:
                current_positions[key] -= qty
    
    # Available quantity for this outcome
    market_keys = [position_market_id, market_slug, market.get("condition_id"), market.get("_id")]
    market_keys = [str(k) for k in market_keys if k]
    norm_outcome = _normalize_outcome(outcome)
    available_qty = 0
    for mk in market_keys:
        available_qty = current_positions.get((mk, norm_outcome), available_qty)
        if available_qty > 0:
            break
    
    if action == "SELL":
        st.markdown(
            f"<p style='color: {COLORS['text_secondary']}; font-size: 12px;'>🔹 {available_qty:.2f} tokens disponibles</p>",
            unsafe_allow_html=True
        )
    
    # Price display - update based on selected token
    moc_price = price_map.get(outcome, 0.5)
    st.markdown(
        f"<p style='color: {COLORS['text_secondary']}; font-size: 12px;'>Prix MOC: <strong style='color: {COLORS['text_primary']};'>${moc_price:.4f}</strong></p>",
        unsafe_allow_html=True
    )
    
    # Quantity input
    prefill_max = st.session_state.get("prefill_max_qty")
    use_max = bool(st.session_state.get("prefill_use_max"))
    
    # Determine default quantity
    if action == "SELL" and available_qty > 0:
        max_qty = available_qty
        if use_max and prefill_max:
            default_qty = min(float(prefill_max), max_qty)
        else:
            default_qty = min(10.0, max_qty)
    else:
        max_qty = None
        default_qty = 10.0
    
    quantity = st.number_input(
        "Quantité",
        min_value=0.01,
        value=default_qty,
        step=1.0,
        format="%.2f",
        key="trade_qty"
    )
    
    # Show max info for SELL
    if action == "SELL" and available_qty > 0 and quantity > available_qty:
        st.warning(f"⚠️ Quantité maximale disponible: {available_qty:.2f}")
    
    # Optional note field
    trade_note = st.text_input(
        "📝 Note (optionnel)",
        value="",
        max_chars=500,
        placeholder="Ajouter une note à cet ordre...",
        key="trade_note"
    )
    
    # Total cost - updates in real-time now!
    total_cost = quantity * moc_price
    action_color = COLORS["accent_green"] if action == "BUY" else COLORS["accent_red"]
    st.markdown(
        f"<div style='background: {COLORS['bg_secondary']}; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid {COLORS['border']}; margin: 10px 0;'>"
        f"<span style='color: {COLORS['text_secondary']};'>Total: </span>"
        f"<span style='color: {action_color}; font-size: 20px; font-weight: bold;'>${total_cost:.2f}</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # Submit button
    submitted = st.button(
        "🚀 Exécuter l'ordre",
        type="primary",
        use_container_width=True
    )
    
    # Process order submission
    if submitted:
        # Quantity is already available from the widget above
        
        errors = []
        
        if action == "BUY":
            if current_cash < total_cost:
                errors.append(f"Fonds insuffisants: ${current_cash:.2f} disponible, ${total_cost:.2f} requis")
        else:
            if available_qty < quantity:
                errors.append(f"Tokens insuffisants: {available_qty:.2f} disponible, {quantity:.2f} requis")
        
        if errors:
            for error in errors:
                st.error(error)
        else:
            # Use market slug for the trade
            trade_market_id = market_slug or position_market_id
            
            trade_resp = api.create_trade(
                portfolio_id=selected_portfolio_id,
                market_id=trade_market_id,
                outcome=outcome,
                side=action.lower(),
                quantity=quantity,
                price=moc_price,
                notes=trade_note if trade_note else None
            )
            
            if trade_resp["status"] == 201:
                st.success("✅ Ordre exécuté!")
                
                # Clear prefill state
                for key in ["prefill_action", "prefill_outcome", "prefill_max_qty", "prefill_use_max", "prefill_portfolio_id"]:
                    st.session_state.pop(key, None)
                
                st.balloons()
                # Stay on the same market detail page - just refresh to show updated data
                import time
                time.sleep(1.5)
                st.rerun()
            else:
                error_detail = trade_resp.get("data", {}).get("detail") if isinstance(trade_resp.get("data"), dict) else trade_resp.get("error")
                st.error(f"Erreur: {error_detail}")


def render():
    """Main render function."""
    _init_state()
    api = APIClient(API_URL)
    
    if st.session_state.get("trading_view") == "detail":
        _render_market_detail(api)
    else:
        _render_market_list(api)
