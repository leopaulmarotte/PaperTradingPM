# pages/login.py

import streamlit as st
from utils.api import APIClient
from config import API_URL

api = APIClient(API_URL)


def render():
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email", value="florian.lava@ensae.fr")
            password = st.text_input("Password", type="password", value="bbbbbbbb")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if email and password:
                    result = api.login(email, password)
                    if result["status"] == 200:
                        st.session_state.token = result["data"]["access_token"]
                        # Fetch user info
                        user_result = api.get_me()
                        if user_result["status"] == 200:
                            st.session_state.user = user_result["data"]
                        st.session_state["is_authenticated"] = True
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        error = result.get("data", {}).get("detail", result.get("error", "Login failed"))
                        st.error(f"Login failed: {error}")
                else:
                    st.warning("Please enter email and password")
    
    with tab2:
        st.subheader("Register")
        with st.form("register_form"):
            email = st.text_input("Email")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if not all([email, new_password, confirm_password]):
                    st.warning("Please fill all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    result = api.register(email, new_password)
                    if result["status"] in [200, 201]:
                        st.success("Registration successful! Please login.")
                    else:
                        error = result.get("data", {}).get("detail", result.get("error", "Registration failed"))
                        st.error(f"Registration failed: {error}")
                        st.error(f"Registration failed: {error}")
