"""Home Assistant add-on entry point: add-on options -> environment variables -> start the app.

The app reads its settings from environment variables (the same names as in .env), so each
option is exported upper-cased, e.g. finnhub_api_key -> FINNHUB_API_KEY.
"""
import json
import os
import sys
from pathlib import Path

import shared_secrets  # noqa: E402

shared_secrets.main()  # fill blank options from addon_secrets.json before they are read

options_file = Path(os.getenv("OPTIONS_PATH", "/data/options.json"))
options = json.loads(options_file.read_text()) if options_file.exists() else {}
for key, value in options.items():
    if value not in (None, ""):
        os.environ[key.upper()] = str(value).lower() if isinstance(value, bool) else str(value)
os.environ.setdefault("DATA_DIR", "/data")
# Claude Code keeps its subscription sign-in here, so it survives add-on restarts and updates.
os.environ.setdefault("CLAUDE_CONFIG_DIR", os.path.join(os.environ["DATA_DIR"], "claude"))
Path(os.environ["CLAUDE_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
# The IB Gateway add-on serves paper on 4004 and live on 4003; with no port set, match trading_mode.
if not os.getenv("IBKR_PORT") and os.getenv("IBKR_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
    os.environ["IBKR_PORT"] = "4003" if os.getenv("TRADING_MODE", "paper").lower() == "live" else "4004"
Path(os.environ["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

# The read-only research tools for Claude, as an always-on local service (starting them per question would
# take several seconds on a small device). Claude Code connects to it through TERMINAL_MCP_URL.
import subprocess  # noqa: E402

TOOLS_PORT = os.getenv("TOOLS_PORT", "8765")
subprocess.Popen([sys.executable, "mcp_server.py", "--http", TOOLS_PORT])
os.environ["TERMINAL_MCP_URL"] = f"http://127.0.0.1:{TOOLS_PORT}/mcp"

port = os.getenv("PORT", "8501")
if os.getenv("UI", "new").lower() != "classic":
    # The fast web terminal (web/server.py). Home Assistant's ingress proxy handles the login in front of it.
    os.environ["HOST"] = "0.0.0.0"
    os.execvp(sys.executable, [sys.executable, "-m", "web.server"])
os.execvp(sys.executable, [
    sys.executable, "-m", "streamlit", "run", "app.py",
    "--server.address=0.0.0.0", f"--server.port={port}", "--server.headless=true",
    # Home Assistant's ingress proxy sits in front of the app and handles the login, so the
    # browser never talks to Streamlit directly; these checks would reject the proxied requests.
    "--server.enableCORS=false", "--server.enableXsrfProtection=false",
    "--browser.gatherUsageStats=false",
])
