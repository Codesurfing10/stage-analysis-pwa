#!/usr/bin/env bash
# Weekday propose-only scan. Never places live orders.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif [[ -x /workspace/xlsx-venv/bin/python ]]; then
  PY=/workspace/xlsx-venv/bin/python
else
  echo "No venv found. Create with: python3 -m venv $ROOT/.venv && $ROOT/.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

echo "[run_daily] $(date '+%Y-%m-%d %H:%M:%S %Z') using $PY"
"$PY" bot.py scan
"$PY" bot.py status
echo "[run_daily] done — review out/proposed_orders_*.md ; approve then execute only after user yes"
