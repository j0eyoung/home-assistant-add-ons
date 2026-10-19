"""Builds the brokers that are configured in .env."""
from __future__ import annotations

from .. import config
from .base import Broker, OrderRequest

__all__ = ["Broker", "OrderRequest", "connect_all"]


def connect_all() -> tuple[dict[str, Broker], dict[str, str]]:
    """Returns (connected brokers by name, error message by name for ones that failed)."""
    brokers: dict[str, Broker] = {}
    errors: dict[str, str] = {}

    if config.ALPACA_API_KEY and config.ALPACA_SECRET_KEY:
        try:
            from .alpaca_broker import AlpacaBroker

            b = AlpacaBroker(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY, paper=not config.LIVE)
            b.account()
            brokers[b.name] = b
        except Exception as e:
            errors["Alpaca"] = str(e)

    if config.IBKR_ENABLED:
        try:
            from .ibkr_broker import IBKRBroker

            b = IBKRBroker(config.IBKR_HOST, config.IBKR_PORT, config.IBKR_CLIENT_ID)
            brokers[b.name] = b
        except Exception as e:
            errors["Interactive Brokers"] = (
                f"{e or type(e).__name__} - is TWS / IB Gateway running on "
                f"{config.IBKR_HOST}:{config.IBKR_PORT} with API access enabled?"
            )

    return brokers, errors
