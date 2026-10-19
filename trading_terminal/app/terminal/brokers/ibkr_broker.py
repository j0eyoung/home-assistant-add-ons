"""Interactive Brokers via ib_async. Needs TWS or IB Gateway running locally.

ib_async is asyncio-based and Streamlit reruns the script on arbitrary threads, so
the IB connection lives on its own event-loop thread and every call hops onto it.
"""
from __future__ import annotations

import asyncio
import threading
import time

from ib_async import IB, LimitOrder, MarketOrder, Stock, StopOrder

from .base import Broker, OrderRequest

ACTIVE = {"PendingSubmit", "ApiPending", "PreSubmitted", "Submitted"}


def _last_message(trade) -> str:
    """Latest note IBKR attached to an order (warnings, rejection reasons)."""
    for entry in reversed(trade.log or []):
        if entry.message:
            return entry.message
    return ""


def _price(ticker) -> float | None:
    """Best available price: bid/ask midpoint, else last trade, else previous close."""
    import math

    ok = lambda v: v is not None and not math.isnan(v) and v > 0
    if ok(ticker.bid) and ok(ticker.ask):
        return (ticker.bid + ticker.ask) / 2
    for v in (ticker.last, ticker.close):
        if ok(v):
            return v
    return None


class IBKRBroker(Broker):
    name = "Interactive Brokers"

    def __init__(self, host: str, port: int, client_id: int):
        self.host, self.port, self.client_id = host, port, client_id
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.ib: IB | None = None
        self._run(self._connect())

    def _run(self, coro, timeout: float = 20):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    RETRY_AFTER = 30  # seconds between reconnect attempts while IB Gateway is down

    async def _connect(self):
        self.ib = IB()
        await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=8)

    async def _ensure(self):
        if self.ib is not None and self.ib.isConnected():
            return
        # While IB Gateway is down, fail fast instead of making every screen wait 8 s for a new attempt.
        since = time.time() - getattr(self, "_failed_at", 0)
        if since < self.RETRY_AFTER:
            raise ConnectionError(f"IB Gateway is not connected (retrying in {int(self.RETRY_AFTER - since)}s): "
                                  f"{getattr(self, '_fail_reason', '')}")
        try:
            await self._connect()
            self._failed_at = 0
        except Exception as e:
            self._failed_at, self._fail_reason = time.time(), str(e) or type(e).__name__
            raise

    def account(self) -> dict:
        async def go():
            await self._ensure()
            vals = {
                v.tag: v.value
                for v in self.ib.accountValues()
                if v.currency in ("USD", "BASE") and v.tag in ("NetLiquidation", "TotalCashValue", "BuyingPower")
            }
            return {
                "equity": float(vals.get("NetLiquidation", 0) or 0),
                "cash": float(vals.get("TotalCashValue", 0) or 0),
                "buying_power": float(vals.get("BuyingPower", 0) or 0),
                "currency": "USD",
            }

        return self._run(go())

    def positions(self) -> list[dict]:
        async def go():
            await self._ensure()
            return [
                {
                    "symbol": p.contract.symbol,
                    "qty": p.position,
                    "avg_cost": p.averageCost,
                    "price": p.marketPrice,
                    "market_value": p.marketValue,
                    "unrealized_pl": p.unrealizedPNL,
                }
                for p in self.ib.portfolio()
            ]

        return self._run(go())

    def orders(self) -> list[dict]:
        async def go():
            await self._ensure()
            await self.ib.reqAllOpenOrdersAsync()
            return [
                {
                    "id": str(t.order.orderId),
                    "symbol": t.contract.symbol,
                    "side": t.order.action.lower(),
                    "qty": t.order.totalQuantity,
                    "type": t.order.orderType.lower(),
                    "limit_price": t.order.lmtPrice if t.order.orderType == "LMT" else None,
                    "status": t.orderStatus.status,
                    "submitted": t.log[0].time if t.log else None,
                    "message": _last_message(t),
                }
                for t in self.ib.trades()
            ]

        return self._run(go())

    def activity(self):
        """Executions IBKR still reports (typically the last day or so). Dividends aren't in the API feed."""
        import pandas as pd

        async def go():
            await self._ensure()
            fills = await self.ib.reqExecutionsAsync()
            return [{"symbol": f.contract.symbol, "side": "buy" if f.execution.side == "BOT" else "sell",
                     "qty": float(f.execution.shares), "price": float(f.execution.price),
                     "time": pd.Timestamp(f.execution.time)}
                    for f in fills if f.contract.secType == "STK"]

        fills = pd.DataFrame(self._run(go()), columns=["symbol", "side", "qty", "price", "time"])
        return fills, pd.DataFrame(columns=["symbol", "amount", "date"])

    def forecast_markets(self, products: list[str], expiries: int = 2, max_contracts: int = 40) -> list[dict]:
        """ForecastEx event contracts (exchange FORECASTX). IBKR models them as options paying $1:
        a call is "Yes", a put "No", and the strike is the outcome's threshold. Returns events in the
        same shape as terminal.predictions, with the Yes price (0-1) as the market's probability."""
        from ib_async import Contract

        async def go():
            await self._ensure()
            self.ib.reqMarketDataType(4)  # live if subscribed, otherwise delayed / last available
            events, problems = [], {}
            for product in products:
                try:
                    details = await self.ib.reqContractDetailsAsync(
                        Contract(secType="OPT", symbol=product, exchange="FORECASTX", currency="USD", right="C"))
                except Exception as e:
                    problems[product] = str(e)
                    continue
                if not details:
                    problems[product] = "IBKR has no ForecastEx contracts under this code"
                    continue
                by_expiry: dict[str, list] = {}
                for d in details:
                    by_expiry.setdefault(d.contract.lastTradeDateOrContractMonth, []).append(d)
                for expiry in sorted(by_expiry)[:expiries]:
                    group = sorted(by_expiry[expiry], key=lambda d: d.contract.strike)[:max_contracts]
                    tickers = await self.ib.reqTickersAsync(*[d.contract for d in group])
                    outcomes = []
                    for d, t in zip(group, tickers):
                        p = _price(t)
                        if p is not None:
                            outcomes.append((f"{d.contract.strike:g}", p))
                    if outcomes:
                        name = group[0].longName or product
                        when = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}" if len(expiry) >= 8 else expiry
                        events.append({
                            "source": "IBKR ForecastEx", "title": f"{name} ({product})", "subtitle": f"Resolves {when}",
                            "category": "forecastex " + product.lower(), "volume": 0,
                            "outcomes": sorted(outcomes, key=lambda o: -o[1]),
                            "url": "https://forecasttrader.interactivebrokers.com",
                        })
            return events, problems

        return self._run(go(), timeout=60)

    def submit_order(self, req: OrderRequest) -> str:
        if req.is_option or req.take_profit or req.stop_loss:
            raise ValueError("Options and bracket orders are only supported through Alpaca in this app.")

        async def go():
            await self._ensure()
            contract = Stock(req.symbol, "SMART", "USD")
            if not await self.ib.qualifyContractsAsync(contract):
                raise ValueError(f"IBKR does not recognise {req.symbol}")
            action = "BUY" if req.side == "buy" else "SELL"
            tif = "GTC" if req.tif == "gtc" else "DAY"
            if req.order_type == "limit":
                order = LimitOrder(action, req.qty, req.limit_price, tif=tif)
            elif req.order_type == "stop":
                order = StopOrder(action, req.qty, req.stop_price, tif=tif)
            else:
                order = MarketOrder(action, req.qty, tif=tif)
            trade = self.ib.placeOrder(contract, order)
            # Give IBKR a few seconds to accept or reject it, so problems show up here and not as a
            # status that never moves.
            for _ in range(25):
                await asyncio.sleep(0.2)
                if trade.orderStatus.status not in ("PendingSubmit", "ApiPending"):
                    break
            if trade.orderStatus.status in ("Cancelled", "ApiCancelled", "Inactive"):
                raise ValueError(f"IBKR did not accept the order: {_last_message(trade) or trade.orderStatus.status}")
            return str(trade.order.orderId)

        return self._run(go())

    def cancel_order(self, order_id: str) -> None:
        async def go():
            await self._ensure()
            for t in self.ib.trades():
                if str(t.order.orderId) == order_id:
                    self.ib.cancelOrder(t.order)
                    return
            raise ValueError(f"No open IBKR order {order_id}")

        self._run(go())
