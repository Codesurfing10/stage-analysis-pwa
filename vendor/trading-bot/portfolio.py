#!/usr/bin/env python3
"""Local ledger of open positions + optional Schwab positions sync stub."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from signals import load_config

PT = ZoneInfo("America/Tijuana")
BOT_ROOT = Path(__file__).resolve().parent


def ledger_path(cfg: Optional[dict] = None) -> Path:
    cfg = cfg or load_config()
    p = BOT_ROOT / cfg.get("ledger_file", "data/ledger.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_ledger(cfg: Optional[dict] = None) -> dict[str, Any]:
    path = ledger_path(cfg)
    if not path.exists():
        return {
            "updated_at": None,
            "equity_usd": None,
            "positions": [],
            "notes": "Local ledger — not broker of record until Schwab sync succeeds.",
        }
    with open(path) as f:
        return json.load(f)


def save_ledger(ledger: dict[str, Any], cfg: Optional[dict] = None) -> Path:
    path = ledger_path(cfg)
    ledger["updated_at"] = datetime.now(PT).isoformat()
    with open(path, "w") as f:
        json.dump(ledger, f, indent=2)
    return path


def open_positions(cfg: Optional[dict] = None) -> list[dict]:
    led = load_ledger(cfg)
    return [p for p in led.get("positions", []) if float(p.get("qty") or 0) > 0]


def upsert_position(
    symbol: str,
    qty: float,
    avg_price: Optional[float] = None,
    side_fill: str = "BUY",
    ticket_id: Optional[str] = None,
    cfg: Optional[dict] = None,
) -> dict:
    """Update local ledger after a (simulated or real) fill."""
    cfg = cfg or load_config()
    led = load_ledger(cfg)
    positions = led.setdefault("positions", [])
    found = None
    for p in positions:
        if p.get("symbol") == symbol:
            found = p
            break
    if found is None:
        found = {
            "symbol": symbol,
            "qty": 0.0,
            "avg_price": None,
            "opened_at": datetime.now(PT).isoformat(),
            "last_ticket_id": None,
        }
        positions.append(found)

    cur_qty = float(found.get("qty") or 0)
    cur_avg = found.get("avg_price")
    if side_fill.upper() == "BUY":
        new_qty = cur_qty + float(qty)
        if avg_price is not None and new_qty > 0:
            if cur_qty > 0 and cur_avg is not None:
                found["avg_price"] = round(
                    (cur_qty * float(cur_avg) + float(qty) * float(avg_price)) / new_qty, 4
                )
            else:
                found["avg_price"] = float(avg_price)
        found["qty"] = new_qty
    else:  # SELL
        new_qty = max(0.0, cur_qty - float(qty))
        found["qty"] = new_qty
        if new_qty == 0:
            found["closed_at"] = datetime.now(PT).isoformat()

    if ticket_id:
        found["last_ticket_id"] = ticket_id
    found["updated_at"] = datetime.now(PT).isoformat()
    # Drop zero-qty closed from "open" view but keep in ledger history lightly
    led["positions"] = [p for p in positions if float(p.get("qty") or 0) > 0]
    save_ledger(led, cfg)
    return found


def has_open_buy(symbol: str, cfg: Optional[dict] = None) -> bool:
    return any(p.get("symbol") == symbol for p in open_positions(cfg))


def sync_from_schwab(client: Any, cfg: Optional[dict] = None) -> dict[str, Any]:
    """Optional stub: pull positions from Schwab and merge into local ledger.

    Raises NeedsAuthError from client if credentials missing.
    """
    cfg = cfg or load_config()
    account = client.get_account_with_positions()
    securities = (
        account.get("securitiesAccount")
        or account.get("securities_account")
        or account
    )
    bal = securities.get("currentBalances") or securities.get("current_balances") or {}
    equity = (
        bal.get("equity")
        or bal.get("liquidationValue")
        or bal.get("accountValue")
    )
    positions_raw = securities.get("positions") or []
    mapped = []
    for pos in positions_raw:
        inst = pos.get("instrument") or {}
        sym = inst.get("symbol")
        if not sym:
            continue
        qty = float(pos.get("longQuantity") or pos.get("long_quantity") or 0)
        if qty <= 0:
            continue
        mapped.append(
            {
                "symbol": sym,
                "qty": qty,
                "avg_price": pos.get("averagePrice") or pos.get("average_price"),
                "market_value": pos.get("marketValue") or pos.get("market_value"),
                "source": "schwab",
                "updated_at": datetime.now(PT).isoformat(),
            }
        )
    led = load_ledger(cfg)
    led["equity_usd"] = float(equity) if equity is not None else led.get("equity_usd")
    led["positions"] = mapped
    led["schwab_synced_at"] = datetime.now(PT).isoformat()
    save_ledger(led, cfg)
    return led


if __name__ == "__main__":
    print(json.dumps(load_ledger(), indent=2))
