import streamlit as st

from config import API_URL
from utils.api import APIClient


def render():
    st.title("Portfolios")

    api = APIClient(API_URL)

    if "selected_portfolio_id" not in st.session_state:
        st.session_state.selected_portfolio_id = None

    # Creation form
    with st.expander("➕ Créer un portfolio", expanded=True):
        with st.form("create_portfolio_form"):
            name = st.text_input("Nom du portfolio", placeholder="Ex: Swing BTC")
            initial_balance = st.number_input(
                "Montant disponible", min_value=0.0, step=100.0, value=1000.0
            )
            submitted = st.form_submit_button("Créer", use_container_width=True)
            if submitted:
                if not name:
                    st.error("Le nom est requis")
                elif initial_balance <= 0:
                    st.error("Le montant doit être positif")
                else:
                    resp = api.create_portfolio(name, initial_balance)
                    if resp.get("status") == 201 or resp.get("status") == 200:
                        st.success("Portfolio créé")
                        st.rerun()
                    else:
                        detail = resp.get("data", {}).get("detail") if isinstance(resp.get("data"), dict) else resp.get("error")
                        st.error(detail or "Impossible de créer le portfolio")

    st.divider()

    # List portfolios
    st.subheader("Vos portfolios")
    resp = api.list_portfolios()
    if resp.get("status") == 200:
        portfolios = resp.get("data") or []
        if isinstance(portfolios, dict):
            portfolios = list(portfolios.values())
        if portfolios:
            # CSS for portfolio cards
            st.markdown("""
            <style>
            .portfolio-card {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                border: 1px solid rgba(99, 102, 241, 0.2);
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            .portfolio-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }
            .portfolio-name {
                font-size: 1.4rem;
                font-weight: 700;
                color: #ffffff;
                margin: 0;
            }
            .portfolio-id {
                font-size: 0.75rem;
                color: #888;
                margin-top: 4px;
            }
            .portfolio-metrics {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 16px;
            }
            .metric-box {
                background: rgba(255, 255, 255, 0.03);
                border-radius: 12px;
                padding: 16px;
                text-align: center;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            .metric-label {
                font-size: 0.75rem;
                color: #888;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
            }
            .metric-value {
                font-size: 1.3rem;
                font-weight: 700;
                color: #fff;
            }
            .metric-value.positive {
                color: #22c55e;
            }
            .metric-value.negative {
                color: #ef4444;
            }
            .metric-value.neutral {
                color: #6366f1;
            }
            .perf-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            .perf-badge.positive {
                background: rgba(34, 197, 94, 0.15);
                color: #22c55e;
            }
            .perf-badge.negative {
                background: rgba(239, 68, 68, 0.15);
                color: #ef4444;
            }
            .perf-badge.neutral {
                background: rgba(99, 102, 241, 0.15);
                color: #6366f1;
            }
            </style>
            """, unsafe_allow_html=True)
            
            for p in portfolios:
                name = p.get("name", "Sans nom")
                cash_balance = p.get("cash_balance") or p.get("initial_balance", 0)
                initial_balance = p.get("initial_balance", 0)
                pid = p.get("_id") or p.get("id")
                
                # Calculate total portfolio value (cash + positions)
                total_exposure = 0.0
                positions_count = 0
                
                # Get trades to calculate positions value
                trades_resp = api.get_trades(pid, page=1, page_size=100)
                if trades_resp.get("status") == 200:
                    data_trades = trades_resp.get("data")
                    if isinstance(data_trades, dict):
                        trades = data_trades.get("trades") or []
                    elif isinstance(data_trades, list):
                        trades = data_trades
                    else:
                        trades = []
                    
                    if trades:
                        trades = sorted(trades, key=lambda t: t.get("created_at") or t.get("timestamp") or "")
                        positions = {}
                        for t in trades:
                            if not isinstance(t, dict):
                                continue
                            market = t.get("market_id") or "N/A"
                            outcome = t.get("outcome") or "N/A"
                            side = t.get("side") or "buy"
                            qty = t.get("quantity", 0) or 0
                            price = t.get("price", 0) or 0
                            key = (market, outcome)
                            if key not in positions:
                                positions[key] = {"qty": 0.0, "notional": 0.0}
                            delta = qty if side == "buy" else -qty
                            positions[key]["qty"] += delta
                            positions[key]["notional"] += price * qty * (1 if side == "buy" else -1)
                        
                        for (market, outcome), agg in positions.items():
                            qty = agg["qty"]
                            if qty <= 0:
                                continue
                            positions_count += 1
                            avg_price = agg["notional"] / qty if qty else 0
                            current_price = avg_price
                            
                            # Try to get current price
                            market_resp = api.get_market(market)
                            if not (isinstance(market_resp, dict) and market_resp.get("status") == 200):
                                market_resp = api.get_market_by_condition(market)
                            if isinstance(market_resp, dict) and market_resp.get("status") == 200:
                                mdata = market_resp.get("data", {})
                                outcomes_list = mdata.get("outcomes") or []
                                prices = mdata.get("outcome_prices") or []
                                norm_out = (outcome or "").strip().lower()
                                for i, o in enumerate(outcomes_list):
                                    if (o or "").strip().lower() == norm_out and i < len(prices):
                                        try:
                                            current_price = float(prices[i])
                                        except:
                                            pass
                                        break
                            
                            total_exposure += qty * current_price
                
                # Calculate total value and performance
                total_value = cash_balance + total_exposure
                if initial_balance > 0:
                    performance = ((total_value - initial_balance) / initial_balance) * 100
                else:
                    performance = 0
                
                perf_class = "positive" if performance > 0 else ("negative" if performance < 0 else "neutral")
                perf_sign = "+" if performance > 0 else ""
                
                # Render portfolio card
                st.markdown(f"""
                <div class="portfolio-card">
                    <div class="portfolio-header">
                        <div>
                            <div class="portfolio-name">{name}</div>
                            <div class="portfolio-id">ID: {pid}</div>
                        </div>
                        <div class="perf-badge {perf_class}">{perf_sign}{performance:.2f}%</div>
                    </div>
                    <div class="portfolio-metrics">
                        <div class="metric-box">
                            <div class="metric-label">Valeur Totale</div>
                            <div class="metric-value neutral">${total_value:,.2f}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Cash Disponible</div>
                            <div class="metric-value">${cash_balance:,.2f}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">En Position</div>
                            <div class="metric-value">${total_exposure:,.2f}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">P&L</div>
                            <div class="metric-value {perf_class}">{perf_sign}${total_value - initial_balance:,.2f}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                with col1:
                    if st.button(
                        "📊 Détails" if st.session_state.selected_portfolio_id != pid else "🔼 Masquer",
                        key=f"view_{pid}",
                        use_container_width=True,
                    ):
                        if st.session_state.selected_portfolio_id == pid:
                            st.session_state.selected_portfolio_id = None
                        else:
                            st.session_state.selected_portfolio_id = pid
                        st.rerun()
                with col2:
                    if st.button("📈 Metrics", key=f"metrics_{pid}", use_container_width=True):
                        st.session_state["metrics_portfolio_id"] = pid
                        st.session_state["nav_override"] = "Metrics"
                        st.rerun()
                with col3:
                    if st.button("💹 Trader", key=f"trade_{pid}", use_container_width=True):
                        st.session_state["nav_override"] = "Trading"
                        st.rerun()
                with col4:
                    if st.button("🗑️ Supprimer", key=f"delete_{pid}", use_container_width=True):
                        del_resp = api.delete_portfolio(pid)
                        if del_resp.get("status") in (200, 204):
                            st.success("Portfolio supprimé")
                            if st.session_state.selected_portfolio_id == pid:
                                st.session_state.selected_portfolio_id = None
                            st.rerun()
                        else:
                            detail = del_resp.get("data", {}).get("detail") if isinstance(del_resp.get("data"), dict) else del_resp.get("error")
                            st.error(detail or "Suppression impossible")

                # Inline detail if selected
                if st.session_state.selected_portfolio_id == pid:
                    detail_resp = api.get_portfolio(pid)
                    if detail_resp.get("status") == 200:
                        p_detail = detail_resp.get("data", {})
                        init_bal = p_detail.get("initial_balance", 0)
                        st.caption(f"Montant initial: ${init_bal:,.2f}")
                    else:
                        detail = detail_resp.get("data", {}).get("detail") if isinstance(detail_resp.get("data"), dict) else detail_resp.get("error")
                        st.error(detail or "Impossible de charger le portfolio")
                        st.divider()
                        continue

                    trades_resp = api.get_trades(pid, page=1, page_size=100)
                    if trades_resp.get("status") == 200:
                        data_trades = trades_resp.get("data")
                        if isinstance(data_trades, dict):
                            trades = data_trades.get("trades") or []
                        elif isinstance(data_trades, list):
                            trades = data_trades
                        else:
                            trades = []

                        if trades:
                            # Sort trades by date (oldest first) for correct cost basis calculation
                            trades = sorted(trades, key=lambda t: t.get("created_at") or t.get("timestamp") or "")
                            
                            positions = {}
                            for t in trades:
                                if not isinstance(t, dict):
                                    continue
                                market = t.get("market_id") or "N/A"
                                outcome = t.get("outcome") or "N/A"
                                side = t.get("side") or "buy"
                                qty = t.get("quantity", 0) or 0
                                price = t.get("price", 0) or 0
                                key = (market, outcome)
                                if key not in positions:
                                    positions[key] = {"qty": 0.0, "notional": 0.0, "count": 0, "cost": 0.0}
                                
                                # Track cost basis BEFORE updating quantity
                                if side == "buy":
                                    positions[key]["cost"] += qty * price
                                else:
                                    # Reduce cost proportionally when selling
                                    # Calculate average cost per unit before this sale
                                    current_qty = positions[key]["qty"]
                                    current_cost = positions[key]["cost"]
                                    if current_qty > 0:
                                        avg_cost_per_unit = current_cost / current_qty
                                        positions[key]["cost"] -= qty * avg_cost_per_unit
                                        # Ensure cost doesn't go negative
                                        if positions[key]["cost"] < 0:
                                            positions[key]["cost"] = 0
                                
                                # Now update quantity
                                delta = qty if side == "buy" else -qty
                                positions[key]["qty"] += delta
                                positions[key]["notional"] += price * qty * (1 if side == "buy" else -1)
                                positions[key]["count"] += 1

                            st.subheader("📊 Composition du portfolio")
                            
                            # Prepare positions data with current prices
                            positions_data = []
                            total_exposure = 0.0
                            total_cost = 0.0
                            
                            for (market, outcome), agg in positions.items():
                                qty = agg["qty"]
                                if qty == 0:
                                    continue
                                    
                                avg_price = 0 if qty == 0 else agg["notional"] / (agg["qty"] if agg["qty"] else 1)
                                cost_basis = agg.get("cost", 0)
                                
                                # Get current market price and question
                                current_price = avg_price
                                market_question = market  # Default to slug
                                market_resp = api.get_market(market)
                                if not (isinstance(market_resp, dict) and market_resp.get("status") == 200):
                                    market_resp = api.get_market_by_condition(market)
                                if isinstance(market_resp, dict) and market_resp.get("status") == 200:
                                    mdata = market_resp.get("data", {})
                                    # Get readable market question
                                    market_question = mdata.get("question") or market
                                    outcomes_list = mdata.get("outcomes") or []
                                    prices = mdata.get("outcome_prices") or []
                                    norm_out = (outcome or "").strip().lower()
                                    for i, o in enumerate(outcomes_list):
                                        if (o or "").strip().lower() == norm_out and i < len(prices):
                                            try:
                                                current_price = float(prices[i])
                                            except Exception:
                                                pass
                                            break
                                
                                current_value = qty * current_price
                                total_exposure += current_value
                                total_cost += cost_basis
                                
                                # Performance
                                if cost_basis > 0:
                                    performance = ((current_value - cost_basis) / cost_basis) * 100
                                else:
                                    performance = 0
                                
                                positions_data.append({
                                    "market": market,
                                    "market_question": market_question,
                                    "outcome": outcome,
                                    "qty": qty,
                                    "current_price": current_price,
                                    "cost_basis": cost_basis,
                                    "current_value": current_value,
                                    "performance": performance,
                                })
                            
                            if positions_data:
                                # CSS for position cards
                                st.markdown("""
                                <style>
                                .position-card {
                                    background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
                                    border-radius: 12px;
                                    padding: 20px;
                                    margin-bottom: 15px;
                                    border-left: 4px solid #6366f1;
                                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                                }
                                .position-header {
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: flex-start;
                                    margin-bottom: 15px;
                                }
                                .position-market {
                                    font-size: 14px;
                                    font-weight: 600;
                                    color: #e0e0e0;
                                    max-width: 300px;
                                    word-wrap: break-word;
                                }
                                .position-outcome {
                                    display: inline-block;
                                    background: #6366f1;
                                    color: white;
                                    padding: 4px 12px;
                                    border-radius: 20px;
                                    font-size: 12px;
                                    font-weight: 500;
                                }
                                .position-metrics {
                                    display: grid;
                                    grid-template-columns: repeat(5, 1fr);
                                    gap: 15px;
                                }
                                .metric-box {
                                    text-align: center;
                                    padding: 10px;
                                    background: rgba(255,255,255,0.05);
                                    border-radius: 8px;
                                }
                                .metric-label {
                                    font-size: 11px;
                                    color: #888;
                                    text-transform: uppercase;
                                    letter-spacing: 0.5px;
                                }
                                .metric-value {
                                    font-size: 18px;
                                    font-weight: 700;
                                    color: #fff;
                                    margin-top: 4px;
                                }
                                .perf-positive { color: #22c55e !important; }
                                .perf-negative { color: #ef4444 !important; }
                                .portfolio-summary {
                                    display: flex;
                                    gap: 20px;
                                    margin-top: 20px;
                                }
                                .summary-card {
                                    flex: 1;
                                    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
                                    border-radius: 10px;
                                    padding: 15px 25px;
                                    text-align: center;
                                }
                                .summary-card.perf-positive-bg {
                                    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
                                }
                                .summary-card.perf-negative-bg {
                                    background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
                                }
                                .summary-label {
                                    font-size: 12px;
                                    color: rgba(255,255,255,0.8);
                                    text-transform: uppercase;
                                }
                                .summary-value {
                                    font-size: 28px;
                                    font-weight: 700;
                                    color: white;
                                }
                                </style>
                                """, unsafe_allow_html=True)
                                
                                for pos in positions_data:
                                    perf_class = "perf-positive" if pos["performance"] >= 0 else "perf-negative"
                                    perf_sign = "+" if pos["performance"] >= 0 else ""
                                    # Truncate market question if too long
                                    market_display = pos.get("market_question", pos["market"])
                                    if len(market_display) > 60:
                                        market_display = market_display[:57] + "..."
                                    
                                    st.markdown(f"""
                                    <div class="position-card">
                                        <div class="position-header">
                                            <div class="position-market">{market_display}</div>
                                            <span class="position-outcome">{pos["outcome"]}</span>
                                        </div>
                                        <div class="position-metrics">
                                            <div class="metric-box">
                                                <div class="metric-label">Quantité</div>
                                                <div class="metric-value">{pos["qty"]:.2f}</div>
                                            </div>
                                            <div class="metric-box">
                                                <div class="metric-label">Prix Actuel</div>
                                                <div class="metric-value">${pos["current_price"]:.4f}</div>
                                            </div>
                                            <div class="metric-box">
                                                <div class="metric-label">Coût</div>
                                                <div class="metric-value">${pos["cost_basis"]:.2f}</div>
                                            </div>
                                            <div class="metric-box">
                                                <div class="metric-label">Valeur</div>
                                                <div class="metric-value">${pos["current_value"]:.2f}</div>
                                            </div>
                                            <div class="metric-box">
                                                <div class="metric-label">Performance</div>
                                                <div class="metric-value {perf_class}">{perf_sign}{pos["performance"]:.1f}%</div>
                                            </div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    # Buttons row
                                    btn_col1, btn_col2, btn_spacer = st.columns([1, 1, 4])
                                    with btn_col1:
                                        if st.button("✏️ Modifier", key=f"modify_{pid}_{pos['market']}_{pos['outcome']}", use_container_width=True):
                                            st.session_state["nav_page"] = "Trading"
                                            st.session_state["nav_override"] = "Trading"
                                            st.session_state["selected_market"] = pos["market"]
                                            st.session_state["trading_view"] = "detail"
                                            st.session_state["prefill_action"] = "SELL"
                                            st.session_state["prefill_outcome"] = pos["outcome"]
                                            st.session_state["prefill_max_qty"] = float(pos["qty"])
                                            st.session_state["prefill_portfolio_id"] = pid
                                            st.rerun()
                                    with btn_col2:
                                        if st.button("🔥 Liquider", key=f"liquidate_{pid}_{pos['market']}_{pos['outcome']}", use_container_width=True):
                                            with st.spinner("Liquidation en cours..."):
                                                sell_price = pos["current_price"]
                                                resp_trade = api.create_trade(
                                                    portfolio_id=pid,
                                                    market_id=pos["market"],
                                                    outcome=pos["outcome"],
                                                    side="sell",
                                                    quantity=float(pos["qty"]),
                                                    price=float(sell_price),
                                                    notes="Liquidation automatique",
                                                )
                                                if resp_trade.get("status") in (200, 201):
                                                    st.success("Position liquidée avec succès")
                                                    st.rerun()
                                                else:
                                                    detail = resp_trade.get("data", {}).get("detail") if isinstance(resp_trade.get("data"), dict) else resp_trade.get("error")
                                                    st.error(detail or "Échec de la liquidation")
                                    
                                    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                                
                                # Calculate global performance based on initial balance vs current total value
                                cash_balance = p_detail.get("cash_balance", 0) or 0
                                total_value = cash_balance + total_exposure
                                
                                if init_bal > 0:
                                    global_perf = ((total_value - init_bal) / init_bal) * 100
                                    perf_sign = "+" if global_perf >= 0 else ""
                                    perf_class = "perf-positive-bg" if global_perf >= 0 else "perf-negative-bg"
                                else:
                                    global_perf = 0
                                    perf_sign = ""
                                    perf_class = ""
                                
                                # Portfolio summary with total value and performance
                                st.markdown(f"""
                                <div class="portfolio-summary">
                                    <div class="summary-card">
                                        <div class="summary-label">Valeur Totale</div>
                                        <div class="summary-value">${total_value:,.2f}</div>
                                    </div>
                                    <div class="summary-card {perf_class}">
                                        <div class="summary-label">Performance Globale</div>
                                        <div class="summary-value">{perf_sign}{global_perf:.1f}%</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.info("Pas encore de positions.")
                        else:
                            st.info("Pas de trades pour ce portfolio.")
                    else:
                        detail = trades_resp.get("data", {}).get("detail") if isinstance(trades_resp.get("data"), dict) else trades_resp.get("error")
                        st.error(detail or "Impossible de récupérer les trades")

                st.divider()
        else:
            st.info("Aucun portfolio pour l'instant. Créez-en un ci-dessus.")
    else:
        detail = resp.get("data", {}).get("detail") if isinstance(resp.get("data"), dict) else resp.get("error")
        st.error(detail or "Impossible de récupérer les portfolios")
    
