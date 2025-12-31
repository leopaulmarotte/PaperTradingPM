import streamlit as st
from utils.api import APIClient
from config import API_URL


def render():
    st.title("My Account")
    
    api = APIClient(API_URL)
    
    # --- Sections en onglets
    tab1, tab2 = st.tabs(["Profile", "Security"])
    
    with tab1:
        st.subheader("Profile Information")
        
        # Récupérer les infos utilisateur
        user_info = api.get_me()
        if user_info["status"] == 200:
            user_data = user_info["data"]
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Email:** {user_data.get('email')}")
            with col2:
                st.write(f"**ID:** {user_data.get('id')}")
            st.write(f"**Rôles:** {', '.join(user_data.get('roles', []))}")
        else:
            st.error("Unable to retrieve user information")
        
        st.divider()
        
        # --- Bouton de déconnexion
        if st.button("Log out", use_container_width=True):
            # On met à jour la session
            st.session_state.is_authenticated = False
            # On peut vider les infos utilisateur si tu veux
            st.session_state.username = ""
            st.session_state.balance = 0.0
            # On "relance" Streamlit pour revenir à la page login
            st.rerun()
    
    with tab2:
        st.subheader("Change Password")
        
        with st.form("change_password_form"):
            current_password = st.text_input(
                "Current password",
                type="password",
                help="Enter your current password for verification"
            )
            new_password = st.text_input(
                "New password",
                type="password",
                help="Minimum 8 characters"
            )
            new_password_confirm = st.text_input(
                "Confirm new password",
                type="password",
                help="Must match the new password"
            )
            submitted = st.form_submit_button(
                "Change password",
                use_container_width=True
            )
            if submitted:
                # Client-side validation
                if not current_password:
                    st.error("Please enter your current password")
                elif not new_password:
                    st.error("Please enter a new password")
                elif len(new_password) < 8:
                    st.error("The new password must be at least 8 characters long")
                elif new_password != new_password_confirm:
                    st.error("The new passwords do not match")
                elif current_password == new_password:
                    st.error("The new password must be different from the old one")
                else:
                    # API call
                    response = api.change_password(
                        current_password=current_password,
                        new_password=new_password,
                        new_password_confirm=new_password_confirm,
                    )
                    if response["status"] == 200:
                        st.success("Password changed successfully!")
                        st.info("Please log in again with your new password.")
                        # Log out user after password change
                        st.session_state.is_authenticated = False
                        st.session_state.token = None
                        st.rerun()
                    elif response["status"] == 401:
                        st.error("Incorrect current password")
                    else:
                        error_msg = response.get("data", {}).get("detail", response.get("error", "Unknown error"))
                        st.error(f"Error: {error_msg}")
