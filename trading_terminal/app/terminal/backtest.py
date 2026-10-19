"""Long-only backtests of simple rules on daily prices.

Signals are read at each day's close and acted on at the next day's open, so a rule never
trades on a price it could not have known. No commissions, slippage, dividends or taxes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind

# name -> (description template, default parameters as {key: (label, default, min, max)})
STRATEGIES = {
    "RSI dip": (
        "Buy when RSI({length}) falls below {buy_below}; sell when it rises above {sell_above}.",
        {"length": ("RSI length", 14, 2, 50), "buy_below": ("Buy below", 30, 5, 50),
         "sell_above": ("Sell above", 70, 50, 95)},
    ),
    "Moving-average crossover": (
        "Hold while the {fast}-day average is above the {slow}-day average; otherwise stay in cash.",
        {"fast": ("Fast average (days)", 50, 2, 100), "slow": ("Slow average (days)", 200, 10, 300)},
    ),
    "Bollinger bounce": (
        "Buy when the close drops below the lower Bollinger band ({length} days, {width} std); "
        "sell when it gets back above the middle band.",
        {"length": ("Band length", 20, 5, 60), "width": ("Band width (std)", 2, 1, 4)},
    ),
    "Breakout": (
        "Buy when the close beats the highest close of the previous {entry} days; "
        "sell when it falls below the lowest close of the previous {exit} days.",
        {"entry": ("Breakout window (days)", 55, 5, 250), "exit": ("Exit window (days)", 20, 5, 120)},
    ),
}


@dataclass
class Result:
    equity: pd.Series  # strategy account value
    benchmark: pd.Series  # buy and hold the same stock
    position: pd.Series  # 1 = invested during that day
    trades: pd.DataFrame  # entry_date, entry, exit_date, exit, return_pct, days, open
    stats: dict


def _hold_between(entries: pd.Series, exits: pd.Series) -> pd.Series:
    """1 from an entry signal until the next exit signal."""
    state = pd.Series(np.nan, index=entries.index)
    state[exits.fillna(False)] = 0
    state[entries.fillna(False)] = 1
    return state.ffill().fillna(0)


def signals(df: pd.DataFrame, strategy: str, p: dict) -> pd.Series:
    close = df["Close"]
    if strategy == "RSI dip":
        r = ind.rsi(close, int(p["length"]))
        return _hold_between(r < p["buy_below"], r > p["sell_above"])
    if strategy == "Moving-average crossover":
        return (ind.sma(close, int(p["fast"])) > ind.sma(close, int(p["slow"]))).astype(float)
    if strategy == "Bollinger bounce":
        lower, mid, _ = ind.bollinger(close, int(p["length"]), float(p["width"]))
        return _hold_between(close < lower, close > mid)
    if strategy == "Breakout":
        high = close.rolling(int(p["entry"])).max().shift(1)
        low = close.rolling(int(p["exit"])).min().shift(1)
        return _hold_between(close > high, close < low)
    raise ValueError(f"Unknown strategy {strategy}")


def run(df: pd.DataFrame, strategy: str, p: dict, capital: float = 10_000) -> Result:
    df = df.dropna(subset=["Open", "Close"])
    o, c = df["Open"], df["Close"]
    pos = signals(df, strategy, p).shift(1).fillna(0)  # decided at yesterday's close, held from today's open
    before = pos.shift(1).fillna(0)
    prev_c = c.shift(1)
    daily = np.select(
        [(pos == 1) & (before == 1), (pos == 1) & (before == 0), (pos == 0) & (before == 1)],
        [c / prev_c - 1, c / o - 1, o / prev_c - 1],
        default=0.0,
    )
    daily = pd.Series(daily, index=df.index).fillna(0)
    equity = capital * (1 + daily).cumprod()
    benchmark = capital * c / c.iloc[0]

    trades, entry = [], None
    for day, now, was in zip(df.index, pos, before):
        if now == 1 and was == 0:
            entry = (day, o[day])
        elif now == 0 and was == 1 and entry:
            trades.append((*entry, day, o[day], False))
            entry = None
    if entry:
        trades.append((*entry, df.index[-1], c.iloc[-1], True))
    t = pd.DataFrame(trades, columns=["entry_date", "entry", "exit_date", "exit", "open"])
    if not t.empty:
        t["return_pct"] = (t["exit"] / t["entry"] - 1) * 100
        t["days"] = (pd.to_datetime(t["exit_date"]) - pd.to_datetime(t["entry_date"])).dt.days

    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-9)
    closed = t[~t["open"]] if not t.empty else t

    def summary(curve: pd.Series, rets: pd.Series) -> dict:
        return {
            "total_return": (curve.iloc[-1] / capital - 1) * 100,
            "cagr": ((curve.iloc[-1] / capital) ** (1 / years) - 1) * 100,
            "max_drawdown": (curve / curve.cummax() - 1).min() * 100,
            "sharpe": rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0,
        }

    stats = summary(equity, daily)
    stats.update({
        "trades": len(t),
        "win_rate": (closed["return_pct"] > 0).mean() * 100 if len(closed) else None,
        "avg_trade": closed["return_pct"].mean() if len(closed) else None,
        "exposure": pos.mean() * 100,
        "final": equity.iloc[-1],
        "benchmark": summary(benchmark, c.pct_change().fillna(0)),
    })
    return Result(equity, benchmark, pos, t, stats)
