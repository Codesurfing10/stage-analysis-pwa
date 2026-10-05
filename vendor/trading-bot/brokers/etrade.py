"""E*TRADE OAuth 1.0a stub.

Env names (values are never printed):
  ETRADE_CONSUMER_KEY
  ETRADE_CONSUMER_SECRET
  ETRADE_ACCESS_TOKEN       # absent until the OAuth dance finishes
  ETRADE_ACCESS_SECRET
  ETRADE_ACCOUNT_ID
Optional:
  ETRADE_BASE_URL  default sandbox https://apisb.etrade.com
                   production is https://api.etrade.com (not the default)

credentials_present is false until consumer key/secret AND access token/secret
AND account id are all set. place_equity_order raises NeedsAuth and does not
sign a request or POST /v1/accounts/{id}/orders/place. Completing OAuth is a
manual step outside this stub.
"""
from __future__ import annotations

import os
from typing import Any

from signals import OrderTicket

from .base import BrokerClient, NeedsAuth, env_flag


_SANDBOX_BASE = "https://apisb.etrade.com"
_REQUIRED = (
    "ETRADE_CONSUMER_KEY",
    "ETRADE_CONSUMER_SECRET",
    "ETRADE_ACCESS_TOKEN",
    "ETRADE_ACCESS_SECRET",
    "ETRADE_ACCOUNT_ID",
)


class EtradeBroker(BrokerClient):
    name = "etrade"
    mode = "oauth-stub"
    env_vars = _REQUIRED + ("ETRADE_BASE_URL",)

    def credentials_present(self) -> bool:
        return all(env_flag(name) for name in _REQUIRED)

    def base_url(self) -> str:
        raw = os.environ.get("ETRADE_BASE_URL", "").strip()
        return (raw or _SANDBOX_BASE).rstrip("/")

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        missing = [n for n in _REQUIRED if not env_flag(n)]
        if missing:
            raise NeedsAuth(
                "etrade NeedsAuth until OAuth tokens exist. Missing: "
                + ", ".join(missing)
                + ". Consumer key/secret alone are not enough. No order was sent."
            )
        raise NeedsAuth(
            "etrade NeedsAuth: OAuth stub does not sign or POST orders "
            f"(base {self.base_url()}). No order was sent for {ticket.symbol}."
        )
