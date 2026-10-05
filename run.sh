#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
# Load PIN from file into env if not already set (does not print value)
if [[ -z "${STAGE_APP_PIN:-}" && -f .app_pin ]]; then
  export STAGE_APP_PIN="$(tr -d '\n' < .app_pin)"
fi
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787
