"""Broker adapter interface. Screen/execution only. Never prints secrets."""
from __future__ import annotations

import os
from typing import Any, Optional

from signals import OrderTicket


class NeedsAuth(Exception):
    """Credentials or broker session are not ready. No order was sent."""


class DryRunRefused(Exception):
    """dry_run is true. No order was sent."""


def env_flag(name: str) -> bool:
    """True if the env var is set to a non-empty value. Never returns the value."""
    raw = os.environ.get(name)
    if raw is None:
        return False
    return bool(str(raw).strip())


def first_env(*names: str) -> str:
    """Return the first non-empty env value for internal request use. Do not log it."""
    for name in names:
        raw = os.environ.get(name)
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return ""


def resolve_qty(ticket: OrderTicket) -> int:
    qty = ticket.qty
    if qty is None or float(qty) <= 0:
        price = ticket.limit_price or ticket.price
        if ticket.dollar_amount and price:
            qty = max(1, int(float(ticket.dollar_amount) // float(price)))
        else:
            raise ValueError("Order needs qty or dollar_amount with price/limit")
    return int(qty)


class BrokerClient:
    """Screen/execution adapter. Subclasses must not log credential values."""

    name: str = "base"
    #: Human label: paper / sandbox / oauth-stub / session-stub / gated
    mode: str = "gated"
    #: Env var names checked for the CLI (booleans only).
    env_vars: tuple[str, ...] = ()

    def credentials_present(self) -> bool:
        raise NotImplementedError

    def env_status(self) -> dict[str, bool]:
        return {name: env_flag(name) for name in self.env_vars}

    def manual_entry_text(self, ticket: OrderTicket) -> str:
        lines = [
            f"=== MANUAL {self.name.upper()} ENTRY (no API order sent) ===",
            f"broker:      {self.name}",
            f"ticket_id:   {ticket.ticket_id}",
            f"symbol:      {ticket.symbol}",
            f"side:        {ticket.side}",
            f"order_type:  {ticket.order_type}",
            f"qty:         {ticket.qty}",
            f"dollar_amt:  {ticket.dollar_amount}",
            f"limit_price: {ticket.limit_price}",
            f"reason:      {ticket.reason}",
            f"stage:       {ticket.stage}",
            "===============================================",
        ]
        return "\n".join(lines)

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        """Submit an equity order. Caller must already have rejected dry_run."""
        raise NotImplementedError

    def _refuse_if_dry_run(self) -> None:
        from signals import load_config

        if load_config().get("dry_run", True):
            raise DryRunRefused(
                f"{self.name}: config dry_run=true. Refusing to POST an order."
            )

    def _missing_env(self, names: tuple[str, ...]) -> list[str]:
        return [n for n in names if not env_flag(n)]
