"""
Polymarket Paper Trading Dashboard - Streamlit Frontend

A simple frontend to test the FastAPI backend features:
- Authentication (login/register)
- Market browsing with filters
- Portfolio management
- Trade simulation
- Price history visualization
"""
import os
from datetime import datetime
from typing import Optional

import pandas as pd
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
    if "selected_market" not in st.session_state:
        st.session_state.selected_market = None
    if "selected_portfolio" not in st.session_state:
        st.session_state.selected_portfolio = None


init_session_state()


# ==================== API Client ====================

class APIClient:
    """Simple API client for backend requests."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def _headers(self) -> dict:
        """Get headers for requests."""
        return {"Content-Type": "application/json"}
    
    def _get_params(self, params: Optional[dict] = None) -> dict:
        """Get URL parameters including auth token if available."""
        if params is None:
            params = {}
        if st.session_state.token:
            params["token"] = st.session_state.token
        return params
    
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make GET request."""
        try:
            resp = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                params=self._get_params(params),
                timeout=30,
            )
            return {"status": resp.status_code, "data": resp.json() if resp.text else None}
        except requests.exceptions.ConnectionError:
            return {"status": 0, "error": "Cannot connect to backend"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def _post(self, endpoint: str, data: dict, params: Optional[dict] = None) -> dict:
        """Make POST request."""
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                headers=self._headers(),
                json=data,
                params=self._get_params(params) if st.session_state.token else params,
                timeout=30,
            )
            return {"status": resp.status_code, "data": resp.json() if resp.text else None}
        except requests.exceptions.ConnectionError:
            return {"status": 0, "error": "Cannot connect to backend"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    # Auth endpoints
    def login(self, email: str, password: str) -> dict:
        """Login and get token."""
        return self._post("/auth/login", {
            "email": email,
            "password": password,
        }, params={})  # No token needed for login
    
    def register(self, email: str, password: str) -> dict:
        """Register new user."""
        return self._post("/auth/register", {
            "email": email,
            "password": password,
            "password_confirm": password,
        }, params={})  # No token needed for registration
    
    def get_me(self) -> dict:
        """Get current user profile."""
        return self._get("/auth/me")
    
    # Health endpoint
    def health(self) -> dict:
        """Check API health."""
        return self._get("/health", params={})
    
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
    
    def delete_portfolio(self, portfolio_id: str) -> dict:
        """Delete portfolio."""
        try:
            resp = requests.delete(
                f"{self.base_url}/portfolios/{portfolio_id}",
                headers=self._headers(),
                params=self._get_params(),
                timeout=30,
            )
            return {"status": resp.status_code, "data": None}
        except requests.exceptions.ConnectionError:
            return {"status": 0, "error": "Cannot connect to backend"}
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    def add_trade(
        self, 
        portfolio_id: str, 
        market_id: str, 
        outcome: str, 
        side: str, 
        quantity: float, 
        price: float,
        notes: str = None,
    ) -> dict:
        """Add trade to portfolio."""
        data = {
            "market_id": market_id,
            "outcome": outcome,
            "side": side,
            "quantity": quantity,
            "price": price,
        }
        if notes:
            data["notes"] = notes
        return self._post(f"/portfolios/{portfolio_id}/trades", data)
    
    def get_trades(self, portfolio_id: str, page: int = 1, page_size: int = 50) -> dict:
        """Get trade history for portfolio."""
        return self._get(f"/portfolios/{portfolio_id}/trades", {"page": page, "page_size": page_size})
    
    def get_portfolio_metrics(self, portfolio_id: str) -> dict:
        """Get portfolio metrics."""
        return self._get(f"/portfolios/{portfolio_id}/metrics")


api = APIClient(API_URL)


# ==================== UI Components ====================

def show_login_form():
    """Show login/register forms."""
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
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


def show_sidebar():
    """Show sidebar navigation."""
    with st.sidebar:
        st.title("📈 Paper Trading")
        
        if st.session_state.user:
            st.write(f"👤 **{st.session_state.user.get('email', 'User')}**")
            st.write(f"Role: {', '.join(st.session_state.user.get('roles', ['user']))}")
            
            if st.button("Logout"):
                st.session_state.token = None
                st.session_state.user = None
                st.rerun()
            
            st.divider()
        
        # Navigation
        st.subheader("Navigation")
        
        pages = {
            "markets": "🏪 Markets",
            "market_detail": "📊 Market Detail",
            "portfolios": "💼 Portfolios",
            "portfolio_detail": "📈 Portfolio Detail",
            "trade": "💹 Trade",
            "health": "🏥 System Health",
        }
        
        for key, label in pages.items():
            # Hide detail pages if nothing selected
            if key == "market_detail" and not st.session_state.selected_market:
                continue
            if key == "portfolio_detail" and not st.session_state.selected_portfolio:
                continue
            if key == "trade" and not st.session_state.selected_portfolio:
                continue
            
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
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 0.5])
                    
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
                    
                    with col5:
                        if st.button("📊", key=f"view_{market.get('slug')}", help="View details"):
                            st.session_state.selected_market = market.get("slug")
                            st.session_state.current_page = "market_detail"
                            st.rerun()
                    
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
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 0.5])
                    
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
                    
                    with col4:
                        portfolio_id = portfolio.get('id', portfolio.get('_id'))
                        if st.button("📈", key=f"view_pf_{portfolio_id}", help="View details"):
                            st.session_state.selected_portfolio = portfolio_id
                            st.session_state.current_page = "portfolio_detail"
                            st.rerun()
                    
                    st.divider()
        else:
            st.info("No portfolios yet. Create one above!")
    else:
        st.error(f"Failed to fetch portfolios: {result.get('error', 'Unknown error')}")


def show_market_detail_page():
    """Show market detail with price history chart."""
    st.header("📊 Market Detail")
    
    if not st.session_state.token:
        st.warning("Please login to view market details")
        return
    
    slug = st.session_state.selected_market
    if not slug:
        st.warning("No market selected. Go to Markets to select one.")
        return
    
    # Back button
    if st.button("← Back to Markets"):
        st.session_state.current_page = "markets"
        st.rerun()
    
    # Fetch market details (tests lazy-loading)
    with st.spinner("Loading market details..."):
        result = api.get_market(slug)
    
    if result["status"] != 200:
        st.error(f"Failed to load market: {result.get('data', {}).get('detail', result.get('error', 'Unknown'))}")
        return
    
    market = result["data"]
    
    # Market header
    status_emoji = "🟢" if not market.get("closed") else "🔴"
    st.subheader(f"{status_emoji} {market.get('question', 'Unknown Market')}")
    
    # Market info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("24h Volume", f"${market.get('volume_24h', 0):,.0f}")
    with col2:
        st.metric("Total Volume", f"${market.get('volume_num', 0):,.0f}")
    with col3:
        st.metric("Liquidity", f"${market.get('liquidity_num', 0):,.0f}")
    with col4:
        st.metric("Status", "Closed" if market.get("closed") else "Active")
    
    # Outcomes with prices
    st.subheader("Current Prices")
    outcomes = market.get("outcomes", [])
    prices = market.get("outcome_prices", [])
    
    if outcomes and prices:
        cols = st.columns(len(outcomes))
        for i, (outcome, price) in enumerate(zip(outcomes, prices)):
            with cols[i]:
                try:
                    pct = float(price) * 100
                    st.metric(outcome, f"{pct:.1f}%")
                except:
                    st.metric(outcome, "-")
    
    st.divider()
    
    # Price History Chart
    st.subheader("📈 Price History")
    
    # Outcome selector for price history
    if outcomes:
        selected_outcome_idx = st.selectbox(
            "Select outcome", 
            range(len(outcomes)), 
            format_func=lambda i: outcomes[i],
        )
    else:
        selected_outcome_idx = 0
    
    # Fetch price history (tests lazy-loading from CLOB API)
    with st.spinner("Loading price history..."):
        price_result = api.get_price_history(slug, outcome_index=selected_outcome_idx)
    
    if price_result["status"] == 200:
        price_data = price_result["data"]
        history = price_data.get("history", [])
        
        if history:
            # Convert to DataFrame for plotting
            df = pd.DataFrame(history)
            
            # Handle timestamp conversion
            if "t" in df.columns:
                df["timestamp"] = pd.to_datetime(df["t"], unit="s")
            elif "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            
            if "p" in df.columns:
                df["price"] = df["p"].astype(float) * 100  # Convert to percentage
            elif "price" in df.columns:
                df["price"] = df["price"].astype(float) * 100
            
            if "timestamp" in df.columns and "price" in df.columns:
                df = df.sort_values("timestamp")
                
                # Plot using Streamlit's native chart
                st.line_chart(df.set_index("timestamp")["price"], use_container_width=True)
                
                st.caption(f"Showing {len(history)} price points for '{outcomes[selected_outcome_idx] if outcomes else 'Unknown'}'")
            else:
                st.info("Price data format not recognized")
                st.json(history[:5] if len(history) > 5 else history)
        else:
            st.info("No price history available for this market/outcome")
    else:
        error_detail = price_result.get('data', {}).get('detail') if isinstance(price_result.get('data'), dict) else None
        error_msg = error_detail or price_result.get('error') or 'Unknown error'
        st.warning(f"Could not fetch price history: {error_msg}")
    
    st.divider()
    
    # Market metadata (expandable)
    with st.expander("📋 Market Metadata"):
        st.write(f"**Slug:** {market.get('slug')}")
        st.write(f"**Condition ID:** {market.get('condition_id')}")
        
        clob_token_ids = market.get("clob_token_ids", [])
        if clob_token_ids:
            st.write("**CLOB Token IDs:**")
            for i, token_id in enumerate(clob_token_ids):
                outcome_name = outcomes[i] if i < len(outcomes) else f"Outcome {i}"
                st.code(f"{outcome_name}: {token_id}")
        
        st.write(f"**End Date:** {market.get('end_date_iso', 'N/A')}")
        st.write(f"**Description:** {market.get('description', 'N/A')[:500]}")
    
    # Quick trade section
    st.divider()
    st.subheader("💹 Quick Trade")
    
    # Portfolio selector
    portfolios_result = api.list_portfolios()
    if portfolios_result["status"] == 200:
        portfolios = portfolios_result["data"]
        if isinstance(portfolios, dict):
            portfolios = portfolios.get("portfolios", [])
        
        if portfolios:
            portfolio_options = {p.get("id", p.get("_id")): p.get("name") for p in portfolios}
            selected_portfolio = st.selectbox(
                "Select Portfolio", 
                list(portfolio_options.keys()),
                format_func=lambda x: portfolio_options[x],
            )
            
            if not outcomes:
                st.warning("No outcomes available for this market")
            else:
                with st.form("quick_trade_form"):
                    col1, col2 = st.columns(2)
                
                with col1:
                    trade_outcome_idx = st.selectbox(
                        "Outcome",
                        range(len(outcomes)) if outcomes else [0],
                        format_func=lambda i: outcomes[i] if outcomes else "Unknown",
                    )
                    trade_outcome = outcomes[trade_outcome_idx] if outcomes else "Unknown"
                    
                    side = st.selectbox("Side", ["buy", "sell"])
                
                with col2:
                    quantity = st.number_input("Quantity", min_value=1.0, value=10.0, step=1.0)
                    
                    current_price = 0.5
                    if prices and trade_outcome_idx < len(prices):
                        try:
                            current_price = float(prices[trade_outcome_idx])
                            # Clamp to valid range
                            current_price = max(0.01, min(0.99, current_price))
                        except:
                            pass
                    
                    price = st.number_input(
                        "Price (0-1)", 
                        min_value=0.01, 
                        max_value=0.99, 
                        value=current_price,
                        step=0.01,
                        help="Price per share (probability)"
                    )
                
                notes = st.text_input("Notes (optional)")
                
                submitted = st.form_submit_button("Execute Trade")
                
                if submitted:
                    trade_result = api.add_trade(
                        portfolio_id=selected_portfolio,
                        market_id=slug,
                        outcome=trade_outcome,
                        side=side,
                        quantity=quantity,
                        price=price,
                        notes=notes if notes else None,
                    )
                    
                    if trade_result["status"] in [200, 201]:
                        total = quantity * price
                        st.success(f"Trade executed! {side.upper()} {quantity} shares of '{trade_outcome}' @ ${price:.2f} = ${total:.2f}")
                    else:
                        error = trade_result.get("data", {}).get("detail", trade_result.get("error", "Unknown"))
                        st.error(f"Trade failed: {error}")
        else:
            st.info("Create a portfolio first to trade")
    else:
        st.warning("Could not load portfolios")


def show_portfolio_detail_page():
    """Show portfolio detail with positions and trades."""
    st.header("📈 Portfolio Detail")
    
    if not st.session_state.token:
        st.warning("Please login to view portfolio details")
        return
    
    portfolio_id = st.session_state.selected_portfolio
    if not portfolio_id:
        st.warning("No portfolio selected. Go to Portfolios to select one.")
        return
    
    # Back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back"):
            st.session_state.current_page = "portfolios"
            st.rerun()
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Fetch portfolio with positions
    with st.spinner("Loading portfolio..."):
        result = api.get_portfolio(portfolio_id)
    
    if result["status"] != 200:
        st.error(f"Failed to load portfolio: {result.get('data', {}).get('detail', result.get('error', 'Unknown'))}")
        return
    
    portfolio = result["data"]
    
    # Portfolio header
    st.subheader(f"💼 {portfolio.get('name', 'Unknown Portfolio')}")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_value = portfolio.get("total_value", portfolio.get("initial_balance", 0))
        st.metric("Total Value", f"${total_value:,.2f}")
    with col2:
        cash = portfolio.get("cash_balance", portfolio.get("initial_balance", 0))
        st.metric("Cash Balance", f"${cash:,.2f}")
    with col3:
        pnl = portfolio.get("total_pnl", 0)
        pnl_pct = portfolio.get("total_pnl_percent", 0)
        st.metric("Total P&L", f"${pnl:,.2f}", f"{pnl_pct:+.2f}%")
    with col4:
        initial = portfolio.get("initial_balance", 10000)
        st.metric("Initial Balance", f"${initial:,.2f}")
    
    st.divider()
    
    # Positions
    st.subheader("📊 Positions")
    positions = portfolio.get("positions", [])
    
    if positions:
        for pos in positions:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                
                with col1:
                    st.write(f"**{pos.get('market_question', pos.get('market_id', 'Unknown')[:30])}**")
                    st.caption(f"Outcome: {pos.get('outcome', 'N/A')}")
                
                with col2:
                    st.metric("Quantity", f"{pos.get('quantity', 0):.2f}")
                
                with col3:
                    avg_price = pos.get("average_price", 0)
                    st.metric("Avg Price", f"${avg_price:.3f}")
                
                with col4:
                    current = pos.get("current_price")
                    if current:
                        st.metric("Current", f"${current:.3f}")
                    else:
                        st.metric("Current", "-")
                
                with col5:
                    pnl = pos.get("unrealized_pnl")
                    if pnl is not None:
                        color = "🟢" if pnl >= 0 else "🔴"
                        st.metric("P&L", f"{color} ${pnl:,.2f}")
                    else:
                        st.metric("P&L", "-")
                
                st.divider()
    else:
        st.info("No positions yet. Execute some trades!")
    
    # Trade History
    st.subheader("📜 Trade History")
    
    trades_result = api.get_trades(portfolio_id, page=1, page_size=20)
    
    if trades_result["status"] == 200:
        trades_data = trades_result["data"]
        trades = trades_data.get("trades", [])
        
        if trades:
            for trade in trades:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        side_emoji = "🟢" if trade.get("side") == "buy" else "🔴"
                        st.write(f"{side_emoji} **{trade.get('side', '').upper()}** - {trade.get('market_question', trade.get('market_id', 'Unknown')[:40])}")
                        st.caption(f"Outcome: {trade.get('outcome', 'N/A')} | {trade.get('trade_timestamp', '')[:10]}")
                    
                    with col2:
                        st.write(f"Qty: {trade.get('quantity', 0):.2f}")
                    
                    with col3:
                        st.write(f"@ ${trade.get('price', 0):.3f}")
                    
                    with col4:
                        total = trade.get("total_value", 0)
                        st.write(f"**${total:,.2f}**")
                
                st.divider()
            
            total_trades = trades_data.get("total", len(trades))
            st.caption(f"Showing {len(trades)} of {total_trades} trades")
        else:
            st.info("No trades yet")
    else:
        st.warning("Could not load trade history")
    
    # Metrics (expandable)
    with st.expander("📊 Portfolio Metrics"):
        metrics_result = api.get_portfolio_metrics(portfolio_id)
        if metrics_result["status"] == 200:
            metrics = metrics_result["data"]
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                win_rate = metrics.get("win_rate")
                st.metric("Win Rate", f"{win_rate*100:.1f}%" if win_rate else "N/A")
            with col2:
                avg_trade = metrics.get("avg_trade_size")
                st.metric("Avg Trade Size", f"${avg_trade:.2f}" if avg_trade else "N/A")
            with col3:
                sharpe = metrics.get("sharpe_ratio")
                st.metric("Sharpe Ratio", f"{sharpe:.2f}" if sharpe else "N/A")
            with col4:
                drawdown = metrics.get("max_drawdown")
                st.metric("Max Drawdown", f"{drawdown*100:.1f}%" if drawdown else "N/A")
        else:
            st.info("Metrics not available")
    
    # Delete portfolio (danger zone)
    with st.expander("⚠️ Danger Zone"):
        st.warning("Deleting a portfolio will remove all trades and cannot be undone.")
        if st.button("🗑️ Delete Portfolio", type="secondary"):
            delete_result = api.delete_portfolio(portfolio_id)
            if delete_result["status"] == 204:
                st.success("Portfolio deleted")
                st.session_state.selected_portfolio = None
                st.session_state.current_page = "portfolios"
                st.rerun()
            else:
                st.error("Failed to delete portfolio")


def show_trade_page():
    """Show dedicated trade execution page."""
    st.header("💹 Execute Trade")
    
    if not st.session_state.token:
        st.warning("Please login to trade")
        return
    
    portfolio_id = st.session_state.selected_portfolio
    if not portfolio_id:
        st.warning("No portfolio selected. Go to Portfolios to select one.")
        return
    
    # Portfolio info
    portfolio_result = api.get_portfolio(portfolio_id)
    if portfolio_result["status"] == 200:
        portfolio = portfolio_result["data"]
        st.subheader(f"Trading in: {portfolio.get('name', 'Unknown')}")
        st.write(f"Cash available: **${portfolio.get('cash_balance', 0):,.2f}**")
    
    st.divider()
    
    # Market search
    st.subheader("1️⃣ Find Market")
    search = st.text_input("Search markets", placeholder="e.g., Trump, Bitcoin, Election...")
    
    if search:
        markets_result = api.list_markets(
            page=1, 
            page_size=10, 
            search=search, 
            active=True,
            sort_by="volume_24h"
        )
        
        if markets_result["status"] == 200:
            markets = markets_result["data"].get("markets", [])
            
            if markets:
                market_options = {m.get("slug"): f"{m.get('question', 'Unknown')[:60]}..." for m in markets}
                selected_slug = st.selectbox("Select market", list(market_options.keys()), format_func=lambda x: market_options[x])
                
                # Get full market details
                if selected_slug:
                    market_detail = api.get_market(selected_slug)
                    
                    if market_detail["status"] == 200:
                        market = market_detail["data"]
                        
                        st.divider()
                        st.subheader("2️⃣ Trade Details")
                        
                        outcomes = market.get("outcomes", ["Yes", "No"])
                        prices = market.get("outcome_prices", [])
                        
                        # Show current prices
                        st.write("**Current Prices:**")
                        price_cols = st.columns(len(outcomes))
                        for i, (outcome, col) in enumerate(zip(outcomes, price_cols)):
                            with col:
                                try:
                                    pct = float(prices[i]) * 100 if i < len(prices) else 50
                                    st.metric(outcome, f"{pct:.1f}%")
                                except:
                                    st.metric(outcome, "-")
                        
                        with st.form("trade_form"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                trade_outcome = st.selectbox("Outcome", outcomes)
                                side = st.selectbox("Side", ["buy", "sell"])
                            
                            with col2:
                                quantity = st.number_input("Quantity (shares)", min_value=1.0, value=100.0, step=10.0)
                                
                                # Default to current market price
                                outcome_idx = outcomes.index(trade_outcome)
                                default_price = 0.5
                                try:
                                    default_price = float(prices[outcome_idx]) if outcome_idx < len(prices) else 0.5
                                    # Clamp to valid range
                                    default_price = max(0.01, min(0.99, default_price))
                                except:
                                    pass
                                
                                price = st.number_input(
                                    "Price per share", 
                                    min_value=0.01, 
                                    max_value=0.99, 
                                    value=default_price,
                                    step=0.01,
                                )
                            
                            # Trade preview
                            total_cost = quantity * price
                            st.write(f"**Trade Preview:** {side.upper()} {quantity:.0f} shares of '{trade_outcome}' @ ${price:.3f}")
                            st.write(f"**Total:** ${total_cost:,.2f}")
                            
                            notes = st.text_input("Notes (optional)")
                            
                            submitted = st.form_submit_button("🚀 Execute Trade", type="primary")
                            
                            if submitted:
                                trade_result = api.add_trade(
                                    portfolio_id=portfolio_id,
                                    market_id=selected_slug,
                                    outcome=trade_outcome,
                                    side=side,
                                    quantity=quantity,
                                    price=price,
                                    notes=notes if notes else None,
                                )
                                
                                if trade_result["status"] in [200, 201]:
                                    st.success(f"✅ Trade executed successfully!")
                                    st.balloons()
                                else:
                                    error = trade_result.get("data", {}).get("detail", trade_result.get("error", "Unknown"))
                                    st.error(f"Trade failed: {error}")
            else:
                st.info("No markets found. Try different search terms.")
        else:
            st.error("Failed to search markets")


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
        elif page == "market_detail":
            show_market_detail_page()
        elif page == "portfolios":
            show_portfolios_page()
        elif page == "portfolio_detail":
            show_portfolio_detail_page()
        elif page == "trade":
            show_trade_page()
        elif page == "health":
            show_health_page()
        else:
            show_markets_page()


if __name__ == "__main__":
    main()
