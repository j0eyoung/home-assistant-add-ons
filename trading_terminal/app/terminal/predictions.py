"""Prediction-market odds from Kalshi and Polymarket public APIs (read-only, no account needed).

Both APIs are read defensively: field names have changed over time (e.g. Kalshi prices in cents
vs "_dollars" strings), so each value is looked up under every name we know about.
"""
from __future__ import annotations

import json

import requests

from . import config

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
POLY = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "Mozilla/5.0 trading-terminal"}

TOPICS = {
    "Fed & rates": ["fed ", "fed's", "federal reserve", "fomc", "interest rate", "rate cut", "rate hike", "powell"],
    "Inflation": ["cpi", "inflation", "pce"],
    "Economy & jobs": ["recession", "gdp", "unemployment", "jobs", "payroll", "jobless"],
    "Markets": ["s&p", "nasdaq", "dow ", "stock market", "bitcoin", "oil", "gold", "treasury", "10-year"],
}


FORECAST_PATH = config.DATA_DIR / "forecastex.json"
DEFAULT_FORECAST_PRODUCTS = ["FF"]  # FF = US Fed Funds target rate; more codes are listed in IBKR ForecastTrader


def forecast_products() -> list[str]:
    try:
        return json.loads(FORECAST_PATH.read_text()) or DEFAULT_FORECAST_PRODUCTS
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_FORECAST_PRODUCTS


def set_forecast_products(codes: list[str]) -> None:
    FORECAST_PATH.parent.mkdir(parents=True, exist_ok=True)
    FORECAST_PATH.write_text(json.dumps([c.strip().upper() for c in codes if c.strip()]))


def _get(url: str, **params):
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def _num(*values) -> float | None:
    for v in values:
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _kalshi_prob(m: dict) -> float | None:
    """0-1 chance of Yes: bid/ask midpoint if both are quoted, else the last trade."""
    bid = _num(m.get("yes_bid_dollars")) or ((_num(m.get("yes_bid")) or 0) / 100 or None)
    ask = _num(m.get("yes_ask_dollars")) or ((_num(m.get("yes_ask")) or 0) / 100 or None)
    if bid and ask and ask >= bid:
        return (bid + ask) / 2
    last = _num(m.get("last_price_dollars"))
    if last is None and _num(m.get("last_price")) is not None:
        last = _num(m.get("last_price")) / 100
    return last


def kalshi_events(pages: int = 5) -> list[dict]:
    out, cursor = [], None
    for _ in range(pages):
        params = {"status": "open", "with_nested_markets": "true", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        page = _get(f"{KALSHI}/events", **params)
        for e in page.get("events", []):
            outcomes = []
            for m in e.get("markets") or []:
                p = _kalshi_prob(m)
                if p is not None:
                    label = m.get("yes_sub_title") or m.get("subtitle") or m.get("title") or m.get("ticker")
                    outcomes.append((label, p, _num(m.get("volume"), m.get("volume_fp")) or 0))
            if outcomes:
                series = e.get("series_ticker") or (e.get("event_ticker") or "").split("-")[0]
                out.append({
                    "source": "Kalshi", "title": e.get("title") or "", "subtitle": e.get("sub_title") or "",
                    "category": e.get("category") or "", "volume": sum(o[2] for o in outcomes),
                    "outcomes": sorted(((o[0], o[1]) for o in outcomes), key=lambda o: -o[1]),
                    "url": f"https://kalshi.com/markets/{series.lower()}" if series else "https://kalshi.com",
                })
        cursor = page.get("cursor")
        if not cursor:
            break
    return out


def polymarket_events(limit: int = 300) -> list[dict]:
    out = []
    rows = _get(f"{POLY}/events", closed="false", active="true", limit=limit, order="volume24hr", ascending="false")
    for e in rows if isinstance(rows, list) else []:
        outcomes = []
        for m in e.get("markets") or []:
            try:
                names = json.loads(m.get("outcomes") or "[]")
                prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except (TypeError, ValueError):
                continue
            if not prices or m.get("closed"):
                continue
            if len(names) == 2 and names[0].lower() == "yes":  # yes/no market: one outcome per question
                outcomes.append((m.get("groupItemTitle") or m.get("question") or "Yes", prices[0]))
            else:
                outcomes += list(zip(names, prices))
        if outcomes:
            out.append({
                "source": "Polymarket", "title": e.get("title") or "", "subtitle": "",
                "category": ", ".join(t.get("label", "") for t in (e.get("tags") or [])[:3]),
                "volume": _num(e.get("volume")) or 0, "outcomes": sorted(outcomes, key=lambda o: -o[1]),
                "url": f"https://polymarket.com/event/{e.get('slug', '')}",
            })
    return out


def all_events() -> tuple[list[dict], dict[str, str]]:
    """(events from every source that answered, {source: error} for the ones that did not)."""
    events, errors = [], {}
    for name, fn in (("Kalshi", kalshi_events), ("Polymarket", polymarket_events)):
        try:
            events += fn()
        except requests.exceptions.SSLError:
            errors[name] = "the connection was cut during the secure handshake; this network appears to block the site"
        except Exception as e:
            errors[name] = str(e)[:200]
    return events, errors


def matching(events: list[dict], topic: str | None = None, query: str = "") -> list[dict]:
    words = TOPICS.get(topic or "", [])
    q = query.strip().lower()

    def hit(e):
        text = f" {e['title']} {e['subtitle']} {e['category']} ".lower()
        return (not words or any(w in text for w in words)) and (not q or q in text)

    return sorted((e for e in events if hit(e)), key=lambda e: -e["volume"])
