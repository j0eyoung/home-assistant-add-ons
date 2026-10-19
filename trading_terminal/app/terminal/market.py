"""Official, free data APIs used ahead of Yahoo: Alpaca (prices, news) and Finnhub (company data).

Every function returns empty (DataFrame / dict / list) when its source can't help, and the caller
in data.py falls back to Yahoo.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import pandas as pd

from . import config

NY = "America/New_York"
SIP_DELAY = dt.timedelta(minutes=16)  # the free plan excludes the latest 15 minutes of full-market data


def _alpaca_ok() -> bool:
    return bool(config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY)


@lru_cache(maxsize=1)
def _client():
    from alpaca.data.historical import StockHistoricalDataClient

    return StockHistoricalDataClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)


def _to_alpaca(s: str) -> str:
    return s.replace("-", ".")


def _from_alpaca(s: str) -> str:
    return s.replace(".", "-")


def _timeframe(interval: str):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    return {
        "5m": TimeFrame(5, TimeFrameUnit.Minute), "15m": TimeFrame(15, TimeFrameUnit.Minute),
        "30m": TimeFrame(30, TimeFrameUnit.Minute), "1h": TimeFrame(1, TimeFrameUnit.Hour),
        "1d": TimeFrame.Day, "1wk": TimeFrame.Week, "1mo": TimeFrame.Month,
    }.get(interval)


def _start(period: str, now: dt.datetime) -> dt.datetime | None:
    days = {"1d": 5, "5d": 9, "1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731, "5y": 1827, "10y": 3653}
    if period == "ytd":
        return dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc)
    return now - dt.timedelta(days=days[period]) if period in days else None


def _fetch(symbols: list[str], timeframe, start, end, feed):
    from alpaca.data.enums import Adjustment
    from alpaca.data.requests import StockBarsRequest

    req = StockBarsRequest(symbol_or_symbols=[_to_alpaca(s) for s in symbols], timeframe=timeframe, start=start,
                           end=end, feed=feed, adjustment=Adjustment.ALL)
    return _client().get_stock_bars(req).df


def bars(symbols: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    """{symbol: OHLCV DataFrame indexed in New York time}, Yahoo-style columns. {} if unavailable."""
    from alpaca.data.enums import DataFeed

    tf, now = _timeframe(interval), dt.datetime.now(dt.timezone.utc)
    start = _start(period, now)
    if not (_alpaca_ok() and tf and start and symbols):
        return {}
    intraday = interval.endswith(("m", "h"))
    cut = now - SIP_DELAY
    try:
        frames = [_fetch(symbols, tf, start, cut, DataFeed.SIP)]
        if intraday:  # stitch in the latest minutes from the free real-time (IEX) feed
            frames.append(_fetch(symbols, tf, cut, None, DataFeed.IEX))
    except Exception:
        return {}
    df = pd.concat([f for f in frames if f is not None and not f.empty])
    if df.empty:
        return {}
    df = df[~df.index.duplicated(keep="first")]
    out = {}
    for sym, g in df.groupby(level="symbol"):
        g = g.droplevel("symbol").sort_index()
        g.index = pd.DatetimeIndex(g.index).tz_convert(NY)
        if intraday:
            t = g.index.hour * 60 + g.index.minute
            g = g[(t >= 9 * 60 + 30) & (t < 16 * 60)]  # regular session only, like Yahoo's default
            days = sorted(set(g.index.date))
            keep = {"1d": 1, "5d": 5}.get(period)
            if keep:
                g = g[[d in days[-keep:] for d in g.index.date]]
        g = g.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
        out[_from_alpaca(sym)] = g
    return out


def history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return bars([symbol], period, interval).get(symbol, pd.DataFrame())


def news(symbol: str, limit: int = 20) -> list[dict]:
    if not _alpaca_ok():
        return []
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.requests import NewsRequest

    try:
        res = NewsClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY).get_news(
            NewsRequest(symbols=_to_alpaca(symbol), limit=limit))
    except Exception:
        return []
    items = res.data.get("news", []) if hasattr(res, "data") else getattr(res, "news", [])
    out = []
    for a in items:
        imgs = {str(getattr(i.size, "value", i.size)): i.url for i in (a.images or [])}
        out.append({
            "thumb": imgs.get("thumb") or imgs.get("small"), "title": a.headline,
            "publisher": (a.source or "").replace("benzinga", "Benzinga"),
            "published": pd.Timestamp(a.created_at).tz_convert("UTC").strftime("%Y-%m-%d %H:%M"),
            "summary": a.summary or None, "url": a.url,
        })
    return [i for i in out if i["title"] and i["url"]]


# ---------- Finnhub company data, mapped onto the Yahoo field names the screens already use ----------
def _pct(v):
    return v / 100 if isinstance(v, (int, float)) else None


def fundamentals(symbol: str) -> dict:
    if not config.FINNHUB_API_KEY:
        return {}
    from . import sources

    try:
        p = sources._finnhub("/stock/profile2", symbol=symbol) or {}
        m = (sources._finnhub("/stock/metric", symbol=symbol, metric="all") or {}).get("metric") or {}
    except Exception:
        return {}
    if not p and not m:
        return {}
    shares = (p.get("shareOutstanding") or 0) * 1e6
    num = lambda k: m.get(k) if isinstance(m.get(k), (int, float)) else None
    out = {
        "longName": p.get("name"), "shortName": p.get("name"), "industry": p.get("finnhubIndustry"),
        "country": p.get("country"), "website": p.get("weburl"), "currency": p.get("currency"),
        "exchange": p.get("exchange"), "logo_url": p.get("logo"),
        "marketCap": p["marketCapitalization"] * 1e6 if p.get("marketCapitalization") else None,
        "enterpriseValue": num("enterpriseValue") * 1e6 if num("enterpriseValue") else None,
        "trailingPE": num("peTTM"), "forwardPE": num("forwardPE"), "priceToSalesTrailing12Months": num("psTTM"),
        "priceToBook": num("pb"), "enterpriseToEbitda": num("evEbitdaTTM"),
        "grossMargins": _pct(num("grossMarginTTM")), "operatingMargins": _pct(num("operatingMarginTTM")),
        "profitMargins": _pct(num("netProfitMarginTTM")), "returnOnEquity": _pct(num("roeTTM")),
        "revenueGrowth": _pct(num("revenueGrowthTTMYoy")), "earningsGrowth": _pct(num("epsGrowthTTMYoy")),
        "debtToEquity": num("totalDebt/totalEquityQuarterly") * 100 if num("totalDebt/totalEquityQuarterly") is not None else None,
        "dividendYield": num("dividendYieldIndicatedAnnual"), "dividendRate": num("dividendIndicatedAnnual"),
        "beta": num("beta"), "trailingEps": num("epsTTM"),
        "averageVolume": num("3MonthAverageTradingVolume") * 1e6 if num("3MonthAverageTradingVolume") else None,
        "totalRevenue": num("revenuePerShareTTM") * shares if num("revenuePerShareTTM") and shares else None,
        "fiftyTwoWeekHigh": num("52WeekHigh"), "fiftyTwoWeekLow": num("52WeekLow"),
    }
    if out["marketCap"] and num("pfcfShareTTM"):  # price / free cash flow -> free cash flow
        out["freeCashflow"] = out["marketCap"] / num("pfcfShareTTM")
    return {k: v for k, v in out.items() if v not in (None, "")}


def recommendations(symbol: str) -> pd.DataFrame:
    """Analyst rating counts by month, newest first, with Yahoo-style period labels (0m, -1m, ...)."""
    if not config.FINNHUB_API_KEY:
        return pd.DataFrame()
    from . import sources

    try:
        rows = sources._finnhub("/stock/recommendation", symbol=symbol) or []
    except Exception:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("period", ascending=False).head(4).reset_index(drop=True)
    df["period"] = ["0m" if i == 0 else f"-{i}m" for i in range(len(df))]
    return df[["period", "strongBuy", "buy", "hold", "sell", "strongSell"]]
