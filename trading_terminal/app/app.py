"""Trading terminal. Run with:  .venv\\Scripts\\streamlit run app.py"""
from __future__ import annotations

import functools
import hashlib
import html as htmllib
import json
import os
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from terminal import (ai, alerts, backtest, cache, claude_code, collector, config, data, gains, ideas, journal,
                      predictions, profile, sentiment, sources, store, stream, watchlists)
from terminal import indicators as ind
from terminal.brokers import OrderRequest, connect_all

PAGE_STARTED = time.perf_counter()
SLOW_SECONDS = 1.0  # anything slower is written to the log (the add-on's Log tab in Home Assistant)


def log_if_slow(what: str, started: float):
    took = time.perf_counter() - started
    if took >= SLOW_SECONDS:
        print(f"[speed] {what} took {took:.1f}s", file=sys.stderr, flush=True)


def timed(what: str):
    """Decorator: log a section's run time when it's slow."""
    def wrap(fn):
        @functools.wraps(fn)  # keeps each wrapped section's own identity (Streamlit keys fragments on it)
        def run(*args, **kwargs):
            started = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                log_if_slow(what, started)
        return run
    return wrap

# Sections and their screens. The codes also work typed into the search box ("NVDA GP").
NAV = {
    "Home": {"PORT": "Portfolio", "ORD": "Trade", "JRNL": "Journal", "GAIN": "Gains & dividends", "ALRT": "Alerts"},
    "Stock": {"DES": "Overview", "GP": "Chart", "N": "News", "FA": "Financials", "VAL": "Valuation",
              "ANR": "Analysts", "ERN": "Earnings", "SEC": "Filings & insiders", "OMON": "Options",
              "BT": "Backtest"},
    "Market": {"MON": "Watchlist", "SPX": "S&P 500", "IDEA": "Ideas", "CAL": "Earnings calendar",
               "PRED": "Predictions", "SCR": "Screens", "ECO": "Economy"},
    "Assistant": {"BRF": "Morning brief", "AI": "Ask AI", "PLAN": "My trading plan", "CLD": "Connect Claude", "DATA": "Data collection",
                  "HELP": "Shortcuts"},
}
HOME = "PORT"  # first screen, like Robinhood's home: account value, positions, watchlist
FUNCTIONS = {code: label for items in NAV.values() for code, label in items.items()}
GROUP_OF = {code: group for group, items in NAV.items() for code in items}
# Brand accent is burnt orange; green and red are kept only for gains and losses, and the loss red
# is a true red so it is never mistaken for the accent.
ORANGE = "#e2711d"
AMBER, GREEN, RED, MUTED = "#f5a524", "#00c805", "#f6465d", "#8c8c8c"
CLEAR = "rgba(0,0,0,0)"
LINE = "#1e2124"  # hairline borders and chart grid

st.set_page_config(page_title="Terminal", page_icon="▮", layout="wide")
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, button, input, textarea, select, p, li, td, th {font-family: 'Inter', sans-serif !important;}
header[data-testid="stHeader"] {display: none;}
/* Live sections redraw every second or two; don't dim them while they do */
[data-stale="true"] {opacity: 1 !important; transition: none !important;}
.block-container {padding: .9rem 2.2rem 2rem; max-width: 1480px;}
h3 {font-size: 1.35rem !important; font-weight: 700 !important; padding: 1.4rem 0 .5rem !important;
    border-bottom: 1px solid #1e2124; margin-bottom: .6rem !important;}
hr {border-color: #1e2124 !important; margin: .4rem 0 1rem !important;}
[data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums;}
[data-testid="stMetricLabel"] {color: #8c8c8c;}

/* Tabs: section bar, range selectors, buy/sell -- plain text, active one underlined in the accent */
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
    background: transparent !important; border: none !important; box-shadow: none !important;
    border-radius: 0 !important; padding: .3rem .1rem !important; margin-right: 1.15rem; color: #fff !important;
    font-weight: 600; border-bottom: 2px solid transparent !important;}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {color: var(--acc) !important;}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"] {
    color: var(--acc) !important; border-bottom: 2px solid var(--acc) !important;}
/* Chips: the screen picker under the top bar */
[data-testid="stButtonGroup"] button[data-variant="pills"] {
    background: #1e2124 !important; border: none !important; color: #fff !important; font-weight: 600;
    border-radius: 999px !important; padding: .25rem .9rem !important;}
[data-testid="stButtonGroup"] button[data-variant="pills"]:hover {background: #2a2d31 !important;}
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-checked="true"],
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-pressed="true"],
[data-testid="stButtonGroup"] button[data-variant="pills"][data-selected="true"] {
    background: var(--acc) !important; color: #000 !important;}
/* Buttons: accent pill for the main action, outlined pill otherwise */
[data-testid="stBaseButton-primary"] {background: var(--acc) !important; color: #000 !important; border: none !important;
    border-radius: 999px !important; font-weight: 700 !important; min-height: 2.9rem;}
[data-testid="stBaseButton-primary"]:hover {filter: brightness(1.12);}
[data-testid="stBaseButton-primary"] * {color: #000 !important;}
[data-testid="stBaseButton-primary"]:disabled {opacity: .45;}
[data-testid="stButtonGroup"] button[data-variant="pills"][aria-checked="true"] * {color: #000 !important;}
[data-testid="stBaseButton-secondary"] {background: transparent !important; color: var(--acc) !important;
    border: 1px solid var(--acc) !important; border-radius: 999px !important; font-weight: 600 !important;}
[data-testid="stTextInputRootElement"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"] {
    border-radius: .5rem !important;}
[data-testid="stTextInputRootElement"]:has(input[aria-label="Search"]) {border-radius: 999px !important; background: #1e2124 !important;}
[data-testid="stExpander"] details {border: none !important; border-top: 1px solid #1e2124 !important; border-radius: 0 !important;}

.brand {font-weight: 800; font-size: 1.15rem; color: var(--acc); letter-spacing: -.01em; white-space: nowrap;}
.mode {text-align: right;}
.mode span {font-size: .72rem; font-weight: 700; padding: .25rem .6rem; border-radius: 999px; letter-spacing: .04em;}

/* Stock header */
.tk-name {font-size: 2.1rem; font-weight: 600; line-height: 1.15;}
.tk-px {font-size: 2.1rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.2;}
.tk-chg {font-weight: 600; font-variant-numeric: tabular-nums; margin-top: .15rem;}
.tk-chg small {color: #8c8c8c; font-weight: 500; margin-left: .3rem;}
.tk-sub {color: #8c8c8c; font-size: .8rem; margin-top: .35rem; font-variant-numeric: tabular-nums;}
.dot {display: inline-block; width: .5rem; height: .5rem; border-radius: 50%; margin: 0 .3rem 0 .1rem;}

/* Grids of label / value */
.stats {display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem 1.6rem;}
.stats div span {display: block; font-weight: 700; font-size: .82rem; margin-bottom: .2rem;}
.stats div b {font-weight: 400; font-variant-numeric: tabular-nums; color: #d9d9d9;}
.about {color: #d9d9d9; line-height: 1.55;}
.about summary {color: var(--acc); font-weight: 600; cursor: pointer; margin: .3rem 0 1rem;}

/* In-app links: a stock row or card with an invisible button laid over it, so a click opens the
   stock without reloading the page */
[class*="st-key-golist_"], [class*="st-key-golist_"] [data-testid="stVerticalBlock"] {gap: 0 !important;}
[class*="st-key-goto_"] {position: relative;}
[class*="st-key-goto_"] [data-testid="stElementContainer"]:has(button) {position: absolute; inset: 0; z-index: 2; margin: 0;
    width: 100% !important; height: 100% !important; max-width: none !important;}
[class*="st-key-goto_"] [data-testid="stMarkdownContainer"], [class*="st-key-goto_"] [data-testid="stMarkdown"] {margin-bottom: 0 !important;}
[class*="st-key-goto_"] [data-testid="stButton"], [class*="st-key-goto_"] button {width: 100% !important; height: 100% !important;}
[class*="st-key-goto_"] button {opacity: 0; cursor: pointer;}
[class*="st-key-goto_"]:hover div.row, [class*="st-key-goto_"]:hover div.card {background: #0d0f11;}
/* Lists: watchlist, positions, movers */
div.row {display: grid; grid-template-columns: 1.2fr 1fr 96px 1fr; align-items: center; gap: .8rem;
    padding: .75rem .2rem; border-bottom: 1px solid #1e2124; color: #fff !important; text-decoration: none !important;}
div.row:hover {background: #0d0f11;}
div.row.compact {grid-template-columns: 1fr 72px 1fr;}
.row b {font-weight: 700;} .row small {display: block; color: #8c8c8c; font-size: .78rem; margin-top: .1rem;}
.row .r {text-align: right; font-variant-numeric: tabular-nums;}
.pill {display: inline-block; min-width: 4.6rem; text-align: center; color: #000; font-weight: 700; font-size: .8rem;
    padding: .3rem .5rem; border-radius: .45rem; font-variant-numeric: tabular-nums;}
.cards {display: grid; grid-template-columns: repeat(5, 1fr); gap: .8rem;}
div.card {border: 1px solid #1e2124; border-radius: .8rem; padding: .9rem 1rem; color: #fff !important;
    text-decoration: none !important; display: block;}
div.card:hover {background: #0d0f11;}
.card .n {color: #8c8c8c; font-size: .78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.card .p {font-size: 1.15rem; font-weight: 700; margin-top: .5rem; font-variant-numeric: tabular-nums;}
.box {border: 1px solid #1e2124; border-radius: .8rem; padding: 1.1rem 1.2rem 1rem; margin-top: .2rem;}
.box-title {font-size: 1.05rem; font-weight: 700; margin-bottom: .6rem;}
.line {display: flex; justify-content: space-between; padding: .45rem 0; font-variant-numeric: tabular-nums;}
.line.total {border-top: 1px solid #2a2d31; margin-top: .3rem; padding-top: .7rem; font-weight: 700;}
.muted {color: #8c8c8c;}
.loading {border: 1px solid #1e2124; border-radius: .8rem; padding: 2.4rem; text-align: center; color: #8c8c8c;}

/* News */
a.news {display: flex; gap: 1rem; justify-content: space-between; padding: .9rem 0; border-bottom: 1px solid #1e2124;
    color: #fff !important; text-decoration: none !important;}
a.news:hover .t {color: var(--acc);}
.news .src {font-size: .78rem; font-weight: 700;} .news .src span {color: #8c8c8c; font-weight: 500;}
.news .t {font-weight: 600; margin-top: .2rem; line-height: 1.35;}
.news img {width: 76px; height: 76px; object-fit: cover; border-radius: .5rem; flex: none;}

/* Analyst ratings */
.anr {display: grid; grid-template-columns: 9rem 1fr; gap: 1.6rem; align-items: center;}
.anr .big {width: 8.5rem; height: 8.5rem; border-radius: 50%; display: flex; flex-direction: column;
    align-items: center; justify-content: center;}
.anr .big b {font-size: 1.9rem;} .anr .big small {color: #d9d9d9; font-size: .78rem;}
.bar {display: grid; grid-template-columns: 3rem 1fr 3rem; gap: .8rem; align-items: center; margin: .45rem 0;}
.bar .track {height: .55rem; background: #1e2124; border-radius: 999px; overflow: hidden;}
.bar .fill {height: 100%; border-radius: 999px;}

/* Idea lists, calendar, prediction cards */
a.idea {display: grid; grid-template-columns: 1.4fr 3.2fr 1fr; align-items: center; gap: 1rem;
    padding: .8rem .2rem; border-bottom: 1px solid #1e2124; color: #fff !important; text-decoration: none !important;}
a.idea:hover {background: #0d0f11;}
.idea small {display: block; color: #8c8c8c; font-size: .78rem;}
.chip {display: inline-block; font-size: .72rem; font-weight: 600; padding: .18rem .55rem; border-radius: 999px;
    margin: .15rem .3rem .15rem 0; white-space: nowrap;}
.score {font-weight: 800; font-size: .8rem; color: #8c8c8c;}
.cal {display: grid; grid-template-columns: 8.5rem 1fr 9rem 9rem 9rem; align-items: center; gap: 1rem;
    padding: .8rem .4rem; border-bottom: 1px solid #1e2124;}
.cal.soon {border-left: 3px solid var(--acc); background: #0d0f11;}
.cal a {color: #fff !important; text-decoration: none !important; font-weight: 700;}
.cal small {display: block; color: #8c8c8c; font-size: .78rem;}
.pred {border: 1px solid #1e2124; border-radius: .8rem; padding: 1rem 1.1rem; margin-bottom: .8rem;}
.pred a {color: #fff !important; text-decoration: none !important; font-weight: 700;}
.pred .bar {grid-template-columns: minmax(8rem, 1.2fr) 2fr 3.2rem;}
.brand {overflow: hidden; text-overflow: clip;}

/* Narrow windows: drop the wordmark so the search box never covers it */
@media (max-width: 1100px) {
    .brand {font-size: 0; } .brand::first-letter {font-size: 1.3rem;}
    .block-container {padding: .7rem 1rem 2rem;}
}
/* Phones (Streamlit stacks columns below ~640px) */
@media (max-width: 640px) {
    .block-container {padding: .5rem .75rem 3rem;}
    .brand {font-size: 1.1rem;} .brand::first-letter {font-size: inherit;}
    .mode {text-align: left;}
    .tk-name {font-size: 1.55rem;} .tk-px {font-size: 1.75rem;}
    h3 {font-size: 1.15rem !important; padding-top: 1rem !important;}
    .stats {grid-template-columns: repeat(2, 1fr); gap: .9rem 1rem;}
    .cards {grid-template-columns: repeat(2, 1fr);}
    div.row {grid-template-columns: 1fr 64px auto; gap: .5rem;}
    div.row:not(.compact) > div:nth-child(2) {display: none;}  /* volume / extra detail column */
    a.idea {grid-template-columns: 1fr auto; gap: .4rem .8rem;}
    a.idea > div:nth-child(2) {grid-column: 1 / -1; order: 3;}  /* check chips on their own line */
    .cal {grid-template-columns: 1fr 1fr; gap: .5rem 1rem;}
    .anr {grid-template-columns: 1fr; justify-items: center;}
    .anr > div:last-child {width: 100%;}
    .news img {width: 58px; height: 58px;}
    [data-testid="stButtonGroup"] button[data-variant="segmented_control"] {margin-right: .8rem;}
    [data-testid="stMetricValue"] {font-size: 1.25rem;}
}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)

stream.start()  # background price stream; no-op if already running or Alpaca is not configured
collector.start()  # daily data collection; does nothing until storage is set up (Assistant > Data collection)

ss = st.session_state
ss.setdefault("ticker", "AAPL")
ss.setdefault("fn", HOME)
ss.setdefault("pending_order", None)
ss.setdefault("ticket_symbol", None)  # set by the options chain to trade a contract
ss.setdefault("chat", [])  # [(role, text)] for display
ss.setdefault("chat_api", [])  # full message history sent to Claude


# ---------- cached data ----------
@st.cache_data(ttl=120, show_spinner=False)  # live price is laid over this every few seconds
def c_quote(s): return data.quote(s)
def _syms_key(prefix, syms): return prefix + hashlib.md5(",".join(syms).encode()).hexdigest()[:12]
def c_quotes(syms):
    """Quotes for a list; the last saved copy shows instantly and refreshes in the background."""
    return cache.latest(_syms_key("quotes-", syms), lambda: data.quotes(list(syms)), 120)
@st.cache_data(ttl=300, show_spinner=False)
def c_history(s, period, interval): return data.history(s, period, interval)
@st.cache_data(ttl=900, show_spinner=False)
def c_info(s): return data.info(s)
@st.cache_data(ttl=300, show_spinner=False)
def c_news(s): return data.news(s)
@st.cache_data(ttl=3600, show_spinner=False)
def c_fin(s, stmt, q): return data.financials(s, stmt, q)
@st.cache_data(ttl=3600, show_spinner=False)
def c_recs(s): return data.recommendations(s)
@st.cache_data(ttl=120, show_spinner=False)
def c_screen(name): return data.screen(name)
@st.cache_data(ttl=900, show_spinner=False)
def c_filings(s): return sources.sec_filings(s)
@st.cache_data(ttl=3600, show_spinner=False)
def c_insiders(s): return sources.insider_transactions(s)
@st.cache_data(ttl=3600, show_spinner=False)
def c_surprises(s): return sources.earnings_surprises(s)
@st.cache_data(ttl=3600, show_spinner=False)
def c_calendar(days): return sources.earnings_calendar(days)
@st.cache_data(ttl=3600, show_spinner=False)
def c_fmp(endpoint, s): return sources.fmp(endpoint, s)
@st.cache_data(ttl=3600, show_spinner=False)
def c_fred(series_id): return sources.fred_series(series_id)
@st.cache_data(ttl=3600, show_spinner=False)
def c_expiries(s): return data.option_expirations(s)
@st.cache_data(ttl=60, show_spinner=False)
def c_chain(s, expiry): return data.option_chain(s, expiry)
def c_sparks(syms):
    return cache.latest(_syms_key("sparks-", syms), lambda: data.sparklines(list(syms)), 300)
@st.cache_data(ttl=60, show_spinner=False)
def c_port_history(broker_name, period): return c_brokers()[0][broker_name].portfolio_history(period)
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def c_upcoming(syms): return sources.upcoming_earnings(list(syms))
@st.cache_data(ttl=600, show_spinner=False)
def c_public_predictions(): return predictions.all_events()
@st.cache_data(ttl=600, show_spinner=False)
def c_forecastex(products):
    b = c_brokers()[0].get("Interactive Brokers")
    return b.forecast_markets(list(products)) if b else ([], {})


def c_predictions(wait: bool = False):
    """Kalshi + Polymarket (public sites) plus IBKR ForecastEx through IB Gateway when it's connected.

    Fetching these can take a minute (ForecastEx waits on IB Gateway), so by default this returns the last
    saved odds straight away and refreshes them in the background; only the Predictions screen waits."""
    if wait:
        events, errors = c_public_predictions()
    else:
        saved, _, _, err = cache.get("predictions-public", predictions.all_events, 600)
        events, errors = saved if saved is not None else ([], {"Prediction markets": err or "still loading"})
    b = c_brokers()[0].get("Interactive Brokers")
    if b:
        codes = tuple(predictions.forecast_products())
        try:
            if wait:
                fx, problems = c_forecastex(codes)
            else:
                saved, _, _, err = cache.get("predictions-fx-" + "-".join(codes),
                                             lambda: b.forecast_markets(list(codes)), 600)
                fx, problems = saved if saved is not None else ([], {})
            events = events + fx
            errors = {**errors, **{f"ForecastEx {k}": v for k, v in problems.items()}}
        except Exception as e:
            errors = {**errors, "ForecastEx": str(e)}
    return events, errors
@st.cache_data(ttl=60, show_spinner=False)
def c_held():
    """Stock symbols held at any connected broker (options left out)."""
    held = []
    for b in c_brokers()[0].values():
        try:
            held += [p["symbol"] for p in b.positions()]
        except Exception:
            pass
    stocks = [s for s in dict.fromkeys(held) if not OrderRequest(s, "buy", 1).is_option]
    collector.note_symbols(stocks)  # so the collector saves data for what you own
    return stocks
@st.cache_data(ttl=10, show_spinner=False)
def c_account(name): return c_brokers()[0][name].account()
@st.cache_data(ttl=10, show_spinner=False)
def c_positions(name): return c_brokers()[0][name].positions()
@st.cache_resource(show_spinner="Connecting to brokers...")
def c_brokers(): return connect_all()


# ---------- helpers ----------
def big(n) -> str:
    if n is None or pd.isna(n):
        return "-"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:,.2f}{suf}"
    return f"{n:,.2f}"


def num(n, fmt="{:,.2f}") -> str:
    return "-" if n is None or pd.isna(n) else fmt.format(n)


def run_command():
    """Command bar: 'AAPL GP', 'MSFT', 'PORT' ..."""
    parts = ss.cmd.upper().split()
    ss.cmd = ""
    for p in parts:
        if p in FUNCTIONS:
            ss.fn = p
        else:
            ss.ticker = p
            ss.pending_order = None
            ss.ticket_symbol = None


def usd(n, sign: bool = False) -> str:
    if n is None or pd.isna(n):
        return "-"
    # "&#36;" rather than "$": two dollar signs in one markdown block are read as a LaTeX formula.
    return f"{'+' if sign and n > 0 else '-' if n < 0 else ''}&#36;{abs(n):,.2f}"


def link(symbol: str) -> str:
    """URL that opens a symbol's overview (list rows and cards are plain links)."""
    return f"?t={symbol}"


# ---------- header ----------
# Clicking a row in a list loads ?t=SYMBOL; open that stock, then tidy the address bar.
if "t" in st.query_params or "f" in st.query_params:  # ?f=CODE opens a screen directly, e.g. ?f=SPX
    if "t" in st.query_params:
        ss.ticker, ss.fn = st.query_params["t"].upper(), "DES"
        ss.pending_order = ss.ticket_symbol = None
    if st.query_params.get("f", "").upper() in FUNCTIONS:
        ss.fn = st.query_params["f"].upper()
    st.query_params.clear()

sym = ss.ticker
fn = ss.fn if ss.fn in FUNCTIONS else HOME
group = GROUP_OF[fn]
# The two nav widgets mirror `fn`, so typed commands and buttons that change screen stay in sync.
ss.nav_group, ss.nav_item = group, fn
STOCK_HEADER = group == "Stock" or fn in ("ALRT", "AI")

q = None
def prefetch(*jobs):
    """Run cached loaders side by side so a new stock's data arrives in one wait, not one per source."""
    from concurrent.futures import ThreadPoolExecutor

    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    ctx = get_script_run_ctx()

    def run(job):
        add_script_run_ctx(ctx=ctx)  # lets the worker thread use Streamlit's caches
        try:
            job[0](*job[1:])
        except Exception:
            pass  # the screen shows the error when it asks for this again

    with ThreadPoolExecutor(len(jobs)) as pool:
        list(pool.map(run, jobs))


if STOCK_HEADER or fn == "ORD":
    stock_jobs = [(c_quote, sym), (c_info, sym)]
    if fn == "DES":
        stock_jobs += [(c_news, sym), (c_history, sym, *("1d", "5m")), (c_recs, sym)]
    prefetch(*stock_jobs)
    try:
        q = c_quote(sym)
    except Exception:
        q = None
ACC = ORANGE  # brand accent: buttons, tabs, highlights. Gains and losses stay green / red.
st.markdown(f"<style>:root {{--acc: {ACC};}}</style>", unsafe_allow_html=True)


def pick_group():
    ss.fn = next(iter(NAV[ss.nav_group or group]))


def pick_item():
    ss.fn = ss.nav_item or fn


top = st.columns([1.1, 3.2, 5, 1.4], vertical_alignment="center")
top[0].markdown(f"<a class='brand' href='?f={HOME}' target='_self' style='text-decoration:none;display:block'>▮ Terminal</a>",
               unsafe_allow_html=True)
top[1].text_input(
    "Search", key="cmd", on_change=run_command, placeholder="Search", label_visibility="collapsed",
    icon=":material/search:", help="Type a ticker (NVDA), a screen code (GP), or both (MSFT FA) and press Enter",
)
top[2].segmented_control("Section", list(NAV), key="nav_group", on_change=pick_group, label_visibility="collapsed")
mode_color = RED if config.LIVE else GREEN
top[3].markdown(
    f"<div class='mode'><span style='color:{mode_color};background:{mode_color}22'>{config.MODE_LABEL}</span></div>",
    unsafe_allow_html=True,
)
st.pills("Screen", list(NAV[group]), key="nav_item", format_func=lambda c: NAV[group][c], on_change=pick_item,
         label_visibility="collapsed")
st.divider()

brokers, broker_errors = c_brokers()


def stream_badge() -> str:
    state, why = stream.status()
    label, color = {"live": ("Live", GREEN), "connecting": ("Delayed", AMBER)}.get(state, ("Snapshot", MUTED))
    return f"<span title='{why}'><span class='dot' style='background:{color}'></span>{label}</span>"


@st.fragment(run_every=3)
@timed("price header")
def live_header(base: dict, name: str):
    """Name, price and today's move; redrawn every second from the background price stream."""
    q = data.with_live(base)
    color = GREEN if (q["change"] or 0) >= 0 else RED
    quote = f" · Bid {usd(q['bid'])} × Ask {usd(q['ask'])}" if q.get("bid") else ""
    st.markdown(
        f"<div class='tk-name'>{name or sym}</div>"
        f"<div class='tk-px'>{usd(q['last'])}</div>"
        f"<div class='tk-chg' style='color:{color}'>{usd(q['change'], sign=True)} "
        f"({num(q['change_pct'], '{:+.2f}%')})<small>Today</small></div>"
        f"<div class='tk-sub'>{sym}{quote} · {stream_badge()}</div>",
        unsafe_allow_html=True,
    )


@st.fragment(run_every=30)
@timed("alert check")
def alert_watch():
    for a in alerts.check():
        st.toast(f"ALERT: {a['symbol']} is {a['direction']} {a['price']:,.2f} (now {a['triggered']:,.2f})", icon="🔔")


alert_watch()
company = ""
if STOCK_HEADER:
    if q is None:
        st.error(f"No market data for '{sym}'. Check the ticker symbol.")
    else:
        try:
            company = c_info(sym).get("shortName") or ""
        except Exception:
            pass
        if fn != "DES":  # the overview places the header beside its order card instead
            live_header(q, company)

RANGES = {"1D": ("1d", "5m"), "1W": ("5d", "15m"), "1M": ("1mo", "1h"), "3M": ("3mo", "1d"),
          "YTD": ("ytd", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk"), "MAX": ("max", "1mo")}
NO_TOOLBAR = {"displayModeBar": False}


def style_fig(fig, height: int, **layout):
    layout.setdefault("margin", dict(l=0, r=0, t=10, b=0))
    fig.update_layout(template="plotly_dark", paper_bgcolor=CLEAR, plot_bgcolor=CLEAR, height=height,
                      font=dict(color=MUTED, family="Inter"),
                      hoverlabel=dict(bgcolor="#1e2124", bordercolor="#1e2124", font_color="#fff"), **layout)
    fig.update_xaxes(gridcolor=LINE, zeroline=False)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


def skip_closed_hours(fig, rng: str):
    if RANGES[rng][1] in ("5m", "15m", "1h"):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[16, 9.5], pattern="hour")])


def line_chart(series: pd.Series, height: int, color: str, baseline: float | None = None, rng: str | None = None):
    """Robinhood-style chart: one line, no axes or grid, a crosshair and price + date on hover."""
    idx = pd.DatetimeIndex(series.index)
    intraday = bool((idx != idx.normalize()).any())  # bars with a time of day, so show the time too
    when = "%b %d, %Y · %I:%M %p" if intraday else "%a, %b %d, %Y"
    fig = go.Figure(go.Scatter(x=series.index, y=series.values, mode="lines", line=dict(color=color, width=2),
                               hovertemplate=f"<b>$%{{y:,.2f}}</b><br>%{{x|{when}}}<extra></extra>"))
    if baseline:
        fig.add_hline(y=baseline, line=dict(color="#4a4d52", width=1, dash="dot"))
    style_fig(fig, height, showlegend=False, hovermode="x", margin=dict(l=0, r=0, t=6, b=0))
    fig.update_xaxes(visible=False, showspikes=True, spikemode="across", spikethickness=1, spikecolor="#4a4d52",
                     spikedash="solid")
    fig.update_yaxes(visible=False)
    if rng:
        skip_closed_hours(fig, rng)
    st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)


def spark_svg(vals: list[float], color: str, baseline: float | None = None, w: int = 96, h: int = 34) -> str:
    if not vals or len(vals) < 2:
        return ""
    pts = vals + ([baseline] if baseline else [])
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1

    def y(v):
        return h - 2 - (v - lo) / span * (h - 4)

    line = " ".join(f"{i * w / (len(vals) - 1):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    base = (f"<line x1='0' x2='{w}' y1='{y(baseline):.1f}' y2='{y(baseline):.1f}' stroke='#4a4d52' "
            "stroke-dasharray='1 3'/>") if baseline else ""
    return (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{base}"
            f"<polyline fill='none' stroke='{color}' stroke-width='1.6' points='{line}'/></svg>")


def stock_rows(rows: list[dict], compact: bool = False) -> str:
    """List rows like Robinhood's watchlist: symbol, sparkline, price and a coloured change pill.
    Each row: symbol, last, change_pct, optional prev, spark, sub, extra (right-hand detail)."""
    html = []
    for r in rows:
        pct = r.get("change_pct")
        color = RED if (pct or 0) < 0 else GREEN
        sub = f"<small>{r['sub']}</small>" if r.get("sub") else ""
        extra = "" if compact else f"<div class='r'>{r.get('extra', '')}</div>"
        html.append(
            f"<div class='row{' compact' if compact else ''}'>"
            f"<div><b>{r['symbol']}</b>{sub}</div>{extra}"
            f"<div>{spark_svg(r.get('spark') or [], color, r.get('prev'), w=72 if compact else 96)}</div>"
            f"<div class='r'><b>{usd(r.get('last'))}</b><br>"
            f"<span class='pill' style='background:{color}'>{num(pct, '{:+.2f}%')}</span></div></div>"
        )
    # Wrapped in a block element so markdown passes it through as raw HTML.
    return "<div>" + "".join(html) + "</div>"


def open_stock(symbol: str):
    ss.ticker, ss.fn = symbol, "DES"
    ss.pending_order = ss.ticket_symbol = None


def nav_list(rows: list[dict], key: str, compact: bool = False):
    """Stock rows that open the stock in place (no page reload) when clicked."""
    with st.container(key=f"golist_{key}"):
        for r in rows:
            with st.container(key=f"goto_{key}_{r['symbol']}"):
                st.markdown(stock_rows([r], compact), unsafe_allow_html=True)
                if st.button(f"Open {r['symbol']}", key=f"gobtn_{key}_{r['symbol']}"):
                    open_stock(r["symbol"])
                    st.rerun(scope="app")


# ---------- screens ----------
def screen_des():
    i = c_info(sym)
    left, right = st.columns([2.3, 1], gap="large")
    with left:
        if q:
            head = st.columns([5, 1.3])
            with head[0]:
                live_header(q, company)
            watch_button(head[1])
        chart_box = st.container()  # filled after the range tabs below it are read
        rng = st.segmented_control("Range", list(RANGES), default="1D", key="des_range",
                                   label_visibility="collapsed") or "1D"
        with chart_box:
            df = c_history(sym, *RANGES[rng])
            if df.empty:
                st.markdown("<div class='loading'>No price history for this range yet.</div>", unsafe_allow_html=True)
            elif rng == "1D":
                line_chart(df.Close, 330, RED if (q or {}).get("change", 0) < 0 else GREEN, (q or {}).get("prev_close"), rng)
            else:
                line_chart(df.Close, 330, GREEN if df.Close.iloc[-1] >= df.Close.iloc[0] else RED, None, rng)
        research_links(i)
        if not (i.get("longName") or i.get("shortName")):
            st.caption("No company profile available for this symbol.")
            return
        about_section(i)
        key_stats(i)
        st.subheader("News")
        news_with_sentiment(c_news(sym)[:6])
        st.subheader("Analyst ratings")
        analyst_block(i)
    with right:
        with st.container(border=True):
            order_ticket()
        st.write("")
        st.markdown("<div class='box-title'>Watchlist</div>", unsafe_allow_html=True)
        watchlist_panel(tuple(watchlists.symbols()), compact=True)


def research_links(i: dict):
    """One-click links to the same stock on popular research sites (opens a new tab)."""
    s, etf = sym.upper(), (i.get("quoteType") == "ETF")
    sites = [
        ("Stock Analysis", f"https://stockanalysis.com/{'etf' if etf else 'stocks'}/{s.lower().replace('-', '.')}/"),
        ("Seeking Alpha", f"https://seekingalpha.com/symbol/{s}"),
        ("Google Finance", f"https://www.google.com/finance?q={s}"),
        ("Finviz", f"https://finviz.com/quote.ashx?t={s}"),
        ("TradingView", f"https://www.tradingview.com/symbols/{s.replace('-', '.')}/"),
        ("Koyfin", "https://app.koyfin.com/"),
        ("TIKR", "https://app.tikr.com/"),
    ]
    st.markdown("<div class='muted' style='font-size:.78rem;margin:.2rem 0 .3rem'>Research elsewhere</div>"
                + "".join(f"<a class='chip' href='{u}' target='_blank' rel='noopener' style='background:#1e2124;"
                          f"color:#fff;text-decoration:none'>{n} ↗</a>" for n, u in sites),
                unsafe_allow_html=True)
    st.caption("Koyfin and TIKR open their home page; search for the ticker there.")


def watch_button(where):
    """+ Watchlist / ✓ Watching toggle for the current stock on the active list."""
    listed = sym in watchlists.symbols()
    label = f"✓ On {watchlists.active()}" if listed else "+ Watchlist"
    if where.button(label, key="watch_toggle", width="stretch",
                    help="Remove from this watchlist" if listed else f"Add {sym} to {watchlists.active()}"):
        (watchlists.remove if listed else watchlists.add)(sym)
        st.rerun()


def news_with_sentiment(items: list[dict]):
    """News list with a Positive / Negative / Neutral tag on each headline, scored by the AI.

    Scoring runs in the background (it takes a few seconds), so the headlines show straight away
    and the tags appear once they're ready.
    """
    scores = []
    if items and ai.provider():
        titles = [n["title"] for n in items]
        key = "sent-" + hashlib.md5((sym + "|".join(titles)).encode()).hexdigest()[:12]
        job = lambda: sentiment.score(sym, titles)
        scores, _, running, err = cache.get(key, job, 6 * 3600)
        scores = scores or []
        if scores and not ss.setdefault("sent_saved", set()) >= {key}:  # archive once per set
            collector.record_sentiment(sym, titles, scores)
            ss.sent_saved.add(key)
        if not scores and running:
            st.caption("Rating headlines…")
            wait_for(key, job, 6 * 3600)
        elif not scores and err:
            st.caption(f"Headline sentiment unavailable: {err}")
    rated = [v for v in scores if v is not None]
    if rated:
        avg = sum(rated) / len(rated)
        word, _ = sentiment.label(avg)
        color = GREEN if word == "Positive" else RED if word == "Negative" else MUTED
        st.markdown(f"<div class='muted' style='margin:-.2rem 0 .3rem'>Headline mood: <b style='color:{color}'>{word}"
                    f"</b> ({avg:+.2f} on a −1 to +1 scale, {len(rated)} headlines, rated by {ai.provider()})</div>",
                    unsafe_allow_html=True)
    news_list(items, scores)


def about_section(i: dict):
    st.subheader("About")
    text = htmllib.escape(i.get("longBusinessSummary") or "")
    if text:
        cut = text.find(". ", 320)
        head, rest = (text[: cut + 1], text[cut + 1:]) if cut > 0 else (text, "")
        more = f"<details><summary>Show more</summary>{rest}</details>" if rest else ""
        st.markdown(f"<div class='about'>{head}{more}</div>", unsafe_allow_html=True)
    hq = ", ".join(x for x in (i.get("city"), i.get("state") or i.get("country")) if x)
    site = i.get("website")
    facts = [("Sector", i.get("sector") or "-"), ("Industry", i.get("industry") or "-"),
             ("Employees", num(i.get("fullTimeEmployees"), "{:,.0f}")), ("Headquarters", hq or "-")]
    if site:
        facts.append(("Website", f"<a href='{site}' target='_blank' style='color:var(--acc)'>{site.split('//')[-1]}</a>"))
    stats_grid(facts)


def stats_grid(pairs: list[tuple[str, str]]):
    st.markdown("<div class='stats'>" + "".join(f"<div><span>{k}</span><b>{v}</b></div>" for k, v in pairs)
                + "</div>", unsafe_allow_html=True)


def key_stats(i: dict):
    st.subheader("Key statistics")
    qq = q or {}
    pct = lambda v: num(v, "{:.1%}")
    stats_grid([
        ("Market cap", big(i.get("marketCap"))), ("Price-earnings ratio", num(i.get("trailingPE"))),
        ("Forward P/E", num(i.get("forwardPE"))), ("Dividend yield", num(i.get("dividendYield"), "{:.2f}%")),
        ("Average volume", big(i.get("averageVolume"))), ("Volume", big(qq.get("volume"))),
        ("High today", usd(qq.get("day_high"))), ("Low today", usd(qq.get("day_low"))),
        ("Open price", usd(i.get("open"))), ("Previous close", usd(qq.get("prev_close"))),
        ("52 week high", usd(qq.get("year_high"))), ("52 week low", usd(qq.get("year_low"))),
        ("Revenue (ttm)", big(i.get("totalRevenue"))), ("Revenue growth", pct(i.get("revenueGrowth"))),
        ("Gross margin", pct(i.get("grossMargins"))), ("Profit margin", pct(i.get("profitMargins"))),
        ("Return on equity", pct(i.get("returnOnEquity"))), ("Free cash flow", big(i.get("freeCashflow"))),
        ("Debt / equity", num(i.get("debtToEquity"))), ("Beta", num(i.get("beta"))),
        ("Price / sales", num(i.get("priceToSalesTrailing12Months"))), ("Price / book", num(i.get("priceToBook"))),
        ("EV / EBITDA", num(i.get("enterpriseToEbitda"))), ("Short % of float", pct(i.get("shortPercentOfFloat"))),
    ])


def analyst_block(i: dict):
    recs = c_recs(sym)
    if recs.empty or "period" not in recs:
        st.caption("No analyst ratings for this symbol.")
        return
    now = recs[recs["period"] == "0m"]
    r = (now if not now.empty else recs).iloc[0]
    counts = {"Buy": r.get("strongBuy", 0) + r.get("buy", 0), "Hold": r.get("hold", 0),
              "Sell": r.get("sell", 0) + r.get("strongSell", 0)}
    total = sum(counts.values())
    if not total:
        st.caption("No analyst ratings for this symbol.")
        return
    share = {k: v / total * 100 for k, v in counts.items()}
    lead = max(share, key=share.get)
    lead_color = {"Buy": GREEN, "Hold": "#d9d9d9", "Sell": RED}[lead]
    bars = "".join(
        f"<div class='bar'><span>{k}</span><div class='track'><div class='fill' style='width:{v:.0f}%;"
        f"background:{ {'Buy': GREEN, 'Hold': '#8c8c8c', 'Sell': RED}[k]}'></div></div>"
        f"<span class='r'>{v:.0f}%</span></div>" for k, v in share.items())
    target = ""
    if i.get("targetMeanPrice"):
        target = (f"<div class='muted' style='margin-top:1rem'>Average price target <b style='color:#fff'>"
                  f"{usd(i['targetMeanPrice'])}</b> · low {usd(i.get('targetLowPrice'))} · "
                  f"high {usd(i.get('targetHighPrice'))}</div>")
    st.markdown(
        f"<div class='anr'><div class='big' style='background:{lead_color}22;color:{lead_color}'>"
        f"<b>{share[lead]:.0f}%</b><small>{lead} · {total} ratings</small></div><div>{bars}</div></div>{target}",
        unsafe_allow_html=True)


def ago(published) -> str:
    try:
        mins = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(published, tz="UTC")).total_seconds() / 60
    except Exception:
        return str(published or "")
    return f"{max(int(mins), 1)}m" if mins < 60 else f"{int(mins / 60)}h" if mins < 1440 else f"{int(mins / 1440)}d"


def news_list(items: list[dict], scores: list | None = None):
    if not items:
        st.caption("No recent news for this symbol.")
        return
    html = []
    for i, n in enumerate(items):
        img = f"<img src='{n['thumb']}' loading='lazy'>" if n.get("thumb") else ""
        tag = ""
        if scores and i < len(scores) and scores[i] is not None:
            word, state = sentiment.label(scores[i])
            color = {"positive": GREEN, "negative": RED}.get(state, MUTED)
            tag = f" <span class='chip' style='background:{color}22;color:{color}'>{word}</span>"
        html.append(
            f"<a class='news' href='{n['url']}' target='_blank'><div>"
            f"<div class='src'>{htmllib.escape(n['publisher'] or '')} <span>{ago(n['published'])}</span>{tag}</div>"
            f"<div class='t'>{htmllib.escape(n['title'])}</div></div>{img}</a>")
    st.markdown("<div>" + "".join(html) + "</div>", unsafe_allow_html=True)


def watch_data(symbols: tuple) -> list[dict]:
    """Rows for stock_rows(): cached quotes, live last price and today's sparkline."""
    df = c_quotes(symbols)
    live = data.live_prices(list(symbols))
    sparks = c_sparks(symbols)
    rows = []
    for r in df.to_dict("records"):
        s = r["symbol"]
        last = live.get(s, {}).get("last", r.get("last"))
        prev = r.get("prev_close")
        rows.append({
            "symbol": s, "last": last, "prev": prev,
            "change_pct": (last / prev - 1) * 100 if last and prev else r.get("change_pct"),
            "spark": (sparks.get(s) or []) + ([last] if last and sparks.get(s) else []),
            "volume": r.get("volume"), "market_cap": r.get("market_cap"),
            "year_low": r.get("year_low"), "year_high": r.get("year_high"),
        })
    return rows


@st.fragment(run_every=5)
@timed("watchlist")
def watchlist_panel(symbols: tuple, compact: bool = False):
    rows = watch_data(symbols)
    if not compact:
        for r in rows:
            r["extra"] = (f"<span class='muted'>Vol</span> {big(r['volume'])}<small>Mkt cap {big(r['market_cap'])}</small>")
    nav_list(rows, "wlc" if compact else "wl", compact=compact)


def order_ticket(symbol_input: bool = False):
    """Robinhood-style order card. Every order goes through Review -> Submit before it is sent."""
    if not brokers:
        broker_notices()
        return
    names = list(brokers)
    bname = st.selectbox("Account", names) if len(names) > 1 else names[0]
    tsym = st.text_input("Symbol", value=ss.ticket_symbol or sym).strip().upper() if symbol_input else sym
    is_opt = bool(tsym) and OrderRequest(tsym, "buy", 1).is_option
    ref = data.with_live(q)["last"] if q and tsym == sym else None  # reference price for defaults and the estimate
    side = st.segmented_control("Side", ["buy", "sell"], default="buy", key="ticket_side", label_visibility="collapsed",
                                format_func=lambda s: f"{s.title()} {'' if is_opt else tsym}") or "buy"
    kinds = {"market": "Market order", "limit": "Limit order", "stop": "Stop order"}
    otype = st.selectbox("Order type", ["limit", "market"] if is_opt else ["market", "limit", "stop"],
                         format_func=kinds.get)
    for k, v in (("ticket_qty", 1.0), ("ticket_bracket", False), ("ticket_sl", 0.0), ("ticket_tp", 0.0)):
        ss.setdefault(k, v)
    qty = st.number_input("Contracts (100 shares each)" if is_opt else "Shares", min_value=0.0, step=1.0,
                          key="ticket_qty")
    px = None
    if otype != "market":
        px = st.number_input(f"{otype.title()} price", min_value=0.0, value=float(round(ref or 0, 2)), step=0.01)
    if not is_opt and (px or ref):
        size_by_risk(bname, side, px or ref)
    tp = sl = None
    with st.expander("Advanced"):
        tif = st.selectbox("Time in force", ["day"] if is_opt else ["day", "gtc"],
                           format_func={"day": "Good for day", "gtc": "Good till canceled"}.get)
        if not is_opt and st.toggle("Attach exits (bracket)", key="ticket_bracket",
                                    help="Adds a take-profit and/or stop-loss order that activates once this order "
                                         "fills. Alpaca only."):
            c = st.columns(2)
            tp = c[0].number_input("Take profit at", min_value=0.0, step=0.01, help="0 = none", key="ticket_tp") or None
            sl = c[1].number_input("Stop loss at", min_value=0.0, step=0.01, help="0 = none", key="ticket_sl") or None
    with st.expander("Journal note"):
        note = st.text_area("Why this trade?", key="ticket_note", height=80,
                            placeholder="What's the setup, what would make you exit, what's the target?")
        tags = st.multiselect("Tags", journal.TAGS, key="ticket_tags", placeholder="Optional")
    unit = px or ref
    est = qty * unit * (100 if is_opt else 1) if unit else None
    st.markdown(
        (f"<div class='line'><span>Market price</span><b style='color:var(--acc)'>{usd(ref)}</b></div>" if ref else "")
        + f"<div class='line total'><span>Estimated {'cost' if side == 'buy' else 'credit'}</span>"
        f"<span>{usd(est) if est else '-'}</span></div>", unsafe_allow_html=True)
    if st.button("Review order", type="primary", width="stretch",
                 disabled=not tsym or qty <= 0 or (otype != "market" and not px)):
        ss.pending_order = (bname, OrderRequest(tsym, side, qty, otype, px if otype == "limit" else None,
                                                px if otype == "stop" else None, tif, tp, sl))
    if ss.pending_order:
        pb, req = ss.pending_order
        unit_px = req.limit_price or req.stop_price or (ref if req.symbol == tsym else None)
        value = usd(req.qty * unit_px * (100 if req.is_option else 1)) if unit_px else "unknown (market order)"
        with st.container(border=True):
            st.markdown(f"**Confirm {config.MODE_LABEL.lower()} order via {pb}**  \n{req.describe()}  \n"
                        f"Estimated value: {value}")
            if config.LIVE:
                st.error("This uses real money.")
            c = st.columns(2)
            if c[0].button("Submit order", type="primary", width="stretch"):
                try:
                    oid = brokers[pb].submit_order(req)
                    st.success(f"Order sent. Id {oid}")
                    c_account.clear(); c_positions.clear()  # show the new balance straight away
                    try:
                        journal.add(pb, oid, req, unit_px, note, tags)
                    except Exception as e:
                        st.warning(f"Order sent, but the journal entry wasn't saved: {e}")
                except Exception as e:
                    st.error(f"Order rejected: {e}")
                ss.pending_order = None
            if c[1].button("Edit", width="stretch"):
                ss.pending_order = None
                st.rerun()
    try:
        bp = c_account(bname)["buying_power"]
        st.markdown(f"<div class='muted' style='text-align:center;margin-top:.6rem'>{usd(bp)} buying power available"
                    "</div>", unsafe_allow_html=True)
    except Exception:
        pass


def use_size(shares: int, stop: float):
    ss.ticket_qty = float(shares)
    ss.ticket_bracket = True
    ss.ticket_sl = round(stop, 2)


def size_by_risk(bname: str, side: str, entry: float):
    """Shares to buy so that hitting the stop loses no more than the amount you choose."""
    plan = profile.load()
    with st.expander("Size by risk"):
        try:
            equity = c_account(bname)["equity"] or 0
        except Exception:
            equity = 0
        c = st.columns(2)
        mode = c[0].segmented_control("Risk", ["% of account", "$ amount"], default="% of account", key="size_mode",
                                      label_visibility="collapsed") or "% of account"
        if mode == "% of account":
            pct = c[1].number_input("Risk %", min_value=0.1, max_value=100.0, step=0.25, key="size_pct",
                                    value=float(plan["risk_per_trade"] or 1.0))
            risk = equity * pct / 100
        else:
            risk = c[1].number_input("Risk $", min_value=1.0, step=10.0, key="size_usd", value=100.0)
        default_stop = round(entry * (0.95 if side == "buy" else 1.05), 2)
        stop = st.number_input("Stop loss price", min_value=0.01, step=0.01, key="size_stop", value=default_stop)
        per_share = (entry - stop) if side == "buy" else (stop - entry)
        if per_share <= 0:
            st.caption("For a buy the stop has to be below the entry price; for a short sale, above it.")
            return
        shares = int(risk // per_share)
        value = shares * entry
        st.markdown(
            f"<div class='line'><span>Risk if stopped out</span><b>{usd(shares * per_share)}</b></div>"
            f"<div class='line'><span>Loss per share</span><span>{usd(per_share)} ({per_share / entry * 100:.1f}%)"
            f"</span></div><div class='line total'><span>Shares</span><span>{shares:,}</span></div>"
            f"<div class='line'><span>Position size</span><span>{usd(value)}"
            + (f" ({value / equity * 100:.1f}% of account)" if equity else "") + "</span></div>",
            unsafe_allow_html=True)
        cap = plan["max_position"]
        if equity and cap and value > equity * cap / 100:
            st.warning(f"That's more than your {cap:g}% max position size (My trading plan).")
        if shares < 1:
            st.caption("The risk amount is smaller than the loss on a single share. Widen the risk or tighten the stop.")
            return
        st.button(f"Use {shares:,} shares with a stop at {usd(stop).replace('&#36;', '$')}", width="stretch",
                  on_click=use_size, args=(shares, stop))


INDICATORS = ["SMA 20", "SMA 50", "SMA 200", "Bollinger bands", "RSI", "MACD"]


def screen_gp():
    c = st.columns([5, 4, 2], vertical_alignment="center")
    rng = c[0].segmented_control("Range", list(RANGES), default="1Y", label_visibility="collapsed") or "1Y"
    chosen = c[1].multiselect("Indicators", INDICATORS, default=["SMA 50", "SMA 200"],
                              label_visibility="collapsed", placeholder="Add indicators")
    compare = c[2].toggle("vs S&P 500", help="Show both as % change over the range (SPY tracks the S&P 500)")
    period, interval = RANGES[rng]
    df = c_history(sym, period, interval)
    if df.empty:
        st.info("No price history for this range.")
        return
    if compare:
        compare_chart(df, rng)
        return
    # Daily charts: compute indicators on 5 years so long averages are filled from the first bar shown.
    full = c_history(sym, "5y", "1d") if interval == "1d" and rng != "MAX" else df
    close = full.Close
    clip = lambda s: s.reindex(df.index)

    panels = [p for p in ("RSI", "MACD") if p in chosen]
    heights = [0.62, 0.14] + [0.12] * len(panels)
    fig = make_subplots(rows=2 + len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[h / sum(heights) for h in heights])
    fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name=sym,
                                 increasing_line_color=GREEN, decreasing_line_color=RED), row=1, col=1)
    for name, colr in zip(("SMA 20", "SMA 50", "SMA 200"), ("#4da3ff", AMBER, "#c77dff")):
        if name in chosen:
            fig.add_trace(go.Scatter(x=df.index, y=clip(ind.sma(close, int(name.split()[1]))), name=name,
                                     line=dict(color=colr, width=1.2)), row=1, col=1)
    if "Bollinger bands" in chosen:
        lower, mid, upper = (clip(s) for s in ind.bollinger(close))
        band = dict(color="#8c8c8c", width=1)
        fig.add_trace(go.Scatter(x=df.index, y=upper, name="Bollinger upper", line=band), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=lower, name="Bollinger lower", line=band, fill="tonexty",
                                 fillcolor="rgba(140,140,140,0.08)"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=mid, name="Bollinger mid", line=dict(color="#8c8c8c", width=1,
                                                                                 dash="dot")), row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df.Volume, name="Volume", marker_color="#3b4352"), row=2, col=1)
    row = 3
    if "RSI" in chosen:
        fig.add_trace(go.Scatter(x=df.index, y=clip(ind.rsi(close)), name="RSI 14", line=dict(color=AMBER, width=1.2)),
                      row=row, col=1)
        for level in (30, 70):
            fig.add_hline(y=level, line=dict(color="#4a4d52", width=1, dash="dot"), row=row, col=1)
        fig.update_yaxes(range=[0, 100], row=row, col=1, title_text="RSI")
        row += 1
    if "MACD" in chosen:
        line, sig, hist = (clip(s) for s in ind.macd(close))
        fig.add_trace(go.Bar(x=df.index, y=hist, name="MACD histogram",
                             marker_color=[GREEN if v >= 0 else RED for v in hist.fillna(0)]), row=row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=line, name="MACD", line=dict(color="#4da3ff", width=1.2)), row=row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=sig, name="Signal", line=dict(color=AMBER, width=1.2)), row=row, col=1)
        fig.update_yaxes(title_text="MACD", row=row, col=1)
    style_fig(fig, 640 + 150 * len(panels), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.04),
              hovermode="x unified")
    skip_closed_hours(fig, rng)
    st.plotly_chart(fig, width="stretch")
    st.caption("RSI above 70 is often read as overbought and below 30 as oversold. MACD crossing above its signal "
               "line is a common momentum signal. Bollinger bands mark two standard deviations around a 20-day average.")


def compare_chart(df: pd.DataFrame, rng: str):
    """The stock against SPY, both as % change from the start of the range."""
    spy = c_history("SPY", *RANGES[rng])
    fig = go.Figure()
    lines = [(sym, df.Close, ACC)] + ([("S&P 500 (SPY)", spy.Close, "#8c8c8c")] if sym != "SPY" and not spy.empty else [])
    for name, s, colr in lines:
        pct = (s / s.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(x=s.index, y=pct, name=name, line=dict(color=colr, width=2),
                                 hovertemplate=f"{name} %{{y:+.2f}}%<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#4a4d52", width=1, dash="dot"))
    style_fig(fig, 560, hovermode="x unified", legend=dict(orientation="h", y=1.06), yaxis_ticksuffix="%")
    skip_closed_hours(fig, rng)
    st.plotly_chart(fig, width="stretch")
    if len(lines) == 2:
        a, b = ((s.iloc[-1] / s.iloc[0] - 1) * 100 for _, s, _ in lines)
        verdict = "ahead of" if a > b else "behind"
        st.markdown(f"<div class='muted'>{sym} <b style='color:#fff'>{a:+.2f}%</b> vs S&P 500 <b style='color:#fff'>"
                    f"{b:+.2f}%</b> over this range: {abs(a - b):.2f} points {verdict} the market.</div>",
                    unsafe_allow_html=True)


def screen_fa():
    c = st.columns([4, 2, 6])
    stmt = c[0].segmented_control("Statement", ["income", "balance", "cashflow"], default="income",
                                  format_func=str.title, label_visibility="collapsed") or "income"
    quarterly = c[1].toggle("Quarterly")
    df = c_fin(sym, stmt, quarterly)
    if df.empty:
        st.info("No financial statements available for this symbol.")
        return
    source = df.attrs.get("source", "Yahoo Finance")
    # Trend of the statement's headline lines, oldest to newest
    headline = {"income": ["Revenue", "Net income"], "balance": ["Total assets", "Total liabilities"],
                "cashflow": ["Operating cash flow", "Free cash flow"]}[stmt]
    shown = [r for r in headline if r in df.index]
    if shown:
        fig = go.Figure()
        for row, colr in zip(shown, (ORANGE, "#8c8c8c")):
            s = pd.to_numeric(df.loc[row], errors="coerce").iloc[::-1]
            fig.add_trace(go.Bar(x=list(s.index), y=s.values, name=row, marker_color=colr,
                                 hovertemplate=f"{row} %{{x}}: $%{{y:,.0f}}<extra></extra>"))
        style_fig(fig, 260, barmode="group", legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)
    st.dataframe(df.map(big), height=520 if shown else 680, width="stretch")
    st.caption(f"Source: {source}. Columns are the end date of each "
               f"{'quarter' if quarterly else 'fiscal year'}, newest first."
               + (" Fourth quarters are worked out as the full year minus the first three." if quarterly and
                  source == "SEC filings" else ""))


def screen_news():
    items = c_news(sym)
    news_with_sentiment(items[:15])
    if not ai.provider():
        st.caption("Sign in to Claude or add a Gemini key to tag each headline as positive or negative.")


def screen_anr():
    i = c_info(sym)
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.subheader("Analyst ratings")
        analyst_block(i)
    with right:
        st.subheader("How ratings changed")
        recs = c_recs(sym)
        if recs.empty:
            st.caption("No analyst rating history for this symbol.")
            return
        labels = {"strongBuy": "Strong buy", "buy": "Buy", "hold": "Hold", "sell": "Sell", "strongSell": "Strong sell"}
        colors = ("#00c805", "#5be36b", "#5c5f63", "#ff8a50", RED)
        fig = go.Figure()
        for (col, name), colr in zip(labels.items(), colors):
            if col in recs.columns:
                fig.add_trace(go.Bar(x=recs["period"], y=recs[col], name=name, marker_color=colr))
        style_fig(fig, 320, barmode="stack", xaxis_title="Months ago (0m = this month)",
                  legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)


def needs_key(name: str, value: str, where: str) -> bool:
    if not value:
        st.info(f"Add {name} to .env to use this screen (free key from {where}), then restart the app.")
    return not value


def screen_val():
    if needs_key("FMP_API_KEY", config.FMP_API_KEY, "financialmodelingprep.com"):
        return
    try:
        dcf = c_fmp("discounted-cash-flow", sym)
        scores = c_fmp("financial-scores", sym)
        rating = c_fmp("ratings-snapshot", sym)
        target = c_fmp("price-target-consensus", sym)
    except Exception as e:
        st.error(f"Financial Modeling Prep: {sources.clean_error(e)}")
        return
    last = (q or {}).get("last")
    fair = dcf.get("dcf")
    m = st.columns(6)
    m[0].metric("DCF fair value", num(fair), None if not (fair and last) else f"{(fair / last - 1) * 100:+.1f}% vs price")
    m[1].metric("Rating", rating.get("rating", "-"), help="FMP's composite grade from the sub-scores below")
    m[2].metric("Piotroski score", num(scores.get("piotroskiScore"), "{:.0f} / 9"), help="Financial strength, 0-9. 8-9 is strong.")
    m[3].metric("Altman Z-score", num(scores.get("altmanZScore")), help="Bankruptcy risk. Above 3 is safe, below 1.8 is distress.")
    tc = target.get("targetConsensus")
    m[4].metric("Analyst target", num(tc), None if not (tc and last) else f"{(tc / last - 1) * 100:+.1f}% vs price")
    m[5].metric("Target range", f"{num(target.get('targetLow'), '{:,.0f}')}-{num(target.get('targetHigh'), '{:,.0f}')}")
    st.caption("DCF is one model's estimate with its own assumptions; it often differs widely from the market price.")
    c = st.columns(3)
    tables = (("Rating sub-scores (1-5)", rating), ("Ratios (ttm)", c_fmp("ratios-ttm", sym)),
              ("Key metrics (ttm)", c_fmp("key-metrics-ttm", sym)))
    for col, (title, rec) in zip(c, tables):
        rows = [(k, v) for k, v in rec.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        col.caption(title)
        col.dataframe(pd.DataFrame(rows, columns=["Metric", "Value"]), hide_index=True, width="stretch", height=520,
                      column_config={"Value": st.column_config.NumberColumn(format="compact")})


def screen_ern():
    if needs_key("FINNHUB_API_KEY", config.FINNHUB_API_KEY, "finnhub.io"):
        return
    left, right = st.columns([2, 3])
    with left:
        st.subheader(f"{sym} vs estimates")
        try:
            s = c_surprises(sym)
        except Exception as e:
            s = pd.DataFrame()
            st.error(f"Finnhub: {sources.clean_error(e)}")
        if s.empty:
            st.caption("No earnings history for this symbol.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=s["period"], y=s["estimate"], mode="markers", name="Estimate",
                                     marker=dict(color="#888", size=11, symbol="circle-open")))
            fig.add_trace(go.Scatter(x=s["period"], y=s["actual"], mode="markers", name="Actual", marker=dict(
                size=11, color=[GREEN if (a or 0) >= (e or 0) else RED for a, e in zip(s["actual"], s["estimate"])])))
            style_fig(fig, 300, yaxis_title="EPS")
            st.plotly_chart(fig, width="stretch")
            st.dataframe(s[["period", "estimate", "actual", "surprisePercent"]], hide_index=True, width="stretch",
                         column_config={"surprisePercent": st.column_config.NumberColumn("surprise", format="%+.1f%%")})
    with right:
        st.subheader("Upcoming earnings")
        c = st.columns(2)
        days = c[0].segmented_control("Window", [7, 14, 30], default=14, format_func=lambda d: f"{d} days",
                                      label_visibility="collapsed") or 14
        only_est = c[1].toggle("Only with estimates", value=True, help="Hides small companies no analyst covers")
        try:
            cal = c_calendar(days)
        except Exception as e:
            st.error(f"Finnhub: {sources.clean_error(e)}")
            return
        if not cal.empty and only_est:
            cal = cal[cal["epsEstimate"].notna()]
        if cal.empty:
            st.caption("No earnings in this window.")
            return
        cal = cal.assign(hour=cal["hour"].map({"bmo": "before open", "amc": "after close", "dmh": "during hours"}))
        st.dataframe(cal[["date", "hour", "symbol", "epsEstimate", "revenueEstimate"]], hide_index=True, width="stretch",
                     height=600, column_config={
                         "epsEstimate": st.column_config.NumberColumn("EPS est.", format="%.2f"),
                         "revenueEstimate": st.column_config.NumberColumn("revenue est.", format="compact")})


def screen_sec():
    left, right = st.columns([3, 2])
    with left:
        st.subheader("SEC filings")
        try:
            f = c_filings(sym)
        except Exception as e:
            f = pd.DataFrame()
            st.error(f"SEC EDGAR: {sources.clean_error(e)}")
        if f.empty:
            st.caption("No SEC filings found. Only US-registered companies file with the SEC.")
        else:
            kinds = {"Reports (10-K, 10-Q)": ["10-K", "10-Q"], "Events (8-K)": ["8-K"], "Insider (Form 4)": ["4"],
                     "Proxy": ["DEF 14A"], "All": None}
            kind = st.segmented_control("Type", list(kinds), default="Reports (10-K, 10-Q)",
                                        label_visibility="collapsed") or "All"
            if kinds[kind]:
                f = f[f["form"].isin(kinds[kind])]
            st.dataframe(f, hide_index=True, width="stretch", height=600,
                         column_config={"url": st.column_config.LinkColumn("document", display_text="open")})
    with right:
        st.subheader("Insider transactions")
        if needs_key("FINNHUB_API_KEY", config.FINNHUB_API_KEY, "finnhub.io"):
            return
        try:
            ins = c_insiders(sym)
        except Exception as e:
            st.error(f"Finnhub: {sources.clean_error(e)}")
            return
        if ins.empty:
            st.caption("No insider transactions reported.")
            return
        if st.toggle("Open-market buys and sells only", value=True, help="Hides grants, option exercises and tax withholding"):
            ins = ins[ins["transactionCode"].isin(["P", "S"])]
        ins = ins.assign(type=ins["transactionCode"].map({"P": "BUY", "S": "SELL"}).fillna(ins["transactionCode"]),
                         value=ins["change"].abs() * ins["transactionPrice"])
        st.dataframe(ins[["transactionDate", "name", "type", "change", "transactionPrice", "value"]], hide_index=True,
                     width="stretch", height=560, column_config={
                         "transactionDate": "date", "change": st.column_config.NumberColumn("shares", format="localized"),
                         "transactionPrice": st.column_config.NumberColumn("price", format="%.2f"),
                         "value": st.column_config.NumberColumn(format="compact")})


def screen_eco():
    if needs_key("FRED_API_KEY", config.FRED_API_KEY, "fred.stlouisfed.org/docs/api/api_key.html"):
        return
    events, errors = c_predictions()
    fed = predictions.matching(events, "Fed & rates")[:2]
    if fed:
        st.markdown("<div class='box-title'>What markets expect</div>", unsafe_allow_html=True)
        for col, e in zip(st.columns(len(fed)), fed):
            col.markdown(pred_card(e, n=4), unsafe_allow_html=True)
    elif errors:
        st.caption("Prediction-market odds would show here, but Kalshi and Polymarket can't be reached from this "
                   "network (see Market → Predictions).")
    names = list(sources.FRED_SERIES)
    for row in (names[:5], names[5:]):
        for col, name in zip(st.columns(5), row):
            try:
                s = c_fred(sources.FRED_SERIES[name])
            except Exception as e:
                col.error(f"{name}: {sources.clean_error(e)}")
                continue
            prev = s.iloc[-2] if len(s) > 1 else s.iloc[-1]
            col.metric(name, f"{s.iloc[-1]:,.2f}", f"{s.iloc[-1] - prev:+.2f}", delta_color="off")
            col.caption(f"as of {s.index[-1]:%Y-%m-%d}")
            fig = go.Figure(go.Scatter(x=s.index, y=s.values, line=dict(color=AMBER, width=1.5)))
            style_fig(fig, 180, showlegend=False)
            col.plotly_chart(fig, width="stretch", key=f"eco_{name}")
    st.caption("Source: FRED, Federal Reserve Bank of St. Louis. Five years of history.")


def color_moves(df: pd.DataFrame, cols: list[str]):
    """Green for gains, red for losses in the given columns."""
    def tint(v):
        if pd.isna(v) or v == 0:
            return ""
        return f"color: {GREEN}" if v > 0 else f"color: {RED}"

    return df.style.map(tint, subset=[c for c in cols if c in df.columns])


def quote_table(df: pd.DataFrame):
    st.dataframe(
        color_moves(df, ["change", "change_pct", "chg_52w_pct"]), hide_index=True, width="stretch",
        height=min(720, 38 + 35 * len(df)),
        column_config={
            "symbol": "Symbol", "name": "Name", "analyst_rating": "Analyst rating",
            "day_high": st.column_config.NumberColumn("Day high", format="%.2f"),
            "day_low": st.column_config.NumberColumn("Day low", format="%.2f"),
            "year_high": st.column_config.NumberColumn("52w high", format="%.2f"),
            "year_low": st.column_config.NumberColumn("52w low", format="%.2f"),
            "eps": st.column_config.NumberColumn("EPS", format="%.2f"),
            "change_pct": st.column_config.NumberColumn("Change %", format="%+.2f%%"),
            "chg_52w_pct": st.column_config.NumberColumn("52w %", format="%+.1f%%"),
            "last": st.column_config.NumberColumn("Last", format="%.2f"),
            "change": st.column_config.NumberColumn("Change", format="%+.2f"),
            "volume": st.column_config.NumberColumn("Volume", format="compact"),
            "market_cap": st.column_config.NumberColumn("Market cap", format="compact"),
            "pe": st.column_config.NumberColumn("P/E", format="%.1f"),
            "fwd_pe": st.column_config.NumberColumn("Fwd P/E", format="%.1f"),
        },
    )


def screen_mon():
    left, right = st.columns([2.3, 1], gap="large")
    with left:
        st.markdown("<div class='tk-name'>Watchlists</div>", unsafe_allow_html=True)
        names, current = watchlists.names(), watchlists.active()
        if len(names) > 1:
            pick = st.segmented_control("List", names, default=current, key=f"wl_pick_{current}",
                                        label_visibility="collapsed")
            if pick and pick != current:
                watchlists.set_active(pick)
                st.rerun()
        c = st.columns([3, 1], vertical_alignment="bottom")
        new = c[0].text_input("Add a stock", placeholder="Add a stock, e.g. AMD", label_visibility="collapsed",
                              key=f"wl_add_{current}")
        if c[1].button("Add", width="stretch") and new.strip():
            for s in new.replace(",", " ").split():
                watchlists.add(s, current)
            st.rerun()
        symbols = watchlists.symbols(current)
        if symbols:
            watchlist_panel(tuple(symbols))
        else:
            st.caption("This list is empty. Add a stock above, or use \"+ Watchlist\" on any stock's page.")
        st.markdown(f"<div class='muted' style='margin-top:.8rem'>Click a stock to open it. {stream_badge()}</div>",
                    unsafe_allow_html=True)
        with st.expander("Edit lists"):
            if symbols:
                for s in symbols:
                    r = st.columns([4, 1, 1, 1], vertical_alignment="center")
                    r[0].write(s)
                    if r[1].button("↑", key=f"wl_up_{current}_{s}", help="Move up"):
                        watchlists.move(s, -1, current); st.rerun()
                    if r[2].button("↓", key=f"wl_dn_{current}_{s}", help="Move down"):
                        watchlists.move(s, 1, current); st.rerun()
                    if r[3].button("✕", key=f"wl_rm_{current}_{s}", help="Remove"):
                        watchlists.remove(s, current); st.rerun()
            st.divider()
            c = st.columns(2, vertical_alignment="bottom")
            make = c[0].text_input("New list name", placeholder="e.g. Earnings plays")
            if c[1].button("Create list", width="stretch") and make.strip():
                watchlists.create(make); st.rerun()
            c = st.columns(2, vertical_alignment="bottom")
            rename = c[0].text_input("Rename this list", value=current, key=f"wl_ren_{current}")
            if c[1].button("Rename", width="stretch") and rename.strip() != current:
                watchlists.rename(current, rename); st.rerun()
            if len(names) > 1 and st.button(f"Delete \"{current}\"", type="secondary"):
                watchlists.delete(current); st.rerun()
    with right:
        market_panel()


@st.fragment(run_every=15)
@timed("market panel")
def market_panel():
    """Index ETFs as a quick market read, Robinhood-card style."""
    rows = watch_data(("SPY", "QQQ", "DIA", "IWM"))
    names = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "DIA": "Dow Jones", "IWM": "Russell 2000"}
    for r in rows:
        r["sub"] = names.get(r["symbol"], "")
    with st.container(border=True):
        st.markdown("<div class='box-title'>Market today</div>", unsafe_allow_html=True)
        nav_list(rows, "mkt", compact=True)


def open_ticket(symbol: str):
    ss.ticket_symbol = symbol
    ss.pending_order = None
    ss.fn = "ORD"


def screen_omon():
    try:
        expiries = c_expiries(sym)
    except Exception:
        expiries = []
    if not expiries:
        st.info("No listed options for this symbol.")
        return
    c = st.columns([3, 2, 2, 5])
    # Default past the nearest expiries, which are often about to expire and thinly quoted.
    expiry = c[0].selectbox("Expiry", expiries, index=min(3, len(expiries) - 1), label_visibility="collapsed")
    side = c[1].segmented_control("Side", ["Calls", "Puts"], default="Calls", label_visibility="collapsed") or "Calls"
    near = c[2].toggle("Near the money", value=True, help="Only strikes within 15% of the share price")
    calls, puts = c_chain(sym, expiry)
    df = calls if side == "Calls" else puts
    last = (q or {}).get("last")
    if near and last:
        df = df[df["strike"].between(last * 0.85, last * 1.15)]
    picked = st.dataframe(
        df, hide_index=True, width="stretch", height=560, on_select="rerun", selection_mode="single-row",
        column_config={
            "contractSymbol": "contract", "lastPrice": st.column_config.NumberColumn("last", format="%.2f"),
            "bid": st.column_config.NumberColumn(format="%.2f"), "ask": st.column_config.NumberColumn(format="%.2f"),
            "openInterest": "open int.", "inTheMoney": "ITM",
            "delta": st.column_config.NumberColumn(format="%.2f"), "theta": st.column_config.NumberColumn(format="%.2f"),
            "impliedVolatility": st.column_config.NumberColumn("implied vol", format="percent"),
        },
    )
    rows = picked.selection.rows
    if rows:
        contract = df.iloc[rows[0]]
        st.button(f"Trade {contract['contractSymbol']} in the order ticket", type="primary",
                  on_click=open_ticket, args=(contract["contractSymbol"],))
    st.caption("Quotes and greeks from Alpaca when connected, otherwise Yahoo (may be delayed). Tick a row to select a contract. "
               "One contract controls 100 shares. Option orders go through Alpaca.")


def screen_alrt():
    c = st.columns([2, 2, 2, 2, 4], vertical_alignment="bottom")
    a_sym = c[0].text_input("Symbol", value=sym).strip().upper()
    direction = c[1].selectbox("When price is", ["above", "below"])
    price = c[2].number_input("Price", min_value=0.0, value=float(round((q or {}).get("last") or 0, 2)), step=0.5)
    if c[3].button("Add alert", width="stretch", disabled=not a_sym or price <= 0):
        alerts.add(a_sym, direction, price)
        st.rerun()
    items = alerts.load()
    if not items:
        st.caption("No alerts yet.")
    for i, a in enumerate(items):
        c = st.columns([6, 1])
        state = f"TRIGGERED at {a['triggered']:,.2f}" if a["triggered"] else "waiting"
        c[0].markdown(f"**{a['symbol']}** {a['direction']} {a['price']:,.2f} · "
                      f"<span style='color:{GREEN if a['triggered'] else '#888'}'>{state}</span>", unsafe_allow_html=True)
        if c[1].button("Remove", key=f"alrt_{i}"):
            alerts.save(items[:i] + items[i + 1:])
            st.rerun()
    st.caption("Alerts are checked every 15 seconds and pop up on screen. They only fire while this app is open in a browser.")


def screen_scr():
    name = st.segmented_control("Screen", list(data.SCREENS), default="Most active",
                                label_visibility="collapsed") or "Most active"
    try:
        df = c_screen(name)
    except Exception as e:
        st.error(f"Screen failed: {e}")
        return
    quote_table(df)
    st.caption("Screens are filters on public market data, not recommendations.")


SP500_MAX_AGE = 30 * 60  # refresh in the background when the saved scan is older than this


def screen_spx():
    df, age, refreshing, err = cache.get("sp500", data.sp500_scan, SP500_MAX_AGE)
    if df is None:
        if err and not refreshing:
            st.error(f"S&P 500 scan failed: {err}")
            if st.button("Try again"):
                cache.get("sp500", data.sp500_scan, 0)
                st.rerun()
            return
        st.markdown("<div class='loading'><b style='color:#fff;font-size:1.1rem'>Loading all 503 S&P 500 stocks"
                    "</b><br>The first scan takes about a minute. After that it opens instantly and refreshes "
                    "itself in the background every 30 minutes.</div>", unsafe_allow_html=True)
        wait_for_scan()
        return
    note = f"Data from {int(age // 60)} min ago" + (" · updating in the background" if refreshing else "")
    st.markdown(f"<div class='tk-name'>S&P 500</div><div class='muted'>{len(df)} stocks · {note}</div>",
                unsafe_allow_html=True)
    movers(df)
    sector_map(df)
    st.subheader("Scanner")
    views = {
        "Top today": ("chg_1d", False), "Worst today": ("chg_1d", True),
        "1M leaders": ("chg_1m", False), "3M leaders": ("chg_3m", False), "1Y leaders": ("chg_1y", False),
        "Near 52w high": ("from_high", False), "Furthest below high": ("from_high", True),
        "Oversold (RSI)": ("rsi", True), "Overbought (RSI)": ("rsi", False),
    }
    if "pe" in df.columns:
        views |= {"Lowest P/E": ("pe", True), "Lowest forward P/E": ("fwd_pe", True),
                  "Highest dividend": ("div_yield", False), "Largest": ("market_cap", False)}
    c = st.columns([7, 3, 2])
    view = c[0].segmented_control("View", list(views), default="Top today", label_visibility="collapsed") or "Top today"
    sectors = c[1].multiselect("Sector", sorted(df["sector"].unique()), placeholder="All sectors",
                               label_visibility="collapsed")
    uptrend = c[2].toggle("Uptrend only", help="Price above both its 50-day and 200-day average")
    if sectors:
        df = df[df["sector"].isin(sectors)]
    if uptrend:
        df = df[df["above_50d"] & df["above_200d"]]
    col, asc = views[view]
    pct = lambda label: st.column_config.NumberColumn(label, format="%+.1f%%")
    st.dataframe(
        color_moves(df.sort_values(col, ascending=asc, na_position="last"), ["chg_1d", "chg_1m", "chg_3m", "chg_1y"]),
        hide_index=True, width="stretch", height=640,
        column_config={
            "symbol": "Symbol", "name": "Name", "sector": "Sector", "analyst_rating": "Analyst rating",
            "market_cap": st.column_config.NumberColumn("Market cap", format="compact"),
            "pe": st.column_config.NumberColumn("P/E", format="%.1f"),
            "fwd_pe": st.column_config.NumberColumn("Fwd P/E", format="%.1f"),
            "pb": st.column_config.NumberColumn("P/B", format="%.1f"),
            "div_yield": st.column_config.NumberColumn("Div %", format="%.2f"),
            "last": st.column_config.NumberColumn("Last", format="%.2f"),
            "chg_1d": pct("1D"), "chg_1m": pct("1M"), "chg_3m": pct("3M"), "chg_1y": pct("1Y"),
            "from_high": pct("vs 52w high"),
            "rsi": st.column_config.NumberColumn("RSI 14", format="%.0f"),
            "above_50d": "> 50d avg", "above_200d": "> 200d avg",
        },
    )
    st.caption("Daily-close prices; the 1D column is as of the last scan, not live. A ranking, not a recommendation.")


@st.fragment(run_every=3)
def wait_for_scan():
    """Re-runs the page once the first background scan has finished."""
    if cache.get("sp500", data.sp500_scan, SP500_MAX_AGE)[0] is not None:
        st.rerun()


def movers(df: pd.DataFrame):
    st.subheader("Daily movers")

    def cards(rows: pd.DataFrame, key: str):
        for col, r in zip(st.columns(5), rows.itertuples()):
            color = RED if r.chg_1d < 0 else GREEN
            with col, st.container(key=f"goto_{key}_{r.symbol}"):
                st.markdown(f"<div class='card'><b>{r.symbol}</b><div class='n'>{htmllib.escape(r.name)}</div>"
                            f"<div class='p'>{usd(r.last)}</div><span class='pill' style='background:{color};"
                            f"margin-top:.4rem'>{r.chg_1d:+.2f}%</span></div>", unsafe_allow_html=True)
                if st.button(f"Open {r.symbol}", key=f"gobtn_{key}_{r.symbol}"):
                    open_stock(r.symbol)
                    st.rerun()

    ranked = df.dropna(subset=["chg_1d"]).sort_values("chg_1d")
    st.markdown("<div class='muted' style='margin-bottom:.5rem'>Biggest gains</div>", unsafe_allow_html=True)
    cards(ranked.tail(5)[::-1], "up")
    st.markdown("<div class='muted' style='margin:.6rem 0 .5rem'>Biggest drops</div>", unsafe_allow_html=True)
    cards(ranked.head(5), "down")


def sector_map(df: pd.DataFrame):
    st.subheader("Market map")
    d = df.dropna(subset=["chg_1d"]).copy()
    d["size"] = d["market_cap"].fillna(d["market_cap"].median()) if "market_cap" in d else 1
    fig = go.Figure(go.Treemap(
        ids=list(d["sector"].unique()) + list(d["symbol"]),
        labels=list(d["sector"].unique()) + list(d["symbol"]),
        parents=[""] * d["sector"].nunique() + list(d["sector"]),
        values=[0] * d["sector"].nunique() + list(d["size"]),
        branchvalues="remainder",
        marker=dict(colors=[0] * d["sector"].nunique() + list(d["chg_1d"]), cmin=-3, cmax=3, cmid=0,
                    colorscale=[[0, RED], [0.5, "#1e2124"], [1, GREEN]], line=dict(color="#000", width=1)),
        customdata=[""] * d["sector"].nunique() + [f"{v:+.2f}%" for v in d["chg_1d"]],
        texttemplate="<b>%{label}</b><br>%{customdata}", hovertemplate="%{label} %{customdata}<extra></extra>",
        tiling=dict(pad=1), pathbar=dict(visible=False), textfont=dict(color="#fff"),
    ))
    style_fig(fig, 520, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)
    st.caption("Box size is market value; colour is today's move (full green at +3% or more, full red at -3%). "
               "Click a sector to zoom in, click again to zoom out.")


# ---------- backtest ----------
def screen_bt():
    c = st.columns([3, 2, 2], vertical_alignment="bottom")
    strat = c[0].selectbox("Rule", list(backtest.STRATEGIES))
    period = c[1].segmented_control("Period", ["1y", "2y", "5y", "10y", "max"], default="5y", key="bt_period",
                                    format_func=lambda p: "Max" if p == "max" else p) or "5y"
    capital = c[2].number_input("Starting money ($)", min_value=100.0, value=10_000.0, step=1000.0)
    desc, params = backtest.STRATEGIES[strat]
    p = {}
    for col, (k, (label, default, lo, hi)) in zip(st.columns(len(params)), params.items()):
        p[k] = col.number_input(label, min_value=lo, max_value=hi, value=default, step=1, key=f"bt_{strat}_{k}")
    if strat == "RSI dip" and p["buy_below"] >= p["sell_above"]:
        st.warning("'Buy below' has to be lower than 'Sell above'.")
        return
    if strat == "Moving-average crossover" and p["fast"] >= p["slow"]:
        st.warning("The fast average needs fewer days than the slow one.")
        return
    df = c_history(sym, period, "1d")
    if len(df) < 60:
        st.info("Not enough price history for this symbol and period.")
        return
    r = backtest.run(df, strat, p, capital)
    s, b = r.stats, r.stats["benchmark"]
    st.markdown(f"<div class='muted' style='margin:.4rem 0 1rem'>{sym}: {desc.format(**p)} Signals are read at the "
                "close and traded at the next day's open.</div>", unsafe_allow_html=True)
    m = st.columns(6)
    m[0].metric("Final value", usd(s["final"]).replace("&#36;", "$"),
                f"{s['total_return'] - b['total_return']:+.1f} pts vs buy & hold")
    m[1].metric("Total return", f"{s['total_return']:+.1f}%", f"buy & hold {b['total_return']:+.1f}%", delta_color="off")
    m[2].metric("Yearly return", f"{s['cagr']:+.1f}%", f"buy & hold {b['cagr']:+.1f}%", delta_color="off")
    m[3].metric("Worst drop", f"{s['max_drawdown']:.1f}%", f"buy & hold {b['max_drawdown']:.1f}%", delta_color="off")
    m[4].metric("Trades", s["trades"], f"{num(s['win_rate'], '{:.0f}%')} winners" if s["win_rate"] is not None else None,
                delta_color="off")
    m[5].metric("Time invested", f"{s['exposure']:.0f}%", f"Sharpe {s['sharpe']:.2f}", delta_color="off")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=r.equity.index, y=r.equity, name="This rule", line=dict(color=ACC, width=2)))
    fig.add_trace(go.Scatter(x=r.benchmark.index, y=r.benchmark, name=f"Buy & hold {sym}",
                             line=dict(color="#8c8c8c", width=1.5)))
    style_fig(fig, 340, hovermode="x unified", legend=dict(orientation="h", y=1.08), yaxis_tickprefix="$")
    st.subheader("Account value")
    st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)

    st.subheader("Trades on the price chart")
    fig = go.Figure(go.Scatter(x=df.index, y=df.Close, name=sym, line=dict(color="#d9d9d9", width=1.3)))
    if not r.trades.empty:
        fig.add_trace(go.Scatter(x=r.trades["entry_date"], y=r.trades["entry"], mode="markers", name="Buy",
                                 marker=dict(symbol="triangle-up", size=11, color=GREEN)))
        done = r.trades[~r.trades["open"]]
        fig.add_trace(go.Scatter(x=done["exit_date"], y=done["exit"], mode="markers", name="Sell",
                                 marker=dict(symbol="triangle-down", size=11, color=RED)))
    style_fig(fig, 320, hovermode="x unified", legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)
    if not r.trades.empty:
        t = r.trades.assign(entry_date=pd.to_datetime(r.trades["entry_date"]).dt.date,
                            exit_date=pd.to_datetime(r.trades["exit_date"]).dt.date,
                            status=r.trades["open"].map({True: "still open", False: "closed"})).drop(columns="open")
        st.dataframe(color_moves(t.iloc[::-1], ["return_pct"]), hide_index=True, width="stretch", height=300,
                     column_config={"entry_date": "Bought", "entry": st.column_config.NumberColumn("Buy price", format="%.2f"),
                                    "exit_date": "Sold", "exit": st.column_config.NumberColumn("Sell price", format="%.2f"),
                                    "return_pct": st.column_config.NumberColumn("Return", format="%+.2f%%"),
                                    "days": "Days held", "status": "Status"})
    st.caption("Past results don't predict future ones. No commissions, slippage, dividends or taxes are included, "
               "and a rule tuned to fit the past usually does worse going forward.")


# ---------- ideas ----------
def chip(label: str, state: bool | None, pending: bool = False) -> str:
    if pending:
        return f"<span class='chip' style='background:#1e2124;color:#8c8c8c'>… {label}</span>"
    if state is None:
        return f"<span class='chip' style='background:#1e2124;color:#8c8c8c' title='No data'>? {label}</span>"
    color = GREEN if state else MUTED
    return f"<span class='chip' style='background:{color}22;color:{color}'>{'✓' if state else '✗'} {label}</span>"


@st.fragment(run_every=3)
def wait_for(key: str, fn, max_age: float):
    """Re-runs the page once a background job saved by cache.get() has finished."""
    if cache.get(key, fn, max_age)[0] is not None:
        st.rerun()


def screen_idea():
    scan, _, _, _ = cache.get("sp500", data.sp500_scan, SP500_MAX_AGE)
    if scan is None:
        st.markdown("<div class='loading'><b style='color:#fff'>Loading the S&P 500 scan first</b><br>"
                    "About a minute the very first time.</div>", unsafe_allow_html=True)
        wait_for_scan()
        return
    st.markdown("<div class='tk-name'>Stock ideas</div>", unsafe_allow_html=True)
    idea = st.segmented_control("List", list(ideas.IDEAS), default=next(iter(ideas.IDEAS)), key="idea_pick",
                                label_visibility="collapsed") or next(iter(ideas.IDEAS))
    desc, checks, deep = ideas.IDEAS[idea]
    s1 = ideas.stage1(scan, idea)
    top = list(s1["symbol"][: ideas.MAX_DEEP])
    key = "ideas-" + hashlib.md5((idea + ",".join(top)).encode()).hexdigest()[:10]
    job = lambda: ideas.deep_checks(top, deep)
    res, _, running, _ = cache.get(key, job, 6 * 3600) if top else ({}, None, False, None)
    st.markdown(f"<div class='muted'>{desc} {len(s1)} of {len(scan)} S&P 500 stocks pass the price checks; the top "
                f"{len(top)} by analyst rating get the deeper checks.</div>", unsafe_allow_html=True)
    if not top:
        st.caption("Nothing passes this list's checks today.")
        return

    rows = []
    for r in s1.head(ideas.MAX_DEEP).itertuples():
        found = (res or {}).get(r.symbol, {})
        chips = [chip(ideas.CHECKS[c][0], True) for c in checks]
        chips += [chip(ideas.DEEP[d][0], found.get(d), pending=res is None) for d in deep]
        passed = len(checks) + sum(1 for d in deep if found.get(d))
        color = RED if (r.chg_1d or 0) < 0 else GREEN
        rows.append((passed, f"<a class='idea' href='{link(r.symbol)}' target='_self'><div><b>{r.symbol}</b>"
                             f"<small>{htmllib.escape(r.name)} · {r.sector}</small></div><div>{''.join(chips)}</div>"
                             f"<div class='r'><b>{usd(r.last)}</b><br><span class='pill' style='background:{color}'>"
                             f"{r.chg_1d:+.2f}%</span><br><span class='score'>{passed} of {len(checks) + len(deep)} checks"
                             f"</span></div></a>"))
    rows.sort(key=lambda x: -x[0])
    st.markdown("<div>" + "".join(h for _, h in rows) + "</div>", unsafe_allow_html=True)
    if res is None and running:
        st.caption("Running the deeper checks in the background (about 2 seconds per stock)…")
        wait_for(key, job, 6 * 3600)
    if len(s1) > len(top):
        with st.expander(f"{len(s1) - len(top)} more passed the price checks"):
            st.markdown(" · ".join(f"<a href='{link(s)}' target='_self' style='color:var(--acc)'>{s}</a>"
                                   for s in s1["symbol"][len(top):]), unsafe_allow_html=True)
    with st.expander("What each check means"):
        for c in checks:
            st.markdown(f"**{ideas.CHECKS[c][0]}**: {ideas.CHECKS[c][1]}")
        for d in deep:
            st.markdown(f"**{ideas.DEEP[d][0]}**: {ideas.DEEP[d][1]}")
    st.caption("These are filters on public data, not recommendations. ? means the data source had nothing for "
               "that stock. Price checks use the S&P 500 scan (refreshed every 30 minutes).")


# ---------- earnings calendar ----------
def my_symbols() -> tuple[list[str], list[str]]:
    """(held, watchlist-only) stock symbols."""
    held = c_held()
    return held, [s for s in watchlists.everything() if s not in held]


def when_label(d) -> str:
    days = (d - pd.Timestamp.now(tz="America/New_York").date()).days
    return "Today" if days == 0 else "Tomorrow" if days == 1 else f"In {days} days"


def screen_cal():
    if needs_key("FINNHUB_API_KEY", config.FINNHUB_API_KEY, "finnhub.io"):
        return
    held, watch = my_symbols()
    up = c_upcoming(tuple(held + watch))
    st.markdown("<div class='tk-name'>Earnings calendar</div>"
                f"<div class='muted'>Next reports for your {len(held)} holdings and {len(watch)} watchlist stocks, "
                "next 45 days. Funds like SPY don't report earnings.</div>", unsafe_allow_html=True)
    if up.empty:
        st.markdown("<div class='loading' style='margin-top:1rem'>None of your stocks report in the next 45 days."
                    "</div>", unsafe_allow_html=True)
        return
    hours = {"bmo": "Before the open", "amc": "After the close", "dmh": "During market hours"}
    rows = []
    for r in up.itertuples():
        try:
            s = c_surprises(r.symbol).head(4)
            record = f"Beat {int((s['surprisePercent'] > 0).sum())} of last {len(s)}" if not s.empty else "No history"
        except Exception:
            record = "-"
        soon = when_label(r.date) in ("Today", "Tomorrow")
        tag = "Holding" if r.symbol in held else "Watchlist"
        rows.append(
            f"<div class='cal{' soon' if soon else ''}'><div><b>{r.date:%a, %b %d}</b><small>{when_label(r.date)}</small>"
            f"</div><div><a href='{link(r.symbol)}' target='_self'>{r.symbol}</a><small>{tag} · "
            f"{hours.get(r.hour, 'Time not announced')}</small></div>"
            f"<div><small>EPS estimate</small>{usd(r.epsEstimate)}</div>"
            f"<div><small>Revenue estimate</small>{big(r.revenueEstimate)}</div>"
            f"<div><small>Track record</small>{record}</div></div>")
    st.markdown("<div style='margin-top:1rem'>" + "".join(rows) + "</div>", unsafe_allow_html=True)
    st.caption("A reminder pops up the day before and the day of each report while the app is open.")


@st.fragment(run_every=600)
def earnings_reminders():
    if not config.FINNHUB_API_KEY:
        return
    held, watch = my_symbols()
    # Never make a page wait for this: use the saved copy, fetched in the background when missing.
    up = cache.get(_syms_key("upcoming-", held + watch), lambda: sources.upcoming_earnings(held + watch), 6 * 3600)[0]
    if up is None:
        return
    shown = ss.setdefault("reminded", set())
    hours = {"bmo": "before the open", "amc": "after the close"}
    for r in up.itertuples() if not up.empty else []:
        label = when_label(r.date)
        if label in ("Today", "Tomorrow") and (r.symbol, r.date) not in shown:
            shown.add((r.symbol, r.date))
            st.toast(f"{r.symbol} reports earnings {label.lower()} {hours.get(r.hour, '')} "
                     f"(EPS estimate {num(r.epsEstimate)})", icon="📅")


# ---------- prediction markets ----------
def pred_card(e: dict, n: int = 5) -> str:
    bars = "".join(
        f"<div class='bar'><span>{htmllib.escape(str(label))[:60]}</span><div class='track'><div class='fill' "
        f"style='width:{p * 100:.0f}%;background:{GREEN if i == 0 else '#5c5f63'}'></div></div>"
        f"<span class='r'>{p * 100:.0f}%</span></div>" for i, (label, p) in enumerate(e["outcomes"][:n]))
    more = f"<small class='muted'>+{len(e['outcomes']) - n} more outcomes</small>" if len(e["outcomes"]) > n else ""
    sub = f" · {htmllib.escape(e['subtitle'])}" if e["subtitle"] else ""
    return (f"<div class='pred'><a href='{e['url']}' target='_blank'>{htmllib.escape(e['title'])}</a>"
            f"<div class='muted' style='font-size:.78rem;margin:.15rem 0 .5rem'>{e['source']}{sub} · volume "
            f"{big(e['volume'])}</div>{bars}{more}</div>")


def prediction_notice(errors: dict) -> str:
    return ("Kalshi and Polymarket can't be reached from this computer: the connection is cut during the secure "
            "handshake, which is what a network filter does. Your network (often a company network or security "
            "software) appears to block these sites. On a network that allows kalshi.com and polymarket.com this "
            "fills in on its own.") if errors and all("handshake" in v for v in errors.values()) else \
        "; ".join(f"{k}: {v}" for k, v in errors.items())


def screen_pred():
    events, errors = c_predictions(wait=True)  # this screen is about the odds, so it waits for fresh ones
    have_ibkr = "Interactive Brokers" in brokers
    st.markdown("<div class='tk-name'>Prediction markets</div><div class='muted'>What traders are paying for "
                "each outcome, read as the market's odds. From Kalshi and Polymarket"
                + (", plus IBKR ForecastEx through your IB Gateway" if have_ibkr else "")
                + ", refreshed every 10 minutes.</div>", unsafe_allow_html=True)
    public_errors = {k: v for k, v in errors.items() if not k.startswith("ForecastEx")}
    fx_errors = {k.removeprefix("ForecastEx").strip() or "connection": v for k, v in errors.items()
                 if k.startswith("ForecastEx")}
    if public_errors:
        (st.info if not events else st.caption)(prediction_notice(public_errors))
    for code, err in fx_errors.items():
        st.caption(f"ForecastEx {code}: {err}")
    with st.expander("ForecastEx settings" if have_ibkr else "ForecastEx (needs Interactive Brokers)"):
        st.caption("IBKR's own prediction markets, read through IB Gateway. Enter ForecastEx product codes, e.g. FF "
                   "(US Fed Funds target rate). Find more codes in IBKR's ForecastTrader. Each outcome's odds are the "
                   "price of its Yes contract, which pays $1.")
        codes = st.text_input("Product codes", ", ".join(predictions.forecast_products()), key="fx_codes")
        if st.button("Save codes"):
            predictions.set_forecast_products(codes.replace(",", " ").split())
            c_forecastex.clear()
            st.rerun()
    if not events:
        return
    c = st.columns([5, 3], vertical_alignment="center")
    topics = [*predictions.TOPICS, *(["ForecastEx"] if have_ibkr else []), "All"]
    topic = c[0].segmented_control("Topic", topics, default="Fed & rates", key="pred_topic",
                                   label_visibility="collapsed") or "All"
    query = c[1].text_input("Search markets", placeholder="Search markets, e.g. tariffs", label_visibility="collapsed")
    if topic == "ForecastEx":
        found = predictions.matching([e for e in events if e["source"] == "IBKR ForecastEx"], None, query)[:30]
    else:
        found = predictions.matching(events, None if topic == "All" else topic, query)[:30]
    if not found:
        st.caption("No open markets match.")
        return
    cols = st.columns(2, gap="medium")
    for i, e in enumerate(found):
        cols[i % 2].markdown(pred_card(e), unsafe_allow_html=True)


def trader_context() -> dict:
    """Who the user is as a trader: their plan, track record and recent journal notes."""
    out: dict = {}
    if profile.is_set():
        out["my_trading_plan"] = profile.for_ai()
    try:
        fills, _, _ = all_activity()
        s = gains.summary(closed_trades(fills))
        if s.get("trades"):
            out["my_track_record"] = {k: round(v, 2) if isinstance(v, float) else v for k, v in s.items()}
    except Exception:
        pass
    recent = [e for e in journal.load() if e.get("note") or e.get("review")][-10:]
    if recent:
        out["my_recent_journal"] = [{k: e.get(k) for k in ("symbol", "side", "qty", "price", "note", "tags", "review")}
                                    for e in recent]
    return out


# ---------- morning brief ----------
def brief_context() -> str:
    held, watch = my_symbols()
    syms = held + watch
    ctx: dict = {"date": pd.Timestamp.now(tz="America/New_York").strftime("%A %B %d, %Y %H:%M ET"),
                 **trader_context()}
    market = c_quotes(("SPY", "QQQ", "DIA", "IWM"))
    ctx["market_etfs"] = market[["symbol", "last", "change_pct"]].round(2).to_dict("records")
    if config.FRED_API_KEY:
        try:
            ctx["economy"] = {n: round(float(c_fred(sources.FRED_SERIES[n]).iloc[-1]), 2)
                              for n in ("Fed funds rate", "10-year Treasury", "VIX", "CPI inflation (YoY %)")}
        except Exception:
            pass
    ctx["holdings"] = {}
    for name, b in brokers.items():
        try:
            ctx["holdings"][name] = c_positions(name)
        except Exception:
            pass
    q_all = c_quotes(tuple(syms)) if syms else pd.DataFrame()
    ctx["moves_today"] = (q_all[["symbol", "last", "change_pct", "volume"]].round(2).to_dict("records")
                          if not q_all.empty else [])
    ctx["headlines"] = {s: [{k: n[k] for k in ("title", "publisher", "published", "url")} for n in c_news(s)[:3]]
                        for s in syms}
    if config.FINNHUB_API_KEY:
        up = c_upcoming(tuple(syms))
        if not up.empty:
            soon = up[pd.to_datetime(up["date"]) <= pd.Timestamp.now() + pd.Timedelta(days=7)]
            ctx["earnings_next_7_days"] = soon[["symbol", "date", "hour", "epsEstimate"]].astype(str).to_dict("records")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
        trades = []
        for s in syms:
            try:
                t = c_insiders(s)
                t = t[t["transactionCode"].isin(["P", "S"]) & (pd.to_datetime(t["transactionDate"]) > cutoff)]
                trades += t[["symbol", "name", "transactionCode", "change", "transactionPrice", "transactionDate"]] \
                    .head(5).to_dict("records")
            except Exception:
                pass
        ctx["insider_open_market_trades_30d"] = trades
    events, _ = c_predictions()
    if events:
        ctx["prediction_market_odds"] = [{"title": e["title"], "outcomes": [(o, round(p, 3)) for o, p in e["outcomes"][:4]]}
                                         for e in predictions.matching(events, "Fed & rates")[:3]]
    return json.dumps(ctx, default=str)


BRIEF_PROMPT = """Write my morning brief for today from the data in <context>. Use these sections, skipping any \
that have nothing worth saying: **Market** (index ETFs, rates, VIX, Fed odds), **My holdings**, **Watchlist \
movers**, **Earnings this week**, **Insider activity**, **Headlines worth reading** (as markdown links), \
**What to watch today**. Under 400 words, bullet points, concrete numbers. Use only facts that appear in \
<context> (including its headlines); do not add figures from memory, and say when data is missing. \
Flag things to look into rather than telling me what to buy or sell."""


def screen_brf():
    if not ai.provider():
        st.info("Sign in under Assistant > Connect Claude (or add a Gemini key) to use the morning brief.")
        return
    today = pd.Timestamp.now(tz="America/New_York").date()
    path = cache.DIR / f"brief-{today}.md"
    c = st.columns([6, 1], vertical_alignment="center")
    c[0].markdown(f"<div class='tk-name'>Morning brief</div><div class='muted'>{today:%A, %B %d} · written by "
                  f"{ai.provider()} from your holdings, watchlist and today's data</div>", unsafe_allow_html=True)
    jobs = brief_jobs()
    job = jobs.get(str(today), {})
    rewrite = c[1].button("Rewrite", width="stretch", disabled=job.get("running", False))
    st.divider()
    if rewrite:
        path.unlink(missing_ok=True)
        jobs.pop(str(today), None)
        job = {}
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8").replace("$", "\\$"))
        st.caption(f"Written at {pd.Timestamp(path.stat().st_mtime, unit='s', tz='UTC').tz_convert(LOCAL_TZ):%I:%M %p} "
                   "Denver time. A new one is written the first time you open this screen each day.")
        return
    if job.get("error"):
        st.error(f"The brief couldn't be written: {job['error']}")
        if st.button("Try again"):
            jobs.pop(str(today), None)
            st.rerun()
        return
    if not job.get("running"):
        start_brief(str(today), path)
    st.info("Writing today's brief in the background (about a minute). Use the rest of the app meanwhile; "
            "it appears here when it's ready.")
    brief_wait(str(today), path)


@st.cache_resource
def brief_jobs() -> dict:
    """Shared across reruns and sessions: {date: {"running": bool, "error": str}}."""
    return {}


def start_brief(today: str, path):
    """Gather the data and have the AI write the brief in a background thread, so no page waits on it."""
    import threading

    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

    jobs, ctx = brief_jobs(), get_script_run_ctx()
    jobs[today] = {"running": True, "started": time.time()}

    def work():
        add_script_run_ctx(ctx=ctx)  # lets the thread use the app's caches
        started = time.perf_counter()
        try:
            messages = [{"role": "user", "content": f"<context>{brief_context()}</context>\n\n{BRIEF_PROMPT}"}]
            text = "".join(ai.stream_answer(messages))
            cache.DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            jobs[today] = {"running": False}
        except Exception as e:
            jobs[today] = {"running": False, "error": ai.error_text(e)}
        log_if_slow("morning brief (background)", started)

    threading.Thread(target=work, daemon=True, name=f"brief-{today}").start()


@st.fragment(run_every=3)
def brief_wait(today: str, path):
    job = brief_jobs().get(today, {})
    if path.exists() or job.get("error"):
        st.rerun()
    st.caption(f"Working… {int(time.time() - job.get('started', time.time()))}s")


# Raw broker status (Alpaca snake_case, IBKR CamelCase, compared lower-case, no "_") ->
# (plain label, state). "open" orders can still be canceled.
ORDER_STATUS = {
    "pendingsubmit": ("Sending to IBKR", "open"), "apipending": ("Sending to IBKR", "open"),
    "presubmitted": ("Waiting for market open", "open"), "submitted": ("Working", "open"),
    "pendingcancel": ("Canceling", "open"), "pendingnew": ("Sending to Alpaca", "open"),
    "new": ("Working", "open"), "accepted": ("Accepted", "open"), "held": ("Waiting to trigger", "open"),
    "acceptedforbidding": ("Accepted", "open"), "partiallyfilled": ("Partly filled", "open"),
    "pendingreplace": ("Updating", "open"), "calculated": ("Working", "open"),
    "filled": ("Filled", "done"), "doneforday": ("Done for the day", "done"),
    "cancelled": ("Canceled", "closed"), "canceled": ("Canceled", "closed"), "apicancelled": ("Canceled", "closed"),
    "expired": ("Expired", "closed"), "rejected": ("Rejected", "closed"), "inactive": ("Not active", "closed"),
    "replaced": ("Replaced", "closed"), "stopped": ("Stopped", "closed"), "suspended": ("Suspended", "closed"),
}


def order_status(o: dict) -> tuple[str, str]:
    raw = (o.get("status") or "").lower().replace("_", "")
    return ORDER_STATUS.get(raw, ((o.get("status") or "Unknown").replace("_", " ").capitalize(), "open"))


def order_row(o: dict) -> str:
    status, state = order_status(o)
    color = GREEN if state == "done" else MUTED if state == "closed" else AMBER
    when = pd.Timestamp(o["submitted"]).strftime("%b %d, %H:%M") if o.get("submitted") else ""
    price = f" @ {usd(o['limit_price'])}" if o.get("limit_price") else ""
    return (f"<div class='line' style='border-bottom:1px solid {LINE};padding:.75rem 0'>"
            f"<div><b>{o['symbol']}</b> <span class='muted'>{(o.get('type') or '').title()} "
            f"{(o.get('side') or '').title()}{price}</span><br><small class='muted'>{when}</small></div>"
            f"<div class='r'>{(o.get('qty') or 0):g} {'share' if o.get('qty') == 1 else 'shares'}<br>"
            f"<small style='color:{color}'>{status}</small></div></div>"
            + (f"<div class='muted' style='font-size:.78rem;margin:-.4rem 0 .5rem'>IBKR: "
               f"{htmllib.escape(o['message'])}</div>" if o.get("message") else ""))


def broker_notices():
    for name, err in broker_errors.items():
        st.warning(f"{name} not connected: {err}")
    if not brokers and not broker_errors:
        st.info("No broker configured yet. Copy .env.example to .env, add your Alpaca keys "
                "(and set IBKR_ENABLED=true for Interactive Brokers), then restart the app.")
    if st.button("Reconnect brokers"):
        c_brokers.clear()
        st.rerun()


def screen_port():
    if not brokers:
        broker_notices()
        return
    names = list(brokers)
    left, right = st.columns([2.3, 1], gap="large")
    with left:
        bname = (st.segmented_control("Account", names, default=names[0], label_visibility="collapsed")
                 if len(names) > 1 else names[0]) or names[0]
        try:
            a, positions = c_account(bname), c_positions(bname)
        except Exception as e:
            st.error(f"{bname}: {e}")
            return
        chart_box = st.container()
        rng = st.segmented_control("Range", ["1D", "1W", "1M", "3M", "1Y"], default="1D", key="port_range",
                                   label_visibility="collapsed") or "1D"
        with chart_box:
            try:
                hist = c_port_history(bname, rng)
            except Exception:
                hist = pd.Series(dtype=float)
            start = hist.iloc[0] if len(hist) else a["equity"]
            move = a["equity"] - start
            color = RED if move < 0 else GREEN
            label = {"1D": "Today", "1W": "Past week", "1M": "Past month", "3M": "Past 3 months", "1Y": "Past year"}[rng]
            st.markdown(
                f"<div class='muted'>{bname} · investing</div><div class='tk-px'>{usd(a['equity'])}</div>"
                f"<div class='tk-chg' style='color:{color}'>{usd(move, sign=True)} "
                f"({num(move / start * 100 if start else 0, '{:+.2f}%')})<small>{label}</small></div>",
                unsafe_allow_html=True)
            if len(hist) > 1:
                line_chart(hist, 280, color, start if rng == "1D" else None)
            else:
                st.markdown("<div class='loading'>No account history for this range yet.</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='line' style='border-top:1px solid {LINE};border-bottom:1px solid {LINE};padding:.9rem 0'>"
            f"<b>Buying power</b><b>{usd(a['buying_power'])}</b></div>"
            f"<div class='line'><span class='muted'>Cash</span><span>{usd(a['cash'])}</span></div>",
            unsafe_allow_html=True)
        st.subheader("Positions")
        if not positions:
            st.caption("No open positions yet. Open a stock and use the order card to buy.")
        else:
            syms = tuple(p["symbol"] for p in positions if not OrderRequest(p["symbol"], "buy", 1).is_option)
            sparks = c_sparks(syms) if syms else {}
            rows = []
            for p in positions:
                pl, cost = p.get("unrealized_pl") or 0, (p.get("avg_cost") or 0) * (p.get("qty") or 0)
                rows.append({
                    "symbol": p["symbol"], "last": p.get("price"), "spark": sparks.get(p["symbol"]),
                    "change_pct": pl / abs(cost) * 100 if cost else None,
                    "sub": f"{p['qty']:g} shares · avg {usd(p.get('avg_cost'))}",
                    "extra": f"{usd(p.get('market_value'))}<small style='color:{RED if pl < 0 else GREEN}'>"
                             f"{usd(pl, sign=True)} total return</small>",
                })
            nav_list(rows, "pos")
            st.caption("The pill on each position is its total return since you bought it.")
        portfolio_analytics(positions, hist, rng)
        for name, err in broker_errors.items():
            st.warning(f"{name} not connected: {err}")
    with right:
        st.markdown("<div class='box-title'>Watchlist</div>", unsafe_allow_html=True)
        watchlist_panel(tuple(watchlists.symbols()), compact=True)


PORT_SPY = {"1D": ("1d", "5m"), "1W": ("5d", "15m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "1Y": ("1y", "1d")}


def portfolio_analytics(positions: list[dict], hist: pd.Series, rng: str):
    st.subheader("Analytics")
    # Performance against the S&P 500 over the same range
    spy = c_history("SPY", *PORT_SPY[rng]).Close
    if len(hist) > 1 and len(spy) > 1:
        spy = spy[spy.index >= hist.index[0]] if rng != "1D" else spy
        mine, mkt = (hist / hist.iloc[0] - 1) * 100, (spy / spy.iloc[0] - 1) * 100
        fig = go.Figure([go.Scatter(x=mine.index, y=mine, name="Your account", line=dict(color=ACC, width=2),
                                    hovertemplate="You %{y:+.2f}%<extra></extra>"),
                         go.Scatter(x=mkt.index, y=mkt, name="S&P 500 (SPY)", line=dict(color="#8c8c8c", width=1.5),
                                    hovertemplate="S&P 500 %{y:+.2f}%<extra></extra>")])
        fig.add_hline(y=0, line=dict(color="#4a4d52", width=1, dash="dot"))
        style_fig(fig, 260, hovermode="x unified", legend=dict(orientation="h", y=1.12), yaxis_ticksuffix="%")
        skip_closed_hours(fig, "1D" if rng == "1D" else "1W" if rng == "1W" else "1Y")
        st.markdown(f"<div class='muted'>Your account <b style='color:#fff'>{mine.iloc[-1]:+.2f}%</b> vs the S&P 500 "
                    f"<b style='color:#fff'>{mkt.iloc[-1]:+.2f}%</b> over this range</div>", unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)
    if not positions:
        st.caption("Allocation and profit by position appear once you hold something.")
        return
    c = st.columns(2, gap="large")
    # Allocation by sector
    alloc: dict[str, float] = {}
    for p in positions:
        if OrderRequest(p["symbol"], "buy", 1).is_option:
            sector = "Options"
        else:
            try:
                info = c_info(p["symbol"])
                sector = info.get("sector") or ("Funds" if info.get("quoteType") == "ETF" else "Other")
            except Exception:
                sector = "Other"
        alloc[sector] = alloc.get(sector, 0) + abs(p.get("market_value") or 0)
    fig = go.Figure(go.Pie(labels=list(alloc), values=list(alloc.values()), hole=0.62, sort=True,
                           textinfo="percent", hovertemplate="%{label}: $%{value:,.0f} (%{percent})<extra></extra>"))
    style_fig(fig, 300, legend=dict(orientation="v", x=1, y=0.5))
    with c[0]:
        st.markdown("<div class='box-title'>Allocation by sector</div>", unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)
    # Profit or loss per position
    pl = sorted(((p["symbol"], p.get("unrealized_pl") or 0) for p in positions), key=lambda x: x[1])
    fig = go.Figure(go.Bar(x=[v for _, v in pl], y=[s for s, _ in pl], orientation="h",
                           marker_color=[GREEN if v >= 0 else RED for _, v in pl],
                           hovertemplate="%{y}: $%{x:+,.2f}<extra></extra>"))
    style_fig(fig, max(220, 40 * len(pl)), xaxis_tickprefix="$")
    with c[1]:
        st.markdown("<div class='box-title'>Profit or loss by position</div>", unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config=NO_TOOLBAR)


def screen_ord():
    broker_notices()
    if not brokers:
        return
    ticket, book = st.columns([1, 1.6], gap="large")
    with ticket:
        with st.container(border=True):
            order_ticket(symbol_input=True)
    with book:
        st.markdown("<div class='tk-name' style='font-size:1.5rem'>Orders</div>", unsafe_allow_html=True)
        orders_panel()


@st.fragment(run_every=5)
@timed("orders list")
def orders_panel():
    """Order list; re-asks each broker for statuses every few seconds."""
    for name, b in brokers.items():
        try:
            orders = b.orders()
        except Exception as e:
            st.error(f"{name}: {e}")
            continue
        if len(brokers) > 1:
            st.caption(name)
        if not orders:
            st.caption("No orders yet.")
            continue
        st.markdown("<div>" + "".join(order_row(o) for o in orders[:25]) + "</div>", unsafe_allow_html=True)
        open_ = [o for o in orders if order_status(o)[1] == "open"]
        if open_:
            pick = st.selectbox(f"Cancel an open {name} order", open_, key=f"cx_{name}",
                                format_func=lambda o: f"{o['side'].upper()} {o['qty']:g} {o['symbol']} "
                                                      f"({order_status(o)[0]})")
            if st.button("Cancel order", key=f"cxb_{name}"):
                try:
                    b.cancel_order(pick["id"])
                    st.success("Cancel request sent.")
                except Exception as e:
                    st.error(f"Cancel failed: {e}")


def ai_context() -> str:
    ctx: dict = {"ticker": sym, "quote": q}
    i = c_info(sym)
    ctx["fundamentals"] = {k: i.get(k) for k in (
        "longName", "sector", "industry", "marketCap", "trailingPE", "forwardPE", "priceToSalesTrailing12Months",
        "revenueGrowth", "earningsGrowth", "grossMargins", "operatingMargins", "profitMargins", "returnOnEquity",
        "freeCashflow", "debtToEquity", "beta", "recommendationKey", "targetMeanPrice", "numberOfAnalystOpinions")}
    ctx["headlines"] = [{k: n[k] for k in ("title", "publisher", "published")} for n in c_news(sym)[:10]]
    # Extra sources; each is optional, so a missing key or failed call just leaves that part out.
    def add(key, fn_):
        try:
            ctx[key] = fn_()
        except Exception:
            pass

    if config.FMP_API_KEY:
        add("valuation_models", lambda: {
            "dcf": c_fmp("discounted-cash-flow", sym), "scores": c_fmp("financial-scores", sym),
            "rating": c_fmp("ratings-snapshot", sym), "price_target": c_fmp("price-target-consensus", sym)})
    if config.FINNHUB_API_KEY:
        add("earnings_vs_estimates", lambda: c_surprises(sym).to_dict("records"))
        add("insider_open_market_trades", lambda: (lambda d: d[d["transactionCode"].isin(["P", "S"])].head(15)[
            ["transactionDate", "name", "transactionCode", "change", "transactionPrice"]].to_dict("records"))(c_insiders(sym)))
    add("recent_sec_filings", lambda: (lambda f: f[f["form"].isin(["10-K", "10-Q", "8-K"])].head(12)[
        ["filed", "form", "items", "url"]].to_dict("records"))(c_filings(sym)))
    if config.FRED_API_KEY:
        add("economy", lambda: {name: round(float(c_fred(sid).iloc[-1]), 2) for name, sid in sources.FRED_SERIES.items()})
    add("prediction_market_odds", lambda: [
        {"title": e["title"], "source": e["source"], "outcomes": [(o, round(p, 3)) for o, p in e["outcomes"][:4]]}
        for e in predictions.matching(c_predictions()[0], "Fed & rates")[:3]
        + predictions.matching(c_predictions()[0], None, company or sym)[:3]])
    ctx.update(trader_context())
    ctx["holdings"] = {}
    for name, b in brokers.items():
        try:
            ctx["holdings"][name] = {"account": c_account(name), "positions": c_positions(name)}
        except Exception:
            pass
    return json.dumps(ctx, default=str)


def screen_ai():
    if not ai.provider():
        st.info("Sign in under Assistant > Connect Claude, or add GEMINI_API_KEY / ANTHROPIC_API_KEY, to use the research panel, or "
                "and connect Claude Code / Claude Desktop to this app's data instead (see README).")
        return
    who = ai.provider()
    with_tools = who == "Claude Code"
    c = st.columns([8, 1])
    c[0].caption(f"{who} " + ("looks up whatever the question needs with the terminal's research tools (any stock, "
                              "ETF, future, option, the economy, your portfolio) and can search the web."
                              if with_tools else f"sees the data on screen for {sym} plus your holdings, and can "
                              "search the web.") + " It cannot place orders.")
    if c[1].button("Clear"):
        ss.chat, ss.chat_api = [], []
        st.rerun()
    for role, text in ss.chat:
        st.chat_message(role).markdown(text)
    prompt = st.chat_input(f"Ask about {sym}, any market, your portfolio, or the economy")
    if not prompt:
        return
    st.chat_message("user").markdown(prompt)
    ss.chat.append(("user", prompt))
    turn_start = len(ss.chat_api)
    started = time.perf_counter()
    # With tools Claude fetches what it needs, so send only a light starting point; otherwise the full bundle.
    context = light_ai_context() if with_tools else ai_context()
    log_if_slow("Ask AI context", started)
    ss.chat_api.append({"role": "user", "content": f"<context>{context}</context>\n\n{prompt}"})
    with st.chat_message("assistant"):
        status = st.status("Thinking…", expanded=False) if with_tools else None
        looked_up: list[str] = []

        def on_tool(name: str):
            looked_up.append(name.replace("get_", "").replace("_", " "))
            if status:
                status.update(label=f"Looking up: {', '.join(dict.fromkeys(looked_up))}…")

        try:
            # Escape "$" so prices are not swallowed as LaTeX math by the markdown renderer.
            text = st.write_stream(t.replace("$", "\\$") for t in ai.stream_answer(ss.chat_api, on_tool=on_tool))
            ss.chat.append(("assistant", text))
            if status:
                status.update(label=f"Used {len(looked_up)} lookups: {', '.join(dict.fromkeys(looked_up)) or 'none'}",
                              state="complete")
        except Exception as e:
            ss.chat.pop()
            del ss.chat_api[turn_start:]
            if status:
                status.update(label="Didn't finish", state="error")
            st.error(ai.error_text(e))
            st.caption("Details are in the add-on's Log tab (lines starting with [claude]).")


def light_ai_context() -> str:
    """Starting point for Claude with tools: what's on screen and what you hold. Everything else it looks up."""
    ctx: dict = {"screen": FUNCTIONS.get(fn, fn), "ticker_on_screen": sym, "mode": config.MODE_LABEL,
                 "today": pd.Timestamp.now(tz=LOCAL_TZ).strftime("%A %B %d, %Y %I:%M %p Denver time")}
    if q:
        ctx["quote"] = {k: q.get(k) for k in ("last", "change_pct", "day_low", "day_high", "volume")}
    ctx["holdings"] = {}
    for name in brokers:
        try:
            ctx["holdings"][name] = [{k: p.get(k) for k in ("symbol", "qty", "avg_cost", "market_value", "unrealized_pl")}
                                     for p in c_positions(name)]
        except Exception:
            pass
    if profile.is_set():
        ctx["my_trading_plan"] = profile.for_ai()
    return json.dumps(ctx, default=str)


LOCAL_TZ = "America/Denver"


@st.cache_data(ttl=300, show_spinner=False)
def c_activity(broker_name: str):
    return c_brokers()[0][broker_name].activity()


def all_activity() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fills and dividends from every connected broker, with a broker column; errors by broker."""
    fills, divs, errors = [], [], {}
    for name in brokers:
        try:
            f, d = c_activity(name)
            fills.append(f.assign(broker=name))
            divs.append(d.assign(broker=name))
        except Exception as e:
            errors[name] = str(e)
    cat = lambda xs, cols: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame(columns=cols)
    return cat(fills, ["symbol", "side", "qty", "price", "time", "broker"]), \
        cat(divs, ["symbol", "amount", "date", "broker"]), errors


def closed_trades(fills: pd.DataFrame) -> pd.DataFrame:
    parts = [gains.realized(g).assign(broker=b) for b, g in fills.groupby("broker")] if not fills.empty else []
    return pd.concat(parts, ignore_index=True) if parts else gains.realized(fills)


def stat_row(s: dict):
    m = st.columns(6)
    m[0].metric("Closed trades", s.get("trades", 0))
    if not s.get("trades"):
        return
    m[1].metric("Win rate", f"{s['win_rate']:.0f}%")
    m[2].metric("Total P/L", usd(s["total"], sign=True).replace("&#36;", "$"))
    m[3].metric("Average win", usd(s["avg_win"]).replace("&#36;", "$"))
    m[4].metric("Average loss", usd(s["avg_loss"]).replace("&#36;", "$"))
    m[5].metric("Profit factor", num(s["profit_factor"]), help="Total won ÷ total lost. Above 1 means winners outweigh losers.")


def screen_jrnl():
    st.markdown("<div class='tk-name'>Trade journal</div><div class='muted'>Every order you send from the app, with "
                "your note on why. Add a review once a trade is done.</div>", unsafe_allow_html=True)
    entries = journal.load()
    fills, _, errors = all_activity()
    closed = closed_trades(fills)
    st.subheader("Track record")
    stat_row(gains.summary(closed))
    # Which journal tags win: credit each closed trade to the latest journal entry that opened it.
    if not closed.empty and entries:
        def utc(ts):
            ts = pd.Timestamp(ts)
            return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")

        tagged = []
        for t in closed.itertuples():
            opener = "buy" if t.direction == "Long" else "sell"
            # Allow a minute of clock difference between the app and the broker's fill time.
            cutoff = utc(t.opened) + pd.Timedelta(minutes=1)
            match = [e for e in entries if e["symbol"] == t.symbol and e["side"] == opener
                     and pd.Timestamp(e["time"], unit="s", tz="UTC") <= cutoff]
            for tag in (match[-1]["tags"] if match else []) or ["(no tag)"]:
                tagged.append({"tag": tag, "pl": t.pl, "win": t.pl > 0})
        if tagged:
            by = pd.DataFrame(tagged).groupby("tag").agg(trades=("pl", "size"), win_rate=("win", "mean"), total=("pl", "sum"))
            by["win_rate"] *= 100
            st.markdown("<div class='box-title' style='margin-top:1rem'>By setup tag</div>", unsafe_allow_html=True)
            st.dataframe(color_moves(by.sort_values("total", ascending=False), ["total"]), width="stretch",
                         column_config={"win_rate": st.column_config.NumberColumn("Win rate", format="%.0f%%"),
                                        "total": st.column_config.NumberColumn("Total P/L", format="$%.2f"),
                                        "trades": "Trades"})
    for name, err in errors.items():
        st.caption(f"{name} trade history unavailable: {err}")
    st.subheader("Entries")
    if not entries:
        st.caption("No entries yet. Orders you submit from the order card are logged here; add a note under "
                   "\"Journal note\" before you submit.")
        return
    syms = sorted({e["symbol"] for e in entries})
    only = st.multiselect("Filter", syms, placeholder="All symbols", label_visibility="collapsed")
    for e in reversed(entries):
        if only and e["symbol"] not in only:
            continue
        when = pd.Timestamp(e["time"], unit="s", tz="UTC").tz_convert(LOCAL_TZ)
        price = f" @ {usd(e['price'])}" if e.get("price") else ""
        exits = " · ".join(x for x in (f"stop {usd(e['stop_loss'])}" if e.get("stop_loss") else "",
                                       f"target {usd(e['take_profit'])}" if e.get("take_profit") else "") if x)
        with st.container(border=True):
            st.markdown(
                f"<b><a href='{link(e['symbol'])}' target='_self' style='color:#fff'>{e['symbol']}</a></b> "
                f"<span class='muted'>{e['side'].title()} {e['qty']:g} · {e['type'].title()}{price} · {e['broker']} "
                f"{e.get('mode', '').lower()} · {when:%b %d, %Y %I:%M %p}</span>"
                + (f"<br><span class='muted'>{exits}</span>" if exits else "")
                + "".join(f" <span class='chip' style='background:#1e2124'>{htmllib.escape(t)}</span>" for t in e["tags"])
                + (f"<div style='margin-top:.4rem'>{htmllib.escape(e['note'])}</div>" if e["note"] else
                   "<div class='muted' style='margin-top:.4rem'>No note.</div>"),
                unsafe_allow_html=True)
            c = st.columns([5, 1, 1], vertical_alignment="bottom")
            review = c[0].text_input("How did it go?", value=e.get("review", ""), key=f"rv_{e['id']}",
                                     placeholder="How did it go? What would you do differently?",
                                     label_visibility="collapsed")
            if c[1].button("Save", key=f"rvs_{e['id']}", width="stretch"):
                journal.update(e["id"], review=review); st.rerun()
            if c[2].button("Delete", key=f"rvd_{e['id']}", width="stretch"):
                journal.delete(e["id"]); st.rerun()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def c_dividend_info(symbol: str) -> dict:
    i = c_info(symbol)
    return {k: i.get(k) for k in ("exDividendDate", "dividendRate", "lastDividendValue", "dividendYield", "shortName")}


def screen_gain():
    st.markdown("<div class='tk-name'>Gains & dividends</div><div class='muted'>Profit on closed trades "
                "(first-in, first-out) and dividend income, for tracking and tax time.</div>", unsafe_allow_html=True)
    if not brokers:
        broker_notices()
        return
    fills, divs, errors = all_activity()
    closed = closed_trades(fills)
    years = sorted({d.year for d in pd.to_datetime(closed["closed"])} | {d.year for d in pd.to_datetime(divs["date"])},
                   reverse=True) or [pd.Timestamp.now().year]
    year = st.segmented_control("Year", ["All", *years], default=years[0], key="gain_year",
                                label_visibility="collapsed") or years[0]
    if year != "All":
        closed = closed[pd.to_datetime(closed["closed"]).dt.year == year]
        divs = divs[pd.to_datetime(divs["date"]).dt.year == year]
    s = gains.summary(closed)
    st.subheader("Realized gains")
    stat_row(s)
    if s.get("trades"):
        st.markdown(f"<div class='muted'>Short-term (held a year or less): <b style='color:#fff'>"
                    f"{usd(s['short_term'], sign=True)}</b> · Long-term (more than a year): <b style='color:#fff'>"
                    f"{usd(s['long_term'], sign=True)}</b></div>", unsafe_allow_html=True)
        view = closed.assign(opened=pd.to_datetime(closed["opened"]).dt.date,
                             closed=pd.to_datetime(closed["closed"]).dt.date).sort_values("closed", ascending=False)
        st.dataframe(color_moves(view, ["pl", "pl_pct"]), hide_index=True, width="stretch", height=360,
                     column_config={"symbol": "Symbol", "opened": "Opened", "closed": "Closed", "qty": "Shares",
                                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                                    "proceeds": st.column_config.NumberColumn("Proceeds", format="$%.2f"),
                                    "pl": st.column_config.NumberColumn("Gain / loss", format="$%+.2f"),
                                    "pl_pct": st.column_config.NumberColumn("Return", format="%+.2f%%"),
                                    "days": "Days held", "term": "Term", "direction": "Long/short", "broker": "Account"})
        st.download_button("Download realized gains (CSV)", view.to_csv(index=False), f"realized-gains-{year}.csv",
                           "text/csv")
    else:
        st.caption("No closed trades yet. A trade counts once you've sold shares you bought (or bought back a short).")

    st.subheader("Dividends received")
    if divs.empty:
        st.caption("No dividends received yet.")
    else:
        m = st.columns(3)
        m[0].metric("Total", usd(divs["amount"].sum()).replace("&#36;", "$"))
        m[1].metric("Payments", len(divs))
        top = divs.groupby("symbol")["amount"].sum().sort_values(ascending=False)
        m[2].metric("Largest payer", f"{top.index[0]} ({usd(top.iloc[0]).replace('&#36;', '$')})")
        view = divs.assign(date=pd.to_datetime(divs["date"]).dt.date).sort_values("date", ascending=False)
        st.dataframe(view, hide_index=True, width="stretch", height=260,
                     column_config={"symbol": "Symbol", "date": "Paid", "broker": "Account",
                                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f")})
        st.download_button("Download dividends (CSV)", view.to_csv(index=False), f"dividends-{year}.csv", "text/csv")

    st.subheader("Upcoming dividends on what you hold")
    rows = []
    for bname in brokers:
        try:
            held = c_positions(bname)
        except Exception:
            continue
        for p in held:
            if OrderRequest(p["symbol"], "buy", 1).is_option or (p.get("qty") or 0) <= 0:
                continue
            d = c_dividend_info(p["symbol"])
            if not d.get("dividendRate"):
                continue
            ex = pd.Timestamp(d["exDividendDate"], unit="s").date() if d.get("exDividendDate") else None
            rows.append({"symbol": p["symbol"], "shares": p["qty"],
                         "ex_date": ex if ex and ex >= pd.Timestamp.now().date() else None,
                         "per_payment": d.get("lastDividendValue"),
                         "next_payment": (d.get("lastDividendValue") or 0) * p["qty"],
                         "yearly": d["dividendRate"] * p["qty"]})
    if rows:
        up = pd.DataFrame(rows).sort_values("ex_date", na_position="last")
        st.metric("Expected dividend income per year", usd(up["yearly"].sum()).replace("&#36;", "$"))
        st.dataframe(up, hide_index=True, width="stretch",
                     column_config={"symbol": "Symbol", "shares": "Shares", "ex_date": "Next ex-dividend date",
                                    "per_payment": st.column_config.NumberColumn("Per share", format="$%.4f"),
                                    "next_payment": st.column_config.NumberColumn("Next payment (est.)", format="$%.2f"),
                                    "yearly": st.column_config.NumberColumn("Per year (est.)", format="$%.2f")})
        st.caption("Estimates from the last dividend paid and the yearly rate; companies can change them. "
                   "Own the shares before the ex-dividend date to get the payment.")
    else:
        st.caption("None of your current holdings pay a dividend.")
    for name, err in errors.items():
        st.warning(f"{name} history unavailable: {err}")
    if "Interactive Brokers" in brokers:
        st.caption("Interactive Brokers only shares about a day of trades through IB Gateway and no dividends, so "
                   "use IBKR's own statements for its full history.")
    st.caption("For your records, not tax advice. Check your broker's 1099 for the official figures.")


def screen_plan():
    st.markdown("<div class='tk-name'>My trading plan</div><div class='muted'>Sent with every question to the AI "
                "(Ask AI, the morning brief), so its answers fit your goals, risk limits and rules. The risk numbers "
                "also set the defaults in \"Size by risk\" on the order card.</div>", unsafe_allow_html=True)
    p = profile.load()
    with st.form("plan"):
        values = {}
        for key, (label, hint, kind, _) in profile.FIELDS.items():
            if kind == "area":
                values[key] = st.text_area(label, p[key], placeholder=hint, height=80)
            elif kind == "number":
                values[key] = st.number_input(label, value=float(p[key] or 0), min_value=0.0, help=hint or None,
                                              step=1000.0 if key == "account_size" else 0.5)
            else:
                options = kind.split(":", 1)[1].split("|")
                values[key] = st.segmented_control(label, options, default=p[key] if p[key] in options else options[0])
        if st.form_submit_button("Save plan", type="primary"):
            profile.save(values)
            st.success("Saved. The AI will use it from your next question.")


def screen_cld():
    st.markdown("<div class='tk-name'>Connect Claude</div><div class='muted'>Sign in with your Claude subscription, "
                "the same way the Claude Code CLI does. Ask AI, the morning brief and headline sentiment then run on "
                "your subscription; no API key needed.</div>", unsafe_allow_html=True)
    st.write("")
    if not claude_code.binary():
        st.warning("Claude Code isn't installed here. It's included in the Home Assistant add-on; on a computer, "
                   "install Claude Code and sign in with `claude` in a terminal.")
        return
    status = claude_code.status(max_age=5)
    login = ss.get("claude_login")
    if status.get("loggedIn") and not (login and not login.done):
        who = status.get("email") or status.get("account", {}).get("email") or "your Claude account"
        st.success(f"Signed in as {who} ({status.get('subscriptionType') or status.get('authMethod')}).")
        st.markdown(f"<div class='muted'>The AI in this app is currently: <b style='color:#fff'>{ai.provider()}</b>."
                    "</div>", unsafe_allow_html=True)
        c = st.columns(2)
        if c[0].button("Test it", width="stretch"):
            with st.spinner("Asking Claude…"):
                try:
                    st.info(claude_code.ask("In one short sentence, confirm you're connected and ready to help "
                                            "with stock research.", "Answer in one sentence."))
                except Exception as e:
                    st.error(str(e))
        if c[1].button("Sign out", width="stretch"):
            claude_code.logout()
            ss.pop("claude_login", None)
            st.rerun()
        st.caption("Questions use your subscription's usage limits, the same pool as your normal Claude use. In "
                   "this app Claude can only answer and search the web; it can't run commands or change files.")
        return
    if not login or login.done:
        if login and login.done and login.result:
            (st.error if "error" in login.result.lower() or "fail" in login.result.lower() else st.info)(login.result)
        elif status.get("expired"):
            st.warning("Your Claude sign-in has expired, so Ask AI couldn't answer. Sign in again below.")
        if st.button("Sign in with Claude", type="primary"):
            ss.claude_login = claude_code.Login()
            st.rerun()
        return
    login_steps(login)


@st.fragment(run_every=2)
def login_steps(login):
    if login.done:
        claude_code.forget_status()
        st.rerun()
    if not login.url:
        st.caption("Starting sign-in…")
        return
    st.markdown("**1.** Open the sign-in page and approve access with your Claude account:")
    st.link_button("Open Claude sign-in", login.url, type="primary")
    st.markdown("**2.** Copy the code it shows you and paste it here:")
    c = st.columns([4, 1], vertical_alignment="bottom")
    code = c[0].text_input("Code", key="claude_code_input", label_visibility="collapsed", placeholder="Paste code")
    if c[1].button("Finish", width="stretch", disabled=not code.strip()):
        login.send_code(code)
        st.caption("Checking…")
    if st.button("Cancel"):
        login.cancel()
        ss.pop("claude_login", None)
        st.rerun(scope="app")
    if time.time() - login.started > 600:
        login.cancel()
        st.warning("Sign-in timed out. Start again.")


def screen_data():
    st.markdown("<div class='tk-name'>Data collection</div><div class='muted'>After each market close the app saves "
                "daily and minute prices, key statistics, financial statements and news to your own storage, so "
                "charts and backtests read your copy and nothing piles up on the Green.</div>", unsafe_allow_html=True)
    st.write("")
    if not store.enabled():
        st.info(f"Collection is off: {store.why_off()}.")
        st.markdown("""
**To turn it on (Home Assistant):** open the Trading Terminal add-on's **Configuration** tab and either

- **Cloud bucket** (Cloudflare R2, Backblaze B2, or a NAS with S3 support): set `store_type` to `s3` and fill in
  `s3_endpoint`, `s3_bucket`, `s3_access_key` and `s3_secret_key` from your provider, or
- **Network folder**: add a network share in *Settings > System > Storage* (usage: Share), set `store_type` to
  `folder` and `store_path` to `/share/trading_terminal`.

Save and restart the add-on. The first run downloads the history (several minutes); after that it runs each
weekday at about 4:35 PM New York time (2:35 PM Denver).
""")
        return
    st.success(f"Saving to {store.describe()}.")
    s = collector.status
    if s["running"]:
        st.info(f"Collecting now: {s['job'] or 'starting'} · {s['detail']}")
    c = st.columns([1, 1, 3])
    if c[0].button("Run now", disabled=s["running"], help="Collect today's data now instead of waiting for the "
                                                          "after-close run"):
        collector.run_now()
        st.rerun()
    if c[1].button("Test connection", help="Save and read back a tiny test file"):
        try:
            stamp = pd.Timestamp.now(tz="UTC").isoformat()
            store.write_json("collector/connection-test.json", {"checked": stamp})
            back = store._backend().get("collector/connection-test.json")
            if back and stamp in back.decode():
                st.success("Connection works: a test file was saved and read back. Look for a "
                           f"\"{os.getenv('S3_PREFIX', 'trading-terminal/')}collector\" folder in your bucket.")
            else:
                st.error("Saved a test file but couldn't read it back. Check the key has read access too.")
        except Exception as e:
            st.error(f"Storage refused the test: {type(e).__name__}: {e}")
            st.caption("Common causes: the key's ID and secret swapped or mistyped, the key not allowed to use this "
                       "bucket, the bucket name not matching exactly, or the endpoint's region not matching the "
                       "bucket's.")
    if s["last_error"]:
        st.warning(f"Last problem: {s['last_error']}")
    names = {"daily_prices": "Daily prices", "minute_prices": "Minute prices", "stats": "Key statistics",
             "financials": "Financial statements (weekly)", "news": "News"}
    try:
        runs, use = collector.last_runs(), store.usage()
    except Exception as e:
        st.error(f"Couldn't read the storage: {e}")
        return
    st.subheader("Last runs")
    rows = [{"What": names[j], "Last run": runs.get(j, {}).get("day", "never"),
             "Result": runs.get(j, {}).get("error") or runs.get(j, {}).get("result", ""),
             "Took": f"{runs[j]['seconds']}s" if runs.get(j, {}).get("seconds") is not None else ""}
            for j in collector.JOBS]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.subheader("What's stored")
    labels = {"prices/daily": "Daily prices", "prices/minute": "Minute prices", "stats": "Statistics snapshots",
              "financials": "Financial statements", "news": "News", "sentiment": "Headline sentiment",
              "collector": "Collector bookkeeping"}
    table = [{"Data": labels.get(k, k), "Files": n, "Size": f"{b / 1e6:,.1f} MB"} for k, (n, b) in use.items()]
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    total = sum(b for _, b in use.values())
    own = collector.own_symbols()
    st.caption(f"Total {total / 1e6:,.1f} MB. Collecting for the S&P 500 plus {len(own)} of your own stocks "
               f"(watchlists and holdings); minute prices and news for your own stocks only, minute history going "
               f"back {collector.minute_backfill_days()} days.")


def screen_help():
    st.subheader("Keyboard shortcuts")
    st.markdown("In the search box, type a ticker, a screen code, or both, then press Enter. "
                "Examples: `NVDA`, `GP`, `MSFT FA`, `PORT`.")
    st.dataframe(pd.DataFrame([(c, g, s) for g, items in NAV.items() for c, s in items.items()],
                              columns=["Code", "Section", "Screen"]), hide_index=True, width=520, height=668)
    st.caption(f"Mode: {config.MODE_LABEL}. Change TRADING_MODE in .env and restart to switch. "
               "Market data comes from Yahoo Finance and may be delayed.")


{"DES": screen_des, "GP": screen_gp, "FA": screen_fa, "N": screen_news, "ANR": screen_anr, "VAL": screen_val,
 "ERN": screen_ern, "SEC": screen_sec, "ECO": screen_eco, "MON": screen_mon,
 "SCR": screen_scr, "SPX": screen_spx, "OMON": screen_omon, "ALRT": screen_alrt, "PORT": screen_port, "ORD": screen_ord,
 "AI": screen_ai, "HELP": screen_help, "BT": screen_bt, "IDEA": screen_idea, "CAL": screen_cal, "PRED": screen_pred,
 "BRF": screen_brf, "JRNL": screen_jrnl, "GAIN": screen_gain, "PLAN": screen_plan, "CLD": screen_cld, "DATA": screen_data}[fn]()
earnings_reminders()  # last, so its first (slower) data fetch never holds up the screen
log_if_slow(f"page {fn} ({FUNCTIONS.get(fn, fn)}, {sym})", PAGE_STARTED)
