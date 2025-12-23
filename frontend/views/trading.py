# from utils.api import get_orderbook, get_trades
# from utils.design_html import render_html_table
# import streamlit as st


# # def render():
# #     st.title("Trading")

# #     # --- Sélection du marché
# #     markets = ["BTC-USD", "ETH-USD", "SOL-USD"]

# #     selected_market = st.selectbox(
# #         "Marché",
# #         markets,
# #         index=markets.index(st.session_state.get("selected_market", markets[0]))
# #         if st.session_state.get("selected_market") in markets
# #         else 0,
# #         key="market_select"
# #     )

# #     st.session_state["selected_market"] = selected_market

# #     st.divider()

#     # --- Layout
#     col1, col2 = st.columns(2)

#     # --- Orderbook
#     with col1:
#         st.subheader("Order Book")

#         bids, asks = get_orderbook()

#         st.write("🟢 Bids")
#         render_html_table(bids, height=250)

#         st.write("🔴 Asks")
#         render_html_table(asks, height=250)

#     # --- Trades
#     with col2:
#         st.subheader("Derniers trades")

#         trades = get_trades()
#         render_html_table(trades, height=400)

#     st.divider()

#     if st.button("Rafraîchir", key="refresh_trading"):
#         st.rerun()
