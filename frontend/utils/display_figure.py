import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict
from utils.styles import COLORS
from utils.helper import _parse_datetime


def _build_trades_dataframe(trades: List[Dict]) -> pd.DataFrame:
	"""
	Convert trades list into formatted pandas DataFrame.
	
	Expected trade fields:
	- created_at: ISO datetime string
	- portfolio_name: Portfolio name
	- side: "buy" or "sell"
	- outcome: YES or NO
	- quantity: Trade quantity
	- price: Unit price
	- notes: Optional notes
	"""
	if not trades:
		return pd.DataFrame()
	
	rows = []
	for trade in trades:
		try:
			# Parse datetime
			dt = _parse_datetime(trade.get("created_at"))
			# Fusionne date et heure en un seul timestamp
			if dt:
				timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
			else:
				timestamp_str = ""
			
			# Get fields
			portfolio = trade.get("portfolio_name", "N/A")
			market_name = trade.get("market_name", "")
			action = (trade.get("side") or "").upper()
			outcome = (trade.get("outcome") or "").upper()
			quantity = float(trade.get("quantity") or 0)
			price = float(trade.get("price") or 0)
			notes = trade.get("notes") or ""
			
			# Calculate total
			total = quantity * price
			
			rows.append({
				"Timestamp": timestamp_str,
				"Portefeuille": portfolio,
				"Marché": market_name,
				"Action": action,
				"Token": outcome,
				"Quantité": quantity,
				"Prix unitaire": price,
				"Prix total": total,
				"Note": notes,
			})
		except Exception:
			# Skip malformed trades
			continue
	
	if not rows:
		return pd.DataFrame()
	
	df = pd.DataFrame(rows)
	
	# Ensure numeric columns are properly typed
	for col in ["Quantité", "Prix unitaire", "Prix total"]:
		if col in df.columns:
			df[col] = pd.to_numeric(df[col], errors="coerce")
	
	# Sort by date descending (newest first)
	if "Date" in df.columns:
		df = df.sort_values("Date", ascending=False, key=lambda x: pd.to_datetime(x, errors='coerce'), na_position='last')
	
	df = df.reset_index(drop=True)
	return df

def _create_portfolio_pnl_chart(pnl_series: List[Dict]) -> go.Figure:
    """
    Create the global portfolio P&L chart.
    
    Args:
        pnl_series: List of P&L snapshots with timestamp and total_pnl
        
    Returns:
        Plotly Figure with continuous P&L curve
    """
    fig = go.Figure()
    
    if not pnl_series:
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color=COLORS["text_secondary"])
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor=COLORS["bg_secondary"],
            height=450,
        )
        return fig
    
    # Extract data
    timestamps = []
    pnl_values = []
    
    for point in pnl_series:
        ts = point.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                continue
        timestamps.append(ts)
        pnl_values.append(point.get("total_pnl", 0))
    
    if not timestamps:
        fig.add_annotation(
            text="Aucune donnée disponible",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color=COLORS["text_secondary"])
        )
        return fig
    
    # Determine color based on final P&L
    final_pnl = pnl_values[-1] if pnl_values else 0
    line_color = COLORS["accent_green"] if final_pnl >= 0 else COLORS["accent_red"]
    fill_color = 'rgba(59, 185, 80, 0.15)' if final_pnl >= 0 else 'rgba(248, 81, 73, 0.15)'
    
    # Add P&L trace
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=pnl_values,
        mode='lines',
        name='Portfolio P&L',
        line=dict(color=line_color, width=2.5),
        fill='tozeroy',
        fillcolor=fill_color,
        hovertemplate='%{x|%d/%m/%Y %H:%M}<br><b>P&L: $%{y:,.2f}</b><extra></extra>'
    ))
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["border"], opacity=0.7)
    
    # Find first non-zero P&L to trim empty beginning
    first_nonzero_idx = 0
    for i, pnl in enumerate(pnl_values):
        if pnl != 0:
            first_nonzero_idx = max(0, i - 1)  # Keep one point before
            break
    
    # Trim timestamps and values if there's empty space at the beginning
    if first_nonzero_idx > 0:
        timestamps = timestamps[first_nonzero_idx:]
        pnl_values = pnl_values[first_nonzero_idx:]
        # Update the trace data
        fig.data[0].x = timestamps
        fig.data[0].y = pnl_values
    
    # Layout with range set to data bounds
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor=COLORS["bg_secondary"],
        font=dict(color=COLORS["text_primary"], family="Inter, sans-serif"),
        margin=dict(l=60, r=40, t=40, b=60),
        height=450,
        showlegend=False,
        hovermode='x unified',
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.05)',
            tickformat='%d/%m\n%H:%M',
            title=dict(text="Date", font=dict(size=12)),
            range=[timestamps[0], timestamps[-1]] if timestamps else None,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.08)',
            tickprefix='$',
            tickformat=',.2f',
            title=dict(text="P&L ($)", font=dict(size=12)),
            zeroline=True,
            zerolinecolor=COLORS["border"],
        ),
    )
    
    return fig


def _create_position_pnl_chart(position: Dict) -> go.Figure:
    """
    Create the individual position P&L chart.
    
    Args:
        position: Position data with timestamps and total_pnls arrays
        
    Returns:
        Plotly Figure with position P&L curve
    """
    fig = go.Figure()
    
    timestamps = position.get("timestamps", [])
    pnl_values = position.get("total_pnls", [])
    first_trade_at = position.get("first_trade_at")
    
    if not timestamps or not pnl_values:
        fig.add_annotation(
            text="Aucune donnée pour cette position",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor=COLORS["bg_secondary"],
            height=400,
        )
        return fig
    
    # Convert timestamps
    parsed_timestamps = []
    for ts in timestamps:
        if isinstance(ts, str):
            try:
                parsed_timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except:
                continue
        else:
            parsed_timestamps.append(ts)
    
    if not parsed_timestamps:
        fig.add_annotation(
            text="Aucune donnée pour cette position",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
        return fig
    
    # Parse first_trade_at for range start
    range_start = parsed_timestamps[0]
    if first_trade_at:
        try:
            if isinstance(first_trade_at, str):
                range_start = datetime.fromisoformat(first_trade_at.replace("Z", "+00:00"))
            else:
                range_start = first_trade_at
        except:
            pass
    
    # Determine color based on final P&L
    final_pnl = pnl_values[-1] if pnl_values else 0
    line_color = COLORS["accent_green"] if final_pnl >= 0 else COLORS["accent_red"]
    fill_color = 'rgba(59, 185, 80, 0.15)' if final_pnl >= 0 else 'rgba(248, 81, 73, 0.15)'
    
    # Add P&L trace
    fig.add_trace(go.Scatter(
        x=parsed_timestamps,
        y=pnl_values,
        mode='lines',
        name='Position P&L',
        line=dict(color=line_color, width=2),
        fill='tozeroy',
        fillcolor=fill_color,
        hovertemplate='%{x|%d/%m/%Y %H:%M}<br><b>P&L: $%{y:,.2f}</b><extra></extra>'
    ))
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color=COLORS["border"], opacity=0.7)
    
    # Use first_trade_at as range start, last timestamp as range end
    last_ts = parsed_timestamps[-1] if parsed_timestamps else None
    
    # Layout with explicit range from first trade to now
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor=COLORS["bg_secondary"],
        font=dict(color=COLORS["text_primary"], family="Inter, sans-serif"),
        margin=dict(l=60, r=40, t=40, b=60),
        height=400,
        showlegend=False,
        hovermode='x unified',
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.05)',
            tickformat='%d/%m\n%H:%M',
            title=dict(text="Date", font=dict(size=12)),
            range=[range_start, last_ts] if range_start and last_ts else None,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.08)',
            tickprefix='$',
            tickformat=',.2f',
            title=dict(text="P&L ($)", font=dict(size=12)),
            zeroline=True,
            zerolinecolor=COLORS["border"],
        ),
    )
    
    return fig

def _create_price_chart(price_history: list, market_name: str, is_no: bool = False) -> go.Figure:
    """Create a Plotly price history chart for YES or NO token only."""
    if not price_history:
        fig = go.Figure()
        fig.add_annotation(
            text="Pas de données de prix disponibles",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"])
        )
        fig.update_layout(
            paper_bgcolor=COLORS["bg_secondary"],
            plot_bgcolor=COLORS["bg_secondary"],
            height=300
        )
        return fig

    timestamps = []
    prices = []
    for point in price_history:
        ts = point.get("timestamp") or point.get("t")
        if ts:
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromtimestamp(ts)
                timestamps.append(dt)
            except:
                continue
        # Toujours utiliser 'price' (ou 'p'), car l'API retourne l'historique du token demandé
        p = point.get("price") or point.get("p")
        if p is not None:
            try:
                prices.append(float(p) * 100)
            except:
                prices.append(None)

    fig = go.Figure()
    if prices and timestamps:
        color = COLORS["accent_red"] if is_no else COLORS["accent_green"]
        fill_color = 'rgba(248, 81, 73, 0.1)' if is_no else 'rgba(63, 185, 80, 0.1)'
        token_name = 'NO' if is_no else 'YES'
        fig.add_trace(go.Scatter(
            x=timestamps[:len(prices)],
            y=prices,
            mode='lines',
            name=token_name,
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=fill_color
        ))

    fig.update_layout(
        title=None,
        paper_bgcolor=COLORS["bg_secondary"],
        plot_bgcolor=COLORS["bg_secondary"],
        height=300,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_secondary"]),
            ticksuffix='%',
            range=[0, 100]
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color=COLORS["text_secondary"])
        ),
        hovermode='x unified'
    )
    return fig