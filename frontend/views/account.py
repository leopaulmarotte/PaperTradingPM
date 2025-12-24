import streamlit as st
from utils.api import APIClient
from config import API_URL


def render():
    st.title("Mon compte")
    
    api = APIClient(API_URL)
    
    # --- Sections en onglets
    tab1, tab2 = st.tabs(["Profil", "Sécurité"])
    
    with tab1:
        st.subheader("Informations du profil")
        
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
            st.error("Impossible de récupérer les informations utilisateur")
        
        st.divider()
        
        # --- Bouton de déconnexion
        if st.button("Se déconnecter", use_container_width=True):
            # On met à jour la session
            st.session_state.is_authenticated = False
            # On peut vider les infos utilisateur si tu veux
            st.session_state.username = ""
            st.session_state.balance = 0.0
            # On "relance" Streamlit pour revenir à la page login
            st.rerun()
    
    with tab2:
        st.subheader("Changer le mot de passe")
        
        with st.form("change_password_form"):
            current_password = st.text_input(
                "Mot de passe actuel",
                type="password",
                help="Entrez votre mot de passe actuel pour vérification"
            )
            
            new_password = st.text_input(
                "Nouveau mot de passe",
                type="password",
                help="Minimum 8 caractères"
            )
            
            new_password_confirm = st.text_input(
                "Confirmer le nouveau mot de passe",
                type="password",
                help="Doit correspondre au nouveau mot de passe"
            )
            
            submitted = st.form_submit_button(
                "Changer le mot de passe",
                use_container_width=True
            )
            
            if submitted:
                # Validation côté client
                if not current_password:
                    st.error("Veuillez entrer votre mot de passe actuel")
                elif not new_password:
                    st.error("Veuillez entrer un nouveau mot de passe")
                elif len(new_password) < 8:
                    st.error("Le nouveau mot de passe doit contenir au moins 8 caractères")
                elif new_password != new_password_confirm:
                    st.error("Les nouveaux mots de passe ne correspondent pas")
                elif current_password == new_password:
                    st.error("Le nouveau mot de passe doit être différent de l'ancien")
                else:
                    # Appel API
                    response = api.change_password(
                        current_password=current_password,
                        new_password=new_password,
                        new_password_confirm=new_password_confirm,
                    )
                    
                    if response["status"] == 200:
                        st.success("✅ Mot de passe changé avec succès!")
                        st.info("Veuillez vous reconnecter avec votre nouveau mot de passe.")
                        # Déconnecter l'utilisateur après changement
                        st.session_state.is_authenticated = False
                        st.session_state.token = None
                        st.rerun()
                    elif response["status"] == 401:
                        st.error("❌ Mot de passe actuel incorrect")
                    else:
                        error_msg = response.get("data", {}).get("detail", response.get("error", "Erreur inconnue"))
                        st.error(f"❌ Erreur: {error_msg}")
