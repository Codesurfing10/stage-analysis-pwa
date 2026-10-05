"""Schwab adapter — wraps the existing schwab_client.SchwabClient.

Does not read credential files itself. Env names only:
  SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN, SCHWAB_ACCOUNT_HASH
"""
from __future__ import annotations

from typing import Any

from signals import OrderTicket

from schwab_client import NeedsAuthError, SchwabClient, manual_entry_text

from .base import BrokerClient, NeedsAuth


class SchwabBroker(BrokerClient):
    name = "schwab"
    mode = "gated"
    env_vars = (
        "SCHWAB_APP_KEY",
        "SCHWAB_APP_SECRET",
        "SCHWAB_REFRESH_TOKEN",
        "SCHWAB_ACCOUNT_HASH",
    )

    def __init__(self) -> None:
        self._client = SchwabClient()

    def credentials_present(self) -> bool:
        return self._client.credentials_present()

    def manual_entry_text(self, ticket: OrderTicket) -> str:
        return manual_entry_text(ticket)

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        if not self.credentials_present():
            raise NeedsAuth(
                "schwab: missing SCHWAB_APP_KEY, SCHWAB_APP_SECRET, "
                "SCHWAB_REFRESH_TOKEN, and/or SCHWAB_ACCOUNT_HASH. No order was sent."
            )
        try:
            return self._client.place_equity_order(ticket)
        except NeedsAuthError as exc:
            raise NeedsAuth(str(exc)) from exc
