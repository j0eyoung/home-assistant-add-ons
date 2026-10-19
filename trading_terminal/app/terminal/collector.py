"""Background data collector: after each market close, saves to the configured store (see store.py)
  - daily prices: full history for the S&P 500 plus your watchlists and holdings
  - minute prices: your watchlists and holdings
  - a daily snapshot of key statistics for the S&P 500, plus Finnhub fundamentals for your stocks
  - SEC financial statements for your stocks (weekly)
  - news headlines for your stocks (sentiment scores are added when the app rates them)
Nothing runs unless storage is configured. One collector thread per process.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import threading
import time
import traceback

import pandas as pd

from . import config, store

NY = "America/New_York"
RUN_AFTER = dt.time(16, 35)  # market close + 35 min (the free full-market feed runs 15 min behind)
DEEP_HISTORY = True  # also keep pre-2016 daily history (Yahoo) for your own stocks, for long backtests
THREAD_NAME = "data-collector"
SYMBOLS_FILE = config.DATA_DIR / "collect_symbols.json"
STATE_KEY = "collector/state.json"

# Kept on the threading module so it survives Streamlit re-importing this file after a code change
# (the running collector thread keeps updating the same dict the page reads).
status: dict = getattr(threading, "_trading_collector_status", None) or {
    "running": False, "job": "", "detail": "", "last_error": "", "started": None}
threading._trading_collector_status = status


def minute_backfill_days() -> int:
    try:
        return max(0, int(os.getenv("MINUTE_BACKFILL_DAYS", "365")))
    except ValueError:
        return 365


def log(msg: str) -> None:
    status["detail"] = msg
    print(f"[collector] {msg}", file=sys.stderr, flush=True)


# ---------- which symbols ----------
def note_symbols(held: list[str]) -> None:
    """The app reports current holdings here, so they get collected too."""
    try:
        old = json.loads(SYMBOLS_FILE.read_text()) if SYMBOLS_FILE.exists() else []
        if sorted(old) != sorted(held):
            SYMBOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SYMBOLS_FILE.write_text(json.dumps(sorted(set(held))))
    except Exception:
        pass


def own_symbols() -> list[str]:
    """Watchlists + holdings (stocks only)."""
    from . import watchlists

    held = json.loads(SYMBOLS_FILE.read_text()) if SYMBOLS_FILE.exists() else []
    return list(dict.fromkeys([*held, *watchlists.everything()]))


def sp500_symbols() -> list[str]:
    from . import cache, data

    scan = cache.latest("sp500", data.sp500_scan, 30 * 60)
    return list(scan["symbol"]) if scan is not None and not scan.empty else []


# ---------- jobs ----------
def _daily_key(s: str) -> str:
    return f"prices/daily/{s}.parquet"


def _alpaca_daily(symbols: list[str], start: dt.datetime) -> dict[str, pd.DataFrame]:
    from alpaca.data.enums import DataFeed
    from alpaca.data.timeframe import TimeFrame

    from . import market

    out = {}
    end = dt.datetime.now(dt.timezone.utc) - market.SIP_DELAY
    for i in range(0, len(symbols), 100):
        batch = symbols[i:i + 100]
        df = market._fetch(batch, TimeFrame.Day, start, end, DataFeed.SIP)
        if df is None or df.empty:
            continue
        for sym, g in df.groupby(level="symbol"):
            g = g.droplevel("symbol").sort_index()
            g.index = pd.DatetimeIndex(g.index).tz_convert(NY).normalize()
            out[market._from_alpaca(sym)] = g.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
        time.sleep(0.4)  # stay well under the free plan's ~200 requests/minute
    return out


def _yahoo_deep(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=True)
    if df.empty:
        return df
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.index = pd.DatetimeIndex(df.index).tz_convert(NY).normalize()
    return df


def job_daily_prices(universe: list[str], own: set[str]) -> str:
    """Append new daily bars; re-download a symbol's whole history when a split or dividend has
    re-adjusted past prices (detected by comparing overlapping days)."""
    first = dt.datetime(2016, 1, 1, tzinfo=dt.timezone.utc)
    stored = {s: store.read(_daily_key(s)) for s in universe}
    fresh, update = [s for s in universe if stored[s] is None or stored[s].empty], []
    for s in universe:
        if s not in fresh:
            update.append(s)
    added = refreshed = 0
    # Brand-new symbols: everything Alpaca has (2016 on), plus deeper Yahoo history for your own stocks.
    if fresh:
        log(f"daily prices: downloading history for {len(fresh)} symbols")
        got = _alpaca_daily(fresh, first)
        for s in fresh:
            df = got.get(s, pd.DataFrame())
            if DEEP_HISTORY and s in own:
                try:
                    deep = _yahoo_deep(s)
                    df = pd.concat([deep[deep.index < df.index[0]] if not df.empty else deep, df])
                except Exception:
                    pass
            if not df.empty:
                store.write(_daily_key(s), df[~df.index.duplicated(keep="last")])
                added += 1
    # Existing symbols: fetch from a week before their last day, check the overlap, append.
    if update:
        since = min(stored[s].index.max() for s in update) - pd.Timedelta(days=7)
        log(f"daily prices: updating {len(update)} symbols from {since:%Y-%m-%d}")
        got = _alpaca_daily(update, since.to_pydatetime())
        for s in update:
            new, old = got.get(s), stored[s]
            if new is None or new.empty:
                continue
            overlap = old.index.intersection(new.index)
            if len(overlap) and (abs(new.loc[overlap, "Close"] / old.loc[overlap, "Close"] - 1) > 0.002).any():
                # Past prices were re-adjusted (split / dividend): rebuild this symbol from scratch.
                full = _alpaca_daily([s], first).get(s, new)
                if DEEP_HISTORY and s in own:
                    try:
                        deep = _yahoo_deep(s)
                        full = pd.concat([deep[deep.index < full.index[0]], full])
                    except Exception:
                        pass
                store.write(_daily_key(s), full[~full.index.duplicated(keep="last")])
                refreshed += 1
            elif new.index.max() > old.index.max():
                df = pd.concat([old, new[new.index > old.index.max()]])
                store.write(_daily_key(s), df)
    return f"{added} new, {len(update)} updated, {refreshed} rebuilt after splits/dividends"


def job_minute_prices(symbols: list[str]) -> str:
    """Raw (unadjusted) one-minute bars, regular session, one file per symbol per month."""
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    from . import market

    if not symbols or minute_backfill_days() == 0:
        return "skipped"
    end = dt.datetime.now(dt.timezone.utc) - market.SIP_DELAY
    state = store.read_json("collector/minute.json")  # symbol -> last stored bar time (ISO)
    files = 0
    for s in symbols:
        last = pd.Timestamp(state[s]) if s in state else None
        start = (last + pd.Timedelta(minutes=1)).to_pydatetime() if last is not None else \
            end - dt.timedelta(days=minute_backfill_days())
        cursor = pd.Timestamp(start)
        while cursor < pd.Timestamp(end):
            month_end = min((cursor + pd.offsets.MonthBegin(1)).normalize(), pd.Timestamp(end))
            log(f"minute prices: {s} {cursor:%Y-%m}")
            req = StockBarsRequest(symbol_or_symbols=market._to_alpaca(s), timeframe=TimeFrame.Minute,
                                   start=cursor.to_pydatetime(), end=month_end.to_pydatetime(),
                                   feed=DataFeed.SIP, adjustment=Adjustment.RAW)
            df = market._client().get_stock_bars(req).df
            time.sleep(0.4)
            if df is not None and not df.empty:
                df = df.droplevel("symbol")
                df.index = pd.DatetimeIndex(df.index).tz_convert(NY)
                mins = df.index.hour * 60 + df.index.minute
                df = df[(mins >= 570) & (mins < 960)].rename(columns=str.capitalize)
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                if not df.empty:
                    key = f"prices/minute/{s}/{df.index[0]:%Y-%m}.parquet"
                    old = store.read(key)
                    if old is not None:
                        df = pd.concat([old, df])
                        df = df[~df.index.duplicated(keep="last")].sort_index()
                    store.write(key, df)
                    files += 1
                    state[s] = df.index.max().isoformat()
                    store.write_json("collector/minute.json", state)
            cursor = month_end
    return f"{files} month files written for {len(symbols)} symbols"


def job_stats(own: list[str]) -> str:
    from . import cache, data, market

    today = pd.Timestamp.now(tz=NY).date()
    scan = cache.latest("sp500", data.sp500_scan, 30 * 60)
    n = 0
    if scan is not None and not scan.empty:
        store.write(f"stats/sp500/{today}.parquet", scan.assign(date=str(today)))
        n += len(scan)
    rows = []
    for s in own:
        log(f"fundamentals: {s}")
        f = market.fundamentals(s)
        if f:
            rows.append({"symbol": s, "date": str(today), **{k: v for k, v in f.items() if isinstance(v, (int, float))}})
        time.sleep(2.1)  # two Finnhub calls per stock; the free plan allows 60 a minute
    if rows:
        store.write(f"stats/fundamentals/{today}.parquet", pd.DataFrame(rows))
    return f"S&P 500 snapshot ({n} stocks), fundamentals for {len(rows)} of your stocks"


def job_financials(own: list[str]) -> str:
    from . import sources

    done = 0
    for s in own:
        log(f"financials: {s}")
        try:
            facts = sources.sec_facts(s)
        except Exception:
            facts = {}
        if not facts:
            continue
        for stmt in ("income", "balance", "cashflow"):
            for q in (False, True):
                df = sources.sec_statements(s, stmt, q, periods=60, facts=facts)
                if not df.empty:
                    df.columns = [str(c) for c in df.columns]
                    store.write(f"financials/{s}/{stmt}-{'q' if q else 'y'}.parquet", df)
        done += 1
        time.sleep(0.3)  # SEC asks for at most 10 requests a second
    return f"statements for {done} of {len(own)} stocks"


def job_news(own: list[str]) -> str:
    from . import market

    month = f"{pd.Timestamp.now(tz=NY):%Y-%m}"
    key = f"news/{month}.parquet"
    rows = []
    for s in own:
        for n in market.news(s, 50):
            rows.append({"symbol": s, **{k: n.get(k) for k in ("published", "publisher", "title", "summary", "url")}})
        time.sleep(0.4)
    if not rows:
        return "no headlines"
    df = pd.DataFrame(rows)
    old = store.read(key)
    if old is not None:
        df = pd.concat([old, df])
    df = df.drop_duplicates(["symbol", "url"], keep="first")
    store.write(key, df)
    return f"{len(df)} headlines stored for {month}"


def record_sentiment(symbol: str, titles: list[str], scores: list) -> None:
    """Called by the app after it rates headlines; kept alongside the news archive."""
    if not store.enabled():
        return
    try:
        month = f"{pd.Timestamp.now(tz=NY):%Y-%m}"
        key = f"sentiment/{month}.parquet"
        new = pd.DataFrame({"symbol": symbol, "title": titles, "score": scores,
                            "rated": pd.Timestamp.now(tz="UTC").isoformat()})
        old = store.read(key)
        df = pd.concat([old, new]) if old is not None else new
        store.write(key, df.drop_duplicates(["symbol", "title"], keep="last"))
    except Exception:
        pass


# ---------- scheduling ----------
JOBS = ["daily_prices", "minute_prices", "stats", "financials", "news"]


def run_all(force: bool = False) -> None:
    if status["running"]:
        return
    status.update(running=True, started=time.time(), last_error="")
    state = store.read_json(STATE_KEY)
    today = str(pd.Timestamp.now(tz=NY).date())
    try:
        own = [s for s in own_symbols() if s]
        universe = list(dict.fromkeys([*sp500_symbols(), *own]))
        plan = {
            "daily_prices": lambda: job_daily_prices(universe, set(own)),
            "minute_prices": lambda: job_minute_prices(own),
            "stats": lambda: job_stats(own),
            "financials": lambda: job_financials(own),
            "news": lambda: job_news(own),
        }
        for name in JOBS:
            last = state.get(name, {}).get("day")
            due = force or last != today
            if name == "financials" and last and not force:  # weekly
                due = (pd.Timestamp(today) - pd.Timestamp(last)).days >= 7
            if not due:
                continue
            status["job"] = name
            t = time.time()
            try:
                result = plan[name]()
                state[name] = {"day": today, "result": result, "seconds": round(time.time() - t)}
                log(f"{name}: {result} ({time.time() - t:.0f}s)")
            except Exception as e:
                state[name] = {**state.get(name, {}), "error": f"{type(e).__name__}: {e}", "failed_at": today}
                status["last_error"] = f"{name}: {e}"
                log(f"{name} failed: {e}\n{traceback.format_exc(limit=3)}")
            store.write_json(STATE_KEY, state)
    finally:
        status.update(running=False, job="", detail="")


def _loop() -> None:
    time.sleep(60)  # let the app finish starting
    log("checking whether a collection run is due")
    while True:
        try:
            if store.enabled():
                now = pd.Timestamp.now(tz=NY)
                state = store.read_json(STATE_KEY)
                never_ran = not state
                after_close = now.weekday() < 5 and now.time() >= RUN_AFTER
                done_today = state.get("daily_prices", {}).get("day") == str(now.date())
                if never_ran or (after_close and not done_today):
                    run_all()
        except Exception as e:
            status["last_error"] = f"{type(e).__name__}: {e}"
            log(f"couldn't reach storage: {status['last_error']}")
        time.sleep(600)


def start() -> None:
    """Start the collector thread once per process (safe to call on every page load)."""
    if any(t.name == THREAD_NAME for t in threading.enumerate()):
        return
    log(f"storage: {store.describe()}" + ("" if store.enabled() else f" - collection is off ({store.why_off()})"))
    threading.Thread(target=_loop, daemon=True, name=THREAD_NAME).start()


def run_now() -> None:
    if not status["running"]:
        threading.Thread(target=run_all, kwargs={"force": True}, daemon=True, name="collector-run-now").start()


def last_runs() -> dict:
    return store.read_json(STATE_KEY)
