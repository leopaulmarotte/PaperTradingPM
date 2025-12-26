import streamlit as st
from streamlit_option_menu import option_menu
from views import login, trading, metrics, history, account, portfolio
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
    init_session()

    # --- Contrôle d'accès
    if not st.session_state["is_authenticated"]:
        login.render()  # <-- utiliser render(), pas show()
        st.stop()       # <-- stoppe le reste du script

    # --- Sidebar navigation
    with st.sidebar:
        # Allow programmatic navigation via session_state
        nav_options = ["Trading", "Metrics", "Portfolio", "History", "Account"]
        # If a nav_override is present, use it for default selection and remount widget with a different key
        nav_override = st.session_state.get("nav_override")
        default_page = nav_override or st.session_state.get("nav_page", "Trading")
        try:
            default_index = nav_options.index(default_page)
        except ValueError:
            default_index = 0

        menu_key = "main_nav" if not nav_override else f"main_nav_{default_page}"

        page_selected = option_menu(
            menu_title="Navigation",
            options=nav_options,
            icons=["graph-up", "bar-chart", "wallet", "clock-history", "gear"],
            default_index=default_index,
            key=menu_key,
        )

    # Use override if present, else take the user's selection
    if st.session_state.get("nav_override"):
        page = st.session_state["nav_override"]
        st.session_state["nav_override"] = None
    else:
        page = page_selected

    # Persist current navigation selection
    st.session_state["nav_page"] = page

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
