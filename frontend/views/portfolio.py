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
                            table_rows = []
                            total_exposure = 0.0
                            for (market, outcome), agg in positions.items():
                                qty = agg["qty"]
                                avg_price = 0 if qty == 0 else agg["notional"] / agg["qty"]
                                exposure = qty * avg_price if qty and avg_price else 0
                                total_exposure += exposure
                                table_rows.append({
                                    "Marché": market,
                                    "Issue": outcome,
                                    "Quantité nette": round(qty, 4),
                                    "Prix moyen": round(avg_price, 4),
                                    "Exposition": round(exposure, 2),
                                })

                            if table_rows:
                                st.dataframe(table_rows, hide_index=True, use_container_width=True)
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

    # Portfolio details
    if st.session_state.selected_portfolio_id:
        st.subheader("Détails du portfolio")
        pid = st.session_state.selected_portfolio_id
        detail_resp = api.get_portfolio(pid)
        if detail_resp.get("status") == 200:
            p = detail_resp.get("data", {})
            name = p.get("name", "Sans nom")
            cash = p.get("cash_balance", p.get("initial_balance", 0))
            init_bal = p.get("initial_balance", 0)
            st.markdown(f"### {name}")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Disponible", f"${cash:,.2f}")
            with col2:
                st.metric("Montant initial", f"${init_bal:,.2f}")
        else:
            detail = detail_resp.get("data", {}).get("detail") if isinstance(detail_resp.get("data"), dict) else detail_resp.get("error")
            st.error(detail or "Impossible de charger le portfolio")
            return

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
                # Aggregate positions by (market_id, outcome)
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

                st.subheader("Positions (Yes/No ou issues)")
                table_rows = []
                total_exposure = 0.0
                for (market, outcome), agg in positions.items():
                    qty = agg["qty"]
                    avg_price = 0 if qty == 0 else agg["notional"] / agg["qty"]
                    exposure = qty * avg_price if qty and avg_price else 0
                    total_exposure += exposure
                    table_rows.append({
                        "Marché": market,
                        "Issue": outcome,
                        "Quantité nette": round(qty, 4),
                        "Prix moyen": round(avg_price, 4),
                        "Exposition": round(exposure, 2),
                    })

                if table_rows:
                    st.dataframe(table_rows, hide_index=True, use_container_width=True)
                    st.caption(f"Exposition totale estimée: {total_exposure:,.2f}")
                else:
                    st.info("Pas encore de positions.")
            else:
                st.info("Pas de trades pour ce portfolio.")
        else:
            detail = trades_resp.get("data", {}).get("detail") if isinstance(trades_resp.get("data"), dict) else trades_resp.get("error")
            st.error(detail or "Impossible de récupérer les trades")
