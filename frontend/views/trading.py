import streamlit as st
from datetime import datetime

from config import API_URL
from utils.api import APIClient


def _format_number(value: float) -> str:
	"""Format numbers for display."""
	try:
		if value is None:
			return "-"
		if value >= 1_000_000:
			return f"{value/1_000_000:.1f}M"
		if value >= 1_000:
			return f"{value/1_000:.1f}k"
		return f"{value:.2f}" if isinstance(value, float) else str(value)
	except Exception:
		return "-"


def _format_date(date_str: str) -> str:
	"""Format ISO date string for display."""
	try:
		if not date_str:
			return "-"
		dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
		return dt.strftime("%d/%m/%Y")
	except Exception:
		return "-"


def _time_until_end(date_str: str) -> str:
	"""Calculate time remaining until end date."""
	try:
		if not date_str:
			return ""
		end_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
		now = datetime.now(end_date.tzinfo or None)
		
		if now >= end_date:
			return ""  # Already ended
		
		delta = end_date - now
		days = delta.days
		hours = delta.seconds // 3600
		
		if days > 0:
			return f"ends in {days}d"
		elif hours > 0:
			return f"ends in {hours}h"
		else:
			minutes = delta.seconds // 60
			return f"ends in {minutes}m"
	except Exception:
		return ""


def _display_name(market: dict) -> str:
	"""Return a readable market name, avoid raw slugs."""
	name = market.get("question") or market.get("name") or market.get("title")
	if name:
		return name
	slug = market.get("slug") or ""
	if slug:
		return slug.replace("-", " ").replace("_", " ").title()
	return "Marché"


def _init_state():
	if "trading_view" not in st.session_state:
		st.session_state.trading_view = "list"
	if "trading_page" not in st.session_state:
		st.session_state.trading_page = 1
	if "selected_market" not in st.session_state:
		st.session_state.selected_market = None

def _normalize_outcome(name: str) -> str:
	"""Normalize outcome name for matching positions regardless of case/format."""
	try:
		return (name or "").strip().lower()
	except Exception:
		return ""


def _render_market_detail(api: APIClient):
	slug = st.session_state.get("selected_market")
	if not slug:
		st.warning("Aucun marché sélectionné.")
		return

	col_back, _ = st.columns([1, 5])
	with col_back:
		if st.button("← Retour aux marchés", use_container_width=True):
			st.session_state.trading_view = "list"
			st.rerun()

	with st.spinner("Chargement du marché..."):
		resp = api.get_market(slug)

	if resp["status"] != 200:
		err = resp.get("error") or resp.get("data", {}).get("detail", "Impossible de charger le marché")
		st.error(err)
		return

	market = resp["data"]
	name = _display_name(market)
	# Use the stored closed flag
	status = "Clôturé" if market.get("closed", False) else "Actif"
	volume_24h = _format_number(market.get("volume_24h", 0))
	liquidity = _format_number(market.get("liquidity", 0))
	last_price = _format_number(market.get("last_price", 0))
	end_date = _format_date(market.get("end_date"))

	st.subheader(name)
	col1, col2, col3, col4 = st.columns(4)
	with col1:
		st.metric("Volume 24h", volume_24h)
	with col2:
		st.metric("Liquidité", liquidity)
	with col3:
		st.metric("Dernier prix", last_price)
	with col4:
		st.metric("Date de fin", end_date)

	st.write(f"**Statut :** {status}")
	if market.get("description"):
		st.write(market.get("description"))

	st.divider()

	# Outcomes with prices
	outcomes = market.get("outcomes") or []
	prices = market.get("outcome_prices") or []
	if outcomes and prices:
		st.subheader("Prix des issues")
		cols = st.columns(min(len(outcomes), 4))
		for idx, (outcome, price) in enumerate(zip(outcomes, prices)):
			with cols[idx % len(cols)]:
				try:
					price_pct = float(price) * 100
					st.metric(outcome, f"{price_pct:.1f}%")
				except:
					st.metric(outcome, _format_number(price))

	st.divider()
	
	# Trading form - only show for active markets
	if not market.get("closed", False):
		_render_trade_form(api, market)
	else:
		st.info("Ce marché est clôturé. Le trading n'est plus possible.")
	
	st.divider()
	if st.button("← Retour", use_container_width=True):
		st.session_state.trading_view = "list"
		st.rerun()


def _render_trade_form(api: APIClient, market: dict):
	"""Render the trading form for a market."""
	st.subheader("📊 Passer un ordre")
	
	# Get user portfolios
	portfolios_resp = api.list_portfolios()
	if portfolios_resp["status"] != 200:
		st.error("Impossible de charger les portefeuilles")
		return
	
	portfolios = portfolios_resp.get("data", [])
	if not portfolios:
		st.warning("Vous devez créer un portefeuille avant de trader.")
		st.info("Allez dans la section Portfolio pour en créer un.")
		return

	# Try to preselect the portfolio coming from the 'Vendre' button
	prefill_portfolio_id = st.session_state.get("prefill_portfolio_id")
	
	# Extract market data
	outcomes = market.get("outcomes", [])
	outcome_prices = market.get("outcome_prices", [])
	market_slug = market.get("slug")
	market_name = _display_name(market)
	# Use a stable identifier for positions that matches stored trades
	position_market_id = st.session_state.get("selected_market") or market_slug
	
	if not outcomes or not outcome_prices:
		st.warning("Pas de données de prix disponibles pour ce marché.")
		return
	
	# Create price mapping
	price_map = {}
	for outcome, price_str in zip(outcomes, outcome_prices):
		try:
			price_map[outcome] = float(price_str)
		except:
			price_map[outcome] = 0.5
	
	# Form
	with st.form("trade_form", clear_on_submit=False):
		col1, col2 = st.columns(2)
		
		with col1:
			# Portfolio selection (use stable IDs, not names)
			portfolio_ids = []
			portfolio_by_id = {}
			for p in portfolios:
				pid = p.get("_id") or p.get("id")
				if pid is None:
					continue
				pid = str(pid)
				portfolio_ids.append(pid)
				portfolio_by_id[pid] = p
			default_idx = 0
			if prefill_portfolio_id and str(prefill_portfolio_id) in portfolio_ids:
				default_idx = portfolio_ids.index(str(prefill_portfolio_id))
			selected_portfolio_id = st.selectbox(
				"Portefeuille",
				options=portfolio_ids,
				index=default_idx,
				format_func=lambda pid: portfolio_by_id[pid].get("name", pid),
				help="Sélectionnez le portefeuille à utiliser"
			)
			selected_portfolio = portfolio_by_id[selected_portfolio_id]
			
			# Show portfolio balance
			st.caption(f"💰 Cash disponible: ${selected_portfolio.get('cash_balance', 0):,.2f}")
			
			# Action
			default_action = st.session_state.get("prefill_action", "BUY")
			action = st.selectbox("Action", ["BUY", "SELL"], index=(1 if default_action == "SELL" else 0))
			
			# Outcome/Token
			prefill_outcome = st.session_state.get("prefill_outcome")
			outcome_index = None
			if prefill_outcome:
				# Try exact match first
				if prefill_outcome in outcomes:
					outcome_index = outcomes.index(prefill_outcome)
				else:
					# Fallback to case-insensitive matching
					norm_prefill = _normalize_outcome(prefill_outcome)
					for i, o in enumerate(outcomes):
						if _normalize_outcome(o) == norm_prefill:
							outcome_index = i
							break
			if outcome_index is not None:
				outcome = st.selectbox("Token", outcomes, index=outcome_index)
			else:
				outcome = st.selectbox("Token", outcomes)

		# Fetch current portfolio detail and positions once for display and validation
		portfolio_detail = api.get_portfolio(selected_portfolio_id)
		if portfolio_detail.get("status") != 200:
			st.error("Impossible de charger les détails du portefeuille")
			return
		portfolio_data = portfolio_detail.get("data", {})
		current_cash = portfolio_data.get("cash_balance", 0)

		trades: list = []
		# Backend caps page_size at 100; use 100 to avoid 422
		trades_resp = api.get_trades(selected_portfolio_id, page=1, page_size=100)
		current_positions = {}
		if trades_resp.get("status") == 200:
			trades_data = trades_resp.get("data", {})
			if isinstance(trades_data, dict):
				trades = trades_data.get("trades", []) or []
			elif isinstance(trades_data, list):
				trades = trades_data
			for trade in trades:
				key = (trade.get("market_id"), _normalize_outcome(trade.get("outcome")))
				if key not in current_positions:
					current_positions[key] = 0
				qty = trade.get("quantity", 0)
				if trade.get("side") == "buy":
					current_positions[key] += qty
				else:
					current_positions[key] -= qty

		# Compute available tokens for the selected outcome in this market
		market_keys = [position_market_id, market_slug, market.get("condition_id"), market.get("_id")]
		market_keys = [str(k) for k in market_keys if k]
		norm_outcome = _normalize_outcome(outcome)
		available_qty = 0
		for mk in market_keys:
			available_qty = current_positions.get((mk, norm_outcome), available_qty)
			if available_qty > 0:
				break

		st.caption(f"🔹 Tokens disponibles ({outcome}): {available_qty:.2f}")
		st.caption(f"🧾 Portefeuille sélectionné: {selected_portfolio.get('name', '')} (ID: {selected_portfolio_id})")
		
		with col2:
			# Price (MOC - Market On Close simulation)
			moc_price = price_map.get(outcome, 0.5)
			st.metric("Prix MOC", f"${moc_price:.4f}")
			st.caption("Prix simulé (Market-On-Close)")
			
			# Quantity
			prefill_max = st.session_state.get("prefill_max_qty")
			default_qty = 10.0
			min_qty = 0.01
			if default_action == "SELL" and isinstance(prefill_max, (int, float)) and prefill_max > 0:
				default_qty = min(prefill_max, default_qty)
				quantity = st.number_input(
					"Quantité",
					min_value=min_qty,
					max_value=float(prefill_max),
					value=float(default_qty),
					step=1.0,
					format="%.2f",
					help=f"Nombre de tokens à vendre (max {prefill_max:.2f})"
				)
			else:
				quantity = st.number_input(
					"Quantité",
					min_value=min_qty,
					value=float(default_qty),
					step=1.0,
					format="%.2f",
					help="Nombre de tokens à acheter/vendre"
				)
			
			# Calculate total
			total_cost = quantity * moc_price
			st.metric("Coût total", f"${total_cost:.2f}")
		
		# Notes (optional)
		notes = st.text_area("Notes (optionnel)", max_chars=500, height=60)
		
		# Submit button
		submitted = st.form_submit_button(
			"🚀 Passer l'ordre",
			type="primary",
			use_container_width=True
		)
		
		if submitted:
			# Validation
			errors = []
			
			# Validate based on action
			if action == "BUY":
				if current_cash < total_cost:
					errors.append(f"❌ Fonds insuffisants. Disponible: ${current_cash:.2f}, Requis: ${total_cost:.2f}")
			else:  # SELL
				# Match using multiple possible market identifiers (slug, condition_id, selected_market)
				market_keys = [position_market_id, market_slug, market.get("condition_id"), market.get("_id")]
				market_keys = [str(k) for k in market_keys if k]
				norm_outcome = _normalize_outcome(outcome)
				current_qty = available_qty
				if current_qty < quantity:
					errors.append(f"❌ Tokens insuffisants. Disponible: {current_qty:.2f}, Requis: {quantity:.2f}")
					errors.append("⚠️ La vente à découvert n'est pas autorisée")
			
			# Show errors or execute trade
			if errors:
				for error in errors:
					st.error(error)
			else:
				# Execute trade
				trade_resp = api.create_trade(
					portfolio_id=selected_portfolio_id,
					market_id=position_market_id or market_slug,
					outcome=outcome,
					side=action.lower(),
					quantity=quantity,
					price=moc_price,
					notes=notes if notes else None
				)
				
				if trade_resp["status"] == 201:
					st.success(f"✅ Ordre exécuté avec succès!")
					trade_data = trade_resp["data"]
					
					# Show trade summary
					st.info(f"""
**Récapitulatif:**
- Action: {action}
- Token: {outcome}
- Quantité: {quantity:.2f}
- Prix: ${moc_price:.4f}
- Total: ${total_cost:.2f}
- Nouveau solde: ${current_cash - total_cost if action == 'BUY' else current_cash + total_cost:.2f}
					""")
					
					st.balloons()
					# Clear prefill state after successful trade
					st.session_state.pop("prefill_action", None)
					st.session_state.pop("prefill_outcome", None)
					st.session_state.pop("prefill_max_qty", None)
					# Refresh after short delay
					import time
					time.sleep(1)
					st.rerun()
				else:
					error_detail = trade_resp.get("data", {}).get("detail") if isinstance(trade_resp.get("data"), dict) else trade_resp.get("error")
					st.error(f"❌ Erreur lors de l'exécution: {error_detail}")


def _render_market_list(api: APIClient):
	st.title("Trading")

	# Filters
	with st.expander("🔍 Filtres", expanded=True):
		col1, col2, col3, col4 = st.columns(4)
		with col1:
			search = st.text_input("Recherche", placeholder="Nom ou slug")
		with col2:
			status_filter = st.selectbox("Statut", ["Tous", "Actifs", "Clôturés"], index=0)
		with col3:
			sort_by = st.selectbox("Tri", ["volume_24h", "liquidity"], index=0)
		with col4:
			volume_min = st.number_input("Volume min", min_value=0.0, step=100.0, value=0.0)

	# Pagination
	colp1, colp2 = st.columns([3, 1])
	with colp2:
		page_size = st.selectbox("Par page", [10, 20, 50], index=1)

	if "trading_page" not in st.session_state:
		st.session_state.trading_page = 1

	active = None
	closed = None
	if status_filter == "Actifs":
		active, closed = True, False
	elif status_filter == "Clôturés":
		active, closed = None, True

	resp = api.list_markets(
		page=st.session_state.trading_page,
		page_size=page_size,
		search=search or None,
		active=active,
		closed=closed,
		volume_min=volume_min if volume_min > 0 else None,
		sort_by=sort_by,
	)

	if resp["status"] != 200:
		err = resp.get("error") or resp.get("data", {}).get("detail", "Impossible de récupérer les marchés")
		st.error(err)
		return

	data = resp.get("data") or {}
	markets = data.get("items") or data.get("markets") or (data if isinstance(data, list) else [])
	total = data.get("total", len(markets)) if isinstance(data, dict) else len(markets)
	total_pages = data.get("total_pages", 1) if isinstance(data, dict) else 1

	st.write(f"Trouvé **{total}** marchés (Page {st.session_state.trading_page}/{total_pages})")

	# Pagination controls
	col_prev, col_page, col_next = st.columns([1, 2, 1])
	with col_prev:
		if st.button("← Précédent", disabled=st.session_state.trading_page <= 1):
			st.session_state.trading_page -= 1
			st.rerun()
	with col_page:
		st.write("")
	with col_next:
		if st.button("Suivant →", disabled=st.session_state.trading_page >= total_pages):
			st.session_state.trading_page += 1
			st.rerun()

	st.divider()

	if not markets:
		st.info("Aucun marché trouvé avec ces filtres.")
		return

	for market in markets:
		name = _display_name(market)
		volume = _format_number(market.get("volume_24h", 0))
		liquidity = _format_number(market.get("liquidity", 0))
		end_date_raw = market.get("end_date")
		end_date = _format_date(end_date_raw) if end_date_raw else None
		# Use the stored closed flag
		status_txt = "Clôturé" if market.get("closed", False) else "Actif"
		# Show time remaining for active markets
		time_left = ""
		if not market.get("closed", False) and end_date_raw:
			time_left = _time_until_end(end_date_raw)
			if time_left:
				time_left = f" • {time_left}"
		
		# Build caption based on what data we have
		if end_date:
			caption = f"📅 {end_date} • {status_txt}{time_left}"
		else:
			caption = f"{status_txt}{time_left}"
		
		slug = market.get("slug") or name

		with st.container():
			col_a, col_b, col_c, col_d, col_e, col_f = st.columns([3, 1.5, 1.5, 1.5, 1.5, 1])
			with col_a:
				st.markdown(f"**{name}**")
				st.caption(caption)
			with col_b:
				st.metric("Volume 24h", volume)
			with col_c:
				st.metric("Liquidité", liquidity)
			with col_d:
				outcomes = market.get("outcomes", [])
				prices = market.get("outcome_prices", [])
				if outcomes and prices:
					try:
						yes_price = float(prices[0]) * 100
						st.metric(outcomes[0], f"{yes_price:.1f}%")
					except:
						st.write("-")
				else:
					st.write("-")
			with col_e:
				# Espace vide pour équilibrer le layout
				st.write("")
			with col_f:
				if st.button("Détails", key=f"detail_{slug}", use_container_width=True):
					st.session_state.selected_market = slug
					st.session_state.trading_view = "detail"
					st.rerun()
		st.divider()

	# Top markets highlight
	st.subheader("🔥 Top marchés (volume 24h)")
	top_result = api.get_top_markets(limit=5, sort_by="volume_24h")
	if top_result["status"] == 200 and top_result.get("data"):
		top_markets = top_result["data"]
		cols = st.columns(min(len(top_markets), 5))
		for i, market in enumerate(top_markets):
			name = _display_name(market)
			vol = _format_number(market.get("volume_24h", 0))
			liq = _format_number(market.get("liquidity", 0))
			with cols[i % len(cols)]:
				st.markdown(f"**{name}**\n\nVolume 24h: {vol}\n\nLiquidité: {liq}")
	else:
		st.info("Aucun top marché disponible.")


def render():
	_init_state()
	api = APIClient(API_URL)

	if st.session_state.get("trading_view") == "detail":
		_render_market_detail(api)
	else:
		_render_market_list(api)
