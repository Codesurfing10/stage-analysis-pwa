#!/usr/bin/env python3
"""Load Stage Analysis scan outputs and emit proposed OrderTickets.

Execution assistant only — emits user-signal tickets, not advice.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

PT = ZoneInfo("America/Tijuana")
BOT_ROOT = Path(__file__).resolve().parent


@dataclass
class OrderTicket:
    ticket_id: str
    symbol: str
    side: str  # BUY or SELL
    order_type: str  # LIMIT or MARKET
    qty: Optional[float] = None
    dollar_amount: Optional[float] = None
    limit_price: Optional[float] = None
    reason: str = ""
    stage: Optional[str] = None
    score: Optional[float] = None
    price: Optional[float] = None
    sma150: Optional[float] = None
    slope: Optional[float] = None
    vol_ratio: Optional[float] = None
    volume_confirmed: Optional[bool] = None
    extended_pct: Optional[float] = None
    signal_kind: str = ""  # market_top | guide_top | qcom_dip | stage_exit
    asof: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(PT).isoformat())
    status: str = "proposed"  # proposed | approved | executed | cancelled | blocked

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OrderTicket":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


def load_config(path: Optional[Path] = None) -> dict:
    cfg_path = path or (BOT_ROOT / "config.yaml")
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _ticket_id(symbol: str, side: str, kind: str, asof: str) -> str:
    raw = f"{symbol}|{side}|{kind}|{asof}|{datetime.now(PT).strftime('%Y%m%d')}"
    h = hashlib.sha1(raw.encode()).hexdigest()[:10]
    return f"{datetime.now(PT).strftime('%Y%m%d')}-{symbol.replace('.', '_').replace('-', '_')}-{side.lower()}-{h}"


def load_market_results(cfg: dict) -> pd.DataFrame:
    scan_dir = Path(cfg["equity_scan_dir"])
    csv_path = scan_dir / cfg["market_results_csv"]
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing market scan CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    # normalize volume_confirmed to bool
    if "volume_confirmed" in df.columns:
        df["volume_confirmed"] = df["volume_confirmed"].astype(str).str.lower().isin(
            ("true", "1", "yes", "y")
        )
    return df


def parse_dip_scenario(cfg: dict) -> Optional[dict]:
    """Parse QCOM (or configured) dip band from dip_scenario.md."""
    if not cfg.get("qcom_dip_enabled", True):
        return None
    path = Path(cfg["equity_scan_dir"]) / cfg["dip_scenario_md"]
    if not path.exists():
        return None
    text = path.read_text()
    out: dict[str, Any] = {"symbol": cfg.get("qcom_symbol", "QCOM")}
    m = re.search(r"\*\*Ticker:\*\*\s*([A-Z0-9.\-]+)", text)
    if m:
        out["symbol"] = m.group(1)
    # Reference / band / SMA150 from markdown table rows
    for key, pattern in (
        ("reference", r"Reference.*?\|?\s*\*\*([0-9.]+)\*\*"),
        ("dip_3", r"−3%.*?\|?\s*\*\*([0-9.]+)\*\*"),
        ("dip_5", r"−5%.*?\|?\s*\*\*([0-9.]+)\*\*"),
        ("sma150_inv", r"SMA150.*?\|?\s*\*\*([0-9.]+)\*\*"),
    ):
        mm = re.search(pattern, text)
        if mm:
            out[key] = float(mm.group(1))
    # Fallback: compute from reference if band missing
    if "reference" in out and "dip_3" not in out:
        out["dip_3"] = round(out["reference"] * 0.97, 2)
    if "reference" in out and "dip_5" not in out:
        out["dip_5"] = round(out["reference"] * 0.95, 2)
    return out if "reference" in out else None


def _stage2(row) -> bool:
    return str(row.get("stage", "")).startswith("Stage 2")


def _stage4(row) -> bool:
    return str(row.get("stage", "")).startswith("Stage 4")


def _left_stage2(row) -> bool:
    s = str(row.get("stage", ""))
    return not s.startswith("Stage 2")


def _size_dollar(cfg: dict, equity: float) -> float:
    pct = float(cfg.get("max_position_pct", 0.05))
    return round(equity * pct, 2)


def _limit_for(side: str, price: float, offset: float) -> float:
    if side == "BUY":
        return round(price * (1.0 - offset), 2)
    return round(price * (1.0 + offset), 2)


def _row_ticket(
    row,
    side: str,
    kind: str,
    reason: str,
    cfg: dict,
    equity: float,
) -> OrderTicket:
    symbol = str(row["ticker"])
    price = float(row["price"])
    asof = str(row.get("asof", ""))
    order_type = str(cfg.get("default_order_type", "LIMIT")).upper()
    offset = float(cfg.get("limit_offset_pct", 0.002))
    limit_price = _limit_for(side, price, offset) if order_type == "LIMIT" else None
    dollar = _size_dollar(cfg, equity) if side == "BUY" else None
    qty = None
    if side == "SELL":
        # qty filled from ledger by caller; placeholder 0 means "full position"
        qty = 0.0
    elif not cfg.get("dollar_amount_mode", True) and price > 0:
        qty = max(1, int(dollar // price)) if dollar else None
        dollar = None
    return OrderTicket(
        ticket_id=_ticket_id(symbol, side, kind, asof),
        symbol=symbol,
        side=side,
        order_type=order_type,
        qty=qty,
        dollar_amount=dollar,
        limit_price=limit_price,
        reason=reason,
        stage=str(row.get("stage")),
        score=float(row["score"]) if pd.notna(row.get("score")) else None,
        price=price,
        sma150=float(row["sma150"]) if pd.notna(row.get("sma150")) else None,
        slope=float(row["slope"]) if pd.notna(row.get("slope")) else None,
        vol_ratio=float(row["vol_ratio"]) if pd.notna(row.get("vol_ratio")) else None,
        volume_confirmed=bool(row.get("volume_confirmed"))
        if "volume_confirmed" in row.index
        else None,
        extended_pct=float(row["extended_pct"]) if pd.notna(row.get("extended_pct")) else None,
        signal_kind=kind,
        asof=asof,
    )


def build_buy_candidates(df: pd.DataFrame, cfg: dict, equity: float) -> list[OrderTicket]:
    tickets: list[OrderTicket] = []
    seen: set[str] = set()
    n = int(cfg.get("top_n_buys", 10))
    require_vol = bool(cfg.get("require_volume_confirmed", True))

    market = df.copy()
    market = market[market["stage"].astype(str).str.startswith("Stage 2")]
    if require_vol:
        market = market[market["volume_confirmed"] == True]  # noqa: E712
    market = market.sort_values("score", ascending=False).head(n)

    for _, row in market.iterrows():
        sym = str(row["ticker"])
        if sym in seen:
            continue
        seen.add(sym)
        tickets.append(
            _row_ticket(
                row,
                "BUY",
                "market_top",
                f"Stage 2 volume-confirmed market top; score={row.get('score')}",
                cfg,
                equity,
            )
        )

    if cfg.get("include_guide_top", True):
        g_n = int(cfg.get("guide_top_n", 5))
        guide = df[df["source"].astype(str).str.contains("guide", case=False, na=False)].copy()
        guide = guide[guide["stage"].astype(str).str.startswith("Stage 2")]
        if require_vol:
            guide = guide[guide["volume_confirmed"] == True]  # noqa: E712
        guide = guide.sort_values("score", ascending=False).head(g_n)
        for _, row in guide.iterrows():
            sym = str(row["ticker"])
            if sym in seen:
                continue
            # Skip non-US / odd symbols that Schwab equity API won't take easily
            if "." in sym or len(sym) > 6:
                continue
            seen.add(sym)
            tickets.append(
                _row_ticket(
                    row,
                    "BUY",
                    "guide_top",
                    f"Guide Stage 2 top; score={row.get('score')}",
                    cfg,
                    equity,
                )
            )
    return tickets


def build_qcom_dip(
    df: pd.DataFrame, cfg: dict, equity: float, dip: Optional[dict]
) -> list[OrderTicket]:
    if not dip:
        return []
    sym = dip["symbol"]
    rows = df[df["ticker"].astype(str) == sym]
    if rows.empty:
        return []
    row = rows.iloc[0]
    price = float(row["price"])
    stage = str(row.get("stage", ""))

    # Cancel if Stage 4 or below SMA150
    sma150 = float(row["sma150"]) if pd.notna(row.get("sma150")) else dip.get("sma150_inv")
    if stage.startswith("Stage 4") or (sma150 is not None and price < sma150):
        return [
            OrderTicket(
                ticket_id=_ticket_id(sym, "CANCEL", "qcom_dip_cancel", str(row.get("asof", ""))),
                symbol=sym,
                side="CANCEL",
                order_type="NONE",
                reason=(
                    f"QCOM dip cancelled: stage={stage}, price={price}, sma150={sma150}"
                ),
                stage=stage,
                price=price,
                sma150=sma150,
                signal_kind="qcom_dip_cancel",
                asof=str(row.get("asof", "")),
                status="cancelled",
            )
        ]

    lo = float(dip["dip_5"])  # −5% = lower bound of band
    hi = float(dip["dip_3"])  # −3% = upper bound of band
    if not stage.startswith("Stage 2"):
        return []
    if not (lo <= price <= hi):
        # Informational: not in band — no ticket (scan md will note)
        return []

    t = _row_ticket(
        row,
        "BUY",
        "qcom_dip",
        (
            f"QCOM dip: price {price} in −5%/−3% band [{lo}, {hi}] vs ref "
            f"{dip.get('reference')}; still Stage 2"
        ),
        cfg,
        equity,
    )
    # Prefer limit at band mid or current
    t.limit_price = round(price, 2)
    return [t]


def build_exit_tickets(
    df: pd.DataFrame, cfg: dict, open_positions: list[dict]
) -> list[OrderTicket]:
    """Propose SELL when an open position leaves Stage 2 or enters Stage 4."""
    tickets: list[OrderTicket] = []
    by_sym = {str(r["ticker"]): r for _, r in df.iterrows()}
    for pos in open_positions:
        sym = str(pos.get("symbol", ""))
        if not sym or sym not in by_sym:
            continue
        row = by_sym[sym]
        if _stage4(row) or _left_stage2(row):
            t = _row_ticket(
                row,
                "SELL",
                "stage_exit",
                f"Exit signal: left Stage 2 / stage={row.get('stage')}",
                cfg,
                equity=0.0,
            )
            t.qty = float(pos.get("qty") or 0) or None
            t.dollar_amount = None
            tickets.append(t)
    return tickets


def generate_tickets(
    cfg: Optional[dict] = None,
    open_positions: Optional[list[dict]] = None,
    equity: Optional[float] = None,
) -> list[OrderTicket]:
    cfg = cfg or load_config()
    equity = float(equity if equity is not None else cfg.get("assumed_equity_usd", 100000))
    df = load_market_results(cfg)
    dip = parse_dip_scenario(cfg)
    tickets: list[OrderTicket] = []
    tickets.extend(build_buy_candidates(df, cfg, equity))
    tickets.extend(build_qcom_dip(df, cfg, equity, dip))
    tickets.extend(build_exit_tickets(df, cfg, open_positions or []))
    # Deduplicate by symbol+side keeping first (higher priority kinds already first)
    out: list[OrderTicket] = []
    seen: set[tuple[str, str]] = set()
    for t in tickets:
        if t.side == "CANCEL":
            out.append(t)
            continue
        key = (t.symbol, t.side)
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def tickets_to_markdown(tickets: list[OrderTicket], meta: Optional[dict] = None) -> str:
    now = datetime.now(PT).strftime("%Y-%m-%d %H:%M PT")
    lines = [
        "# Proposed order tickets",
        "",
        f"**Generated:** {now}",
        "",
        "Execution assistant for user Stage Analysis signals — not financial advice.",
        "Default is propose-only. No live order is placed without an explicit approval "
        "record and `execute`.",
        "",
    ]
    if meta:
        for k, v in meta.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    buys = [t for t in tickets if t.side == "BUY"]
    sells = [t for t in tickets if t.side == "SELL"]
    other = [t for t in tickets if t.side not in ("BUY", "SELL")]

    def section(title: str, items: list[OrderTicket]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_None_")
            lines.append("")
            return
        lines.append(
            "| ticket_id | symbol | side | type | qty/$ | limit | kind | stage | score | reason |"
        )
        lines.append("|---|---|---|---|---:|---:|---|---|---:|---|")
        for t in items:
            size = (
                f"${t.dollar_amount:,.2f}"
                if t.dollar_amount
                else (str(t.qty) if t.qty is not None else "—")
            )
            lim = f"{t.limit_price:.2f}" if t.limit_price is not None else "—"
            sc = f"{t.score:.2f}" if t.score is not None else "—"
            reason = (t.reason or "").replace("|", "/")[:80]
            lines.append(
                f"| `{t.ticket_id}` | {t.symbol} | {t.side} | {t.order_type} | {size} | "
                f"{lim} | {t.signal_kind} | {t.stage or '—'} | {sc} | {reason} |"
            )
        lines.append("")

    section("BUY candidates", buys)
    section("SELL / exit", sells)
    if other:
        section("Other / cancelled", other)

    # QCOM note
    lines.append("## QCOM dip check")
    lines.append("")
    q = [t for t in tickets if t.signal_kind.startswith("qcom_dip")]
    if not q:
        lines.append(
            "No QCOM dip ticket — price not in −3% to −5% band and/or not Stage 2, "
            "or dip scenario disabled."
        )
    else:
        for t in q:
            lines.append(f"- `{t.ticket_id}`: {t.reason}")
    lines.append("")
    lines.append("## Approve / execute")
    lines.append("")
    lines.append("```bash")
    lines.append("python bot.py approve --id <ticket_id>")
    lines.append("python bot.py execute --id <ticket_id>   # requires approval + dry_run=false + SCHWAB_*")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    ts = generate_tickets()
    print(json.dumps([t.to_dict() for t in ts], indent=2))
