"""
Centralized formatting utilities for the trading UI.
"""
from datetime import datetime
from typing import Optional, Tuple


def format_number(value: float, decimals: int = 2) -> str:
    """Format numbers with K/M suffixes."""
    try:
        if value is None:
            return "-"
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        if abs(value) >= 1_000:
            return f"{value/1_000:.1f}k"
        return f"{value:.{decimals}f}"
    except Exception:
        return "-"


def format_currency(value: float, decimals: int = 2) -> str:
    """Format as currency with $ prefix."""
    try:
        if value is None:
            return "-"
        return f"${value:,.{decimals}f}"
    except Exception:
        return "-"


def format_percent(value: float, decimals: int = 1) -> str:
    """Format as percentage."""
    try:
        if value is None:
            return "-"
        return f"{value * 100:.{decimals}f}%"
    except Exception:
        return "-"


def format_date(date_str: str, fmt: str = "%d/%m/%Y") -> str:
    """Format ISO date string for display."""
    try:
        if not date_str:
            return "-"
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime(fmt)
    except Exception:
        return "-"
    
def _format_datetime(dt: Optional[datetime]) -> str:
	"""Format datetime into separate date and time strings."""
	if not dt:
		return "", ""
	return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")



def format_datetime_parts(date_str: str) -> Tuple[str, str]:
    """Return (date_str, time_str) tuple."""
    try:
        if not date_str:
            return "", ""
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except Exception:
        return "", ""


def time_until_end(date_str: str) -> str:
    """Calculate time remaining until end date."""
    try:
        if not date_str:
            return ""
        end_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(end_date.tzinfo or None)
        
        if now >= end_date:
            return ""
        
        delta = end_date - now
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{delta.seconds // 60}m"
    except Exception:
        return ""


def get_pnl_color_class(value: float) -> str:
    """Return CSS class based on P&L value."""
    if value > 0:
        return "metric-positive"
    elif value < 0:
        return "metric-negative"
    return ""


def get_pnl_color(value: float) -> str:
    """Return hex color based on P&L value."""
    if value > 0:
        return "#3fb950"  # accent_green
    elif value < 0:
        return "#f85149"  # accent_red
    return "#f0f6fc"  # text_primary


def _normalize_outcome(name: str) -> str:
    """Normalize outcome name for matching positions."""
    try:
        return (name or "").strip().lower()
    except Exception:
        return ""
    
def _display_name(market: dict) -> str:
    """Return a readable market name."""
    name = market.get("question") or market.get("name") or market.get("title")
    if name:
        return name
    slug = market.get("slug") or ""
    if slug:
        return slug.replace("-", " ").replace("_", " ").title()
    return "Marché"