"""Smoke test for the web terminal: every API route answers, the page and scripts load, and the safety checks
on POSTs hold. Run before each release:

    .venv\\Scripts\\python -m tests.smoke            (add --fast to skip the slow S&P 500 scan routes)

It calls the real data sources (Alpaca, Yahoo, Finnhub...) with the keys in .env, so it needs the internet.
It never places, changes or cancels an order: order routes are only called in ways the server must refuse.
The start-up jobs (price stream, data collection, warm-up) are not started.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("STREAM", "off")  # the one Alpaca stream belongs to the running add-on

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient  # noqa: E402

from web import server  # noqa: E402

S = "AAPL"
# (route, query) for GETs. Every route in server.ROUTES must appear here or in POSTS/REFUSED below.
GETS = [
    ("boot", {}), ("quotes", {"s": f"{S},SPY,^GSPC", "spark": 1}), ("live", {"s": f"{S},SPY", "once": 1}),
    ("history", {"s": S, "range": "1D"}), ("history", {"s": S, "range": "5Y"}),
    ("chart", {"s": S, "range": "1Y", "ind": "sma20,sma50,sma200,bb,rsi,macd", "vs": 1}),
    ("overview", {"s": S}), ("news", {"s": S, "n": 5}), ("analysts", {"s": S}),
    ("financials", {"s": S, "stmt": "income"}), ("financials", {"s": S, "stmt": "balance", "q": 1}),
    ("valuation", {"s": S}), ("earnings", {"s": S}), ("filings", {"s": S}), ("options", {"s": S}),
    ("backtest", {"s": S}), ("search", {"q": "appl"}), ("portfolio", {"range": "1M"}), ("allocation", {}),
    ("account", {}), ("orders", {}), ("journal", {}), ("gains", {}), ("world", {}), ("futures", {}),
    ("sp500", {}), ("ideas", {}), ("calendar", {}), ("predictions", {}), ("screens", {}), ("economy", {}),
    ("events", {}), ("watchlists", {}), ("alerts", {}), ("plan", {}), ("brief", {}), ("claude", {}), ("data", {}),
    ("pin", {}), ("prefs", {}), ("exits", {}),
]
SLOW = {"sp500", "ideas"}
# POSTs that only read (an empty body changes nothing).
POSTS = ["watchlists", "alerts", "plan", "claude", "data", "orders/preview"]
# Routes that must refuse what we send: (route, body, expected status).
REFUSED = [
    ("orders/submit", {"symbol": S, "qty": 1}, 400),            # not confirmed
    ("orders/preview", {"symbol": S, "qty": 0}, 500),           # quantity must be > 0
    ("orders/cancel", {}, 500),                                 # no order id
    ("journal/update", {}, 500),                                # no entry id
]
UNTESTED = {"brokers/reconnect": "drops live broker connections", "brief": "covered by GET (starting one costs an AI call)"}
# Keys that should be in each GET answer (a cheap check that the shape didn't change under the page).
SHAPE = {
    "boot": ["functions", "brokers", "pending"], "quotes": ["quotes"], "history": ["t"], "chart": ["t", "ind"],
    "overview": ["info"], "news": ["items"], "portfolio": ["brokers"], "orders": ["brokers"], "world": ["indexes"],
    "options": ["expiries"], "backtest": ["strategies"], "watchlists": ["names", "lists"], "plan": ["fields", "values"],
    "account": ["account", "plan"], "screens": ["names", "rows"], "journal": ["summary", "by_tag", "curves"],
    "pin": ["set", "required"], "prefs": ["prefs"], "exits": ["exits"],
}
H = {"X-Terminal": "1"}


def scratch_files():
    """Points the PIN, shared settings and trailing-stop files at a throwaway folder, so the test never
    touches the real ones (and never finds a real PIN)."""
    from terminal import exits, pin, prefs

    d = ROOT / ".smoke"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir()
    pin.PATH, prefs.PATH, exits.PATH = d / "trade_pin.json", d / "prefs.json", d / "exits.json"
    return d


def feature_checks(client, check):
    """Trade PIN, shared settings, trailing stops after a fill, and the order-ticket rules. Nothing is sent
    to a broker: the only submit carries a wrong PIN, which is refused before the broker is called."""
    from terminal import exits, pin

    post = lambda route, body: client.post(f"/api/{route}", json=body, headers=H)
    err = lambda r: (r.json() or {}).get("error", "") if r.headers.get("content-type", "").startswith("application/json") else r.text

    # Shared settings
    post("prefs", {"set": {"port.range": "1M", "recent": ["NVDA", "AAPL"]}})
    got = client.get("/api/prefs").json()["prefs"]
    check("prefs: saved and read back", got.get("port.range") == "1M" and got.get("recent") == ["NVDA", "AAPL"], 0, str(got))
    post("prefs", {"set": {"port.range": None}})
    check("prefs: a null removes the key", "port.range" not in client.get("/api/prefs").json()["prefs"], 0)

    # Trade PIN
    st = client.get("/api/pin").json()
    check("pin: starts unset", st["set"] is False, 0, str(st))
    r = post("pin", {"action": "set", "pin": "12"})
    check("pin: too short is refused", r.status_code == 500 and "4 to 8" in err(r), 0, err(r))
    r = post("pin", {"action": "set", "pin": "4821"})
    check("pin: set", r.status_code == 200 and r.json()["set"], 0, err(r))
    r = post("pin", {"action": "set", "pin": "1111", "current": "0000"})
    check("pin: change needs the current PIN", r.status_code == 500 and "Wrong PIN" in err(r), 0, err(r))
    r = post("pin", {"action": "paper", "on": True, "current": "4821"})
    check("pin: ask for paper orders too", r.status_code == 200 and r.json()["required"], 0, err(r))
    r = post("orders/preview", {"symbol": S, "qty": 1, "side": "buy", "type": "market"})
    check("pin: preview says it's needed", r.status_code == 200 and r.json()["pin"]["required"], 0, err(r))
    r = post("orders/submit", {"symbol": S, "qty": 1, "side": "buy", "type": "market", "confirm": True, "pin": "0000"})
    check("pin: wrong PIN stops the order", r.status_code == 500 and "Wrong PIN" in err(r), 0, err(r))
    r = post("orders/submit", {"symbol": S, "qty": 1, "side": "buy", "type": "market", "confirm": True})
    check("pin: missing PIN stops the order", r.status_code == 500 and "Enter your trade PIN" in err(r), 0, err(r))
    pin._fails.update(n=0, until=0.0)
    last = ""
    for _ in range(5):
        try:
            pin.check("9999")
        except ValueError as e:
            last = str(e)
    check("pin: five wrong tries lock orders", "locked" in last, 0, last)
    try:
        pin.check("4821")
        locked_ok = False
    except ValueError as e:
        locked_ok = "locked" in str(e)
    check("pin: even the right PIN waits out the lock", locked_ok, 0)
    pin._fails.update(n=0, until=0.0)
    pin.check("4821")
    r = post("pin", {"action": "remove", "current": "4821"})
    check("pin: turn off", r.status_code == 200 and not r.json()["set"], 0, err(r))

    # Order ticket rules (preview only)
    base = {"symbol": S, "qty": 10, "side": "buy", "type": "market"}
    r = post("orders/preview", {**base, "exit_trail": "5", "exit_trail_unit": "%"})
    check("ticket: trailing stop after fill is described", r.status_code == 200 and "trailing stop 5% once filled" in r.json()["describe"], 0, err(r))
    r = post("orders/preview", {**base, "exit_trail": "5", "stop_loss": "150"})
    check("ticket: trailing stop and stop loss can't mix", r.status_code == 500 and "replaces" in err(r), 0, err(r))
    r = post("orders/preview", {**base, "side": "sell", "type": "trailing", "price": "2.5", "price_unit": "$"})
    check("ticket: trailing stop order", r.status_code == 200 and "TRAILING STOP $2.50" in r.json()["describe"], 0, err(r))
    r = post("orders/preview", {**base, "type": "trailing"})
    check("ticket: trailing stop needs an amount", r.status_code == 500 and "how far" in err(r), 0, err(r))
    r = post("orders/preview", {**base, "take_profit": "300", "stop_loss": "150"})
    check("ticket: bracket", r.status_code == 200 and "take profit 300.00, stop loss 150.00" in r.json()["describe"], 0, err(r))

    # Trailing stop placed when the entry fills (fake broker)
    class Fake:
        name = "Fake"
        status = "new"
        sent = []

        def orders(self):
            return [{"id": "E1", "status": self.status, "qty": 10, "filled_qty": 10 if self.status == "filled" else 0}]

    fake = Fake()
    exits.add("Fake", "E1", S, "buy", 5.0, None)
    calls = []
    submit = lambda br, x, qty: calls.append((x["side"], qty, x["trail_percent"])) or "X1"
    exits.check({"Fake": fake}, submit)
    check("exits: waits while the entry is open", not calls and exits.waiting(), 0)
    fake.status = "filled"
    msgs = exits.check({"Fake": fake}, submit)
    check("exits: places a sell trailing stop on fill", calls == [("sell", 10.0, 5.0)] and not exits.waiting(), 0, str(msgs))
    exits.add("Fake", "E2", S, "buy", 5.0, None)
    fake.orders = lambda: [{"id": "E2", "status": "canceled", "qty": 10, "filled_qty": 0}]
    exits.check({"Fake": fake}, submit)
    check("exits: dropped when the entry is canceled unfilled", exits.load()[-1]["state"] == "canceled" and len(calls) == 1, 0)

    # Journal stats from made-up fills, with planned risk from the journal
    import pandas as pd
    from terminal import gains

    fills = pd.DataFrame([
        {"symbol": "AAA", "side": "buy", "qty": 10, "price": 100, "time": pd.Timestamp("2026-01-02 15:00", tz="UTC")},
        {"symbol": "AAA", "side": "sell", "qty": 10, "price": 110, "time": pd.Timestamp("2026-01-05 15:00", tz="UTC")},
    ])
    closed = gains.realized(fills)
    entry = {"symbol": "AAA", "side": "buy", "time": pd.Timestamp("2026-01-02 14:59:30", tz="UTC").timestamp(),
             "stop_loss": 95, "tags": ["Breakout"], "risk_per_share": None}
    saved = server.activity, server.journal.load
    server.activity = lambda: (fills.assign(broker="Fake"), pd.DataFrame(), {})
    server.journal.load = lambda: [entry]
    try:
        j = server.journal_api({}, {}, {})
    finally:
        server.activity, server.journal.load = saved
    bt = {x["tag"]: x for x in j["by_tag"]}
    check("journal: R from the stop loss (+$100 on $50 risk = 2R)", abs((bt.get("Breakout") or {}).get("avg_r", 0) - 2.0) < 1e-9
          and abs(j["summary"]["avg_r"] - 2.0) < 1e-9 and len(closed) == 1, 0, str(bt))
    check("journal: equity curve per tag", j["curves"] and j["curves"]["tags"]["Breakout"] == [100.0], 0, str(j["curves"]))


def main() -> int:
    fast = "--fast" in sys.argv
    tmp = scratch_files()
    client = TestClient(server.app, raise_server_exceptions=False)  # no `with`: start-up jobs stay off
    fails, rows = [], []

    def check(name, ok_, took, note=""):
        rows.append((name, "ok " if ok_ else "FAIL", f"{took:5.1f}s", note))
        if not ok_:
            fails.append(name)

    try:
        feature_checks(client, check)
    except Exception as e:
        check("feature checks ran", False, 0, f"{type(e).__name__}: {e}")

    covered = {r for r, _ in GETS} | set(POSTS) | {r for r, _, _ in REFUSED} | set(UNTESTED)
    missing = set(server.ROUTES) - covered
    check("every route has a test", not missing, 0, ", ".join(sorted(missing)))

    for route, q in GETS:
        if fast and route in SLOW:
            continue
        t = time.time()
        r = client.get(f"/api/{route}", params=q)
        took = time.time() - t
        name = f"GET {route} {json.dumps(q) if q else ''}".strip()
        if route == "live":
            ok_ = r.status_code == 200 and r.text.startswith("data: ") and "quotes" in r.text
            check(name, ok_, took, "" if ok_ else r.text[:120])
            continue
        try:
            body = r.json()
        except ValueError:
            check(name, False, took, f"not JSON ({r.status_code})")
            continue
        bad = r.status_code != 200 or (isinstance(body, dict) and body.get("error") and route not in ("sp500", "ideas"))
        lacking = [k for k in SHAPE.get(route, []) if k not in body] if not bad else []
        check(name, not bad and not lacking, took,
              (body.get("error") if isinstance(body, dict) else "") or (f"missing {lacking}" if lacking else ""))

    for route in POSTS:
        t = time.time()
        body = {"symbol": S, "qty": 1, "side": "buy", "type": "market"} if route == "orders/preview" else {}
        r = client.post(f"/api/{route}", json=body, headers={"X-Terminal": "1"})
        check(f"POST {route}", r.status_code == 200, time.time() - t, "" if r.status_code == 200 else r.text[:120])

    for route, body, want in REFUSED:
        t = time.time()
        r = client.post(f"/api/{route}", json=body, headers={"X-Terminal": "1"})
        check(f"POST {route} refused", r.status_code == want, time.time() - t,
              "" if r.status_code == want else f"got {r.status_code}: {r.text[:80]}")

    r = client.post("/api/orders/submit", json={"symbol": S, "qty": 1, "confirm": True})
    check("POST without X-Terminal header is blocked", r.status_code == 403, 0, f"got {r.status_code}")
    r = client.post("/api/ask", json={"messages": []})
    check("Ask AI without header is blocked", r.status_code == 403, 0, f"got {r.status_code}")

    page = client.get("/")
    check("page loads", page.status_code == 200 and "{{V}}" not in page.text and "app.js" in page.text, 0)
    for f in ("app.js", "chart.js", "app.css", "icon.png"):
        check(f"static/{f}", client.get(f"/static/{f}").status_code == 200, 0)
    node = shutil.which("node")
    for f in ("app.js", "chart.js"):
        if node:
            p = subprocess.run([node, "--check", str(ROOT / "web" / "static" / f)], capture_output=True, text=True)
            check(f"{f} syntax", p.returncode == 0, 0, p.stderr.strip()[:160])
        else:
            rows.append((f"{f} syntax", "skip", "", "node not installed"))

    shutil.rmtree(tmp, ignore_errors=True)
    width = max(len(r[0]) for r in rows)
    for name, status, took, note in rows:
        print(f"{status}  {name:<{width}}  {took:>6}  {note}")
    print(f"\n{len(rows) - len(fails)} passed, {len(fails)} failed" + (f": {', '.join(fails)}" if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
