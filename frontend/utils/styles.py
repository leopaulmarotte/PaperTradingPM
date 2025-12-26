"""
Global styles and CSS for the professional trading UI.
Dark theme inspired by Polymarket.
"""

COLORS = {
    "bg_primary": "#0d1117",
    "bg_secondary": "#161b22",
    "bg_card": "#21262d",
    "bg_hover": "#30363d",
    "border": "#30363d",
    "text_primary": "#f0f6fc",
    "text_secondary": "#8b949e",
    "text_muted": "#6e7681",
    "accent_green": "#3fb950",
    "accent_red": "#f85149",
    "accent_blue": "#58a6ff",
    "accent_purple": "#a371f7",
    "accent_yellow": "#d29922",
}


def get_global_css() -> str:
    """Return global CSS for dark theme styling."""
    return f"""
    <style>
        .market-card {{
            background: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            transition: all 0.2s ease;
        }}
        
        .market-card:hover {{
            background: {COLORS['bg_hover']};
            border-color: {COLORS['accent_blue']};
        }}
        
        .market-card-title {{
            color: {COLORS['text_primary']};
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        
        .market-card-meta {{
            color: {COLORS['text_secondary']};
            font-size: 12px;
            margin-bottom: 12px;
        }}
        
        .market-card-price {{
            font-size: 24px;
            font-weight: 700;
            color: {COLORS['accent_green']};
        }}
        
        .badge-active {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(63, 185, 80, 0.2);
            color: {COLORS['accent_green']};
        }}
        
        .badge-closed {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background: rgba(248, 81, 73, 0.2);
            color: {COLORS['accent_red']};
        }}
        
        .pro-table {{
            width: 100%;
            border-collapse: collapse;
            background: {COLORS['bg_card']};
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .pro-table thead {{
            background: {COLORS['bg_secondary']};
        }}
        
        .pro-table th {{
            color: {COLORS['text_secondary']};
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid {COLORS['border']};
        }}
        
        .pro-table td {{
            color: {COLORS['text_primary']};
            padding: 12px 16px;
            border-bottom: 1px solid {COLORS['border']};
            font-size: 14px;
        }}
        
        .pro-table tbody tr:hover {{
            background: {COLORS['bg_hover']};
        }}
        
        .metric-positive {{ color: {COLORS['accent_green']}; }}
        .metric-negative {{ color: {COLORS['accent_red']}; }}
    </style>
    """


def inject_styles():
    """Inject global styles into the Streamlit app."""
    import streamlit as st
    st.markdown(get_global_css(), unsafe_allow_html=True)
