import streamlit as st
from streamlit_option_menu import option_menu
from views import login, trading, metrics, history, account
from config import APP_NAME

def init_session():
    defaults = {
        "is_authenticated": False,
        "user_id": None,
        "token": None,
        "selected_market": None,
        "trades_df": None,
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
        page = option_menu(
        menu_title="Navigation",
        options=["Trading", "Metrics", "History", "Account"],
        icons=["graph-up", "bar-chart", "clock-history", "gear"],
        default_index=0,
    )

    # --- Routing
    if page == "Trading":
        trading.render()   # <-- utiliser render()
    elif page == "Metrics":
        metrics.render()
    elif page == "History":
        history.render()
    elif page == "Account":
        account.render()   # déjà correct

if __name__ == "__main__":
    main()
