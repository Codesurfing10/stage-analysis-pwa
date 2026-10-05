"""Read trading-bot / equity-scan artifacts; call bot.py via subprocess.

Never flips dry_run. Never reads schwab.env or SCHWAB_* values.
"""
from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .config import BOT_PY, BOT_ROOT, BOT_VENV_PYTHON, EQUITY_SCAN_DIR, TZ_NAME

PT = ZoneInfo(TZ_NAME)


def _day() -> str:
    return datetime.now(PT).strftime("%Y%m%d")


def latest_proposed_path() -> Optional[Path]:
    """Pick newest proposed_orders_YYYYMMDD.json by date in the filename.

    Re-globs the filesystem on every call — no in-memory cache — so a daily
    scan that writes a new file is visible on the next /api/dashboard request
    without restarting uvicorn.
    """
    out = BOT_ROOT / "out"
    if not out.is_dir():
        return None
    best: Optional[Path] = None
    best_day = ""
    for path in out.glob("proposed_orders_*.json"):
        day = path.stem.rsplit("_", 1)[-1]
        if not day.isdigit():
            continue
        if day >= best_day:
            best_day = day
            best = path
    return best


def load_proposed(day: Optional[str] = None) -> tuple[dict[str, Any], Path]:
    """Load proposed orders JSON from disk (always fresh read)."""
    out = BOT_ROOT / "out"
    if day:
        path = out / f"proposed_orders_{day}.json"
        if not path.exists():
            raise FileNotFoundError(str(path))
    else:
        path = latest_proposed_path()
        if path is None:
            raise FileNotFoundError("No proposed_orders_*.json")
    # Fresh open each request — do not cache file contents or path at module level.
    with open(path) as f:
        return json.load(f), path


def load_approvals() -> list[dict[str, Any]]:
    path = BOT_ROOT / "out" / "approvals.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def approved_ticket_ids() -> set[str]:
    ids: set[str] = set()
    for rec in load_approvals():
        if rec.get("approved") is True and rec.get("ticket_id"):
            ids.add(rec["ticket_id"])
    return ids


def load_ledger() -> dict[str, Any]:
    path = BOT_ROOT / "data" / "ledger.json"
    if not path.exists():
        return {"equity_usd": None, "positions": [], "updated_at": None}
    with open(path) as f:
        return json.load(f)


def open_positions() -> list[dict]:
    led = load_ledger()
    return [p for p in led.get("positions", []) if float(p.get("qty") or 0) > 0]


def read_config_yaml_flags() -> dict[str, Any]:
    """Minimal YAML parse for dry_run only — no secrets."""
    path = BOT_ROOT / "config.yaml"
    dry_run = True
    if path.exists():
        for line in path.read_text().splitlines():
            s = line.strip()
            if s.startswith("dry_run:"):
                val = s.split(":", 1)[1].strip().lower()
                # strip inline comments
                if "#" in val:
                    val = val.split("#", 1)[0].strip()
                dry_run = val in ("true", "yes", "1")
                break
    # Do NOT read schwab.env — only report whether bot's status would see creds
    # via a flag file presence check without reading contents is still risky;
    # we report schwab_creds from proposed_orders payload or False.
    return {"dry_run": dry_run}


def schwab_creds_flag_from_proposed(data: dict) -> bool:
    return bool(data.get("schwab_creds_present", False))


def read_markdown(path: Path, max_chars: int = 8000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n…(truncated)"
    return text


def parse_top10_from_md() -> list[dict[str, Any]]:
    path = EQUITY_SCAN_DIR / "market_top10.md"
    if not path.is_file():
        return parse_top10_from_csv()
    rows: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 11:
            continue
        if parts[0].lower() in ("rank", "---") or parts[0].startswith("-"):
            continue
        try:
            rank = int(parts[0])
        except ValueError:
            continue
        rows.append(
            {
                "rank": rank,
                "ticker": parts[1],
                "name": parts[2],
                "price": parts[3],
                "sma150": parts[4],
                "slope": parts[5],
                "vol_ratio": parts[6],
                "volume_confirmed": parts[7],
                "extended_pct": parts[8],
                "score": parts[9],
                "why": parts[10] if len(parts) > 10 else "",
            }
        )
    return rows[:10] if rows else parse_top10_from_csv()


def parse_top10_from_csv() -> list[dict[str, Any]]:
    path = EQUITY_SCAN_DIR / "market_scan_results.csv"
    if not path.is_file():
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        scored = []
        for row in reader:
            try:
                score = float(row.get("score") or 0)
            except ValueError:
                continue
            stage = (row.get("stage") or "").lower()
            if "stage 2" not in stage:
                continue
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for i, (score, row) in enumerate(scored[:10], 1):
            out.append(
                {
                    "rank": i,
                    "ticker": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "price": row.get("price", ""),
                    "sma150": row.get("sma150", ""),
                    "slope": row.get("slope", ""),
                    "vol_ratio": row.get("vol_ratio", ""),
                    "volume_confirmed": row.get("volume_confirmed", ""),
                    "extended_pct": row.get("extended_pct", ""),
                    "score": row.get("score", ""),
                    "why": row.get("action", ""),
                }
            )
        return out


def find_qcom_row() -> Optional[dict[str, Any]]:
    path = EQUITY_SCAN_DIR / "market_scan_results.csv"
    if not path.is_file():
        return None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("ticker") or "").upper() == "QCOM":
                return {
                    "ticker": "QCOM",
                    "name": row.get("name", ""),
                    "price": row.get("price"),
                    "sma150": row.get("sma150"),
                    "sma50": row.get("sma50"),
                    "slope": row.get("slope"),
                    "stage": row.get("stage"),
                    "action": row.get("action"),
                    "vol_ratio": row.get("vol_ratio"),
                    "volume_confirmed": row.get("volume_confirmed"),
                    "extended_pct": row.get("extended_pct"),
                    "score": row.get("score"),
                    "asof": row.get("asof"),
                }
    return None


def find_ticket(ticket_id: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    data, path = load_proposed()
    for t in data.get("tickets", []):
        if t.get("ticket_id") == ticket_id:
            return t, data, path
    raise KeyError(ticket_id)


def manual_entry_preview(ticket: dict[str, Any]) -> str:
    """Mirror schwab_client.manual_entry_text without importing schwab secrets path."""
    sym = ticket.get("symbol", "?")
    side = ticket.get("side", "?")
    ot = ticket.get("order_type", "LIMIT")
    limit = ticket.get("limit_price")
    dollar = ticket.get("dollar_amount")
    qty = ticket.get("qty")
    lines = [
        "=== MANUAL SCHWAB ENTRY (dry_run) ===",
        f"Ticket: {ticket.get('ticket_id')}",
        f"Action: {side} {sym}",
        f"Order type: {ot}",
    ]
    if limit is not None:
        lines.append(f"Limit price: {limit}")
    if dollar is not None:
        lines.append(f"Dollar amount: ${dollar}")
    if qty is not None:
        lines.append(f"Quantity: {qty}")
    lines.append(f"Reason: {ticket.get('reason', '')}")
    lines.append("No live order placed — dry_run assistant only.")
    return "\n".join(lines)


def run_bot(cmd: str, ticket_id: str, timeout: int = 60) -> dict[str, Any]:
    """Subprocess: trading-bot venv python bot.py approve|execute --id …"""
    python = str(BOT_VENV_PYTHON if BOT_VENV_PYTHON.is_file() else "python3")
    args = [python, str(BOT_PY), cmd, "--id", ticket_id]
    try:
        proc = subprocess.run(
            args,
            cwd=str(BOT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**dict(__import__("os").environ), "PYTHONPATH": str(BOT_ROOT)},
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "cmd": " ".join(args),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "timeout",
            "cmd": " ".join(args),
        }


def build_dashboard() -> dict[str, Any]:
    flags = read_config_yaml_flags()
    try:
        data, path = load_proposed()
    except FileNotFoundError:
        data, path = {}, None

    approved = sorted(approved_ticket_ids())
    tickets = data.get("tickets", [])
    for t in tickets:
        t = t  # already dicts from JSON
    # annotate approved on copies
    annotated = []
    for t in tickets:
        row = dict(t)
        row["approved"] = row.get("ticket_id") in approved
        annotated.append(row)

    top10 = parse_top10_from_md()
    dip_path = EQUITY_SCAN_DIR / "dip_scenario.md"
    dip_md = read_markdown(dip_path, max_chars=4000)
    qcom = find_qcom_row()
    led = load_ledger()

    generated = data.get("generated_at") or data.get("day")
    day = data.get("day") or (path.stem.replace("proposed_orders_", "") if path else _day())
    proposed_mtime = None
    if path is not None and path.is_file():
        proposed_mtime = datetime.fromtimestamp(path.stat().st_mtime, PT).isoformat()

    positions_stage = load_positions_stage()
    positions_beta = load_positions_beta()

    return {
        "asof": day,
        "generated_at": generated,
        "proposed_mtime": proposed_mtime,
        "timezone": TZ_NAME,
        "dry_run": bool(data.get("dry_run", flags["dry_run"])),
        "config_dry_run": bool(data.get("config_dry_run", flags["dry_run"])),
        "schwab_creds_present": schwab_creds_flag_from_proposed(data)
        if data
        else False,
        "equity_usd": data.get("equity_usd") or led.get("equity_usd"),
        "open_positions": open_positions(),
        "ticket_count": len(annotated),
        "tickets": annotated,
        "approved_ticket_ids": approved,
        "top10": top10,
        "dip_scenario_md": dip_md,
        "qcom": qcom,
        "positions_stage": positions_stage,
        "positions_beta": positions_beta,
        "proposed_path": str(path) if path else None,
        "disclaimer": "Screen/execution assistant only — not financial advice",
    }


def _latest_dated_dir(prefix: str) -> Optional[Path]:
    """Find newest equity-scan/positions_{prefix}_YYYYMMDD directory."""
    dirs = [
        p
        for p in EQUITY_SCAN_DIR.glob(f"positions_{prefix}_*")
        if p.is_dir() and p.name.split("_")[-1].isdigit()
    ]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.name.split("_")[-1])[-1]


def load_positions_stage() -> dict[str, Any]:
    """Load latest positions_stage_*/positions_stage.json."""
    d = _latest_dated_dir("stage")
    if d is None:
        return {"asof": None, "path": None, "count": 0, "positions": []}
    path = d / "positions_stage.json"
    if not path.is_file():
        return {"asof": None, "path": str(d), "count": 0, "positions": []}
    with open(path) as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        rows = rows.get("positions", []) if isinstance(rows, dict) else []
    asof = None
    if rows:
        asof = rows[0].get("asof")
    day = d.name.split("_")[-1]
    return {
        "asof": asof or day,
        "day": day,
        "path": str(path),
        "count": len(rows),
        "positions": rows,
    }


def load_positions_beta() -> dict[str, Any]:
    """Load latest positions_beta_*/positions_beta_corr.json."""
    d = _latest_dated_dir("beta")
    if d is None:
        return {"asof": None, "path": None, "available": False}
    path = d / "positions_beta_corr.json"
    if not path.is_file():
        return {"asof": None, "path": str(d), "available": False}
    with open(path) as f:
        data = json.load(f)
    # Compact summary for dashboard: portfolio SPY 1y + per-symbol SPY 1y
    portfolio = data.get("portfolio") or []
    spy_1y_port = next(
        (
            p
            for p in portfolio
            if p.get("benchmark") == "SPY" and "1y" in str(p.get("window", ""))
        ),
        None,
    )
    per = data.get("per_symbol") or []
    spy_1y_syms = [
        r
        for r in per
        if r.get("benchmark") == "SPY" and "1y" in str(r.get("window", ""))
    ]
    spy_1y_syms_sorted = sorted(
        spy_1y_syms, key=lambda r: abs(float(r.get("beta") or 0)), reverse=True
    )
    return {
        "available": True,
        "asof": data.get("asof"),
        "generated_at_pt": data.get("generated_at_pt"),
        "title": data.get("title"),
        "path": str(path),
        "symbols": data.get("symbols") or [],
        "portfolio_spy_1y": spy_1y_port,
        "portfolio": portfolio,
        "per_symbol_spy_1y": spy_1y_syms_sorted,
        "spy_1y_sorted_by_abs_beta": data.get("spy_1y_sorted_by_abs_beta") or spy_1y_syms_sorted,
        "method_note": (data.get("method") or {}).get("disclaimer"),
    }
