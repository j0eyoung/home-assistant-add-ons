from __future__ import annotations

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLossRequest,
    StopOrderRequest,
    TakeProfitRequest,
)

from .base import Broker, OrderRequest


def _f(v) -> float | None:
    return float(v) if v is not None else None


class AlpacaBroker(Broker):
    name = "Alpaca"

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.client = TradingClient(api_key, secret_key, paper=paper)
        self._auth = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
        self._base = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"

    def _activities(self, kind: str, pages: int = 20) -> list[dict]:
        """Account activity (FILL, DIV, ...) newest first; alpaca-py has no wrapper for this endpoint."""
        import requests

        out, token = [], None
        for _ in range(pages):
            params = {"activity_types": kind, "page_size": 100, "direction": "desc"}
            if token:
                params["page_token"] = token
            r = requests.get(f"{self._base}/v2/account/activities", params=params, headers=self._auth, timeout=20)
            r.raise_for_status()
            page = r.json()
            out += page
            if len(page) < 100:
                break
            token = page[-1]["id"]
        return out

    def activity(self):
        import pandas as pd

        fills = pd.DataFrame([
            {"symbol": a["symbol"], "side": "buy" if a["side"] == "buy" else "sell", "qty": float(a["qty"]),
             "price": float(a["price"]), "time": pd.Timestamp(a["transaction_time"])}
            for a in self._activities("FILL")
        ], columns=["symbol", "side", "qty", "price", "time"])
        divs = pd.DataFrame([
            {"symbol": a.get("symbol"), "amount": float(a.get("net_amount") or 0), "date": pd.Timestamp(a["date"])}
            for a in self._activities("DIV")
        ], columns=["symbol", "amount", "date"])
        return fills, divs

    def account(self) -> dict:
        a = self.client.get_account()
        return {
            "equity": _f(a.equity),
            "cash": _f(a.cash),
            "buying_power": _f(a.buying_power),
            "currency": a.currency,
        }

    def positions(self) -> list[dict]:
        return [
            {
                "symbol": p.symbol,
                "qty": _f(p.qty),
                "avg_cost": _f(p.avg_entry_price),
                "price": _f(p.current_price),
                "market_value": _f(p.market_value),
                "unrealized_pl": _f(p.unrealized_pl),
            }
            for p in self.client.get_all_positions()
        ]

    def orders(self) -> list[dict]:
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=50)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "side": o.side.value,
                "qty": _f(o.qty),
                "type": o.order_type.value,
                "limit_price": _f(o.limit_price),
                "status": o.status.value,
                "submitted": o.submitted_at,
            }
            for o in self.client.get_orders(filter=req)
        ]

    def submit_order(self, req: OrderRequest) -> str:
        common = dict(
            symbol=req.symbol,
            qty=req.qty,
            side=OrderSide.BUY if req.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC if req.tif == "gtc" else TimeInForce.DAY,
        )
        if req.take_profit or req.stop_loss:
            both = req.take_profit and req.stop_loss
            common["order_class"] = OrderClass.BRACKET if both else OrderClass.OTO
            if req.take_profit:
                common["take_profit"] = TakeProfitRequest(limit_price=req.take_profit)
            if req.stop_loss:
                common["stop_loss"] = StopLossRequest(stop_price=req.stop_loss)
        if req.order_type == "limit":
            order = LimitOrderRequest(limit_price=req.limit_price, **common)
        elif req.order_type == "stop":
            order = StopOrderRequest(stop_price=req.stop_price, **common)
        else:
            order = MarketOrderRequest(**common)
        return str(self.client.submit_order(order_data=order).id)

    def cancel_order(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)

    # Range label -> (Alpaca period, bar size)
    HISTORY = {"1D": ("1D", "5Min"), "1W": ("1W", "1H"), "1M": ("1M", "1D"), "3M": ("3M", "1D"), "1Y": ("1A", "1D")}

    def portfolio_history(self, period: str = "1M"):
        import pandas as pd
        from alpaca.trading.requests import GetPortfolioHistoryRequest

        p, tf = self.HISTORY.get(period, ("1M", "1D"))
        h = self.client.get_portfolio_history(GetPortfolioHistoryRequest(period=p, timeframe=tf))
        # Market time, to match the stock charts (and the hover dates on the portfolio chart)
        index = pd.to_datetime(h.timestamp, unit="s", utc=True).tz_convert("America/New_York")
        s = pd.Series(h.equity, index=index, dtype=float)
        return s[s > 0]  # zeros are days before the account existed
