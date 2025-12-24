import streamlit as st

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
	status = "Clôturé" if market.get("closed") else "Actif"
	volume_24h = _format_number(market.get("volume_24h", 0))
	liquidity = _format_number(market.get("liquidity", 0))
	last_price = _format_number(market.get("last_price", 0))

	st.subheader(name)
	col1, col2, col3 = st.columns(3)
	with col1:
		st.metric("Volume 24h", volume_24h)
	with col2:
		st.metric("Liquidité", liquidity)
	with col3:
		st.metric("Dernier prix", last_price)

	st.write(f"**Statut :** {status}")
	if market.get("description"):
		st.write(market.get("description"))

	st.divider()

	# Optionally outcomes
	outcomes = market.get("outcomes") or []
	prices = market.get("outcome_prices") or []
	if outcomes and prices:
		st.subheader("Prix des issues")
		cols = st.columns(min(len(outcomes), 4))
		for idx, (outcome, price) in enumerate(zip(outcomes, prices)):
			with cols[idx % len(cols)]:
				st.metric(outcome, _format_number(price))

	st.divider()
	if st.button("← Retour", use_container_width=True):
		st.session_state.trading_view = "list"
		st.rerun()


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
		status_txt = "Clôturé" if market.get("closed") else "Actif"
		slug = market.get("slug") or name

		with st.container():
			col_a, col_b, col_c, col_d, col_e = st.columns([3, 2, 2, 1.5, 1])
			with col_a:
				st.markdown(f"**{name}**")
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
