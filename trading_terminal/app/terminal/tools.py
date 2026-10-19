"""Read-only research tools for the AI (served by mcp_server.py). None of them can place, change or
cancel an order. Every function returns plain JSON-friendly data, kept compact so answers stay fast.

Symbols follow Yahoo's style, which covers every asset class:
  stocks / ETFs: AAPL, SPY, BRK-B · indexes: ^GSPC, ^IXIC, ^DJI, ^RUT, ^VIX, ^TNX (10y yield)
  futures: ES=F (S&P 500), NQ=F, CL=F (crude), GC=F (gold), ZN=F (10y note) · forex: EURUSD=X · crypto: BTC-USD
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from . import backtest as bt
from . import cache, config, data, gains, journal, predictions, profile, sources, watchlists
from . import indicators as ind


# ---------- helpers ----------
def _clean(v):
    """JSON-safe scalars: NaN/inf -> None, numpy -> python, timestamps -> ISO strings, floats rounded."""
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) or math.isinf(v) else round(float(v), 4)
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(v))
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def _records(df: pd.DataFrame, limit: int | None = None) -> list[dict]:
    if df is None or df.empty:
        return []
    if limit:
        df = df.head(limit)
    return [_clean(r) for r in df.to_dict("records")]


def _sym(s: str) -> str:
    return s.strip().upper()


# ---------- quotes & prices (any asset class) ----------
def get_quote(symbols: str) -> list[dict]:
    """Latest price, change, day range, volume, market cap and 52-week range. `symbols` is comma-separated
    and can mix stocks, ETFs, indexes, futures, forex and crypto (e.g. "AAPL, ES=F, ^VIX, BTC-USD")."""
    from concurrent.futures import ThreadPoolExecutor

    def one(s):
        try:
            q = data.with_live(data.quote(s))
            return _clean({k: q.get(k) for k in ("symbol", "last", "change", "change_pct", "prev_close", "day_low",
                                                 "day_high", "volume", "market_cap", "year_low", "year_high",
                                                 "currency", "bid", "ask", "source")})
        except Exception as e:
            return {"symbol": s, "error": str(e)[:200]}

    syms = [_sym(x) for x in symbols.split(",") if x.strip()][:40]
    with ThreadPoolExecutor(10) as pool:  # one request per symbol, so fetch them side by side
        return list(pool.map(one, syms))


def get_price_history(symbol: str, period: str = "1y", interval: str = "1d", max_rows: int = 120) -> dict:
    """OHLCV history plus a summary (return, high/low, volatility, max drawdown). period: 1d 5d 1mo 3mo 6mo ytd
    1y 2y 5y 10y max. interval: 5m 15m 30m 1h 1d 1wk 1mo. Long ranges are thinned to about `max_rows` rows."""
    s = _sym(symbol)
    df = data.history(s, period, interval)
    if df.empty:
        return {"symbol": s, "error": "no price history for this symbol / range"}
    c = df["Close"]
    rets = c.pct_change().dropna()
    per_year = {"1d": 252, "1wk": 52, "1mo": 12}.get(interval, 252 * 78)
    summary = {
        "start": str(df.index[0]), "end": str(df.index[-1]), "bars": len(df),
        "first_close": c.iloc[0], "last_close": c.iloc[-1], "return_pct": (c.iloc[-1] / c.iloc[0] - 1) * 100,
        "high": df["High"].max(), "low": df["Low"].min(),
        "annualized_volatility_pct": rets.std() * math.sqrt(per_year) * 100 if len(rets) > 2 else None,
        "max_drawdown_pct": (c / c.cummax() - 1).min() * 100,
        "avg_volume": df["Volume"].mean(),
    }
    step = max(1, math.ceil(len(df) / max_rows))
    thin = df.iloc[::step]
    if thin.index[-1] != df.index[-1]:
        thin = pd.concat([thin, df.iloc[[-1]]])
    rows = thin.reset_index().rename(columns={thin.index.name or "index": "time"})
    rows["time"] = rows.iloc[:, 0].astype(str)
    return {"symbol": s, "summary": _clean(summary), "bars_shown_every": step,
            "bars": _records(rows[["time", "Open", "High", "Low", "Close", "Volume"]].round(4))}


def get_technicals(symbol: str) -> dict:
    """Latest technical picture on daily data: moving averages and trend, RSI(14), MACD, Bollinger bands,
    position in the 52-week range, recent returns and volume versus average."""
    s = _sym(symbol)
    df = data.history(s, "2y", "1d")
    if len(df) < 60:
        return {"symbol": s, "error": "not enough daily history"}
    c, v = df["Close"], df["Volume"]
    last = c.iloc[-1]
    macd, sig, hist = ind.macd(c)
    lo, mid, hi = ind.bollinger(c)
    yr = c.iloc[-252:]
    ret = lambda n: (last / c.iloc[-1 - n] - 1) * 100 if len(c) > n else None
    sma = {n: ind.sma(c, n).iloc[-1] for n in (20, 50, 200)}
    return {"symbol": s, "as_of": str(df.index[-1].date()), "close": _clean(last),
            **_clean({
                "sma20": sma[20], "sma50": sma[50], "sma200": sma[200],
                "above_sma50": last > sma[50], "above_sma200": last > sma[200],
                "golden_cross_50_over_200": sma[50] > sma[200],
                "rsi14": ind.rsi(c).iloc[-1], "macd": macd.iloc[-1], "macd_signal": sig.iloc[-1],
                "macd_histogram": hist.iloc[-1], "bollinger_lower": lo.iloc[-1], "bollinger_upper": hi.iloc[-1],
                "pct_of_52w_range": (last - yr.min()) / (yr.max() - yr.min()) * 100 if yr.max() > yr.min() else None,
                "high_52w": yr.max(), "low_52w": yr.min(),
                "return_1w_pct": ret(5), "return_1m_pct": ret(21), "return_3m_pct": ret(63), "return_1y_pct": ret(252),
                "volume_vs_50d_avg": v.iloc[-1] / v.iloc[-50:].mean() if v.iloc[-50:].mean() else None,
                "volatility_20d_annualized_pct": c.pct_change().iloc[-20:].std() * math.sqrt(252) * 100,
            })}


def get_intraday(symbol: str, date: str = "") -> dict:
    """Minute-by-minute prices for one trading day (from your collected data when available, otherwise the
    last session at 5-minute bars). date: YYYY-MM-DD, empty = most recent session."""
    from . import store

    s = _sym(symbol)
    if date and store.enabled():
        try:
            m = store.read(f"prices/minute/{s}/{date[:7]}.parquet")
            if m is not None:
                day = m[m.index.strftime("%Y-%m-%d") == date]
                if not day.empty:
                    five = day.resample("5min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last",
                                                     "Volume": "sum"}).dropna()
                    return {"symbol": s, "date": date, "source": "your collected minute data (5-min summary)",
                            "bars": _records(five.reset_index().assign(time=lambda d: d.iloc[:, 0].astype(str))
                                             [["time", "Open", "High", "Low", "Close", "Volume"]])}
        except Exception:
            pass
    return get_price_history(s, "1d", "5m", max_rows=80)


def get_market_overview() -> dict:
    """Snapshot across markets: major indexes and VIX, index futures, Treasury yields, the dollar,
    commodities, bitcoin, and the 11 S&P sector ETFs (sorted by today's move)."""
    groups = {
        "indexes": "^GSPC,^IXIC,^DJI,^RUT,^VIX",
        "index_futures": "ES=F,NQ=F,YM=F,RTY=F",
        "rates": "^IRX,^FVX,^TNX,^TYX",
        "dollar_fx": "DX-Y.NYB,EURUSD=X,USDJPY=X,GBPUSD=X",
        "commodities": "CL=F,BZ=F,NG=F,GC=F,SI=F,HG=F",
        "crypto": "BTC-USD,ETH-USD",
        "sectors": "XLK,XLF,XLV,XLY,XLP,XLE,XLI,XLB,XLU,XLRE,XLC",
    }
    quotes = {q["symbol"]: q for q in get_quote(",".join(groups.values()))}  # one parallel batch
    out = {k: [{x: quotes.get(s, {}).get(x) for x in ("symbol", "last", "change_pct")} | {"symbol": s}
               for s in v.split(",")] for k, v in groups.items()}
    out["sectors"].sort(key=lambda r: -(r.get("change_pct") or 0))
    out["note"] = "^IRX/^FVX/^TNX/^TYX are 13-week, 5-, 10- and 30-year Treasury yields in percent."
    return out


def get_futures_overview() -> list[dict]:
    """Main US futures: equity index, energy, metals, Treasuries, grains, currencies and bitcoin."""
    return get_quote("ES=F,NQ=F,YM=F,RTY=F,CL=F,NG=F,RB=F,GC=F,SI=F,HG=F,PL=F,ZT=F,ZF=F,ZN=F,ZB=F,"
                     "ZC=F,ZS=F,ZW=F,LE=F,6E=F,6J=F,6B=F,BTC=F")


# ---------- companies ----------
PROFILE_KEYS = ["longName", "quoteType", "sector", "industry", "country", "website", "fullTimeEmployees",
                "marketCap", "enterpriseValue", "trailingPE", "forwardPE", "pegRatio", "trailingPegRatio",
                "priceToSalesTrailing12Months", "priceToBook", "enterpriseToEbitda", "totalRevenue",
                "revenueGrowth", "earningsGrowth", "grossMargins", "operatingMargins", "profitMargins",
                "returnOnEquity", "returnOnAssets", "freeCashflow", "totalCash", "totalDebt", "debtToEquity",
                "currentRatio", "dividendYield", "dividendRate", "payoutRatio", "exDividendDate", "beta",
                "sharesOutstanding", "floatShares", "shortPercentOfFloat", "shortRatio", "heldPercentInsiders",
                "heldPercentInstitutions", "averageVolume", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
                "targetMeanPrice", "targetLowPrice", "targetHighPrice", "recommendationKey",
                "numberOfAnalystOpinions", "trailingEps", "forwardEps"]


def get_company_profile(symbol: str) -> dict:
    """Business description plus key statistics: valuation multiples, growth, margins, returns, balance
    sheet, dividend, ownership, short interest and analyst targets. Margins/growth are fractions (0.25 = 25%)."""
    s = _sym(symbol)
    i = data.info(s)
    if not i:
        return {"symbol": s, "error": "no profile found"}
    out = {"symbol": s, "description": (i.get("longBusinessSummary") or "")[:1500]}
    out.update({k: _clean(i.get(k)) for k in PROFILE_KEYS if i.get(k) not in (None, "")})
    if out.get("exDividendDate"):
        out["exDividendDate"] = str(pd.Timestamp(out["exDividendDate"], unit="s").date())
    return out


def get_financial_statements(symbol: str, statement: str = "income", quarterly: bool = False, periods: int = 8) -> dict:
    """Income statement, balance sheet or cash flow (statement: income | balance | cashflow) from SEC filings,
    newest period first. Annual goes back about 15 years; quarterly about 12 quarters. Values in USD."""
    s = _sym(symbol)
    df = data.financials(s, statement, quarterly)
    if df.empty:
        return {"symbol": s, "error": "no statements found"}
    df = df.iloc[:, :max(1, min(periods, 15))]
    return {"symbol": s, "statement": statement, "quarterly": quarterly,
            "source": df.attrs.get("source", "Yahoo Finance"),
            "lines": {str(row): {str(col): _clean(v) for col, v in df.loc[row].items()} for row in df.index}}


def get_earnings(symbol: str) -> dict:
    """Recent quarters' EPS versus estimates (surprise %) and the next scheduled report with estimates."""
    s = _sym(symbol)
    out: dict = {"symbol": s}
    if not config.FINNHUB_API_KEY:
        return {**out, "error": "FINNHUB_API_KEY not set"}
    try:
        out["history"] = _records(sources.earnings_surprises(s), 8)
    except Exception as e:
        out["history_error"] = str(e)[:200]
    try:
        up = sources.upcoming_earnings([s], days=120)
        out["next"] = _records(up, 1)
    except Exception as e:
        out["next_error"] = str(e)[:200]
    return out


def get_analyst_views(symbol: str) -> dict:
    """Analyst rating counts by month (strong buy ... strong sell), consensus and price targets."""
    s = _sym(symbol)
    i = data.info(s)
    out = {"symbol": s, "ratings_by_month": _records(data.recommendations(s), 4),
           "consensus": i.get("recommendationKey"), "analysts": i.get("numberOfAnalystOpinions"),
           "target_mean": _clean(i.get("targetMeanPrice")), "target_low": _clean(i.get("targetLowPrice")),
           "target_high": _clean(i.get("targetHighPrice"))}
    if config.FMP_API_KEY:
        try:
            out["fmp_price_target_consensus"] = _clean(sources.fmp("price-target-consensus", s))
        except Exception:
            pass
    return out


def get_valuation_scores(symbol: str) -> dict:
    """Financial Modeling Prep's discounted-cash-flow fair value, rating, Piotroski score (0-9 financial
    strength) and Altman Z-score (bankruptcy risk; >3 safe, <1.8 distress)."""
    s = _sym(symbol)
    if not config.FMP_API_KEY:
        return {"symbol": s, "error": "FMP_API_KEY not set"}
    out = {"symbol": s}
    for name, ep in (("dcf", "discounted-cash-flow"), ("rating", "ratings-snapshot"), ("scores", "financial-scores")):
        try:
            out[name] = _clean(sources.fmp(ep, s))
        except Exception as e:
            out[name] = {"error": str(e)[:150]}
    return out


def get_news(symbol: str, limit: int = 15) -> list[dict]:
    """Recent headlines for a symbol: time (UTC), publisher, title, summary and link."""
    return [_clean({k: n.get(k) for k in ("published", "publisher", "title", "summary", "url")})
            for n in data.news(_sym(symbol), min(limit, 30))]


def get_insider_trades(symbol: str, open_market_only: bool = True, limit: int = 20) -> list[dict]:
    """Insider transactions from SEC Form 4 (via Finnhub). Codes: P = open-market buy, S = sale; others are
    grants, option exercises and tax withholding (excluded when open_market_only)."""
    s = _sym(symbol)
    if not config.FINNHUB_API_KEY:
        return [{"error": "FINNHUB_API_KEY not set"}]
    df = sources.insider_transactions(s)
    if df.empty:
        return []
    if open_market_only:
        df = df[df["transactionCode"].isin(["P", "S"])]
    cols = [c for c in ("transactionDate", "name", "transactionCode", "change", "share", "transactionPrice") if c in df]
    return _records(df[cols], limit)


def get_sec_filings(symbol: str, forms: str = "10-K,10-Q,8-K", limit: int = 15) -> list[dict]:
    """Recent SEC filings (newest first) with links. forms: comma-separated form types, or "all"."""
    df = sources.sec_filings(_sym(symbol))
    if df.empty:
        return []
    if forms.strip().lower() != "all":
        df = df[df["form"].isin([f.strip().upper() for f in forms.split(",")])]
    return _records(df, limit)


def read_sec_filing(url: str, max_chars: int = 20000, start: int = 0) -> dict:
    """Text of an SEC filing document (a link from get_sec_filings). Use `start` to page through long filings."""
    if "sec.gov" not in url:
        return {"error": "only sec.gov links are supported"}
    import requests

    r = requests.get(url, headers=sources._sec_headers(), timeout=30)
    r.raise_for_status()
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", r.text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return {"url": url, "total_chars": len(text), "start": start, "text": text[start:start + max_chars]}


# ---------- options ----------
def get_options_expirations(symbol: str) -> list[str]:
    """Available option expiry dates for an underlying."""
    return data.option_expirations(_sym(symbol))


def get_options_chain(symbol: str, expiry: str = "", side: str = "both", strikes_around_price: int = 8) -> dict:
    """Option chain for one expiry (empty = nearest expiry at least a week out): strikes near the price with
    bid/ask, volume, open interest, implied volatility and delta/theta when available, plus a summary:
    at-the-money IV, the expected move implied by the at-the-money straddle, and put/call ratios."""
    s = _sym(symbol)
    exps = data.option_expirations(s)
    if not exps:
        return {"symbol": s, "error": "no listed options"}
    if not expiry:
        week = pd.Timestamp.now().normalize() + pd.Timedelta(days=7)
        expiry = next((e for e in exps if pd.Timestamp(e) >= week), exps[-1])
    calls, puts = data.option_chain(s, expiry)
    last = data.quote(s).get("last")
    mid = lambda r: ((r["bid"] + r["ask"]) / 2 if (r["bid"] or 0) > 0 and (r["ask"] or 0) > 0 else r["lastPrice"])
    # Straddle = call + put at the SAME strike. Blend the two strikes either side of the price by distance.
    both = sorted(set(calls["strike"]) & set(puts["strike"])) if last else []
    below = [k for k in both if k <= last]
    above = [k for k in both if k >= last]
    straddle, atm_strike = None, None
    if below and above:
        lo_k, hi_k = below[-1], above[0]
        legs = lambda k: mid(calls[calls["strike"] == k].iloc[0]) + mid(puts[puts["strike"] == k].iloc[0])
        w = 0.5 if hi_k == lo_k else (last - lo_k) / (hi_k - lo_k)
        straddle = legs(lo_k) * (1 - w) + legs(hi_k) * w
        atm_strike = lo_k if w < 0.5 else hi_k
    ac = calls[calls["strike"] == atm_strike] if atm_strike is not None else calls.head(0)
    ap = puts[puts["strike"] == atm_strike] if atm_strike is not None else puts.head(0)
    summary = {
        "underlying_price": last, "expiry": expiry,
        "days_to_expiry": (pd.Timestamp(expiry) - pd.Timestamp.now().normalize()).days,
        "atm_strike": float(ac["strike"].iloc[0]) if len(ac) else None,
        "atm_call_iv": float(ac["impliedVolatility"].iloc[0]) if len(ac) else None,
        "atm_put_iv": float(ap["impliedVolatility"].iloc[0]) if len(ap) else None,
        "expected_move_from_straddle": straddle,
        "expected_move_pct": straddle / last * 100 if straddle and last else None,
        "put_call_volume_ratio": puts["volume"].sum() / calls["volume"].sum() if calls["volume"].sum() else None,
        "put_call_open_interest_ratio": puts["openInterest"].sum() / calls["openInterest"].sum()
        if calls["openInterest"].sum() else None,
    }

    def near(df):
        if not last or df.empty:
            return df.head(0)
        df = df.assign(dist=(df["strike"] - last).abs()).sort_values("dist").head(strikes_around_price * 2)
        return df.drop(columns="dist").sort_values("strike")

    out = {"symbol": s, "summary": _clean(summary), "all_expiries": exps[:24]}
    if side in ("both", "calls"):
        out["calls"] = _records(near(calls))
    if side in ("both", "puts"):
        out["puts"] = _records(near(puts))
    return out


# ---------- ETFs ----------
def get_etf_profile(symbol: str) -> dict:
    """ETF holdings (top 10), sector weights, asset classes, expense ratio, assets and yield."""
    import yfinance as yf

    s = _sym(symbol)
    t = yf.Ticker(s)
    out: dict = {"symbol": s}
    try:
        fd = t.funds_data
        out["top_holdings"] = _records(fd.top_holdings.reset_index().rename(columns={"Symbol": "symbol"}), 10)
        out["sector_weights"] = _clean(dict(fd.sector_weightings))
        out["asset_classes"] = _clean(dict(fd.asset_classes))
        out["description"] = (fd.description or "")[:800]
        ops = fd.fund_operations
        if ops is not None and not ops.empty:
            out["operations"] = _clean(ops.iloc[:, 0].to_dict())
    except Exception as e:
        out["holdings_error"] = str(e)[:200]
    i = data.info(s)
    for k in ("longName", "category", "fundFamily", "totalAssets", "netExpenseRatio", "yield", "ytdReturn",
              "threeYearAverageReturn", "fiveYearAverageReturn", "beta3Year", "navPrice"):
        if i.get(k) is not None:
            out[k] = _clean(i[k])
    return out


# ---------- screening, economy, predictions, backtests ----------
def screen_sp500(sector: str = "", min_market_cap_billions: float = 0, max_pe: float = 0, min_dividend_pct: float = 0,
                 uptrend_only: bool = False, rsi_below: float = 0, rsi_above: float = 0, sort_by: str = "chg_1d",
                 ascending: bool = False, limit: int = 25) -> dict:
    """Filter and rank all S&P 500 members. sort_by: chg_1d chg_1m chg_3m chg_1y from_high rsi pe fwd_pe
    div_yield market_cap. uptrend_only = above both the 50- and 200-day averages. 0 means no filter."""
    scan = cache.latest("sp500", data.sp500_scan, 30 * 60)
    df = scan.copy()
    if sector:
        df = df[df["sector"].str.contains(sector, case=False, na=False)]
    if min_market_cap_billions:
        df = df[df["market_cap"] >= min_market_cap_billions * 1e9]
    if max_pe:
        df = df[df["pe"].between(0.01, max_pe)]
    if min_dividend_pct:
        df = df[df["div_yield"] >= min_dividend_pct]
    if uptrend_only:
        df = df[df["above_50d"] & df["above_200d"]]
    if rsi_below:
        df = df[df["rsi"] < rsi_below]
    if rsi_above:
        df = df[df["rsi"] > rsi_above]
    if sort_by in df:
        df = df.sort_values(sort_by, ascending=ascending, na_position="last")
    return {"matches": len(df), "sectors": sorted(scan["sector"].dropna().unique()), "stocks": _records(df, limit)}


def get_economic_data() -> dict:
    """Latest US economic readings from FRED: Fed funds rate, Treasury yields and the 10y-2y spread, mortgage
    rate, CPI inflation (year over year), unemployment, real GDP growth, VIX and high-yield credit spreads."""
    if not config.FRED_API_KEY:
        return {"error": "FRED_API_KEY not set"}
    out = {}
    for name, sid in sources.FRED_SERIES.items():
        try:
            s = sources.fred_series(sid, years=2)
            out[name] = {"value": _clean(s.iloc[-1]), "as_of": str(s.index[-1].date()),
                         "a_year_earlier": _clean(s[s.index <= s.index[-1] - pd.Timedelta(days=365)].iloc[-1])
                         if len(s) > 2 else None}
        except Exception as e:
            out[name] = {"error": str(e)[:120]}
    return out


def search_fred(query: str, limit: int = 10) -> list[dict]:
    """Search FRED's 800,000+ economic data series by keyword (e.g. "retail sales", "housing starts")."""
    if not config.FRED_API_KEY:
        return [{"error": "FRED_API_KEY not set"}]
    j = sources._get("https://api.stlouisfed.org/fred/series/search", params={
        "search_text": query, "api_key": config.FRED_API_KEY, "file_type": "json", "limit": limit,
        "order_by": "popularity"}).json()
    return [{k: s.get(k) for k in ("id", "title", "frequency", "units", "observation_end")} for s in j.get("seriess", [])]


def get_fred_series(series_id: str, years: int = 5) -> dict:
    """One FRED series: latest value, changes, and a thinned history (about 60 points)."""
    s = sources.fred_series(series_id.strip().upper(), years=years)
    if s.empty:
        return {"series_id": series_id, "error": "no data"}
    step = max(1, len(s) // 60)
    return {"series_id": series_id, "latest": _clean(s.iloc[-1]), "as_of": str(s.index[-1].date()),
            "min": _clean(s.min()), "max": _clean(s.max()),
            "history": {str(d.date()): _clean(v) for d, v in s.iloc[::step].items()}}


def get_prediction_markets(query: str = "", topic: str = "") -> list[dict]:
    """Prediction-market odds (Kalshi, Polymarket). topic: Fed & rates | Inflation | Economy & jobs | Markets,
    or empty with a free-text query."""
    events, _ = predictions.all_events()
    found = predictions.matching(events, topic or None, query)[:12]
    return [{"title": e["title"], "source": e["source"], "subtitle": e["subtitle"],
             "outcomes": [(o, round(p, 3)) for o, p in e["outcomes"][:6]]} for e in found]


def run_backtest(symbol: str, strategy: str = "RSI dip", period: str = "5y", params: str = "") -> dict:
    """Backtest a long-only rule on daily prices versus buy-and-hold. strategy: "RSI dip", "Moving-average
    crossover", "Bollinger bounce", "Breakout". params: optional JSON overriding the defaults, e.g.
    {"buy_below": 25}. Signals act at the next day's open; no costs, dividends or taxes."""
    import json

    if strategy not in bt.STRATEGIES:
        return {"error": f"strategy must be one of {list(bt.STRATEGIES)}"}
    desc, spec = bt.STRATEGIES[strategy]
    p = {k: v[1] for k, v in spec.items()}
    if params:
        p.update(json.loads(params))
    df = data.history(_sym(symbol), period, "1d")
    if len(df) < 60:
        return {"error": "not enough history"}
    r = bt.run(df, strategy, p)
    return {"symbol": _sym(symbol), "rule": desc.format(**p), "period": period, "stats": _clean(r.stats),
            "last_trades": _records(r.trades.tail(10).assign(entry_date=lambda d: d["entry_date"].astype(str),
                                                             exit_date=lambda d: d["exit_date"].astype(str)))}


# ---------- the user's own account (read-only) ----------
def _brokers():
    from .brokers import connect_all

    return connect_all()


def get_portfolio() -> dict:
    """Your balances and positions at each connected broker, plus whether the app is in paper or live mode."""
    brokers, errors = _brokers()
    out = {"mode": config.MODE_LABEL, "errors": errors, "accounts": {}}
    for name, b in brokers.items():
        try:
            out["accounts"][name] = {"balances": _clean(b.account()), "positions": _clean(b.positions())}
        except Exception as e:
            out["accounts"][name] = {"error": str(e)[:200]}
    return out


def get_orders() -> dict:
    """Recent and open orders at each connected broker."""
    brokers, errors = _brokers()
    out = {"errors": errors}
    for name, b in brokers.items():
        try:
            out[name] = _clean([{**o, "submitted": str(o.get("submitted"))} for o in b.orders()[:30]])
        except Exception as e:
            out[name] = {"error": str(e)[:200]}
    return out


def get_my_trading_plan() -> dict:
    """Your goals, risk limits and rules (Assistant > My trading plan)."""
    return profile.for_ai() or {"note": "No trading plan filled in yet."}


def get_my_watchlists() -> dict:
    """Your watchlists by name."""
    return {n: watchlists.symbols(n) for n in watchlists.names()}


def get_my_journal(limit: int = 20) -> list[dict]:
    """Your trade journal: each order sent from the app with your note, tags and review (newest first)."""
    return [_clean({k: e.get(k) for k in ("time", "broker", "mode", "symbol", "side", "qty", "type", "price",
                                         "stop_loss", "take_profit", "note", "tags", "review")})
            for e in reversed(journal.load()[-limit:])]


def get_my_realized_gains() -> dict:
    """Your closed trades (first-in, first-out) with win rate, average win/loss and short/long-term totals."""
    brokers, _ = _brokers()
    parts = []
    for name, b in brokers.items():
        try:
            fills, _d = b.activity()
            parts.append(gains.realized(fills).assign(broker=name))
        except Exception:
            pass
    closed = pd.concat(parts, ignore_index=True) if parts else gains.realized(pd.DataFrame())
    return {"summary": _clean(gains.summary(closed)), "recent_closed_trades": _records(
        closed.sort_values("closed", ascending=False).assign(opened=lambda d: d["opened"].astype(str),
                                                             closed=lambda d: d["closed"].astype(str)), 20)}


TOOLS = [get_quote, get_price_history, get_technicals, get_intraday, get_market_overview, get_futures_overview,
         get_company_profile, get_financial_statements, get_earnings, get_analyst_views, get_valuation_scores,
         get_news, get_insider_trades, get_sec_filings, read_sec_filing, get_options_expirations, get_options_chain,
         get_etf_profile, screen_sp500, get_economic_data, search_fred, get_fred_series, get_prediction_markets,
         run_backtest, get_portfolio, get_orders, get_my_trading_plan, get_my_watchlists, get_my_journal,
         get_my_realized_gains]
