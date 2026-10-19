"""Stock idea lists: preset combinations of checks run over the S&P 500 scan.

Stage 1 uses columns the scan already has (all 503 stocks, instant). Stage 2 ("deep" checks)
needs one or two API calls per stock, so it only runs on the best stage-1 matches.
These are filters on public data, not recommendations.
"""
from __future__ import annotations

import pandas as pd

from . import config, sources

MAX_DEEP = 15  # stocks per list that get the deep checks


def _rating(d: pd.DataFrame) -> pd.Series:
    """Average analyst rating as a number: 1 = strong buy ... 5 = strong sell ("1.8 - Buy" -> 1.8)."""
    if "analyst_rating" not in d:
        return pd.Series(float("nan"), index=d.index)
    return pd.to_numeric(d["analyst_rating"].astype(str).str.split(" - ").str[0], errors="coerce")


def _col(d: pd.DataFrame, name: str) -> pd.Series:
    return d[name] if name in d else pd.Series(float("nan"), index=d.index)


# key -> (label, explanation, test over the scan DataFrame)
CHECKS = {
    "uptrend": ("Uptrend", "Above both its 50-day and 200-day averages",
                lambda d: d["above_50d"] & d["above_200d"]),
    "above_200d": ("Long-term uptrend", "Above its 200-day average", lambda d: d["above_200d"]),
    "oversold": ("Recent dip", "RSI below 40: it has fallen faster than usual lately", lambda d: d["rsi"] < 40),
    "analyst_buy": ("Analysts: Buy", "Average analyst rating of Buy or better", lambda d: _rating(d) <= 2.0),
    "near_high": ("Near 52-week high", "Within 5% of its 52-week high", lambda d: d["from_high"] > -5),
    "momentum": ("Strong 3 months", "Up more than 10% over 3 months", lambda d: d["chg_3m"] > 10),
    "cheap": ("Low forward P/E", "Forward P/E between 0 and 15", lambda d: _col(d, "fwd_pe").between(0.01, 15)),
    "far_from_high": ("Well off its high", "25% or more below its 52-week high", lambda d: d["from_high"] < -25),
    "dividend": ("Dividend 3%+", "Dividend yield of 3% or more", lambda d: _col(d, "div_yield") >= 3),
}

DEEP = {
    "piotroski": ("Piotroski 7+", "Financial-strength score of 7 or more out of 9 (Financial Modeling Prep)"),
    "beats": ("Beats estimates", "Beat EPS estimates in at least 3 of the last 4 quarters (Finnhub)"),
    "insider_buy": ("Insiders buying", "An insider bought shares on the open market in the last 6 months (Finnhub)"),
}

IDEAS = {
    "Quality pullbacks": ("Long-term uptrend with a recent dip, analysts positive, strong financials.",
                          ["above_200d", "oversold", "analyst_buy"], ["piotroski", "beats"]),
    "Momentum leaders": ("Strong trend near its highs, backed by earnings beats.",
                         ["uptrend", "near_high", "momentum"], ["beats", "insider_buy"]),
    "Value with backing": ("Cheap on forward earnings with analysts and insiders on side.",
                           ["cheap", "analyst_buy"], ["piotroski", "insider_buy"]),
    "Beaten-down quality": ("Far below its high but financially strong and still beating estimates.",
                            ["far_from_high", "analyst_buy"], ["piotroski", "beats"]),
    "Dividend payers in uptrends": ("3%+ dividend and above its 200-day average.",
                                    ["dividend", "above_200d"], ["piotroski", "beats"]),
}


def stage1(scan: pd.DataFrame, idea: str) -> pd.DataFrame:
    """Stocks passing every price/valuation check of an idea, best analyst rating first."""
    _, checks, _ = IDEAS[idea]
    mask = pd.Series(True, index=scan.index)
    for c in checks:
        mask &= CHECKS[c][2](scan).fillna(False).astype(bool)
    out = scan[mask].copy()
    out["_rating"] = _rating(out)
    return out.sort_values(["_rating", "market_cap" if "market_cap" in out else "symbol"],
                           ascending=[True, False]).drop(columns="_rating")


def deep_checks(symbols: list[str], needed: list[str]) -> dict[str, dict[str, bool | None]]:
    """{symbol: {check: True/False, or None when the data is unavailable}}."""
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=180)
    out = {}
    for s in symbols:
        r: dict[str, bool | None] = {}
        if "piotroski" in needed:
            try:
                v = sources.fmp("financial-scores", s).get("piotroskiScore") if config.FMP_API_KEY else None
                r["piotroski"] = None if v is None else v >= 7
            except Exception:
                r["piotroski"] = None
        if "beats" in needed:
            try:
                e = sources.earnings_surprises(s).head(4) if config.FINNHUB_API_KEY else pd.DataFrame()
                r["beats"] = None if e.empty else int((e["surprisePercent"] > 0).sum()) >= 3
            except Exception:
                r["beats"] = None
        if "insider_buy" in needed:
            try:
                t = sources.insider_transactions(s) if config.FINNHUB_API_KEY else pd.DataFrame()
                if t.empty:
                    r["insider_buy"] = None if not config.FINNHUB_API_KEY else False
                else:
                    buys = t[(t["transactionCode"] == "P") & (pd.to_datetime(t["transactionDate"]) > cutoff)]
                    r["insider_buy"] = not buys.empty
            except Exception:
                r["insider_buy"] = None
        out[s] = r
    return out
