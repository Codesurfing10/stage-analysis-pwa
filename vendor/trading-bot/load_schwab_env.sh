#!/usr/bin/env bash
# Source local Schwab env if present. Never echo values.
set -euo pipefail
ENV_FILE="${SCHWAB_ENV_FILE:-/home/box/.config/schwab.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
python3 - <<'PY'
import os
for k in ("SCHWAB_APP_KEY","SCHWAB_APP_SECRET","SCHWAB_REFRESH_TOKEN","SCHWAB_ACCOUNT_HASH"):
    v=os.environ.get(k,"")
    print(f"{k}: set={bool(v)} len={len(v)}")
PY
