"""Market data from Yahoo Finance. No account needed; quotes can be delayed."""
from __future__ import annotations

import io
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import pandas as pd
import requests
import yfinance as yf

from . import cache, config, market, store, stream

SCREENS = {
    "Most active": "most_actives",
    "Day gainers": "day_gainers",
    "Day losers": "day_losers",
    "Undervalued growth": "undervalued_growth_stocks",
    "Undervalued large caps": "undervalued_large_caps",
    "Growth technology": "growth_technology_stocks",
    "Aggressive small caps": "aggressive_small_caps",
    "Small cap gainers": "small_cap_gainers",
}


SNAPSHOT_SECONDS = 5  # how long a REST snapshot is reused, to stay well inside Alpaca's rate limit
_snapshots: dict[str, tuple[float, dict | None]] = {}


@lru_cache(maxsize=1)
def _alpaca_data():
    from alpaca.data.historical import StockHistoricalDataClient

    return StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)


def live_prices(symbols: list[str]) -> dict[str, dict]:
    """Real-time last/bid/ask from Alpaca (IEX feed) for US stocks; {} if unavailable.

    Uses the background stream where it has a recent tick, and a REST snapshot
    (reused for a few seconds) for everything else.
    """
    if not (config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY):
        return {}
    stream.watch([s.replace("-", ".") for s in symbols])
    out, need, now = {}, [], time.time()
    for s in symbols:
        streamed = stream.get(s.replace("-", "."))
        memo = _snapshots.get(s)
        if streamed:
            out[s] = streamed
        elif memo and now - memo[0] < SNAPSHOT_SECONDS:
            if memo[1]:
                out[s] = memo[1]
        else:
            need.append(s)
    if need:
        try:
            from alpaca.data.requests import StockSnapshotRequest

            req = StockSnapshotRequest(symbol_or_symbols=[s.replace("-", ".") for s in need], feed="iex")
            snaps = _alpaca_data().get_stock_snapshot(req)
        except Exception:
            snaps = {}
        for s in need:
            snap = snaps.get(s.replace("-", "."))
            found = None
            if snap and snap.latest_trade:
                q = snap.latest_quote
                found = {
                    "last": snap.latest_trade.price,
                    "bid": q.bid_price if q else None,
                    "ask": q.ask_price if q else None,
                    "source": "Alpaca real-time",
                }
                out[s] = found
            _snapshots[s] = (now, found)
    return out


def with_live(q: dict) -> dict:
    """A cached quote refreshed with the latest real-time price, if one is available."""
    live = live_prices([q["symbol"]]).get(q["symbol"])
    if not live:
        return q
    q = {**q, **live}
    if q.get("prev_close"):
        q["change"] = q["last"] - q["prev_close"]
        q["change_pct"] = q["change"] / q["prev_close"] * 100
    return q


def option_expirations(symbol: str) -> list[str]:
    return list(yf.Ticker(symbol).options)


def option_chain(symbol: str, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(calls, puts) for one expiry. contractSymbol is the OCC symbol brokers trade."""
    chain = yf.Ticker(symbol).option_chain(expiry)
    cols = ["contractSymbol", "strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility", "inTheMoney"]
    live = _alpaca_option_quotes(symbol, expiry)
    return _with_option_quotes(chain.calls[cols], live), _with_option_quotes(chain.puts[cols], live)


def _alpaca_option_quotes(symbol: str, expiry: str) -> dict:
    """Bid/ask, implied vol and greeks per contract from Alpaca; {} if unavailable."""
    if not (config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY):
        return {}
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest

        client = OptionHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
        req = OptionChainRequest(underlying_symbol=symbol.replace("-", "."), expiration_date=pd.Timestamp(expiry).date())
        return client.get_option_chain(req)
    except Exception:
        return {}


def _with_option_quotes(df: pd.DataFrame, live: dict) -> pd.DataFrame:
    if not live:
        return df
    df = df.copy()
    snaps = [live.get(c) for c in df["contractSymbol"]]

    def pick(getter, fallback=None):
        vals = []
        for i, s in enumerate(snaps):
            try:
                v = getter(s)
            except AttributeError:
                v = None
            vals.append(v if v is not None else (fallback.iloc[i] if fallback is not None else None))
        return vals

    df["bid"] = pick(lambda s: s.latest_quote.bid_price, df["bid"])
    df["ask"] = pick(lambda s: s.latest_quote.ask_price, df["ask"])
    df["impliedVolatility"] = pick(lambda s: s.implied_volatility, df["impliedVolatility"])
    df["delta"] = pick(lambda s: s.greeks.delta)
    df["theta"] = pick(lambda s: s.greeks.theta)
    return df


def quote(symbol: str, live: dict | None = None) -> dict:
    fi = yf.Ticker(symbol).fast_info
    last, prev = fi.get("lastPrice"), fi.get("previousClose")
    live = live_prices([symbol]).get(symbol) if live is None else live.get(symbol)
    if live:
        last = live["last"]
    change = last - prev if last is not None and prev else None
    return {
        "source": live["source"] if live else "Yahoo (may be delayed)",
        "bid": live["bid"] if live else None,
        "ask": live["ask"] if live else None,
        "symbol": symbol,
        "last": last,
        "prev_close": prev,
        "change": change,
        "change_pct": change / prev * 100 if change is not None else None,
        "day_high": fi.get("dayHigh"),
        "day_low": fi.get("dayLow"),
        "volume": fi.get("lastVolume"),
        "market_cap": fi.get("marketCap"),
        "year_high": fi.get("yearHigh"),
        "year_low": fi.get("yearLow"),
        "currency": fi.get("currency"),
    }


def alpaca_symbol(s: str) -> bool:
    """US stocks and ETFs (Alpaca has them); indexes, futures, forex and crypto (^GSPC, ES=F, BTC-USD) don't."""
    return bool(s) and s.replace(".", "").replace("-", "").isalpha() and len(s) <= 6 and not s.endswith("-USD")


def daily_refs(symbols: list[str]) -> dict[str, dict]:
    """Previous close and today's open/high/low/volume per US symbol, from one Alpaca request for all of them
    (full-market daily bars, about 15 minutes behind on the free plan)."""
    today = pd.Timestamp.now(tz="America/New_York").date()
    out = {}
    for s, df in market.bars([s for s in symbols if alpaca_symbol(s)], "5d", "1d").items():
        if df.empty:
            continue
        is_today = df.index[-1].date() == today
        prev = df["Close"].iloc[-2] if is_today and len(df) > 1 else df["Close"].iloc[-1]
        bar = df.iloc[-1] if is_today else None
        out[s] = {"prev_close": float(prev), "close": float(df["Close"].iloc[-1]),
                  "open": float(bar["Open"]) if bar is not None else None,
                  "day_high": float(bar["High"]) if bar is not None else None,
                  "day_low": float(bar["Low"]) if bar is not None else None,
                  "volume": float(bar["Volume"]) if bar is not None else None}
    return out


def fast_quotes(symbols: list[str], refs: dict | None = None) -> dict[str, dict]:
    """Quotes for many symbols at once. US stocks and ETFs come from Alpaca in two requests in total (real-time
    last price over the daily bars); everything else (indexes, futures, forex, crypto) from Yahoo, side by side.
    Pass `refs` from daily_refs() to reuse them (they change slowly)."""
    us = [s for s in symbols if alpaca_symbol(s)]
    refs = daily_refs(us) if refs is None else refs
    live = live_prices([s for s in us if s in refs])
    out = {}
    for s in us:
        r = refs.get(s)
        if not r:
            continue
        lv = live.get(s, {})
        last = lv.get("last") or r["close"]
        chg = last - r["prev_close"] if r["prev_close"] else None
        out[s] = {"symbol": s, **r, "last": last, "bid": lv.get("bid"), "ask": lv.get("ask"), "change": chg,
                  "change_pct": chg / r["prev_close"] * 100 if chg is not None else None,
                  "source": lv.get("source", "Alpaca")}
    rest = [s for s in symbols if s not in out]

    def one(s):
        try:
            return quote(s, {})
        except Exception:
            return None

    if rest:
        with ThreadPoolExecutor(min(8, len(rest))) as pool:
            for s, q in zip(rest, pool.map(one, rest)):
                if q and q.get("last") is not None:
                    out[s] = q
    return out


def quotes(symbols: list[str]) -> pd.DataFrame:
    live = live_prices(symbols)

    def one(s):
        try:
            return quote(s, live)
        except Exception:
            return {"symbol": s}

    with ThreadPoolExecutor(8) as pool:  # each quote is a separate Yahoo request
        return pd.DataFrame(list(pool.map(one, symbols)))


def history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    if interval == "1d" and store.enabled():  # your own collected history first (see collector.py)
        df = _stored_daily(symbol, period)
        if df is not None:
            return df
    df = market.history(symbol, period, interval)  # Alpaca: official and quick
    if not df.empty:
        return df
    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
    return df[["Open", "High", "Low", "Close", "Volume"]] if not df.empty else df


PERIOD_DAYS = {"5d": 7, "1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731, "5y": 1827, "10y": 3653}


def _stored_daily(symbol: str, period: str) -> pd.DataFrame | None:
    """Daily bars from the collected store, topped up with the days since the last collection.
    None when the store doesn't cover the requested period (the caller then asks Alpaca/Yahoo)."""
    try:
        df = store.read(f"prices/daily/{symbol}.parquet")
    except Exception:
        return None
    if df is None or df.empty:
        return None
    now = pd.Timestamp.now(tz="America/New_York")
    if period == "ytd":
        start = pd.Timestamp(now.year, 1, 1, tz="America/New_York")
    elif period == "max":
        start = df.index.min()
    elif period in PERIOD_DAYS:
        start = now - pd.Timedelta(days=PERIOD_DAYS[period])
    else:
        return None
    if df.index.min() > start + pd.Timedelta(days=7):  # store doesn't go back far enough
        return None
    if (now.normalize() - df.index.max()).days >= 1:  # add days since the last collection
        recent = market.history(symbol, "1mo", "1d")
        if not recent.empty:
            recent.index = recent.index.normalize()
            df = pd.concat([df, recent[recent.index > df.index.max()]])
    return df[df.index >= start]


def info(symbol: str) -> dict:
    """Company profile and key statistics. Finnhub answers quickly; Yahoo's fuller (but slow) profile
    is fetched in the background and fills in the rest (description, employees, targets...) once saved."""
    base = cache.latest(f"fh-{symbol}", lambda: market.fundamentals(symbol), 3600) if config.FINNHUB_API_KEY else {}
    extra = cache.get(f"yinfo-{symbol}", lambda: yf.Ticker(symbol).info or {}, 24 * 3600)[0]
    if extra is None and not (base or {}).get("longName"):  # Finnhub has no profile (no key, or a fund)
        extra = yf.Ticker(symbol).info or {}
    return {**(base or {}), **{k: v for k, v in (extra or {}).items() if v not in (None, "", [])}}


def news(symbol: str, limit: int = 20) -> list[dict]:
    items = market.news(symbol, limit)  # Alpaca (Benzinga) first
    if items:
        return items
    # Yahoo: Ticker.news currently returns nothing; the search endpoint still serves headlines.
    for c in yf.Search(symbol, news_count=limit).news or []:
        ts = c.get("providerPublishTime")
        thumbs = (c.get("thumbnail") or {}).get("resolutions") or []
        items.append(
            {
                "thumb": next((t["url"] for t in thumbs if t.get("tag") == "140x140"), None),
                "title": c.get("title"),
                "publisher": c.get("publisher"),
                "published": pd.Timestamp(ts, unit="s").strftime("%Y-%m-%d %H:%M") if ts else None,
                "summary": c.get("summary"),
                "url": c.get("link"),
            }
        )
    return [i for i in items if i["title"]]


def financials(symbol: str, statement: str = "income", quarterly: bool = False) -> pd.DataFrame:
    """Statement with rows = line items, columns = period end dates. SEC filings first (about 15 years,
    official); Yahoo (4-5 periods) for companies that don't file with the SEC."""
    from . import sources

    try:
        df = cache.latest(f"sec-{symbol}-{statement}-{int(quarterly)}",
                          lambda: sources.sec_statements(symbol, statement, quarterly), 24 * 3600)
        if df is not None and not df.empty:
            df.attrs["source"] = "SEC filings"
            return df
    except Exception:
        pass
    t = yf.Ticker(symbol)
    df = {
        "income": t.quarterly_income_stmt if quarterly else t.income_stmt,
        "balance": t.quarterly_balance_sheet if quarterly else t.balance_sheet,
        "cashflow": t.quarterly_cashflow if quarterly else t.cashflow,
    }[statement]
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c) for c in df.columns]
    return df


def recommendations(symbol: str) -> pd.DataFrame:
    df = market.recommendations(symbol)  # Finnhub first
    if not df.empty:
        return df
    df = yf.Ticker(symbol).recommendations
    return df if df is not None else pd.DataFrame()


def sparklines(symbols: list[str]) -> dict[str, list[float]]:
    """Today's intraday closes per symbol (last 5 days at 30 min if today has no bars yet)."""
    out: dict[str, list[float]] = {}
    for s, df in market.bars(list(symbols), "1d", "5m").items():  # Alpaca: all symbols in one request
        vals = df["Close"].dropna().round(4).tolist()
        if len(vals) > 1:
            out[s] = vals
    for period, interval in (("1d", "5m"), ("5d", "30m")):
        need = [s for s in symbols if s not in out]
        if not need:
            break
        try:
            px = yf.download(need, period=period, interval=interval, auto_adjust=True, progress=False)["Close"]
        except Exception:
            continue
        for s in need:
            if s in px.columns:
                vals = px[s].dropna().round(4).tolist()
                if len(vals) > 1:
                    out[s] = vals
    return out


def sp500_scan() -> pd.DataFrame:
    """Every S&P 500 member with price momentum, trend and valuation measures (~30s)."""
    with ThreadPoolExecutor(1) as pool:
        fundamentals = pool.submit(_bulk_fundamentals)  # independent of the price download, so overlap them
        html = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers={"User-Agent": "Mozilla/5.0 trading-terminal"},
            timeout=20,
        ).text
        members = pd.read_html(io.StringIO(html))[0]
        members["symbol"] = members["Symbol"].str.replace(".", "-", regex=False)
        symbols = list(members["symbol"])
        got = market.bars(symbols, "1y", "1d")  # Alpaca: the whole index in a few requests
        px = pd.DataFrame({s: b["Close"] for s, b in got.items()})
        missing = [s for s in symbols if s not in px.columns]
        if missing:  # anything Alpaca didn't have (or everything, without Alpaca keys) comes from Yahoo
            extra = yf.download(missing, period="1y", interval="1d", auto_adjust=True, progress=False, threads=True)["Close"]
            if isinstance(extra, pd.Series):
                extra = extra.to_frame(missing[0])
            if not px.empty:
                extra.index = pd.DatetimeIndex(extra.index).tz_localize(px.index.tz) if extra.index.tz is None else extra.index.tz_convert(px.index.tz)
                extra.index = extra.index.normalize()
                px.index = px.index.normalize()
            px = extra if px.empty else px.join(extra, how="outer")
        px = px.sort_index().dropna(axis=1, how="all").ffill()
        try:
            fund = fundamentals.result()
        except Exception:
            fund = None  # valuation columns are a bonus; the price scan still stands without them

    last = px.iloc[-1]
    delta = px.diff()
    gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]

    def ret(days: int) -> pd.Series:
        return (last / px.iloc[-1 - days] - 1) * 100

    stats = pd.DataFrame(
        {
            "last": last,
            "chg_1d": ret(1),
            "chg_1m": ret(21),
            "chg_3m": ret(63),
            "chg_1y": (last / px.bfill().iloc[0] - 1) * 100,
            "from_high": (last / px.max() - 1) * 100,
            "rsi": 100 - 100 / (1 + gain / loss),
            "above_50d": last > px.rolling(50).mean().iloc[-1],
            "above_200d": last > px.rolling(200).mean().iloc[-1],
        }
    )
    out = members[["symbol", "Security", "GICS Sector"]].rename(columns={"Security": "name", "GICS Sector": "sector"})
    out = out.merge(stats, left_on="symbol", right_index=True)
    if fund is not None:
        out = out.merge(fund, on="symbol", how="left")
    return out.reset_index(drop=True)


def _bulk_fundamentals() -> pd.DataFrame:
    """Valuation fields for every large US-listed stock, a page of 250 at a time."""
    from yfinance import EquityQuery as Q

    query = Q("and", [Q("eq", ["region", "us"]), Q("is-in", ["exchange", "NMS", "NYQ"]), Q("gt", ["intradaymarketcap", 5e9])])
    rows: list[dict] = []
    for page in range(10):
        quotes = yf.screen(query, size=250, offset=page * 250, sortField="intradaymarketcap", sortAsc=False).get("quotes", [])
        rows += quotes
        if len(quotes) < 250:
            break
    df = pd.DataFrame(rows).drop_duplicates("symbol")
    cols = {
        "symbol": "symbol",
        "marketCap": "market_cap",
        "trailingPE": "pe",
        "forwardPE": "fwd_pe",
        "priceToBook": "pb",
        "dividendYield": "div_yield",
        "averageAnalystRating": "analyst_rating",
    }
    return df[[c for c in cols if c in df.columns]].rename(columns=cols)


def screen(name: str, count: int = 50) -> pd.DataFrame:
    res = yf.screen(SCREENS.get(name, name), count=count)
    cols = {
        "symbol": "symbol",
        "shortName": "name",
        "regularMarketPrice": "last",
        "regularMarketChangePercent": "change_pct",
        "regularMarketVolume": "volume",
        "marketCap": "market_cap",
        "trailingPE": "pe",
        "forwardPE": "fwd_pe",
        "epsTrailingTwelveMonths": "eps",
        "fiftyTwoWeekChangePercent": "chg_52w_pct",
        "averageAnalystRating": "analyst_rating",
    }
    df = pd.DataFrame(res.get("quotes", []))
    keep = [c for c in cols if c in df.columns]
    return df[keep].rename(columns=cols)
