"""Your trading plan: goals, risk limits and rules, sent with every AI request so answers fit you."""
from __future__ import annotations

import json

from . import config

PATH = config.DATA_DIR / "trading_plan.json"

# key -> (label, help text, kind, default). kind: text | area | number | choice:<a|b|c>
FIELDS = {
    "goal": ("Main goal", "e.g. grow a retirement account steadily, generate income, learn to swing trade", "area", ""),
    "experience": ("Experience", "", "choice:New to trading|Some experience|Experienced", "Some experience"),
    "horizon": ("Usual holding period", "", "choice:Days|Weeks|Months|Years", "Weeks"),
    "account_size": ("Money set aside for trading ($)", "Only what you can afford to lose", "number", 0.0),
    "risk_per_trade": ("Max risk per trade (% of account)", "Common rule of thumb: 1-2%", "number", 1.0),
    "max_position": ("Max size of one position (% of account)", "", "number", 20.0),
    "max_drawdown": ("Stop trading for a while if the account falls (%)", "", "number", 15.0),
    "style": ("What you trade and how", "e.g. large-cap US stocks, trend following, no options yet", "area", ""),
    "avoid": ("What you want to avoid", "e.g. penny stocks, holding through earnings, margin", "area", ""),
    "rules": ("Your rules", "e.g. always set a stop, no more than 5 positions, never average down", "area", ""),
    "notes": ("Anything else the assistant should know", "taxes, other accounts, schedule...", "area", ""),
}


def load() -> dict:
    try:
        saved = json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    return {k: saved.get(k, f[3]) for k, f in FIELDS.items()}


def save(values: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(values, indent=1))


def is_set() -> bool:
    p = load()
    return any(p[k] for k in ("goal", "style", "rules", "avoid")) or bool(p["account_size"])


def for_ai() -> dict:
    """Only the parts that are filled in, with readable names."""
    p = load()
    return {FIELDS[k][0]: v for k, v in p.items() if v not in ("", 0, 0.0, None)}
