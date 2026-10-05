# Dip-Buy Scenario (Stage Analysis)

**Not financial advice — scenario framework only.**

## Selected equity
- **Ticker:** MU (MICRON TECHNOLOGY, INC.)
- **Guides:** Technology
- **Why chosen:** High liquidity in the scan universe (50-day avg volume ≈ 31,601,568). Currently **Stage 2 (Advancing)** with action **BUY / HOLD**. Volume confirmed: **True**. Latest vol/vol50 = 1.4115.

## Reference & alert band
| Level | Price |
|-------|------:|
| Reference (latest close) | **1097.39** |
| −3% dip alert | **1064.47** |
| −5% dip alert | **1042.52** |
| SMA150 (invalidation guide) | **783.82** |
| Data as-of | 2026-10-01 |

## Scenario rules
1. **Setup:** Equity remains in Stage 2 (price > SMA150 and SMA150 slope > 0).
2. **Trigger:** Price trades into the **1042.52 – 1064.47** band (−5% to −3% from reference close 1097.39).
3. **Action (scenario):** Alert to buy the dip while Stage 2 still holds; prefer volume on the bounce ≥ ~1.0× vol50 as a soft confirmation.
4. **Invalidation:** Break and close below SMA150 (**783.82**), or transition into Stage 4 (price < SMA150 and slope < 0). Cancel the dip plan if that occurs before entry.
5. **Position sizing (scenario only):** Starter / add-on slice only — e.g. 25–50% of a normal full position at first touch of −3%, optional add toward −5% if Stage 2 intact. Cap total risk so a stop under SMA150 is an acceptable loss for the account. No leverage assumed.

## Context metrics
- Score: 103.0
- SMA50 / extended: 954.3522 / 0.1499 (15.0% above 50-day MA)
- Slope (SMA150 $/day): 4.101195
