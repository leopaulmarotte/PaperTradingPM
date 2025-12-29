
import streamlit as st
import pandas as pd
import time
from utils.styles import COLORS
from utils.formatters import format_number
from utils.formatters import format_currency
from utils.formatters import format_percent
from utils.formatters import format_date
from utils.formatters import time_until_end
from utils.formatters import _display_name

def render_portfolio_card(name, pid, performance, perf_class, perf_sign, total_value, cash_balance, total_exposure, initial_balance):
    st.markdown(f"""
    <div class="portfolio-card">
        <div class="portfolio-header">
            <div>
                <div class="portfolio-name">{name}</div>
                <div class="portfolio-id">ID: {pid}</div>
            </div>
            <div class="perf-badge {perf_class}">{perf_sign}{performance:.2f}%</div>
        </div>
        <div class="portfolio-metrics">
            <div class="metric-box">
                <div class="metric-label">Valeur Totale</div>
                <div class="metric-value neutral">${total_value:,.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Cash Disponible</div>
                <div class="metric-value">${cash_balance:,.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">En Position</div>
                <div class="metric-value">${total_exposure:,.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">P&L</div>
                <div class="metric-value {perf_class}">{perf_sign}${total_value - initial_balance:,.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_position_card(pos, pid):
    perf_class = "perf-positive" if pos["performance"] >= 0 else "perf-negative"
    perf_sign = "+" if pos["performance"] >= 0 else ""
    market_display = pos.get("market_question", pos["market"])
    if len(market_display) > 60:
        market_display = market_display[:57] + "..."
    st.markdown(f"""
    <div class="position-card">
        <div class="position-header">
            <div class="position-market">{market_display}</div>
            <span class="position-outcome">{pos['outcome']}</span>
        </div>
        <div class="position-metrics">
            <div class="metric-box">
                <div class="metric-label">Quantité</div>
                <div class="metric-value">{pos['qty']:.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Prix Actuel</div>
                <div class="metric-value">${pos['current_price']:.4f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Coût</div>
                <div class="metric-value">${pos['cost_basis']:.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Valeur</div>
                <div class="metric-value">${pos['current_value']:.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Performance</div>
                <div class="metric-value {perf_class}">{perf_sign}{pos['performance']:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def inject_portfolio_css():
    st.markdown("""
    <style>
    .portfolio-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid rgba(99, 102, 241, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .portfolio-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    .portfolio-name {
        font-size: 1.4rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
    }
    .portfolio-id {
        font-size: 0.75rem;
        color: #888;
        margin-top: 4px;
    }
    .portfolio-metrics {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
    }
    .metric-box {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .metric-label {
        font-size: 0.75rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #fff;
    }
    .metric-value.positive {
        color: #22c55e;
    }
    .metric-value.negative {
        color: #ef4444;
    }
    .metric-value.neutral {
        color: #6366f1;
    }
    .perf-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .perf-badge.positive {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
    }
    .perf-badge.negative {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
    }
    .perf-badge.neutral {
        background: rgba(99, 102, 241, 0.15);
        color: #6366f1;
    }
    </style>
    """, unsafe_allow_html=True)

def inject_position_css():
    st.markdown("""
    <style>
    .position-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border-left: 4px solid #6366f1;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .position-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 15px;
    }
    .position-market {
        font-size: 14px;
        font-weight: 600;
        color: #e0e0e0;
        max-width: 300px;
        word-wrap: break-word;
    }
    .position-outcome {
        display: inline-block;
        background: #6366f1;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }
    .position-metrics {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 15px;
    }
    .metric-box {
        text-align: center;
        padding: 10px;
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
    }
    .metric-label {
        font-size: 11px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 18px;
        font-weight: 700;
        color: #fff;
        margin-top: 4px;
    }
    .perf-positive { color: #22c55e !important; }
    .perf-negative { color: #ef4444 !important; }
    .portfolio-summary {
        display: flex;
        gap: 20px;
        margin-top: 20px;
    }
    .summary-card {
        flex: 1;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border-radius: 10px;
        padding: 15px 25px;
        text-align: center;
    }
    .summary-card.perf-positive-bg {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
    }
    .summary-card.perf-negative-bg {
        background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
    }
    .summary-label {
        font-size: 12px;
        color: rgba(255,255,255,0.8);
        text-transform: uppercase;
    }
    .summary-value {
        font-size: 28px;
        font-weight: 700;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

def render_html_table(
    df,
    height=300,
    header_color="#1f2937",
    row_hover_color="#374151",
    text_color="#e5e7eb",
):
    html = f"""
    <style>
        .custom-table-wrapper {{
            max-height: {height}px;
            overflow-y: auto;
            border-radius: 8px;
            border: 1px solid #374151;
        }}

        table.custom-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            color: {text_color};
        }}

        table.custom-table thead {{
            position: sticky;
            top: 0;
            background-color: {header_color};
        }}

        table.custom-table th, table.custom-table td {{
            padding: 8px 10px;
            text-align: right;
        }}

        table.custom-table tbody tr:hover {{
            background-color: {row_hover_color};
        }}
    </style>

    <div class="custom-table-wrapper">
        <table class="custom-table">
            <thead>
                <tr>
                    {''.join(f"<th>{col}</th>" for col in df.columns)}
                </tr>
            </thead>
            <tbody>
                {''.join(
                    "<tr>" +
                    ''.join(f"<td>{val}</td>" for val in row) +
                    "</tr>"
                    for row in df.values
                )}
            </tbody>
        </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


def _create_market_card(market: dict, idx: int) -> str:
    """Generate HTML for a market card."""
    name = _display_name(market)
    # Truncate long names
    display_name = name[:60] + "..." if len(name) > 60 else name
    
    volume = format_number(market.get("volume_24h", 0))
    liquidity = format_number(market.get("liquidity", 0))
    is_closed = market.get("closed", False)
    
    # Get YES price
    prices = market.get("outcome_prices", [])
    yes_price = "—"
    yes_color = COLORS["text_secondary"]
    if prices:
        try:
            yes_val = float(prices[0]) * 100
            yes_price = f"{yes_val:.0f}%"
            # Color based on probability
            if yes_val >= 70:
                yes_color = COLORS["accent_green"]
            elif yes_val <= 30:
                yes_color = COLORS["accent_red"]
            else:
                yes_color = COLORS["accent_blue"]
        except:
            pass
    
    # Status badge
    if is_closed:
        badge = f'<span class="badge-closed">Clôturé</span>'
    else:
        end_date = market.get("end_date")
        time_left = time_until_end(end_date) if end_date else ""
        if time_left:
            badge = f'<span class="badge-active">{time_left}</span>'
        else:
            badge = '<span class="badge-active">Actif</span>'
    
    return f"""
    <div class="market-card" id="card-{idx}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <span style="font-size: 28px; font-weight: bold; color: {yes_color};">{yes_price}</span>
            {badge}
        </div>
        <div style="font-size: 14px; color: {COLORS['text_primary']}; margin-bottom: 12px; line-height: 1.4; min-height: 40px;">
            {display_name}
        </div>
        <div style="display: flex; justify-content: space-between; color: {COLORS['text_secondary']}; font-size: 12px;">
            <span>Vol: ${volume}</span>
            <span>Liq: ${liquidity}</span>
        </div>
    </div>
    """



def display_orderbook_ui(orderbook: dict):
    """Affiche l'orderbook YES/NO côte à côte sous forme de DataFrames."""

    # if not orderbook or len(orderbook) < 2:
    #     st.warning("Raffraichissez l'orderbook pour passer des trades.")
    #     return


    if not orderbook or len(orderbook) < 2:
        st.markdown(
            """
            <div style="
                background-color: #fff3cd;
                color: #664d03;
                border: 1px solid #ffecb5;
                padding: 16px;
                border-radius: 6px;
                font-size: 20px;
                font-weight: 600;
                text-align: center;
            ">
            ⚠️ Rafraîchissez l'orderbook pour passer des trades.
            </div>
            """,
            unsafe_allow_html=True
        )
        return



    # Récupère les clés dans l'ordre
    yes_key, no_key = list(orderbook.keys())[:2]
    yes_data = orderbook[yes_key]
    no_data = orderbook[no_key]

    bids_yes = yes_data.get("bids", {})
    asks_yes = yes_data.get("asks", {})

    bids_no = no_data.get("bids", {})
    asks_no = no_data.get("asks", {})

    # Fonction utilitaire pour créer un DataFrame
    def create_df(prices_dict, reverse=False, side=""):
        df = pd.DataFrame(prices_dict.items(), columns=[side, "Quantity"])
        df[side] = df[side].astype(float)
        df["Quantity"] = df["Quantity"].astype(float)
        return df.sort_values(side, ascending=not reverse).reset_index(drop=True)

    # Crée les DataFrames
    bids_yes_df = create_df(bids_yes, reverse=True, side = 'Bids')
    asks_yes_df = create_df(asks_yes, reverse=True, side ='Asks')

    bids_no_df = create_df(bids_no, reverse=True, side ='Bids')
    asks_no_df = create_df(asks_no, reverse=True, side ='Asks')

    default_height = 180

    # Render both columns within a single HTML flex row to ensure perfect vertical alignment
    parent_height = (default_height * 2) + 6

    st.markdown(
        "<style>"
        ".order-row{display:flex;gap:12px;}"
        ".order-col{flex:1;}"
        ".order-column{display:flex;flex-direction:column;gap:16px;height:" + str(parent_height) + "px;}"
        ".order-table{padding:6px;border-radius:6px;flex:1;overflow:scroll;scrollbar-width:none;box-sizing:border-box;}"
        ".order-table::-webkit-scrollbar{display:none;}"
        ".order-table table{width:100%;border-collapse:collapse; table-layout:fixed; word-break:break-word;}"
        ".order-table table th, .order-table table td{padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.04);}"
        ".order-table table th:nth-child(1), .order-table table td:nth-child(1){width:65%; text-align:left;}"
        ".order-table table th:nth-child(2), .order-table table td:nth-child(2){width:35%; text-align:right;}"
        ".order-table.table-asks{background:rgba(34,197,94,0.06);}"
        ".order-table.table-asks table thead th{background:rgba(34,197,94,0.95);text-align:left; position:sticky; top:0; z-index:3;}"
        ".order-table.table-bids{background:rgba(239,68,68,0.06);}"
        ".order-table.table-bids table thead th{background:rgba(239,68,68,0.95);text-align:left; position:sticky; top:0; z-index:3;}"
        "</style>",
        unsafe_allow_html=True,
    )

    html = (
        "<div class='order-row'>"
        "<div class='order-col'>"
        "<h3 style='margin:6px 0;'>YES</h3>"
        f"<div class='order-column'><div class='order-table table-asks'>{asks_yes_df.to_html(index=False)}</div><div class='order-table table-bids'>{bids_yes_df.to_html(index=False)}</div></div>"
        "</div>"
        "<div class='order-col'>"
        "<h3 style='margin:6px 0;'>NO</h3>"
        f"<div class='order-column'><div class='order-table table-asks'>{asks_no_df.to_html(index=False)}</div><div class='order-table table-bids'>{bids_no_df.to_html(index=False)}</div></div>"
        "</div>"
        "</div>"
    )

    st.markdown(html, unsafe_allow_html=True)
