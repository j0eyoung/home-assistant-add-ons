"""Technical indicators on a pandas Series of closing prices."""
from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI, 0-100."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + gain / loss)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """(macd line, signal line, histogram)."""
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    """(lower band, middle, upper band)."""
    mid = sma(close, n)
    sd = close.rolling(n).std()
    return mid - k * sd, mid, mid + k * sd
