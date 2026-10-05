# Stage PWA verification (2026-10-02 PT)

## How verified

1. Deps in `/workspace/stage-pwa/.venv`
2. Restarted `uvicorn app.main:app --host 0.0.0.0 --port 8787`
3. Curled health + dashboard with `X-App-Pin: 101010`

## Results

| Check | Result |
|-------|--------|
| `GET /api/health` | ok |
| `GET /api/dashboard` without PIN | HTTP 401 |
| `GET /api/dashboard` with `X-App-Pin: 101010` | latest `proposed_orders_*.json`, `dry_run` true |
| `Cache-Control` on `/api/*` | `no-store` |
| `bot_bridge` | re-globs + reads files each request (no module cache) |
| Mobile Refresh / focus refresh | in `static/app.js` |
| SW | `stage-pwa-shell-v2`, network-first `/api/*` |

## PIN

**101010** — `/workspace/stage-pwa/.app_pin` (chmod 600), also `.PIN_NOTE.txt`.
Override with `STAGE_APP_PIN`. Clients use header `X-App-Pin`.

## Start

```bash
cd /workspace/stage-pwa && ./run.sh
```

Server: `0.0.0.0:8787` · dry_run stays true
