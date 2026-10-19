"""Realized gains (first-in, first-out) and dividends from a broker's trade history."""
from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd

LONG_TERM_DAYS = 365  # US rule of thumb: held more than a year is long-term


def realized(fills: pd.DataFrame) -> pd.DataFrame:
    """Match sells against earlier buys (and buys against earlier short sells), oldest first.

    fills: symbol, side ('buy'/'sell'), qty, price, time. One row per closed slice of a position.
    """
    cols = ["symbol", "opened", "closed", "qty", "cost", "proceeds", "pl", "pl_pct", "days", "term", "direction"]
    if fills is None or fills.empty:
        return pd.DataFrame(columns=cols)
    lots: dict[str, deque] = defaultdict(deque)  # symbol -> [signed qty, price, time]; + long, - short
    rows = []
    for f in fills.sort_values("time").itertuples():
        signed = f.qty if f.side == "buy" else -f.qty
        book = lots[f.symbol]
        while signed and book and (book[0][0] > 0) != (signed > 0):  # this fill closes existing lots
            lot = book[0]
            take = min(abs(signed), abs(lot[0]))
            long_side = lot[0] > 0
            entry, exit_ = (lot[1], f.price) if long_side else (f.price, lot[1])
            days = (pd.Timestamp(f.time) - pd.Timestamp(lot[2])).days
            rows.append({
                "symbol": f.symbol, "opened": pd.Timestamp(lot[2]), "closed": pd.Timestamp(f.time), "qty": take,
                "cost": take * entry, "proceeds": take * exit_, "pl": take * (exit_ - entry),
                "pl_pct": (exit_ / entry - 1) * 100 if entry else None, "days": days,
                "term": "Long-term" if days > LONG_TERM_DAYS else "Short-term",
                "direction": "Long" if long_side else "Short",
            })
            lot[0] += take if lot[0] < 0 else -take
            signed += take if signed < 0 else -take
            if lot[0] == 0:
                book.popleft()
        if signed:
            book.append([signed, f.price, f.time])
    return pd.DataFrame(rows, columns=cols)


def summary(closed: pd.DataFrame) -> dict:
    """Win rate, average win/loss and totals over closed trades."""
    if closed.empty:
        return {"trades": 0}
    wins, losses = closed[closed["pl"] > 0], closed[closed["pl"] < 0]
    return {
        "trades": len(closed),
        "total": closed["pl"].sum(),
        "win_rate": len(wins) / len(closed) * 100,
        "avg_win": wins["pl"].mean() if len(wins) else 0.0,
        "avg_loss": losses["pl"].mean() if len(losses) else 0.0,
        "avg_pct": closed["pl_pct"].mean(),
        "profit_factor": wins["pl"].sum() / -losses["pl"].sum() if len(losses) and losses["pl"].sum() else None,
        "short_term": closed.loc[closed["term"] == "Short-term", "pl"].sum(),
        "long_term": closed.loc[closed["term"] == "Long-term", "pl"].sum(),
    }
