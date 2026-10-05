#!/usr/bin/env python3
"""Stage Analysis → multi-broker execution assistant CLI.

Commands:
  scan                 propose tickets from equity-scan CSVs
  approve --id ID      write approval flag to out/approvals.jsonl
  execute --id ID      place ONLY if approved AND dry_run false AND creds present
  brokers              list adapters, creds-present booleans, dry_run
  status               show ledger, approvals, config safety flags

NEVER places a live order without an explicit per-order approval on disk.
Default is propose-only / dry_run. Non-Schwab brokers print a manual ticket
when dry_run is true or credentials are missing — they do not HTTP-post.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from portfolio import load_ledger, open_positions, save_ledger, upsert_position
from risk import RiskViolation, enforce, filter_tickets
from brokers import ADAPTERS, NeedsAuth, get_broker
from schwab_client import NeedsAuthError, SchwabClient, manual_entry_text

def _load_local_schwab_env() -> None:
    """Load /home/box/.config/schwab.env into os.environ if keys missing.
    Never prints file contents. Safe no-op if file absent.
    """
    import os
    from pathlib import Path
    path = Path(os.environ.get("SCHWAB_ENV_FILE", "/home/box/.config/schwab.env"))
    if not path.is_file():
        return
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k.startswith("SCHWAB_") and v and not os.environ.get(k):
                os.environ[k] = v
    except OSError:
        pass

_load_local_schwab_env()

from signals import (
    OrderTicket,
    generate_tickets,
    load_config,
    tickets_to_markdown,
)

PT = ZoneInfo("America/Tijuana")
BOT_ROOT = Path(__file__).resolve().parent


def _day() -> str:
    return datetime.now(PT).strftime("%Y%m%d")


def _out_dir(cfg: dict) -> Path:
    d = BOT_ROOT / cfg.get("out_dir", "out")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _approvals_path(cfg: dict) -> Path:
    p = BOT_ROOT / cfg.get("approvals_file", "out/approvals.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _executions_path(cfg: dict) -> Path:
    p = BOT_ROOT / cfg.get("executions_file", "out/executions.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_jsonl(path: Path, record: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _load_proposed(cfg: dict, day: Optional[str] = None) -> dict[str, Any]:
    day = day or _day()
    path = _out_dir(cfg) / f"proposed_orders_{day}.json"
    if not path.exists():
        # try latest
        files = sorted(_out_dir(cfg).glob("proposed_orders_*.json"))
        if not files:
            raise FileNotFoundError("No proposed_orders_*.json — run: python bot.py scan")
        path = files[-1]
    with open(path) as f:
        return json.load(f), path


def _find_ticket(ticket_id: str, cfg: dict) -> tuple[OrderTicket, Path]:
    data, path = _load_proposed(cfg)
    tickets = data.get("tickets", [])
    for t in tickets:
        if t.get("ticket_id") == ticket_id:
            return OrderTicket.from_dict(t), path
    raise KeyError(f"ticket_id not found in {path}: {ticket_id}")


def is_approved(ticket_id: str, cfg: dict) -> bool:
    """True only if an explicit approval record exists on disk for this id."""
    path = _approvals_path(cfg)
    if not path.exists():
        return False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ticket_id") == ticket_id and rec.get("approved") is True:
                return True
    return False


def effective_dry_run(cfg: dict) -> bool:
    """dry_run stays true until SCHWAB_* present AND config dry_run is false."""
    if cfg.get("dry_run", True):
        return True
    client = SchwabClient()
    if not client.credentials_present():
        return True
    return False


def cmd_scan(args: argparse.Namespace) -> int:
    cfg = load_config()
    led = load_ledger(cfg)
    equity = led.get("equity_usd") or cfg.get("assumed_equity_usd", 100000)
    positions = open_positions(cfg)

    tickets = generate_tickets(cfg, open_positions=positions, equity=equity)
    tickets = filter_tickets(tickets, cfg, equity=equity)

    day = _day()
    out_dir = _out_dir(cfg)
    json_path = out_dir / f"proposed_orders_{day}.json"
    md_path = out_dir / f"proposed_orders_{day}.md"

    payload = {
        "generated_at": datetime.now(PT).isoformat(),
        "day": day,
        "dry_run": effective_dry_run(cfg),
        "config_dry_run": bool(cfg.get("dry_run", True)),
        "schwab_creds_present": SchwabClient().credentials_present(),
        "equity_usd": equity,
        "open_positions": positions,
        "ticket_count": len(tickets),
        "tickets": [t.to_dict() for t in tickets],
    }
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    meta = {
        "day": day,
        "dry_run": payload["dry_run"],
        "schwab_creds_present": payload["schwab_creds_present"],
        "equity_usd": equity,
        "open_positions": len(positions),
        "source_csv": str(
            Path(cfg["equity_scan_dir"]) / cfg["market_results_csv"]
        ),
    }
    md_path.write_text(tickets_to_markdown(tickets, meta=meta))

    active = [t for t in tickets if t.status == "proposed" and t.side in ("BUY", "SELL")]
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(
        f"Tickets: {len(tickets)} total, {len(active)} actionable proposed "
        f"(dry_run={payload['dry_run']})"
    )
    for t in tickets:
        flag = t.status
        size = (
            f"${t.dollar_amount}"
            if t.dollar_amount
            else (f"qty={t.qty}" if t.qty is not None else "")
        )
        print(f"  [{flag}] {t.ticket_id}  {t.side:4} {t.symbol:8} {size}  {t.signal_kind}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    cfg = load_config()
    ticket_id = args.id
    try:
        ticket, _ = _find_ticket(ticket_id, cfg)
    except (FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if ticket.side == "CANCEL" or ticket.status == "cancelled":
        print(f"Refusing to approve cancelled ticket {ticket_id}")
        return 1
    if ticket.status == "blocked":
        print(f"WARNING: ticket is risk-blocked: {ticket.reason}")

    rec = {
        "ticket_id": ticket_id,
        "approved": True,
        "approved_at": datetime.now(PT).isoformat(),
        "approved_by": "parent_agent",  # parent writes via this CLI after user yes
        "symbol": ticket.symbol,
        "side": ticket.side,
        "source": "bot.py approve",
    }
    path = _approvals_path(cfg)
    _append_jsonl(path, rec)
    print(f"Approved {ticket_id} → {path}")
    print(f"  {ticket.side} {ticket.symbol} {ticket.order_type} "
          f"limit={ticket.limit_price} $={ticket.dollar_amount} qty={ticket.qty}")
    print("Next: python bot.py execute --id " + ticket_id)
    return 0


def _selected_broker_name(cfg: dict) -> str:
    return str(cfg.get("broker") or "schwab").strip().lower() or "schwab"


def _record_manual(cfg: dict, ticket: OrderTicket, ticket_id: str, broker_name: str, reason: str) -> None:
    rec = {
        "ticket_id": ticket_id,
        "status": "manual_print",
        "ts": datetime.now(PT).isoformat(),
        "reason": reason,
        "symbol": ticket.symbol,
        "side": ticket.side,
        "broker": broker_name,
        "no_live_order": True,
    }
    _append_jsonl(_executions_path(cfg), rec)
    print(f"No live order placed ({reason}). Manual ticket printed above.")


def _execute_non_schwab(cfg: dict, ticket: OrderTicket, ticket_id: str, broker_name: str) -> int:
    """Route through the selected adapter. Never POST when dry_run or creds missing."""
    try:
        broker = get_broker(broker_name)
    except KeyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    config_dry = bool(cfg.get("dry_run", True))
    creds = broker.credentials_present()
    if config_dry or not creds:
        print(broker.manual_entry_text(ticket))
        reason = []
        if config_dry:
            reason.append("config dry_run=true")
        if not creds:
            reason.append(f"{broker_name} credentials missing")
        _record_manual(cfg, ticket, ticket_id, broker_name, "; ".join(reason) or "dry_run")
        return 0
    try:
        result = broker.place_equity_order(ticket)
    except NeedsAuth as e:
        print(f"NeedsAuth: {e}")
        print(broker.manual_entry_text(ticket))
        _append_jsonl(
            _executions_path(cfg),
            {
                "ticket_id": ticket_id,
                "status": "auth_error",
                "ts": datetime.now(PT).isoformat(),
                "broker": broker_name,
                "error": str(e),
                "no_live_order": True,
            },
        )
        return 4
    except Exception as e:
        print(f"Order error: {e}")
        _append_jsonl(
            _executions_path(cfg),
            {
                "ticket_id": ticket_id,
                "status": "error",
                "ts": datetime.now(PT).isoformat(),
                "broker": broker_name,
                "error": str(e),
                "no_live_order": True,
            },
        )
        return 5
    _append_jsonl(
        _executions_path(cfg),
        {
            "ticket_id": ticket_id,
            "status": "submitted",
            "ts": datetime.now(PT).isoformat(),
            "broker": broker_name,
            "result": result,
            "symbol": ticket.symbol,
            "side": ticket.side,
        },
    )
    print(f"Submitted to {broker_name}: order_id={result.get('order_id')} ticket={ticket_id}")
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    """ONLY executes if: approved on disk AND dry_run false AND broker creds present.

    Otherwise prints the ticket for manual entry and records that fact.
    broker != schwab goes through brokers.get_broker and does not HTTP-post
    while dry_run is true or credentials are missing.
    """
    cfg = load_config()
    ticket_id = args.id

    try:
        ticket, prop_path = _find_ticket(ticket_id, cfg)
    except (FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Hard gate 1: approval file
    if not is_approved(ticket_id, cfg):
        print(
            f"REFUSED: ticket {ticket_id} is not approved. "
            f"Parent must write approval via: python bot.py approve --id {ticket_id}"
        )
        return 2

    # Risk re-check
    led = load_ledger(cfg)
    equity = led.get("equity_usd") or cfg.get("assumed_equity_usd", 100000)
    try:
        enforce(ticket, cfg, equity=equity, for_execute=True)
    except RiskViolation as e:
        print(f"REFUSED risk: {e}")
        return 3

    broker_name = _selected_broker_name(cfg)
    if broker_name != "schwab":
        return _execute_non_schwab(cfg, ticket, ticket_id, broker_name)

    dry = effective_dry_run(cfg)
    client = SchwabClient()
    creds = client.credentials_present()

    # Hard gate 2+3: dry_run / creds
    if dry or not creds or cfg.get("dry_run", True):
        text = manual_entry_text(ticket)
        print(text)
        reason = []
        if cfg.get("dry_run", True):
            reason.append("config dry_run=true")
        if not creds:
            reason.append("SCHWAB_* credentials missing")
        if dry and not cfg.get("dry_run", True) and not creds:
            reason.append("effective dry_run forced by missing creds")
        rec = {
            "ticket_id": ticket_id,
            "status": "manual_print",
            "ts": datetime.now(PT).isoformat(),
            "reason": "; ".join(reason) or "dry_run",
            "symbol": ticket.symbol,
            "side": ticket.side,
            "no_live_order": True,
        }
        _append_jsonl(_executions_path(cfg), rec)
        print(f"No live order placed ({rec['reason']}). Manual ticket printed above.")
        return 0

    # Live path — only reached with approval + dry_run false + creds
    try:
        result = client.place_equity_order(ticket)
    except NeedsAuthError as e:
        print(f"NeedsAuthError: {e}")
        print(manual_entry_text(ticket))
        _append_jsonl(
            _executions_path(cfg),
            {
                "ticket_id": ticket_id,
                "status": "auth_error",
                "ts": datetime.now(PT).isoformat(),
                "error": str(e),
                "no_live_order": True,
            },
        )
        return 4
    except Exception as e:
        print(f"Order error: {e}")
        _append_jsonl(
            _executions_path(cfg),
            {
                "ticket_id": ticket_id,
                "status": "error",
                "ts": datetime.now(PT).isoformat(),
                "error": str(e),
            },
        )
        return 5

    _append_jsonl(
        _executions_path(cfg),
        {
            "ticket_id": ticket_id,
            "status": "submitted",
            "ts": datetime.now(PT).isoformat(),
            "broker": "schwab",
            "result": result,
            "symbol": ticket.symbol,
            "side": ticket.side,
        },
    )
    # Update local ledger optimistically
    qty = ticket.qty
    if (qty is None or qty <= 0) and ticket.dollar_amount and ticket.limit_price:
        qty = max(1, int(float(ticket.dollar_amount) // float(ticket.limit_price)))
    if qty and qty > 0:
        upsert_position(
            ticket.symbol,
            float(qty),
            avg_price=ticket.limit_price or ticket.price,
            side_fill=ticket.side,
            ticket_id=ticket_id,
            cfg=cfg,
        )
    print(f"Submitted to Schwab: order_id={result.get('order_id')} ticket={ticket_id}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = load_config()
    client = SchwabClient()
    led = load_ledger(cfg)
    day = _day()
    json_path = _out_dir(cfg) / f"proposed_orders_{day}.json"
    approvals = []
    ap = _approvals_path(cfg)
    if ap.exists():
        with open(ap) as f:
            for line in f:
                if line.strip():
                    try:
                        approvals.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    print("=== trading-bot status ===")
    print(f"time:                 {datetime.now(PT).strftime('%Y-%m-%d %H:%M:%S PT')}")
    print(f"config dry_run:       {cfg.get('dry_run', True)}")
    print(f"effective dry_run:    {effective_dry_run(cfg)}")
    print(f"schwab creds present: {client.credentials_present()}")
    print(f"max_positions:        {cfg.get('max_positions')}")
    print(f"max_position_pct:     {cfg.get('max_position_pct')}")
    print(f"max_orders_per_day:   {cfg.get('max_orders_per_day')}")
    print(f"top_n_buys:           {cfg.get('top_n_buys')}")
    print(f"qcom_dip_enabled:     {cfg.get('qcom_dip_enabled')}")
    print(f"ledger equity:        {led.get('equity_usd')}")
    print(f"open positions:       {len(open_positions(cfg))}")
    for p in open_positions(cfg):
        print(f"  - {p.get('symbol')}: qty={p.get('qty')} avg={p.get('avg_price')}")
    print(f"today proposed file:  {json_path} exists={json_path.exists()}")
    if json_path.exists():
        data = json.loads(json_path.read_text())
        print(f"  tickets: {data.get('ticket_count')}")
    print(f"approvals on disk:    {len(approvals)}")
    for a in approvals[-10:]:
        print(f"  - {a.get('ticket_id')} approved={a.get('approved')} at={a.get('approved_at')}")
    print(
        "env: SCHWAB_APP_KEY set="
        + str(bool(os.environ.get("SCHWAB_APP_KEY")))
        + " SECRET="
        + str(bool(os.environ.get("SCHWAB_APP_SECRET")))
        + " REFRESH="
        + str(bool(os.environ.get("SCHWAB_REFRESH_TOKEN")))
        + " ACCOUNT_HASH="
        + str(bool(os.environ.get("SCHWAB_ACCOUNT_HASH")))
    )
    return 0


def cmd_brokers(args: argparse.Namespace) -> int:
    """List adapters. Credential checks are booleans only — values are never printed."""
    cfg = load_config()
    selected = _selected_broker_name(cfg)
    enabled = cfg.get("brokers_enabled") or list(ADAPTERS)
    print(f"selected_broker: {selected}")
    print(f"dry_run: {bool(cfg.get('dry_run', True))}")
    print(f"effective_dry_run: {effective_dry_run(cfg)}")
    print("brokers_enabled: " + ", ".join(str(n) for n in enabled))
    for raw in enabled:
        name = str(raw).strip().lower()
        if name not in ADAPTERS:
            print(f"{name}: unknown adapter")
            continue
        broker = get_broker(name)
        flags = " ".join(f"{k}={v}" for k, v in broker.env_status().items())
        mark = " selected" if name == selected else ""
        print(
            f"{name}: creds_present={broker.credentials_present()} "
            f"mode={broker.mode}{mark} {flags}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Stage Analysis Schwab execution assistant (propose-only by default)"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Generate proposed order tickets from equity-scan")
    s.set_defaults(func=cmd_scan)

    a = sub.add_parser("approve", help="Mark a ticket approved in out/approvals.jsonl")
    a.add_argument("--id", required=True, help="ticket_id")
    a.set_defaults(func=cmd_approve)

    e = sub.add_parser(
        "execute",
        help="Execute approved ticket (live only if dry_run=false and SCHWAB_* set)",
    )
    e.add_argument("--id", required=True, help="ticket_id")
    e.set_defaults(func=cmd_execute)

    st = sub.add_parser("status", help="Show ledger, approvals, safety flags")
    st.set_defaults(func=cmd_status)

    b = sub.add_parser(
        "brokers",
        help="List broker adapters, credential presence (booleans), and dry_run",
    )
    b.set_defaults(func=cmd_brokers)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
