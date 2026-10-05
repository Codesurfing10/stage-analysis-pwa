"""Broker registry. Default name comes from config.yaml `broker` (schwab)."""
from __future__ import annotations

from typing import Optional, Type

from .alpaca import AlpacaBroker
from .base import BrokerClient, DryRunRefused, NeedsAuth
from .etrade import EtradeBroker
from .ibkr import IbkrBroker
from .schwab import SchwabBroker
from .tastytrade import TastytradeBroker
from .tradier import TradierBroker

ADAPTERS: dict[str, Type[BrokerClient]] = {
    "schwab": SchwabBroker,
    "alpaca": AlpacaBroker,
    "tradier": TradierBroker,
    "ibkr": IbkrBroker,
    "etrade": EtradeBroker,
    "tastytrade": TastytradeBroker,
}

__all__ = [
    "ADAPTERS",
    "BrokerClient",
    "DryRunRefused",
    "NeedsAuth",
    "get_broker",
    "list_brokers",
]


def list_brokers() -> list[str]:
    return list(ADAPTERS)


def get_broker(name: Optional[str] = None) -> BrokerClient:
    """Return an adapter. If name is omitted, read config.yaml key `broker` (default schwab)."""
    if name is None or not str(name).strip():
        from signals import load_config

        cfg = load_config() or {}
        name = str(cfg.get("broker") or "schwab")
    key = str(name).strip().lower()
    cls = ADAPTERS.get(key)
    if cls is None:
        known = ", ".join(ADAPTERS)
        raise KeyError(f"Unknown broker {key!r}. Known: {known}")
    return cls()
