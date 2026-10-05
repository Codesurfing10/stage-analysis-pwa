"""tastytrade OAuth session stub.

Username/password session login is intentionally unsupported. Do not set or
store TASTY_USERNAME. This module never reads that variable.

Documented env names only:
  TASTY_CLIENT_ID
  TASTY_CLIENT_SECRET
  TASTY_REFRESH_TOKEN
  TASTY_ACCOUNT_NUMBER
Optional:
  TASTY_API_BASE_URL  default certification https://api.cert.tastyworks.com
                      production is https://api.tastyworks.com (not the default)

OAuth refresh would be POST {base}/oauth/token (grant_type=refresh_token).
This stub does not exchange a session and does not POST orders.
place_equity_order always raises NeedsAuth.
"""
from __future__ import annotations

import os
from typing import Any

from signals import OrderTicket

from .base import BrokerClient, NeedsAuth, env_flag


_CERT_BASE = "https://api.cert.tastyworks.com"
_REQUIRED = (
    "TASTY_CLIENT_ID",
    "TASTY_CLIENT_SECRET",
    "TASTY_REFRESH_TOKEN",
    "TASTY_ACCOUNT_NUMBER",
)


class TastytradeBroker(BrokerClient):
    name = "tastytrade"
    mode = "session-stub"
    env_vars = _REQUIRED + ("TASTY_API_BASE_URL",)

    def credentials_present(self) -> bool:
        return all(env_flag(name) for name in _REQUIRED)

    def base_url(self) -> str:
        raw = os.environ.get("TASTY_API_BASE_URL", "").strip()
        return (raw or _CERT_BASE).rstrip("/")

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        missing = [n for n in _REQUIRED if not env_flag(n)]
        detail = (
            "Missing: " + ", ".join(missing) + ". "
            if missing
            else "Refresh-token session exchange is not implemented in this stub. "
        )
        raise NeedsAuth(
            "tastytrade NeedsAuth: "
            + detail
            + "Use OAuth env TASTY_CLIENT_ID, TASTY_CLIENT_SECRET, "
            "TASTY_REFRESH_TOKEN, TASTY_ACCOUNT_NUMBER. "
            "Do not store TASTY_USERNAME. "
            f"No order was sent for {ticket.symbol}."
        )
