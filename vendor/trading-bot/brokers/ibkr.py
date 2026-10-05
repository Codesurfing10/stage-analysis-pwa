"""Interactive Brokers Client Portal Web API stub.

No TWS / IB Gateway socket client (no ibapi, no ib_insync, ports 7496/7497).
The supported retail HTTP surface is the Client Portal Gateway, which you run
locally and log into in a browser. Default base:

  IBKR_BASE_URL=https://localhost:5000/v1/api

Account id (boolean presence check only; not sufficient to trade):

  IBKR_ACCOUNT_ID

After the gateway session is authenticated, equity orders would be
POST /iserver/account/{accountId}/orders. This stub never calls that endpoint.
place_equity_order always raises NeedsAuth and does not open a socket or HTTP
connection.
"""
from __future__ import annotations

import os
from typing import Any

from signals import OrderTicket

from .base import BrokerClient, NeedsAuth, env_flag


_DEFAULT_BASE = "https://localhost:5000/v1/api"


class IbkrBroker(BrokerClient):
    name = "ibkr"
    mode = "client-portal-stub"
    env_vars = ("IBKR_ACCOUNT_ID", "IBKR_BASE_URL")

    def credentials_present(self) -> bool:
        # Account id alone is not a gateway session. Reported true only when set.
        # Orders still NeedsAuth — see place_equity_order.
        return env_flag("IBKR_ACCOUNT_ID")

    def base_url(self) -> str:
        raw = os.environ.get("IBKR_BASE_URL", "").strip()
        return (raw or _DEFAULT_BASE).rstrip("/")

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        self._refuse_if_dry_run()
        raise NeedsAuth(
            "ibkr NeedsAuth: Client Portal Gateway session is not confirmed. "
            f"Start the gateway and log in via browser ({self.base_url()}). "
            "Set IBKR_ACCOUNT_ID. This adapter does not use the TWS socket API. "
            f"No order was sent for {ticket.symbol}."
        )
