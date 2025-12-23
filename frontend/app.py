"""
Polymarket Paper Trading Dashboard - Streamlit Frontend

A simple frontend to test the FastAPI backend features:
- Authentication (login/register)
- Market browsing with filters
- Portfolio management
- Trade simulation
"""
import os
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

# ==================== Configuration ====================

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Page config
st.set_page_config(
    page_title="Polymarket Paper Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==================== Session State ====================

def init_session_state():
    """Initialize session state variables."""
    if "token" not in st.session_state:
        st.session_state.token = None
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "markets"


init_session_state()


# ==================== API Client ====================

class APIClient:
    """Simple API client for backend requests."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def _headers(self) -> dict:
        """Get headers with auth token if available."""
        headers = {"Content-Type": "application/json"}
        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        return headers
    
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make GET request."""
        try:
            resp = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            return {"status": resp.status_code, "data": resp.json() if resp.text else None}
        except requests.exceptions.ConnectionError:
            return {"status": 0, "error": "Cannot connect to backend"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request."""
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                json=data,
                timeout=30,
            )
            return {"status": resp.status_code, "data": resp.json() if resp.text else None}
        except requests.exceptions.ConnectionError:
            return {"status": 0, "error": "Cannot connect to backend"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    # Auth endpoints
    def login(self, username: str, password: str) -> dict:
        """Login and get token."""
        try:
            resp = requests.post(
                f"{self.base_url}/auth/token",
                data={"username": username, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            return {"status": resp.status_code, "data": resp.json() if resp.text else None}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def register(self, email: str, username: str, password: str) -> dict:
        """Register new user."""
        return self._post("/auth/register", {
            "email": email,
            "username": username,
            "password": password,
        })
    
    def get_me(self) -> dict:
        """Get current user profile."""
        return self._get("/auth/me")
    
    # Health endpoint
    def health(self) -> dict:
        """Check API health."""
        return self._get("/health")
    
    # Markets endpoints
    def list_markets(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        active: Optional[bool] = None,
        closed: Optional[bool] = None,
        volume_min: Optional[float] = None,
        sort_by: Optional[str] = None,
    ) -> dict:
        """List markets with filters."""
        params = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        if active is not None:
            params["active"] = active
        if closed is not None:
            params["closed"] = closed
        if volume_min:
            params["volume_min"] = volume_min
        if sort_by:
            params["sort_by"] = sort_by
        return self._get("/markets", params)
    
    def get_top_markets(self, limit: int = 10, sort_by: str = "volume_24h") -> dict:
        """Get top markets."""
        return self._get("/markets/top", {"limit": limit, "sort_by": sort_by})
    
    def get_market(self, slug: str) -> dict:
        """Get market by slug."""
        return self._get(f"/markets/by-slug/{slug}")
    
    def get_price_history(self, slug: str, outcome_index: int = 0) -> dict:
        """Get price history for market."""
        return self._get(f"/markets/by-slug/{slug}/prices", {"outcome_index": outcome_index})
    
    def get_sync_stats(self) -> dict:
        """Get market sync statistics."""
        return self._get("/markets/stats")
    
    # Portfolio endpoints
    def list_portfolios(self) -> dict:
        """List user portfolios."""
        return self._get("/portfolios")
    
    def create_portfolio(self, name: str, initial_balance: float) -> dict:
        """Create new portfolio."""
        return self._post("/portfolios", {
            "name": name,
            "initial_balance": initial_balance,
        })
    
    def get_portfolio(self, portfolio_id: str) -> dict:
        """Get portfolio details."""
        return self._get(f"/portfolios/{portfolio_id}")


api = APIClient(API_URL)


# ==================== UI Components ====================

def show_login_form():
    """Show login/register forms."""
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if username and password:
                    result = api.login(username, password)
                    if result["status"] == 200:
                        st.session_state.token = result["data"]["access_token"]
                        # Fetch user info
                        user_result = api.get_me()
                        if user_result["status"] == 200:
                            st.session_state.user = user_result["data"]
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        error = result.get("data", {}).get("detail", result.get("error", "Login failed"))
                        st.error(f"Login failed: {error}")
                else:
                    st.warning("Please enter username and password")
    
    with tab2:
        st.subheader("Register")
        with st.form("register_form"):
            email = st.text_input("Email")
            new_username = st.text_input("Username", key="reg_username")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if not all([email, new_username, new_password, confirm_password]):
                    st.warning("Please fill all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    result = api.register(email, new_username, new_password)
                    if result["status"] in [200, 201]:
                        st.success("Registration successful! Please login.")
                    else:
                        error = result.get("data", {}).get("detail", result.get("error", "Registration failed"))
                        st.error(f"Registration failed: {error}")


def show_sidebar():
    """Show sidebar navigation."""
    with st.sidebar:
        st.title("📈 Paper Trading")
        
        if st.session_state.user:
            st.write(f"👤 **{st.session_state.user.get('username', 'User')}**")
            st.write(f"Role: {st.session_state.user.get('role', 'user')}")
            
            if st.button("Logout"):
                st.session_state.token = None
                st.session_state.user = None
                st.rerun()
            
            st.divider()
        
        # Navigation
        st.subheader("Navigation")
        
        pages = {
            "markets": "🏪 Markets",
            "portfolios": "💼 Portfolios",
            "health": "🏥 System Health",
        }
        
        for key, label in pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.current_page = key
                st.rerun()


def show_health_page():
    """Show system health status."""
    st.header("🏥 System Health")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("API Health")
        health = api.health()
        if health["status"] == 200:
            data = health["data"]
            st.success(f"Status: {data.get('status', 'unknown')}")
            st.json(data)
        else:
            st.error(f"API unavailable: {health.get('error', 'Unknown error')}")
    
    with col2:
        st.subheader("Market Sync Stats")
        if st.session_state.token:
            stats = api.get_sync_stats()
            if stats["status"] == 200:
                data = stats["data"]
                st.metric("Total Markets", data.get("total_markets", 0))
                st.metric("Active Markets", data.get("active_markets", 0))
                st.metric("Closed Markets", data.get("closed_markets", 0))
                
                if data.get("newest_sync"):
                    st.write(f"Last sync: {data['newest_sync']}")
            else:
                st.warning("Could not fetch sync stats")
        else:
            st.info("Login to view sync statistics")


def show_markets_page():
    """Show markets browser."""
    st.header("🏪 Markets Explorer")
    
    if not st.session_state.token:
        st.warning("Please login to browse markets")
        return
    
    # Filters
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search = st.text_input("Search", placeholder="Search markets...")
        with col2:
            status_filter = st.selectbox("Status", ["All", "Active Only", "Closed Only"])
        with col3:
            volume_min = st.number_input("Min Volume ($)", min_value=0, value=0, step=1000)
        with col4:
            sort_by = st.selectbox("Sort By", ["volume_24h", "volume", "liquidity"])
    
    # Parse filters
    active = None
    closed = None
    if status_filter == "Active Only":
        active = True
        closed = False
    elif status_filter == "Closed Only":
        closed = True
    
    # Pagination
    col1, col2 = st.columns([3, 1])
    with col2:
        page_size = st.selectbox("Per page", [10, 20, 50], index=1)
    
    if "markets_page" not in st.session_state:
        st.session_state.markets_page = 1
    
    # Fetch markets
    result = api.list_markets(
        page=st.session_state.markets_page,
        page_size=page_size,
        search=search if search else None,
        active=active,
        closed=closed,
        volume_min=volume_min if volume_min > 0 else None,
        sort_by=sort_by,
    )
    
    if result["status"] == 200:
        data = result["data"]
        markets = data.get("markets", [])
        total = data.get("total", 0)
        total_pages = data.get("total_pages", 1)
        
        st.write(f"Found **{total}** markets (Page {st.session_state.markets_page}/{total_pages})")
        
        # Pagination controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("← Previous", disabled=not data.get("has_prev")):
                st.session_state.markets_page -= 1
                st.rerun()
        with col3:
            if st.button("Next →", disabled=not data.get("has_next")):
                st.session_state.markets_page += 1
                st.rerun()
        
        # Display markets
        if markets:
            for market in markets:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        status_emoji = "🟢" if not market.get("closed") else "🔴"
                        st.write(f"{status_emoji} **{market.get('question', 'N/A')[:80]}**")
                        st.caption(f"Slug: {market.get('slug', 'N/A')}")
                    
                    with col2:
                        vol_24h = market.get("volume_24h") or 0
                        st.metric("24h Volume", f"${vol_24h:,.0f}")
                    
                    with col3:
                        liq = market.get("liquidity") or 0
                        st.metric("Liquidity", f"${liq:,.0f}")
                    
                    with col4:
                        outcomes = market.get("outcomes", [])
                        prices = market.get("outcome_prices", [])
                        if outcomes and prices:
                            try:
                                price = float(prices[0]) * 100
                                st.metric(outcomes[0], f"{price:.1f}%")
                            except:
                                st.write("-")
                    
                    st.divider()
        else:
            st.info("No markets found matching your criteria")
    else:
        st.error(f"Failed to fetch markets: {result.get('error', result.get('data', {}).get('detail', 'Unknown error'))}")
    
    # Top Markets Section
    st.subheader("🔥 Top Markets by 24h Volume")
    top_result = api.get_top_markets(limit=5, sort_by="volume_24h")
    
    if top_result["status"] == 200:
        top_markets = top_result["data"]
        for i, market in enumerate(top_markets, 1):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{i}. {market.get('question', 'N/A')[:60]}**")
            with col2:
                vol = market.get("volume_24h") or 0
                st.write(f"${vol:,.0f}")


def show_portfolios_page():
    """Show portfolios management."""
    st.header("💼 Portfolios")
    
    if not st.session_state.token:
        st.warning("Please login to manage portfolios")
        return
    
    # Create portfolio form
    with st.expander("➕ Create New Portfolio"):
        with st.form("create_portfolio"):
            name = st.text_input("Portfolio Name")
            initial_balance = st.number_input(
                "Initial Balance ($)", 
                min_value=100.0, 
                max_value=1000000.0, 
                value=10000.0,
                step=1000.0,
            )
            submitted = st.form_submit_button("Create Portfolio")
            
            if submitted:
                if name:
                    result = api.create_portfolio(name, initial_balance)
                    if result["status"] in [200, 201]:
                        st.success(f"Portfolio '{name}' created!")
                        st.rerun()
                    else:
                        error = result.get("data", {}).get("detail", result.get("error", "Failed"))
                        st.error(f"Failed to create portfolio: {error}")
                else:
                    st.warning("Please enter a portfolio name")
    
    # List portfolios
    st.subheader("Your Portfolios")
    result = api.list_portfolios()
    
    if result["status"] == 200:
        portfolios = result["data"]
        if isinstance(portfolios, dict):
            portfolios = portfolios.get("portfolios", [])
        
        if portfolios:
            for portfolio in portfolios:
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"**{portfolio.get('name', 'Unnamed')}**")
                        st.caption(f"ID: {portfolio.get('id', portfolio.get('_id', 'N/A'))}")
                    
                    with col2:
                        balance = portfolio.get("cash_balance", portfolio.get("initial_balance", 0))
                        st.metric("Balance", f"${balance:,.2f}")
                    
                    with col3:
                        created = portfolio.get("created_at", "N/A")
                        if isinstance(created, str) and created != "N/A":
                            created = created[:10]
                        st.write(f"Created: {created}")
                    
                    st.divider()
        else:
            st.info("No portfolios yet. Create one above!")
    else:
        st.error(f"Failed to fetch portfolios: {result.get('error', 'Unknown error')}")


# ==================== Main App ====================

def main():
    """Main application entry point."""
    show_sidebar()
    
    # Main content area
    if not st.session_state.token:
        st.title("📈 Polymarket Paper Trading")
        st.write("Welcome! Please login or register to continue.")
        show_login_form()
    else:
        # Routed pages
        page = st.session_state.current_page
        
        if page == "markets":
            show_markets_page()
        elif page == "portfolios":
            show_portfolios_page()
        elif page == "health":
            show_health_page()
        else:
            show_markets_page()


if __name__ == "__main__":
    main()
