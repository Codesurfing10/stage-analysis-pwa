# Parent summary — Schwab Stage Analysis trading bot

## What was built

`/workspace/trading-bot/` — propose-only execution assistant that reads Stage
Analysis outputs from `/workspace/equity-scan/` and writes order tickets.
Live Schwab orders require **per-ticket approval on disk** + `dry_run: false` +
`SCHWAB_*` env vars. Default is propose-only; no advice language.

Modules: `bot.py`, `signals.py`, `risk.py`, `portfolio.py`, `schwab_client.py`,
`config.yaml`, `README.md`, `run_daily.sh`, venv at `.venv/`.

Sample scan has been run → see `out/proposed_orders_*.json` and `.md`
(top 10 Stage 2 volume-confirmed; QCOM dip typically absent when price is at
reference, not in the −3%/−5% band).

## Weekday routine (parent wiring)

1. **Scan (safe):** run `/workspace/trading-bot/run_daily.sh` or
   `.venv/bin/python bot.py scan` after (or using) latest equity-scan CSVs.
2. **Message user:** attach/summarize `out/proposed_orders_YYYYMMDD.md`. Ask
   which ticket_ids (if any) to approve. Do **not** auto-approve.
3. **On explicit user yes for a specific ticket:**
   ```bash
   /workspace/trading-bot/.venv/bin/python /workspace/trading-bot/bot.py approve --id <ticket_id>
   ```
   That appends the approval flag to `out/approvals.jsonl` (required gate).
4. **Execute:**
   ```bash
   /workspace/trading-bot/.venv/bin/python /workspace/trading-bot/bot.py execute --id <ticket_id>
   ```
   - While `dry_run: true` or creds missing → prints manual Schwab entry text;
     **no** live order.
   - Live POST only when approval exists **and** `config.yaml` `dry_run: false`
     **and** all four env vars are set.
5. **Status:** `python bot.py status` anytime.

Never place a real order without the user’s per-order yes → `approve` file.

## Schwab env vars needed

| Env var | Required for live |
|---------|-------------------|
| `SCHWAB_APP_KEY` | yes |
| `SCHWAB_APP_SECRET` | yes |
| `SCHWAB_REFRESH_TOKEN` | yes (re-OAuth ~every 7 days) |
| `SCHWAB_ACCOUNT_HASH` | yes (from `/trader/v1/accounts/accountNumbers`) |

Setup steps: see `README.md` (developer.schwab.com app → authorize → exchange
code → store refresh token + account hash). Keep `dry_run: true` until the user
explicitly asks to go live.
