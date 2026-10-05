# Stage Analysis → Charles Schwab execution assistant

Propose-only trading bot that turns the user’s Stage Analysis scan
(`/workspace/equity-scan/`) into **order tickets**. Live Schwab orders are
**never** placed unless:

1. An explicit per-order approval is written to `out/approvals.jsonl`
   (`python bot.py approve --id …`), **and**
2. `config.yaml` has `dry_run: false`, **and**
3. `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET`, `SCHWAB_REFRESH_TOKEN`,
   `SCHWAB_ACCOUNT_HASH` are set in the environment.

This is an **execution assistant for the user’s own signals** — not financial
advice, not a recommendation engine.

## Layout

| Path | Role |
|------|------|
| `bot.py` | CLI: `scan` / `approve` / `execute` / `brokers` / `status` |
| `signals.py` | Load equity-scan CSVs + dip scenario → `OrderTicket`s |
| `risk.py` | Position %, daily order cap, no duplicate open buys |
| `portfolio.py` | Local ledger + optional Schwab positions sync stub |
| `schwab_client.py` | OAuth refresh + equity order via Trader API |
| `brokers/` | `BrokerClient` registry (`get_broker`) and US-broker adapters |
| `config.yaml` | Defaults (`dry_run: true`, `top_n_buys: 10`, …) |
| `run_daily.sh` | Weekday wrapper → `scan` using `.venv` |
| `out/` | Proposed tickets JSON/MD, approvals, executions |
| `data/ledger.json` | Open positions tracked by the bot |

## Signal logic (from equity-scan)

- **Entry (market):** top N Stage 2 volume-confirmed names from
  `market_scan_results.csv` (default N=10).
- **Entry (Guide):** optional Guide Stage 2 names (US symbols only).
- **QCOM dip:** if `qcom_dip_enabled` and price is in the −3% to −5% band from
  `dip_scenario.md` **and** still Stage 2 → BUY ticket. Cancel if below SMA150
  / Stage 4.
- **Exit:** open ledger positions that leave Stage 2 or enter Stage 4 → SELL
  ticket.

## Schwab OAuth setup

1. Create an app at [developer.schwab.com](https://developer.schwab.com/)
   (Trader API – Accounts and Trading).
2. Note **App Key** and **App Secret**. Set redirect URI (commonly
   `https://127.0.0.1`).
3. Open the authorize URL (also printable via Python):

   ```text
   https://api.schwabapi.com/v1/oauth/authorize?client_id=<APP_KEY>&redirect_uri=https://127.0.0.1&response_type=code
   ```

4. Log in, consent, copy the `code` from the redirect URL.
5. Exchange the code for tokens (one-time):

   ```bash
   export SCHWAB_APP_KEY=...
   export SCHWAB_APP_SECRET=...
   # then in Python:
   from schwab_client import SchwabClient
   c = SchwabClient()
   print(c.exchange_code("<code_from_redirect>"))
   ```

6. Save `refresh_token` as `SCHWAB_REFRESH_TOKEN` (≈ **7-day** life — re-consent
   when it expires). Access tokens (~30 min) are refreshed automatically.
7. Fetch account hash:

   ```python
   c.refresh_access_token()
   print(c.get_account_numbers())  # use hashValue → SCHWAB_ACCOUNT_HASH
   ```

**Never commit secrets.** Env vars only.

### Env vars

| Variable | Purpose |
|----------|---------|
| `SCHWAB_APP_KEY` | OAuth client id |
| `SCHWAB_APP_SECRET` | OAuth client secret |
| `SCHWAB_REFRESH_TOKEN` | Long-lived refresh token |
| `SCHWAB_ACCOUNT_HASH` | Opaque account hash from `/accounts/accountNumbers` |

API base: `https://api.schwabapi.com/trader/v1`  
Orders: `POST /accounts/{accountHash}/orders`


## Brokers

`config.yaml` selects the execution adapter with `broker` (default `schwab`) and lists screenable names in `brokers_enabled`. Nothing here flips `dry_run`.

```bash
.venv/bin/python bot.py brokers
```

That command prints the selected broker, `dry_run`, and for each adapter whether its credential env vars are set. Output is **booleans only** — values are never printed.

`execute` keeps the existing Schwab client when `broker: schwab`. Any other configured name is routed through `brokers.get_broker`. If `dry_run` is true **or** that adapter’s credentials are missing, the CLI prints a manual-entry ticket and does **not** HTTP POST an order. An on-disk approval is still required before execute will consider an order.

| Broker | Env vars | Paper / sandbox vs live |
|--------|----------|-------------------------|
| `schwab` | `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET`, `SCHWAB_REFRESH_TOKEN`, `SCHWAB_ACCOUNT_HASH` | Trader API `https://api.schwabapi.com/trader/v1`. There is no separate paper host; live POST stays behind approval + `dry_run: false` + all four vars. |
| `alpaca` | `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` (underscore aliases `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` also count) | **Paper default** `https://paper-api.alpaca.markets`. Live is `APCA_API_BASE_URL=https://api.alpaca.markets`. `POST /v2/orders` runs only when `dry_run` is false and keys are set. |
| `tradier` | `TRADIER_ACCESS_TOKEN`, `TRADIER_ACCOUNT_ID` | **Sandbox default** `https://sandbox.tradier.com`. Live is `TRADIER_BASE_URL=https://api.tradier.com`. `POST /v1/accounts/{id}/orders` runs only when `dry_run` is false and both vars are set. |
| `ibkr` | `IBKR_ACCOUNT_ID`; optional `IBKR_BASE_URL` | Client Portal Web API stub. Default `https://localhost:5000/v1/api`. **NeedsAuth** until you log into the Client Portal Gateway in a browser. This adapter does **not** open a TWS/IB Gateway socket (no `ib_insync`, no ports 7496/7497) and never POSTs `/iserver/.../orders` itself. |
| `etrade` | `ETRADE_CONSUMER_KEY`, `ETRADE_CONSUMER_SECRET`; after the OAuth dance also `ETRADE_ACCESS_TOKEN`, `ETRADE_ACCESS_SECRET`, `ETRADE_ACCOUNT_ID` | OAuth 1.0a stub. **NeedsAuth until access tokens exist** (consumer key/secret alone are not enough). Sandbox default `https://apisb.etrade.com`; live would be `ETRADE_BASE_URL=https://api.etrade.com`. The stub does not request tokens or POST orders. |
| `tastytrade` | `TASTY_CLIENT_ID`, `TASTY_CLIENT_SECRET`, `TASTY_REFRESH_TOKEN`, `TASTY_ACCOUNT_NUMBER`; optional `TASTY_API_BASE_URL` | Session stub. Certification default `https://api.cert.tastyworks.com`; production would be `https://api.tastyworks.com`. **Do not set or store `TASTY_USERNAME`** — username/password login is unsupported; document OAuth/session env names only. `place_equity_order` raises NeedsAuth and does not exchange a session or POST an order. |

Fidelity, Robinhood, and Webull are intentionally omitted: Fidelity has no stable public retail order API (Active Trader Pro is a desktop client, not a third-party order REST); Robinhood has no stable public retail order API (only private/unofficial endpoints); Webull has no stable public retail order API (partner OpenAPI is not a supported retail order interface).

## Approve flow

```bash
# 1) Propose (safe — no orders)
./run_daily.sh
# or:  .venv/bin/python bot.py scan

# 2) Parent shows out/proposed_orders_YYYYMMDD.md to the user

# 3) On explicit user yes for a ticket:
.venv/bin/python bot.py approve --id <ticket_id>

# 4) Execute — still no live order while dry_run=true or creds missing
#    (prints manual Schwab entry ticket instead)
.venv/bin/python bot.py execute --id <ticket_id>

# 5) Live path only after you flip dry_run: false in config.yaml
#    AND all SCHWAB_* env vars are set AND approval exists
```

Approval records are append-only lines in `out/approvals.jsonl`:

```json
{"ticket_id":"...","approved":true,"approved_at":"...","approved_by":"parent_agent"}
```

`execute` refuses without that flag.

## Risk limits (`config.yaml` / `risk.py`)

- `max_positions` — cap on distinct open symbols
- `max_position_pct` — max notional per new BUY (e.g. 5% of equity)
- `max_orders_per_day` — execute-path daily cap
- No duplicate open BUY for a symbol already in the ledger
- Batch scan also reserves slots so one day doesn’t propose > remaining capacity

Equity defaults to `assumed_equity_usd` until Schwab sync fills
`data/ledger.json`.

## Install

```bash
cd /workspace/trading-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python bot.py scan
.venv/bin/python bot.py status
```

`run_daily.sh` prefers `.venv`, else `/workspace/xlsx-venv`.

## Safety summary

| Guard | Behavior |
|-------|----------|
| Default `dry_run: true` | No live API orders |
| Missing `SCHWAB_*` | `NeedsAuthError` / manual print; tickets still saved |
| No approval line | `execute` exits refused |
| Risk violation | Ticket marked `blocked` / execute refused |

Do not place live orders in CI or unattended cron without the approval file
written by the parent after an explicit user yes.

## Guided OAuth (`oauth_setup.py`)

```bash
# After SCHWAB_APP_KEY + SCHWAB_APP_SECRET are in env:
.venv/bin/python oauth_setup.py auth-url
# browser consent → copy code from redirect
.venv/bin/python oauth_setup.py exchange --code 'PASTE_CODE'
# store refresh token as SCHWAB_REFRESH_TOKEN
.venv/bin/python oauth_setup.py accounts
# store hashValue as SCHWAB_ACCOUNT_HASH
.venv/bin/python oauth_setup.py test   # read-only; no orders
```

Keep `dry_run: true` in `config.yaml` until you explicitly go live.
