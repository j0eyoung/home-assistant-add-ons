"""Background Alpaca price stream. Keeps the latest trade and quote per watched symbol.

One websocket for the whole process (the free plan allows a single connection), started
only by the app via start(); everything degrades to REST snapshots if it is not running.

The state hangs off the stream's thread rather than this module: Streamlit re-imports
local modules when a source file changes, and a fresh module that opened a second
connection would be refused by Alpaca ("connection limit exceeded").
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections import OrderedDict

from . import config

THREAD_NAME = "alpaca-stream"
MAX_SYMBOLS = 30  # free-plan websocket subscription limit
FRESH_SECONDS = 60  # ignore stream values older than this (quiet market, dropped connection)

_start_lock = threading.Lock()


class _State:
    def __init__(self, stream):
        self.stream = stream
        self.lock = threading.Lock()
        self.latest: dict[str, dict] = {}
        self.watched: OrderedDict[str, None] = OrderedDict()
        self.error: str | None = None  # last connection error reported by the library
        self.error_at = 0.0

    async def on_trade(self, t):
        self.latest.setdefault(t.symbol, {}).update(last=t.price, ts=time.time())

    async def on_quote(self, q):
        self.latest.setdefault(q.symbol, {}).update(bid=q.bid_price, ask=q.ask_price)

    def run(self):
        try:
            self.stream.run()
        except Exception:
            pass


class _ErrorCapture(logging.Handler):
    def __init__(self, state: _State):
        super().__init__(logging.WARNING)
        self.state = state

    def emit(self, record):
        msg = record.getMessage()
        if self.state.error != msg:
            print(f"[price stream] {msg}", file=sys.stderr)  # once per distinct error
        self.state.error, self.state.error_at = msg, time.time()


def status() -> tuple[str, str]:
    """('live' | 'connecting' | 'off', explanation)."""
    s = _state()
    if not s:
        return "off", "Price stream not running (no Alpaca keys). Prices come from snapshots."
    now = time.time()
    newest = max((d.get("ts", 0) for d in s.latest.values()), default=0)
    if now - newest < FRESH_SECONDS:
        return "live", "Streaming from Alpaca (IEX)."
    if s.error and now - s.error_at < 120:
        hint = ""
        if "connection limit" in s.error:
            hint = " Another program is using your one free Alpaca stream: close other copies of this app."
        return "connecting", f"Price stream reconnecting: {s.error}.{hint} Prices update every 5s meanwhile."
    return "connecting", "Waiting for the first trades. Prices update every 5s meanwhile."


def _state() -> _State | None:
    for t in threading.enumerate():
        if t.name == THREAD_NAME:
            return getattr(t, "state", None)
    return None


def start() -> None:
    with _start_lock:
        if _state() or not (config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY):
            return
        if os.getenv("STREAM", "on").strip().lower() == "off":  # a second copy (testing) would take the one stream
            return
        from alpaca.data.enums import DataFeed
        from alpaca.data.live import StockDataStream

        state = _State(StockDataStream(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, feed=DataFeed.IEX))
        # The library logs a full traceback on every failed reconnect; keep the message for the
        # status line instead of flooding the console.
        log = logging.getLogger("alpaca.data.live.websocket")
        log.handlers = [_ErrorCapture(state)]
        log.propagate = False
        thread = threading.Thread(target=state.run, daemon=True, name=THREAD_NAME)
        thread.state = state
        thread.start()


def watch(symbols: list[str]) -> None:
    """Subscribe to symbols (Alpaca format, e.g. BRK.B), dropping the least recently used past the limit."""
    s = _state()
    if not s:
        return
    with s.lock:
        new = [x for x in symbols if x not in s.watched]
        for x in symbols:
            s.watched[x] = None
            s.watched.move_to_end(x)
        dropped = []
        while len(s.watched) > MAX_SYMBOLS:
            old, _ = s.watched.popitem(last=False)
            dropped.append(old)
            s.latest.pop(old, None)
    if new or dropped:
        # The library waits for the websocket to acknowledge; do that off the UI thread so a
        # slow or reconnecting stream can never freeze a page.
        threading.Thread(target=_resubscribe, args=(s, new, dropped), daemon=True).start()


def _resubscribe(s: _State, new: list[str], dropped: list[str]) -> None:
    try:
        if dropped:
            s.stream.unsubscribe_trades(*dropped)
            s.stream.unsubscribe_quotes(*dropped)
        if new:
            s.stream.subscribe_trades(s.on_trade, *new)
            s.stream.subscribe_quotes(s.on_quote, *new)
    except Exception:
        pass


def get(symbol: str) -> dict | None:
    """Latest streamed {'last','bid','ask'} for a symbol, or None if nothing recent has arrived."""
    s = _state()
    d = s.latest.get(symbol) if s else None
    if not d or "last" not in d or time.time() - d["ts"] > FRESH_SECONDS:
        return None
    return {"last": d["last"], "bid": d.get("bid"), "ask": d.get("ask"), "source": "Alpaca live stream"}
