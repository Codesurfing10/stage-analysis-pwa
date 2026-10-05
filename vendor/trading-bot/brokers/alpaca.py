"""Alpaca Markets equity adapter (paper REST by default).

Env (either hyphenated or official underscore form):
  APCA-API-KEY-ID or APCA_API_KEY_ID
  APCA-API-SECRET-KEY or APCA_API_SECRET_KEY
Optional:
  APCA_API_BASE_URL  default https://paper-api.alpaca.markets
                     live host is https://api.alpaca.markets (not the default)

Orders: POST {base}/v2/orders
This method refuses to POST while config dry_run is true.
"""
from __future__ import annotations

from typing import Any

import requests

from signals import OrderTicket

from .base import BrokerClient, NeedsAuth, first_env, resolve_qty


_PAPER_BASE = "https://paper-api.alpaca.markets"


class AlpacaBroker(BrokerClient):
    name = "alpaca"
    mode = "paper-default"
    env_vars = (
        "APCA-API-KEY-ID",
        "APCA-API-SECRET-KEY",
        "APCA_API_KEY_ID",
        "APCA_API_SECRET_KEY",
    )

    def _key(self) -> str:
        return first_env("APCA-API-KEY-ID", "APCA_API_KEY_ID")

    def _secret(self) -> str:
        return first_env("APCA-API-SECRET-KEY", "APCA_API_SECRET_KEY")

    def credentials_present(self) -> bool:
        return bool(self._key() and self._secret())

    def base_url(self) -> str:
        import os

        raw = os.environ.get("APCA_API_BASE_URL", "").strip()
        return (raw or _PAPER_BASE).rstrip("/")

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        if not self.credentials_present():
            raise NeedsAuth(
                "alpaca: set APCA-API-KEY-ID and APCA-API-SECRET-KEY "
                "(or APCA_API_KEY_ID / APCA_API_SECRET_KEY). No order was sent."
            )
        qty = resolve_qty(ticket)
        side = "buy" if ticket.side.upper() == "BUY" else "sell"
        order_type = (ticket.order_type or "LIMIT").lower()
        payload: dict[str, Any] = {
            "symbol": ticket.symbol,
            "qty": str(qty),
            "side": side,
            "type": "market" if order_type == "market" else "limit",
            "time_in_force": "day",
        }
        if payload["type"] == "limit":
            if ticket.limit_price is None:
                raise ValueError("LIMIT order requires limit_price")
            payload["limit_price"] = f"{float(ticket.limit_price):.2f}"
        url = self.base_url() + "/v2/orders"
        resp = requests.post(
            url,
            headers={
                "APCA-API-KEY-ID": self._key(),
                "APCA-API-SECRET-KEY": self._secret(),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"alpaca order failed: HTTP {resp.status_code}")
        body = resp.json() if resp.content else {}
        return {
            "broker": "alpaca",
            "status_code": resp.status_code,
            "order_id": body.get("id"),
            "symbol": ticket.symbol,
            "side": ticket.side,
        }
