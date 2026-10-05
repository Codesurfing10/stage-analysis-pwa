#!/usr/bin/env python3
"""Risk checks: position size, daily order cap, no duplicate open buys."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from portfolio import has_open_buy, open_positions
from signals import OrderTicket, load_config

PT = ZoneInfo("America/Tijuana")
BOT_ROOT = Path(__file__).resolve().parent


class RiskViolation(Exception):
    pass


def _today() -> str:
    return datetime.now(PT).strftime("%Y%m%d")


def _executions_path(cfg: dict) -> Path:
    p = BOT_ROOT / cfg.get("executions_file", "out/executions.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def count_orders_today(cfg: Optional[dict] = None) -> int:
    cfg = cfg or load_config()
    path = _executions_path(cfg)
    if not path.exists():
        return 0
    today = _today()
    n = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = str(rec.get("ts") or rec.get("created_at") or "")
            if today in ts.replace("-", "")[:8] or ts.startswith(
                datetime.now(PT).strftime("%Y-%m-%d")
            ):
                if rec.get("status") in ("submitted", "dry_run_recorded", "manual_print"):
                    n += 1
    # Also count approvals that led to execute attempts today via proposed file day prefix
    return n


def pending_buy_symbols_today(cfg: Optional[dict] = None) -> set[str]:
    """Symbols with proposed BUY tickets already written today (avoid spam duplicates)."""
    cfg = cfg or load_config()
    out_dir = BOT_ROOT / cfg.get("out_dir", "out")
    day = datetime.now(PT).strftime("%Y%m%d")
    path = out_dir / f"proposed_orders_{day}.json"
    syms: set[str] = set()
    if path.exists():
        data = json.loads(path.read_text())
        for t in data.get("tickets", data if isinstance(data, list) else []):
            if str(t.get("side", "")).upper() == "BUY":
                syms.add(str(t.get("symbol")))
    return syms


def check_ticket(
    ticket: OrderTicket,
    cfg: Optional[dict] = None,
    equity: Optional[float] = None,
    *,
    for_execute: bool = False,
) -> list[str]:
    """Return list of violation messages (empty = ok). Does not raise."""
    cfg = cfg or load_config()
    violations: list[str] = []
    equity = float(
        equity
        if equity is not None
        else cfg.get("assumed_equity_usd", 100000)
    )

    if ticket.side == "CANCEL":
        return violations

    max_pos = int(cfg.get("max_positions", 10))
    opens = open_positions(cfg)
    if ticket.side == "BUY" and len(opens) >= max_pos and not has_open_buy(ticket.symbol, cfg):
        violations.append(
            f"max_positions={max_pos} reached (open={len(opens)}); cannot open new symbol {ticket.symbol}"
        )

    if ticket.side == "BUY" and has_open_buy(ticket.symbol, cfg):
        violations.append(f"duplicate open buy blocked for {ticket.symbol}")

    max_pct = float(cfg.get("max_position_pct", 0.05))
    max_dollars = equity * max_pct
    if ticket.side == "BUY" and ticket.dollar_amount is not None:
        if float(ticket.dollar_amount) > max_dollars + 0.01:
            violations.append(
                f"dollar_amount {ticket.dollar_amount} exceeds max_position_pct "
                f"({max_pct:.0%} of equity ${equity:,.2f} = ${max_dollars:,.2f})"
            )
    if ticket.side == "BUY" and ticket.qty and ticket.price:
        notional = float(ticket.qty) * float(ticket.price)
        if notional > max_dollars + 0.01:
            violations.append(
                f"qty*price ${notional:,.2f} exceeds max position ${max_dollars:,.2f}"
            )

    if for_execute:
        cap = int(cfg.get("max_orders_per_day", 15))
        used = count_orders_today(cfg)
        if used >= cap:
            violations.append(f"max_orders_per_day={cap} reached (today={used})")

    return violations


def enforce(
    ticket: OrderTicket,
    cfg: Optional[dict] = None,
    equity: Optional[float] = None,
    *,
    for_execute: bool = False,
) -> OrderTicket:
    """Mark ticket blocked or raise if hard fail on execute."""
    viols = check_ticket(ticket, cfg, equity, for_execute=for_execute)
    if not viols:
        return ticket
    ticket.status = "blocked"
    ticket.reason = (ticket.reason or "") + " | RISK: " + "; ".join(viols)
    if for_execute:
        raise RiskViolation("; ".join(viols))
    return ticket


def filter_tickets(
    tickets: list[OrderTicket],
    cfg: Optional[dict] = None,
    equity: Optional[float] = None,
) -> list[OrderTicket]:
    """Apply risk to a batch; keep blocked tickets for visibility but tagged."""
    cfg = cfg or load_config()
    out: list[OrderTicket] = []
    # Simulate sequential open-buy uniqueness within the batch
    batch_buys: set[str] = set()
    open_syms = {p["symbol"] for p in open_positions(cfg)}
    max_pos = int(cfg.get("max_positions", 10))
    open_count = len(open_positions(cfg))

    for t in tickets:
        if t.side == "BUY":
            if t.symbol in batch_buys or t.symbol in open_syms:
                t.status = "blocked"
                t.reason = (t.reason or "") + " | RISK: duplicate open/proposed buy"
                out.append(t)
                continue
            if open_count >= max_pos:
                t.status = "blocked"
                t.reason = (t.reason or "") + f" | RISK: max_positions={max_pos}"
                out.append(t)
                continue
        t = enforce(t, cfg, equity, for_execute=False)
        if t.side == "BUY" and t.status != "blocked":
            batch_buys.add(t.symbol)
            # Don't increment open_count for proposals — only real opens count toward cap
            # but limit proposed new names to remaining slots
            open_count += 1  # reserve slot for this proposal day
        out.append(t)
    return out
