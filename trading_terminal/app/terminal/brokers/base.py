"""Common shape every broker adapter returns, so the UI doesn't care which one it is."""
from __future__ import annotations

import re
from dataclasses import dataclass

# OCC option contract symbol, e.g. AAPL261016C00330000
OPTION_SYMBOL = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")


@dataclass
class OrderRequest:
    symbol: str
    side: str  # "buy" | "sell"
    qty: float
    order_type: str = "market"  # "market" | "limit" | "stop"
    limit_price: float | None = None
    stop_price: float | None = None
    tif: str = "day"  # "day" | "gtc"
    # Exit orders attached to the entry (a "bracket"); either or both may be set.
    take_profit: float | None = None
    stop_loss: float | None = None

    @property
    def is_option(self) -> bool:
        return bool(OPTION_SYMBOL.match(self.symbol))

    def describe(self) -> str:
        price = ""
        if self.order_type == "limit":
            price = f" @ {self.limit_price:,.2f} LIMIT"
        elif self.order_type == "stop":
            price = f" @ {self.stop_price:,.2f} STOP"
        else:
            price = " @ MARKET"
        exits = ""
        if self.take_profit:
            exits += f", take profit {self.take_profit:,.2f}"
        if self.stop_loss:
            exits += f", stop loss {self.stop_loss:,.2f}"
        unit = " contract(s)" if self.is_option else ""
        return f"{self.side.upper()} {self.qty:g}{unit} {self.symbol}{price} ({self.tif.upper()}){exits}"


class Broker:
    name = "broker"

    def account(self) -> dict:
        """{'equity', 'cash', 'buying_power', 'currency'}"""
        raise NotImplementedError

    def positions(self) -> list[dict]:
        """[{'symbol', 'qty', 'avg_cost', 'price', 'market_value', 'unrealized_pl'}]"""
        raise NotImplementedError

    def orders(self) -> list[dict]:
        """[{'id', 'symbol', 'side', 'qty', 'type', 'limit_price', 'status', 'submitted'}]"""
        raise NotImplementedError

    def submit_order(self, req: OrderRequest) -> str:
        """Send the order; return the broker's order id."""
        raise NotImplementedError

    def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError

    def activity(self):
        """(fills, dividends) DataFrames. fills: symbol, side, qty, price, time.
        dividends: symbol, amount, date. Empty when the broker doesn't provide them."""
        import pandas as pd

        return pd.DataFrame(columns=["symbol", "side", "qty", "price", "time"]), \
            pd.DataFrame(columns=["symbol", "amount", "date"])

    def portfolio_history(self, period: str = "1M"):
        """Account value over time as a pandas Series; empty if the broker doesn't provide it."""
        import pandas as pd

        return pd.Series(dtype=float)
