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
            for p in portfolios:
                name = p.get("name", "Sans nom")
                balance = p.get("cash_balance") or p.get("initial_balance", 0)
                pid = p.get("_id") or p.get("id")
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    with col1:
                        st.markdown(f"**{name}**")
                        st.caption(f"ID: {pid}")
                    with col2:
                        st.metric("Disponible", f"${balance:,.2f}")
                    with col3:
                        if st.button(
                            "Détails" if st.session_state.selected_portfolio_id != pid else "Masquer",
                            key=f"view_{pid}",
                            use_container_width=True,
                        ):
                            # Toggle selection
                            if st.session_state.selected_portfolio_id == pid:
                                st.session_state.selected_portfolio_id = None
                            else:
                                st.session_state.selected_portfolio_id = pid
                            st.rerun()
                    with col4:
                        if st.button("🗑️", key=f"delete_{pid}", use_container_width=True, help="Supprimer ce portfolio"):
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
                                    positions[key] = {"qty": 0.0, "notional": 0.0, "count": 0}
                                delta = qty if side == "buy" else -qty
                                positions[key]["qty"] += delta
                                positions[key]["notional"] += price * qty * (1 if side == "buy" else -1)
                                positions[key]["count"] += 1

                            st.subheader("Composition du portfolio")
                            total_exposure = 0.0
                            has_positions = False
                            for (market, outcome), agg in positions.items():
                                qty = agg["qty"]
                                # Skip positions with zero quantity
                                if qty == 0:
                                    continue
                                avg_price = 0 if qty == 0 else agg["notional"] / (agg["qty"] if agg["qty"] else 1)
                                exposure = qty * avg_price if qty and avg_price else 0
                                total_exposure += exposure
                                has_positions = True

                                cols = st.columns([3, 2, 2, 2, 1.5, 1.5])
                                with cols[0]:
                                    st.write(f"Marché: {market}")
                                    st.caption(f"Issue: {outcome}")
                                with cols[1]:
                                    st.metric("Quantité nette", f"{qty:.4f}")
                                with cols[2]:
                                    st.metric("Prix moyen", f"{avg_price:.4f}")
                                with cols[3]:
                                    st.metric("Exposition", f"${exposure:,.2f}")
                                with cols[4]:
                                    sell_disabled = qty <= 0
                                    if st.button("Modifier", key=f"modify_{pid}_{market}_{outcome}", disabled=sell_disabled, use_container_width=True):
                                        # Navigate to Trading page and open market detail prefilled (edit the position)
                                        st.session_state["nav_page"] = "Trading"
                                        st.session_state["nav_override"] = "Trading"
                                        st.session_state["selected_market"] = market
                                        st.session_state["trading_view"] = "detail"
                                        st.session_state["prefill_action"] = "SELL"
                                        st.session_state["prefill_outcome"] = outcome
                                        st.session_state["prefill_max_qty"] = float(qty)
                                        st.session_state["prefill_portfolio_id"] = pid
                                        st.rerun()
                                with cols[5]:
                                    liquidate_disabled = qty <= 0
                                    if st.button("Liquider", key=f"liquidate_{pid}_{market}_{outcome}", disabled=liquidate_disabled, use_container_width=True):
                                        # Execute immediate liquidation: create SELL trade for full quantity
                                        with st.spinner("Liquidation en cours..."):
                                            # Resolve market details to get outcome price
                                            sell_price = 0.5
                                            market_resp = api.get_market(market)
                                            if not (isinstance(market_resp, dict) and market_resp.get("status") == 200):
                                                # Try by condition id
                                                market_resp = api.get_market_by_condition(market)
                                            if isinstance(market_resp, dict) and market_resp.get("status") == 200:
                                                mdata = market_resp.get("data", {})
                                                outcomes = mdata.get("outcomes") or []
                                                prices = mdata.get("outcome_prices") or []
                                                # Match outcome by case-insensitive comparison
                                                norm_out = (outcome or "").strip().lower()
                                                found_idx = None
                                                for i, o in enumerate(outcomes):
                                                    if (o or "").strip().lower() == norm_out:
                                                        found_idx = i
                                                        break
                                                if found_idx is not None and found_idx < len(prices):
                                                    try:
                                                        sell_price = float(prices[found_idx])
                                                    except Exception:
                                                        sell_price = 0.5
                                            # Create trade
                                            resp_trade = api.create_trade(
                                                portfolio_id=pid,
                                                market_id=market,
                                                outcome=outcome,
                                                side="sell",
                                                quantity=float(qty),
                                                price=float(sell_price),
                                                notes="Liquidation automatique",
                                            )
                                            if resp_trade.get("status") in (200, 201):
                                                st.success("Position liquidée avec succès")
                                                st.rerun()
                                            else:
                                                detail = resp_trade.get("data", {}).get("detail") if isinstance(resp_trade.get("data"), dict) else resp_trade.get("error")
                                                st.error(detail or "Échec de la liquidation")

                            if has_positions:
                                st.caption(f"Exposition totale estimée: {total_exposure:,.2f}")
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
    
