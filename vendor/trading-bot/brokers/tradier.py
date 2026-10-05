"""Tradier brokerage equity adapter (sandbox REST by default).

Env:
  TRADIER_ACCESS_TOKEN
  TRADIER_ACCOUNT_ID
Optional:
  TRADIER_BASE_URL  default https://sandbox.tradier.com
                    production host is https://api.tradier.com (not the default)

Orders: POST {base}/v1/accounts/{account_id}/orders
Refuses to POST while config dry_run is true.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from signals import OrderTicket

from .base import BrokerClient, NeedsAuth, first_env, resolve_qty


_SANDBOX_BASE = "https://sandbox.tradier.com"


class TradierBroker(BrokerClient):
    name = "tradier"
    mode = "sandbox-default"
    env_vars = ("TRADIER_ACCESS_TOKEN", "TRADIER_ACCOUNT_ID")

    def credentials_present(self) -> bool:
        return bool(first_env("TRADIER_ACCESS_TOKEN") and first_env("TRADIER_ACCOUNT_ID"))

    def base_url(self) -> str:
        raw = os.environ.get("TRADIER_BASE_URL", "").strip()
        return (raw or _SANDBOX_BASE).rstrip("/")

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        token = first_env("TRADIER_ACCESS_TOKEN")
        account = first_env("TRADIER_ACCOUNT_ID")
        if not token or not account:
            raise NeedsAuth(
                "tradier: set TRADIER_ACCESS_TOKEN and TRADIER_ACCOUNT_ID. "
                "No order was sent."
            )
        qty = resolve_qty(ticket)
        side = "buy" if ticket.side.upper() == "BUY" else "sell"
        order_type = (ticket.order_type or "LIMIT").lower()
        data = {
            "class": "equity",
            "symbol": ticket.symbol,
            "side": side,
            "quantity": str(qty),
            "type": "market" if order_type == "market" else "limit",
            "duration": "day",
        }
        if data["type"] == "limit":
            if ticket.limit_price is None:
                raise ValueError("LIMIT order requires limit_price")
            data["price"] = f"{float(ticket.limit_price):.2f}"
        url = f"{self.base_url()}/v1/accounts/{account}/orders"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            data=data,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"tradier order failed: HTTP {resp.status_code}")
        body = resp.json() if resp.content else {}
        order = body.get("order") if isinstance(body, dict) else None
        order_id = None
        if isinstance(order, dict):
            order_id = order.get("id")
        return {
            "broker": "tradier",
            "status_code": resp.status_code,
            "order_id": order_id,
            "symbol": ticket.symbol,
            "side": ticket.side,
        }
