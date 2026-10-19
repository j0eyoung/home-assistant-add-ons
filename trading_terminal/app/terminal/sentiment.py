"""Headline sentiment, scored by the AI provider: -1 (clearly bad for the stock) to +1 (clearly good)."""
from __future__ import annotations

import json
import re

from . import ai

SYSTEM = ("You rate financial news headlines for how they are likely to affect one stock's price. "
          "Answer with JSON only.")

PROMPT = """Stock: {symbol}

Rate each headline from -1 (clearly negative for {symbol}'s share price) to +1 (clearly positive). \
Use 0 for neutral, unrelated, or mixed headlines, and for headlines mainly about other companies. \
Return a JSON array of numbers, one per headline, in the same order. Nothing else.

{lines}"""


def score(symbol: str, titles: list[str]) -> list[float | None]:
    if not titles:
        return []
    lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    # Low effort: a quick good/bad/neutral read per headline, run in the background often.
    text = ai.complete(PROMPT.format(symbol=symbol, lines=lines), SYSTEM, max_tokens=1000, effort="low")
    match = re.search(r"\[[^\[\]]*\]", text, re.S)
    try:
        values = json.loads(match.group(0)) if match else []
    except json.JSONDecodeError:
        values = []
    out = []
    for i in range(len(titles)):
        try:
            out.append(max(-1.0, min(1.0, float(values[i]))))
        except (IndexError, TypeError, ValueError):
            out.append(None)
    return out


def label(v: float | None) -> tuple[str, str]:
    """(word, state) for a score; state is positive / negative / neutral / unknown."""
    if v is None:
        return "Unrated", "unknown"
    if v >= 0.25:
        return "Positive", "positive"
    if v <= -0.25:
        return "Negative", "negative"
    return "Neutral", "neutral"
