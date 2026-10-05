#!/usr/bin/env bash
set -euo pipefail
cd /workspace/trading-bot
set -a
source /home/box/.config/schwab.env
set +a
URL_FILE="${1:-/tmp/schwab_redirect_url.txt}"
python3 - "$URL_FILE" <<'PY'
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
raw = Path(sys.argv[1]).read_text().strip()
code = parse_qs(urlparse(raw).query).get("code", [""])[0]
if not code:
    raise SystemExit("no code in redirect url")
Path("/tmp/schwab_oauth_code.txt").write_text(code)
print(f"code_len={len(code)} scheme={urlparse(raw).scheme}")
PY
CODE=$(cat /tmp/schwab_oauth_code.txt)
# Prefer https to match auth-url; fall back to http
if .venv/bin/python oauth_setup.py --redirect "https://127.0.0.1" exchange --code "$CODE"; then
  :
elif .venv/bin/python oauth_setup.py --redirect "http://127.0.0.1" exchange --code "$CODE"; then
  :
else
  rm -f /tmp/schwab_oauth_code.txt
  exit 1
fi
rm -f /tmp/schwab_oauth_code.txt "$URL_FILE"
bash load_schwab_env.sh
