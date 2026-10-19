"""Settings read from .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # never overrides variables already set (the Home Assistant add-on sets them)

# Where alerts, saved scans and briefs live. The Home Assistant add-on points this at /data,
# which survives add-on restarts and updates.
DATA_DIR = Path(os.getenv("DATA_DIR") or ROOT)


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


LIVE = os.getenv("TRADING_MODE", "paper").strip().lower() == "live"
MODE_LABEL = "LIVE" if LIVE else "PAPER"

# Paper and live keys are stored separately; TRADING_MODE picks which pair is used.
_acct = "LIVE" if LIVE else "PAPER"
ALPACA_API_KEY = os.getenv(f"ALPACA_{_acct}_API_KEY", "").strip()
ALPACA_SECRET_KEY = os.getenv(f"ALPACA_{_acct}_SECRET_KEY", "").strip()

IBKR_ENABLED = _flag("IBKR_ENABLED")
IBKR_HOST = os.getenv("IBKR_HOST", "127.0.0.1").strip()
IBKR_PORT = int(os.getenv("IBKR_PORT", "").strip() or (7496 if LIVE else 7497))
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "17").strip() or 17)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"
# Research panel provider: Claude if its key is set, otherwise Gemini.
AI_PROVIDER = "Claude" if os.getenv("ANTHROPIC_API_KEY", "").strip() else "Gemini" if GEMINI_API_KEY else None

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
SEC_CONTACT_EMAIL = os.getenv("SEC_CONTACT_EMAIL", "").strip()

WATCHLIST = [
    s.strip().upper()
    for s in os.getenv(
        "WATCHLIST", "SPY,QQQ,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,JPM"
    ).split(",")
    if s.strip()
]
