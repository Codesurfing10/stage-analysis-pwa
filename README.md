# Stage Analysis — Mobile PWA

Mobile-first Progressive Web App for James Gallagher’s Stage Analysis trading assistant.

**Screen / execution assistant only — not financial advice.**  
`dry_run` stays **true**. This app never places live Schwab orders. Approvals write to disk only (`trading-bot/out/approvals.jsonl`).

## Paths

| Item | Path |
|------|------|
| App root | `/workspace/stage-pwa/` |
| PIN file | `/workspace/stage-pwa/.app_pin` (chmod 600; also see `.PIN_NOTE.txt`) |
| Trading bot | `/workspace/trading-bot/` |
| Equity scan | `/workspace/equity-scan/` |

## Run locally

```bash
cd /workspace/stage-pwa
./run.sh
# → http://0.0.0.0:8787
```

Or manually:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export STAGE_APP_PIN="$(cat .app_pin)"   # or set your own
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8787
```

Open the PIN unlock screen, enter **101010** (from `.app_pin` / `.PIN_NOTE.txt`), then use Top 10 / Tickets / Dip / Status.

**Desktop / tablet dashboard:** `http://0.0.0.0:8787/dashboard` (same PIN; Top 10, tickets + approve, positions stage, beta vs SPY, QCOM / dip).

### API (JSON)

- `GET /api/health` — no PIN
- `GET /api/dashboard` — requires `X-App-Pin` or `?pin=`
- `GET /api/positions-stage` — PIN; latest positions_stage JSON
- `GET /api/beta` — PIN; latest positions_beta vs SPY summary
- `GET /api/ticket/{ticket_id}` — PIN
- `GET /dashboard` — desktop HTML dashboard
- `POST /api/approve` `{"ticket_id":"..."}` — PIN; runs `bot.py approve`
- `POST /api/execute` `{"ticket_id":"..."}` — PIN; runs `bot.py execute` (manual-entry text when dry_run)
- `GET /api/broker-keys` — PIN; booleans + adapter + mode label + key last-4 only (never the secret or full key)
- `POST /api/broker-keys` — PIN; writes `data/broker_keys.json` (chmod 600). Does not enable trading or place orders. `dry_run` stays true.

## Add to Home Screen

**iPhone (Safari)**  
1. Open the app URL in Safari.  
2. Tap Share → **Add to Home Screen**.  
3. Confirm name “Stage” / “Stage Analysis”.

**Android (Chrome)**  
1. Open the app URL in Chrome.  
2. Menu → **Install app** / **Add to Home Screen**.

Offline shell is cached by the service worker; live ticket/dashboard data still needs network.

## Security notes

- Mutating routes require `X-App-Pin` matching `STAGE_APP_PIN` / `.app_pin`.
- PIN is stored in `sessionStorage` only after unlock (not localStorage).
- Do not commit `.app_pin` or `.PIN_NOTE.txt`.
- Never expose `/home/box/.config/schwab.env` or `SCHWAB_*` secrets through this app.
- Broker API secrets live only in `data/broker_keys.json` (chmod 600). The API never returns them.

## Deploy

Optional `Dockerfile` is included for a later Render deploy. Do not deploy until trading-bot / equity-scan paths are available in that environment and PIN is set via env.

## Daily refresh

After the trading-bot / equity-scan daily routine writes a new
`proposed_orders_YYYYMMDD.json`, `/api/dashboard` picks the **latest** file on
every request (no in-memory cache in `bot_bridge`). You do **not** need to
restart uvicorn for new tickets to appear.

- API responses send `Cache-Control: no-store`.
- Mobile/desktop clients refresh on focus/visibility, and have a **Refresh** button
  (mobile also supports a light pull-down near the top).
- Service worker uses **network-first** for `/api/*` and never caches API JSON.
- Header shows **as-of YYYYMMDD** and ticket count so the scan day is obvious.
