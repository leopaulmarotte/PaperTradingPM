import os
from datetime import datetime
from typing import Optional

import requests
import streamlit as st


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
    def login(self, email: str, password: str) -> dict:
        """Login and get token."""
        return self._post("/auth/login", {
            "email": email,
            "password": password,
        })
    
    def register(self, email: str, password: str) -> dict:
        """Register new user."""
        return self._post("/auth/register", {
            "email": email,
            "password": password,
            "password_confirm": password,
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

