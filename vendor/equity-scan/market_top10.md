# Full Market Stage 2 Top 10

**Generated:** 2026-10-02 13:16 PT  
**Market data as-of:** 2026-10-01 (Yahoo Finance via yfinance)  
**Universe scored (liquid):** 1536  
**Stage 2 names in universe:** 487  

*Factual stage/volume screen only — not a recommendation to buy or sell.*

| rank | ticker | name | price | sma150 | slope | vol_ratio | volume_confirmed | extended_pct | score | why |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | ACMR | ACMR | 83.58 | 71.48 | 0.2617 | 1.36x | Y | 9.0% | 112.00 | Stage 2; vol confirmed (1.36x); ext 9.0% vs SMA50; slope/SMA 0.366%/day; 16.9% above SMA150 |
| 2 | SNX | SNX | 271.76 | 234.09 | 0.6360 | 1.43x | Y | 5.3% | 108.73 | Stage 2; vol confirmed (1.43x); ext 5.3% vs SMA50; slope/SMA 0.272%/day; 16.1% above SMA150 |
| 3 | LITE | LITE | 1045.78 | 841.80 | 3.9356 | 1.55x | Y | 19.7% | 108.00 | Stage 2; vol confirmed (1.55x); ext 19.7% vs SMA50; slope/SMA 0.468%/day; 24.2% above SMA150 |
| 4 | VIAV | VIAV | 44.78 | 41.60 | 0.1860 | 1.42x | Y | 17.2% | 108.00 | Stage 2; vol confirmed (1.42x); ext 17.2% vs SMA50; slope/SMA 0.447%/day; 7.6% above SMA150 |
| 5 | PBI | PBI | 16.61 | 15.32 | 0.0399 | 1.95x | Y | -2.5% | 107.85 | Stage 2; vol confirmed (1.95x); ext -2.5% vs SMA50; slope/SMA 0.261%/day; 8.4% above SMA150 |
| 6 | MSGS | MSGS | 399.19 | 366.52 | 0.9384 | 2.24x | Y | 0.4% | 107.48 | Stage 2; vol confirmed (2.24x); ext 0.4% vs SMA50; slope/SMA 0.256%/day; 8.9% above SMA150 |
| 7 | COHR | COHR | 319.19 | 315.61 | 1.2174 | 1.65x | Y | 7.6% | 107.00 | Stage 2; vol confirmed (1.65x); ext 7.6% vs SMA50; slope/SMA 0.386%/day; 1.1% above SMA150 |
| 8 | GLBS | GLOBUS MARITIME LIMITED | 3.40 | 2.66 | 0.0090 | 2.26x | Y | -2.6% | 107.00 | Stage 2; vol confirmed (2.26x); ext -2.6% vs SMA50; slope/SMA 0.337%/day; 27.6% above SMA150 |
| 9 | BFH | BFH | 96.94 | 93.64 | 0.2060 | 1.43x | Y | -9.1% | 104.60 | Stage 2; vol confirmed (1.43x); ext -9.1% vs SMA50; slope/SMA 0.220%/day; 3.5% above SMA150 |
| 10 | ROG | ROG | 155.80 | 130.67 | 0.3299 | 1.31x | Y | 18.4% | 103.20 | Stage 2; vol confirmed (1.31x); ext 18.4% vs SMA50; slope/SMA 0.252%/day; 19.2% above SMA150 |

## Methodology
Same Stage Analysis rules as `report.md`: Stage 2 = close > SMA150 and SMA150 OLS slope > 0 (~140 pts); volume confirm if vol > 1.3× vol50; extended % = (price−SMA50)/SMA50; score = Stage 2 base + slope strength + volume confirm + prefer extended under ~0.25.

## Universe notes
- Constituents: S&P 500 + Nasdaq-100 + S&P 400 + S&P 600 + Guide tickers from `tickers.json`.
- Liquidity: 50-day avg dollar volume ≥ $5M, or avg volume ≥ 500k with price ≥ $5 (Guide names always retained).
- Successfully scored liquid names: **1536**; raw scored before filter: 1541; download failures: 12.
