import streamlit as st
from streamlit_option_menu import option_menu
from views import login, trading, metrics, history, account, portfolio
from utils.styles import inject_styles
from config import APP_NAME

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

def main():
    st.set_page_config(page_title=APP_NAME, layout="wide")
    inject_styles()  # Apply dark theme CSS
    init_session()

    # --- Contrôle d'accès
    if not st.session_state["is_authenticated"]:
        login.render()  # <-- utiliser render(), pas show()
        st.stop()       # <-- stoppe le reste du script

    # --- Handle programmatic navigation (from buttons like "Voir Performance")
    nav_override = st.session_state.get("nav_override")
    if nav_override:
        st.session_state["nav_page"] = nav_override
        st.session_state["nav_override"] = None
        # Increment nav_key to force widget recreation
        st.session_state["nav_key"] = st.session_state.get("nav_key", 0) + 1
        st.rerun()

    # --- Sidebar navigation
    with st.sidebar:
        nav_options = ["Trading", "Metrics", "Portfolio", "History", "Account"]
        
        current_page = st.session_state.get("nav_page", "Trading")
        try:
            default_index = nav_options.index(current_page)
        except ValueError:
            default_index = 0

        # Use dynamic key to force widget recreation when needed
        nav_key = f"main_nav_{st.session_state.get('nav_key', 0)}"
        
        page_selected = option_menu(
            menu_title="Navigation",
            options=nav_options,
            icons=["graph-up", "bar-chart", "wallet", "clock-history", "gear"],
            default_index=default_index,
            key=nav_key,
        )
        
        # Only update nav_page if user explicitly clicked a DIFFERENT menu item
        if page_selected != current_page:
            st.session_state["nav_page"] = page_selected
            # Also reset trading view when navigating away from Trading
            if page_selected != "Trading":
                st.session_state["trading_view"] = "list"
                st.session_state["selected_market"] = None
                for key in ["prefill_action", "prefill_outcome", "prefill_max_qty", "prefill_use_max", "prefill_portfolio_id"]:
                    st.session_state.pop(key, None)
            st.rerun()

    # Use current nav_page for routing (NOT the menu selection)
    page = st.session_state.get("nav_page", "Trading")

    # --- Routing
    if page == "Trading":
        trading.render()   # <-- utiliser render()
    elif page == "Metrics":
        metrics.render()
    elif page == "History":
        history.render()
    elif page == "Portfolio":
        portfolio.render()
    elif page == "Account":
        account.render()   # déjà correct
  
if __name__ == "__main__":
    main()
