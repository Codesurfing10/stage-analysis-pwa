# Thinkorswim scripts — Stage Analysis

Matches the New Bot / spreadsheet rules used in `/workspace/equity-scan` and the daily tickets.

| File | Use in TOS |
|------|------------|
| `StageAnalysis_Study.ts` | Chart study (Daily) — SMA150/50, stage labels, vol confirm dots, bar colors |
| `StageAnalysis_Scan.ts` | Stock Hacker study filter — Stage 2 + volume confirm |
| `Stage2_Watchlist.ts` | Custom quote column — `2` = Stage2+Vol, `1` = Stage2, `-4` = Stage4 |
| `QCOM_Dip_Alert.ts` | Chart study + alert for 3–5% Stage 2 dip zone |
| `watchlist_market_top10.txt` | Symbols from the latest market top 10 (+ QCOM) |

## Install a chart study

1. Open **thinkorswim** → Charts → open a symbol (e.g. `BHE`).
2. **Studies** → **Edit Studies** → **Create…**
3. Name it (e.g. `StageAnalysis`).
4. Delete the default stub; paste the full contents of `StageAnalysis_Study.ts`.
5. **OK** → **Apply**. Prefer **Day** aggregation.

## Install the scan

1. **Scan** → **Stock Hacker**.
2. Add filter → **Study** → pencil / thinkScript Editor.
3. Paste `StageAnalysis_Scan.ts`.
4. Optional: add Liquidity filters (e.g. last > 5, Avg Volume 50-day > 200000).
5. **Scan**.

## Watchlist column

1. On a watchlist, gear → **Customize…** → **Custom Quotes** (or Quotedata).
2. Create new → paste `Stage2_Watchlist.ts` → name `Stage2`.
3. Add the column to the watchlist layout.

## Import symbols

1. **MarketWatch** → Watchlist → (menu) **Import**.
2. Use `watchlist_market_top10.txt` or paste symbols manually.

## Notes

- Slope uses SMA150 now vs SMA150 five bars ago (same idea as a rising 30-week MA).
- Volume confirm = today’s volume > 1.3 × 50-day average volume.
- These scripts do **not** place orders. Use them for charts, scans, and alerts; place trades in Active Trader / Schwab after your usual approval.
- For BHE specifically: load Daily chart + `StageAnalysis_Study`; green bars with a lime dot = Stage 2 + volume confirm (the ticket thesis).

## BHE ticket reminder (manual)

- BUY LIMIT ~60 shares @ 82.35 (~$5,000) — ticket `20260927-BHE-buy-8aacde7a24`
