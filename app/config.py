"""Paths and PIN loading for Stage PWA. Never reads Schwab secrets."""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
BOT_ROOT = Path(os.environ.get("BOT_ROOT", str(APP_ROOT / "vendor" / "trading-bot")))
EQUITY_SCAN_DIR = Path(os.environ.get("EQUITY_SCAN_DIR", str(APP_ROOT / "vendor" / "equity-scan")))
PIN_FILE = APP_ROOT / ".app_pin"
BOT_VENV_PYTHON = BOT_ROOT / ".venv" / "bin" / "python"
BOT_PY = BOT_ROOT / "bot.py"
TZ_NAME = "America/Tijuana"


def get_app_pin() -> str:
    """PIN from STAGE_APP_PIN env, else .app_pin file."""
    env = os.environ.get("STAGE_APP_PIN", "").strip()
    if env:
        return env
    if PIN_FILE.is_file():
        return PIN_FILE.read_text().strip()
    raise RuntimeError("STAGE_APP_PIN not set and .app_pin missing")


def pin_matches(provided: str | None) -> bool:
    if not provided:
        return False
    try:
        expected = get_app_pin()
    except RuntimeError:
        return False
    return provided.strip() == expected
