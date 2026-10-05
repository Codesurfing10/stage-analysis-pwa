"""Local broker-key store. Never places orders and never touches schwab.env.

Secrets stay in data/broker_keys.json (mode 600). Public status is an allowlist:
booleans, adapter, mode label, and at most the last 4 characters of the API key.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import APP_ROOT, TZ_NAME

DATA_DIR = APP_ROOT / "data"
KEYS_PATH = DATA_DIR / "broker_keys.json"

ADAPTERS = (
    "Charles Schwab",
    "Alpaca",
    "Tradier",
    "Interactive Brokers",
    "E*TRADE",
    "tastytrade",
)
MODES = {
    "paper": "Paper",
    "live": "Live",
}

# Chip copy. "connected" only means both secrets are on disk — trading stays off.
STATUS_NONE = "no keys saved, trading not wired"
STATUS_CONNECTED = "connected"

_MAX_SECRET = 4096


def _chmod_private(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _read_raw() -> dict:
    if not KEYS_PATH.is_file():
        return {}
    _chmod_private(KEYS_PATH, 0o600)
    try:
        data = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_raw(stored: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _chmod_private(DATA_DIR, 0o700)
    payload = json.dumps(
        {
            "adapter": stored.get("adapter") or "",
            "mode": stored.get("mode") or "paper",
            "api_key": stored.get("api_key") or "",
            "api_secret": stored.get("api_secret") or "",
            "updated_at": stored.get("updated_at") or "",
        },
        indent=2,
    ).encode("utf-8") + b"\n"
    tmp = KEYS_PATH.with_suffix(".json.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    _chmod_private(tmp, 0o600)
    os.replace(tmp, KEYS_PATH)
    _chmod_private(KEYS_PATH, 0o600)


def _last4(api_key: str) -> str | None:
    """Last 4 only when that is a mask, never the entire key."""
    if not api_key or len(api_key) <= 4:
        return None
    tail = api_key[-4:]
    if tail == api_key:
        return None
    return tail


def public_status(stored: dict | None = None) -> dict:
    """Allowlisted status. Does not read trading flags from disk."""
    raw = _read_raw() if stored is None else stored
    api_key = raw.get("api_key") if isinstance(raw.get("api_key"), str) else ""
    api_secret = raw.get("api_secret") if isinstance(raw.get("api_secret"), str) else ""
    adapter = raw.get("adapter") if raw.get("adapter") in ADAPTERS else None
    mode = raw.get("mode") if raw.get("mode") in MODES else None
    key_saved = bool(api_key)
    secret_saved = bool(api_secret)
    last4 = _last4(api_key) if key_saved else None
    if last4 and last4 == api_key:
        last4 = None
    connected = key_saved and secret_saved
    out = {
        "key_saved": key_saved,
        "secret_saved": secret_saved,
        "adapter": adapter,
        "mode": mode,
        "mode_label": MODES.get(mode) if mode else None,
        "key_last4": last4,
        "status": STATUS_CONNECTED if connected else STATUS_NONE,
        "trading_wired": False,
        "dry_run": True,
    }
    # Refuse to emit the full key or the secret even if they collide with a label.
    for value in out.values():
        if not isinstance(value, str) or not value:
            continue
        if api_key and value == api_key:
            raise RuntimeError("refusing to return full API key")
        if api_secret and value == api_secret:
            raise RuntimeError("refusing to return API secret")
    return out


def normalize_mode(mode: str | None) -> str:
    token = (mode or "").strip().lower()
    if token not in MODES:
        raise ValueError("mode must be paper or live")
    return token


def normalize_adapter(adapter: str | None) -> str:
    name = (adapter or "").strip()
    if name not in ADAPTERS:
        raise ValueError("unknown broker adapter")
    return name


def save_keys(adapter: str, mode: str, api_key: str | None, api_secret: str | None) -> dict:
    """Persist secrets. Blank fields keep the previous value. Does not enable trading."""
    adapter_n = normalize_adapter(adapter)
    mode_n = normalize_mode(mode)
    key_in = (api_key or "").strip()
    secret_in = (api_secret or "").strip()
    if len(key_in) > _MAX_SECRET or len(secret_in) > _MAX_SECRET:
        raise ValueError("credential too long")
    prev = _read_raw()
    prev_key = prev.get("api_key") if isinstance(prev.get("api_key"), str) else ""
    prev_secret = prev.get("api_secret") if isinstance(prev.get("api_secret"), str) else ""
    now = datetime.now(ZoneInfo(TZ_NAME)).isoformat(timespec="seconds")
    stored = {
        "adapter": adapter_n,
        "mode": mode_n,
        "api_key": key_in or prev_key,
        "api_secret": secret_in or prev_secret,
        "updated_at": now,
    }
    _write_raw(stored)
    return public_status(stored)
