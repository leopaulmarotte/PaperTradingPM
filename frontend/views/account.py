import streamlit as st

def render():
    st.title("Mon compte")

    # --- Bouton de déconnexion
    if st.button("Se déconnecter"):
        # On met à jour la session
        st.session_state.is_authenticated = False
        # On peut vider les infos utilisateur si tu veux
        st.session_state.username = ""
        st.session_state.balance = 0.0
        # On “relance” Streamlit pour revenir à la page login
        st.rerun()
