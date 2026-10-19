"""Read-only MCP tool server: gives Claude the terminal's research tools (terminal/tools.py).
Nothing here can place, change or cancel an order.

  python mcp_server.py                 # stdio (Claude Code / Claude Desktop start it themselves)
  python mcp_server.py --http 8765     # long-running server at http://127.0.0.1:8765/mcp (the add-on uses this)

Register with Claude Code:  claude mcp add trading-terminal -- <path>\\.venv\\Scripts\\python.exe <path>\\mcp_server.py
"""
from __future__ import annotations

import os
import sys

# Its own IB Gateway connection, so it never clashes with the app's (IBKR rejects duplicate client ids).
os.environ["IBKR_CLIENT_ID"] = str(int(os.getenv("IBKR_CLIENT_ID", "17") or 17) + 1)

from mcp.server.mcpserver import MCPServer  # noqa: E402

from terminal import tools  # noqa: E402

INSTRUCTIONS = """Read-only market research tools from the user's personal trading terminal. Use them for any figure
you cite instead of relying on memory: quotes and history for stocks, ETFs, indexes, futures, forex and crypto;
technicals; company profiles, 15 years of SEC financial statements, earnings, analyst views, valuation scores,
news, insider trades and SEC filing text; options chains with implied volatility and expected moves; ETF holdings;
an S&P 500 screener; FRED economic data; prediction-market odds; backtests; and the user's own portfolio, orders,
journal, gains and trading plan. Symbols use Yahoo style (AAPL, BRK-B, ^GSPC, ^VIX, ES=F, CL=F, EURUSD=X, BTC-USD).
None of these tools can trade."""

mcp = MCPServer("trading-terminal", instructions=INSTRUCTIONS)
for fn in tools.TOOLS:
    mcp.tool()(fn)


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(sys.argv[sys.argv.index("--http") + 1]) if len(sys.argv) > sys.argv.index("--http") + 1 else 8765
        mcp.run("streamable-http", host="127.0.0.1", port=port, stateless_http=True)
    else:
        mcp.run()
