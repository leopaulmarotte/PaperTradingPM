"""
Tests for frontend/utils/formatters.py - Formatting utilities.

Tests number, currency, percentage, and date formatting functions.
"""
import pytest
from datetime import datetime, timezone


# Import directly since formatters don't depend on streamlit
from frontend.utils.formatters import (
    format_number,
    format_currency,
    format_percent,
    format_date,
    format_datetime_parts,
    time_until_end,
    get_pnl_color_class,
    get_pnl_color,
    _normalize_outcome,
    _display_name,
)


class TestFormatNumber:
    """Tests for format_number function."""
    
    def test_format_small_number(self):
        """Small numbers should show decimal places."""
        assert format_number(123.45) == "123.45"
        assert format_number(0.99) == "0.99"
    
    def test_format_thousands_with_k_suffix(self):
        """Numbers >= 1000 should use k suffix."""
        assert format_number(1000) == "1.0k"
        assert format_number(5500) == "5.5k"
        assert format_number(999_999) == "1000.0k"
    
    def test_format_millions_with_m_suffix(self):
        """Numbers >= 1M should use M suffix."""
        assert format_number(1_000_000) == "1.0M"
        assert format_number(2_500_000) == "2.5M"
        assert format_number(10_000_000) == "10.0M"
    
    def test_format_negative_numbers(self):
        """Negative numbers should preserve sign and use suffix."""
        assert format_number(-5000) == "-5.0k"
        assert format_number(-2_500_000) == "-2.5M"
    
    def test_format_custom_decimals(self):
        """Custom decimal places should be respected."""
        assert format_number(123.456, decimals=3) == "123.456"
        assert format_number(123.456, decimals=1) == "123.5"
        assert format_number(123.456, decimals=0) == "123"
    
    def test_format_none_returns_dash(self):
        """None value should return dash."""
        assert format_number(None) == "-"
    
    def test_format_zero(self):
        """Zero should be formatted normally."""
        assert format_number(0) == "0.00"


class TestFormatCurrency:
    """Tests for format_currency function."""
    
    def test_format_currency_basic(self):
        """Basic currency formatting with $ prefix."""
        assert format_currency(100) == "$100.00"
        assert format_currency(1234.56) == "$1,234.56"
    
    def test_format_currency_thousands(self):
        """Currency should use comma separators."""
        assert format_currency(1000) == "$1,000.00"
        assert format_currency(1000000) == "$1,000,000.00"
    
    def test_format_currency_custom_decimals(self):
        """Custom decimal places for currency."""
        assert format_currency(99.999, decimals=3) == "$99.999"
        assert format_currency(99.999, decimals=0) == "$100"
    
    def test_format_currency_none_returns_dash(self):
        """None value should return dash."""
        assert format_currency(None) == "-"
    
    def test_format_currency_negative(self):
        """Negative currency values."""
        result = format_currency(-50.00)
        assert result == "$-50.00" or result == "-$50.00"  # Both formats acceptable


class TestFormatPercent:
    """Tests for format_percent function."""
    
    def test_format_percent_from_decimal(self):
        """Decimal values should be converted to percentage."""
        assert format_percent(0.5) == "50.0%"
        assert format_percent(0.25) == "25.0%"
        assert format_percent(1.0) == "100.0%"
    
    def test_format_percent_custom_decimals(self):
        """Custom decimal places for percentage."""
        assert format_percent(0.3333, decimals=2) == "33.33%"
        assert format_percent(0.3333, decimals=0) == "33%"
    
    def test_format_percent_small_values(self):
        """Small percentage values."""
        assert format_percent(0.001) == "0.1%"
        assert format_percent(0.0001, decimals=2) == "0.01%"
    
    def test_format_percent_none_returns_dash(self):
        """None value should return dash."""
        assert format_percent(None) == "-"
    
    def test_format_percent_negative(self):
        """Negative percentage values."""
        assert format_percent(-0.15) == "-15.0%"


class TestFormatDate:
    """Tests for format_date function."""
    
    def test_format_iso_date(self):
        """ISO date string should be formatted."""
        assert format_date("2025-01-15T10:30:00Z") == "15/01/2025"
    
    def test_format_date_custom_format(self):
        """Custom date format should be applied."""
        assert format_date("2025-01-15T10:30:00Z", fmt="%Y-%m-%d") == "2025-01-15"
        assert format_date("2025-01-15T10:30:00Z", fmt="%B %d, %Y") == "January 15, 2025"
    
    def test_format_date_with_timezone(self):
        """Date with timezone offset should be parsed."""
        assert format_date("2025-01-15T10:30:00+02:00") == "15/01/2025"
    
    def test_format_date_empty_returns_dash(self):
        """Empty string should return dash."""
        assert format_date("") == "-"
        assert format_date(None) == "-"
    
    def test_format_date_invalid_returns_dash(self):
        """Invalid date string should return dash."""
        assert format_date("not-a-date") == "-"


class TestFormatDatetimeParts:
    """Tests for format_datetime_parts function."""
    
    def test_format_datetime_parts_splits_correctly(self):
        """Should return (date, time) tuple."""
        date_part, time_part = format_datetime_parts("2025-01-15T10:30:45Z")
        assert date_part == "2025-01-15"
        assert time_part == "10:30:45"
    
    def test_format_datetime_parts_empty(self):
        """Empty string should return empty tuple."""
        date_part, time_part = format_datetime_parts("")
        assert date_part == ""
        assert time_part == ""
    
    def test_format_datetime_parts_invalid(self):
        """Invalid date should return empty tuple."""
        date_part, time_part = format_datetime_parts("invalid")
        assert date_part == ""
        assert time_part == ""


class TestTimeUntilEnd:
    """Tests for time_until_end function."""
    
    def test_time_until_end_days(self):
        """Should show days when > 24 hours."""
        # Create a date 5 days in future (mock or use real future date)
        from datetime import timedelta
        future = datetime.now(timezone.utc) + timedelta(days=5)
        future_iso = future.isoformat().replace("+00:00", "Z")
        
        result = time_until_end(future_iso)
        assert "d" in result
    
    def test_time_until_end_hours(self):
        """Should show hours when < 24 hours."""
        from datetime import timedelta
        future = datetime.now(timezone.utc) + timedelta(hours=5)
        future_iso = future.isoformat().replace("+00:00", "Z")
        
        result = time_until_end(future_iso)
        assert "h" in result or "d" in result  # Could round to 1d depending on timing
    
    def test_time_until_end_past_date(self):
        """Past date should return empty string."""
        result = time_until_end("2020-01-01T00:00:00Z")
        assert result == ""
    
    def test_time_until_end_empty(self):
        """Empty string should return empty string."""
        assert time_until_end("") == ""
        assert time_until_end(None) == ""


class TestGetPnlColorClass:
    """Tests for get_pnl_color_class function."""
    
    def test_positive_pnl_class(self):
        """Positive P&L should return positive class."""
        assert get_pnl_color_class(100) == "metric-positive"
        assert get_pnl_color_class(0.01) == "metric-positive"
    
    def test_negative_pnl_class(self):
        """Negative P&L should return negative class."""
        assert get_pnl_color_class(-100) == "metric-negative"
        assert get_pnl_color_class(-0.01) == "metric-negative"
    
    def test_zero_pnl_class(self):
        """Zero P&L should return empty class."""
        assert get_pnl_color_class(0) == ""


class TestGetPnlColor:
    """Tests for get_pnl_color function."""
    
    def test_positive_pnl_color(self):
        """Positive P&L should return green color."""
        assert get_pnl_color(100) == "#3fb950"
    
    def test_negative_pnl_color(self):
        """Negative P&L should return red color."""
        assert get_pnl_color(-100) == "#f85149"
    
    def test_zero_pnl_color(self):
        """Zero P&L should return neutral color."""
        assert get_pnl_color(0) == "#f0f6fc"


class TestNormalizeOutcome:
    """Tests for _normalize_outcome function."""
    
    def test_normalize_lowercase(self):
        """Should convert to lowercase."""
        assert _normalize_outcome("Yes") == "yes"
        assert _normalize_outcome("NO") == "no"
    
    def test_normalize_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert _normalize_outcome("  Yes  ") == "yes"
    
    def test_normalize_empty(self):
        """Empty string should return empty."""
        assert _normalize_outcome("") == ""
        assert _normalize_outcome(None) == ""


class TestDisplayName:
    """Tests for _display_name function."""
    
    def test_display_name_from_question(self, sample_market):
        """Should prefer question field."""
        market = {"question": "Will it rain?", "name": "Rain Market"}
        assert _display_name(market) == "Will it rain?"
    
    def test_display_name_from_name(self):
        """Should fallback to name field."""
        market = {"name": "Rain Market", "title": "The Rain Market"}
        assert _display_name(market) == "Rain Market"
    
    def test_display_name_from_title(self):
        """Should fallback to title field."""
        market = {"title": "The Rain Market"}
        assert _display_name(market) == "The Rain Market"
    
    def test_display_name_from_slug(self):
        """Should fallback to formatted slug."""
        market = {"slug": "rain-market-2025"}
        result = _display_name(market)
        assert "rain" in result.lower()
        assert "market" in result.lower()
    
    def test_display_name_fallback(self):
        """Should return default when nothing available."""
        market = {}
        assert _display_name(market) == "Marché"
