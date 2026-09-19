# Sprint 07R: canonical historical accounting and PAPER research

Canonical entry, intrabar exit, one PnL realization, account/risk feedback and one journal record are implemented in an explicit isolated historical composition. Production confluence stays 90, quality stays 85, and all existing risk limits remain unchanged. No LIVE wiring or broker connection was added.

## Recovery and certification

Continued the existing uncommitted work at 04ce5cd59601c3660f425492dec9569c94ebb71c. Reused all 39 completed C0 runs and 156 completed cost runs; did not restart the study. The recovery audit verified all 205 protected file hashes, empty staging, unchanged branch/HEAD and exact core/research/C0 hashes from the pre-cost declaration.

Across the 39 legacy-versus-canonical comparisons: 13,151 POSITION_FEEDBACK_EXPECTED; 62,613 RISK_FEEDBACK_EXPECTED; zero UNEXPLAINED. No C0 terminal positions were unresolved. Each changed decision reproduces the legacy decision under the recorded counterfactual state and has an explicit execution/risk causal root.

JUN22 / 80: frozen independent simulator +$12,600; legacy close-only lifecycle +$15,935; canonical +$4,800. These are distinct historical authorities, not amounts to sum. Candle 6984 closes the same accepted trade intrabar before evaluation; legacy HOLD / ACTIVE POSITION becomes canonical HOLD / Opposite CHOCH detected. Restoring legacy state exactly reproduces the old decision.

## Costs and aggregate outcomes

FEE_A = $2.50/contract/side; FEE_B = $5/contract/side. These are illustrative research assumptions, not actual broker fees. S0/S1/S2 = 0/1/2 adverse ticks per side. At $20/point and .25 point/tick, slippage alone costs $0/$10/$20 per completed one-contract round trip. Round-trip fees are $5 or $10. Slippage is embedded in executed fills and is not subtracted twice.

Costs enter the existing projected-stop risk check. Different trade counts are chronological risk/position feedback, not deletion of losses or retuned signals. Gross below is fill-based PnL before fees; the normalized trade ledger separately shows PnL before both slippage and fees.

| Boundary | Case | Trades | Gross $ | Fees $ | Net $ | PF | Expectancy $ | Max account equity DD $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 90 | C0 | 0 | 0 | 0 | 0 | N/A | N/A | 0 |
| 80 | C0 | 354 | 19,800 | 0 | 19,800 | 1.1467 | 55.93 | 4,435 |
| 80 | FEE_A/S0 | 354 | 19,800 | 1,770 | 18,030 | 1.1325 | 50.93 | 4,495 |
| 80 | FEE_A/S1 | 353 | 16,870 | 1,765 | 15,105 | 1.1096 | 42.79 | 4,490 |
| 80 | FEE_A/S2 | 306 | 8,280 | 1,530 | 6,750 | 1.0551 | 22.06 | 4,485 |
| 80 | FEE_B/S0 | 353 | 20,400 | 3,530 | 16,870 | 1.1235 | 47.79 | 4,465 |
| 80 | FEE_B/S1 | 306 | 11,340 | 3,060 | 8,280 | 1.0681 | 27.06 | 4,430 |
| 80 | FEE_B/S2 | 305 | 8,900 | 3,050 | 5,850 | 1.0476 | 19.18 | 4,500 |
| 80.5 | C0 | 373 | 24,600 | 0 | 24,600 | 1.1745 | 65.95 | 4,405 |
| 80.5 | FEE_A/S0 | 373 | 24,600 | 1,865 | 22,735 | 1.1599 | 60.95 | 4,490 |
| 80.5 | FEE_A/S1 | 330 | 20,100 | 1,650 | 18,450 | 1.1449 | 55.91 | 4,490 |
| 80.5 | FEE_A/S2 | 328 | 18,040 | 1,640 | 16,400 | 1.1280 | 50.00 | 4,485 |
| 80.5 | FEE_B/S0 | 351 | 23,400 | 3,510 | 19,890 | 1.1475 | 56.67 | 4,465 |
| 80.5 | FEE_B/S1 | 328 | 21,320 | 3,280 | 18,040 | 1.1419 | 55.00 | 4,430 |
| 80.5 | FEE_B/S2 | 326 | 17,480 | 3,260 | 14,220 | 1.1106 | 43.62 | 4,410 |

These sums combine independent contract outcomes; they are not a continuous portfolio return or equity curve. Max account drawdown is the largest marked-equity drawdown in any one segment.

## Direction and cohort robustness

| Boundary | Case | Direction | Trades | Win rate % | Gross $ | Net $ | PF | Expectancy $ | Max independent realized DD $ | Largest positive contract share |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 80 | C0 | LONG | 167 | 28.74 | -13,800 | -13,800 | 0.8067 | -82.63 | 6,600 | 37.50% |
| 80 | C0 | SHORT | 187 | 43.32 | 33,600 | 33,600 | 1.5283 | 179.68 | 3,600 | 28.12% |
| 80 | FEE_A/S0 | LONG | 167 | 28.74 | -13,800 | -14,635 | 0.7967 | -87.63 | 6,685 | 37.95% |
| 80 | FEE_A/S0 | SHORT | 187 | 43.32 | 33,600 | 32,665 | 1.5094 | 174.68 | 3,645 | 28.32% |
| 80 | FEE_A/S1 | LONG | 166 | 28.92 | -14,860 | -15,690 | 0.7838 | -94.52 | 6,855 | 38.99% |
| 80 | FEE_A/S1 | SHORT | 187 | 43.32 | 31,730 | 30,795 | 1.4724 | 164.68 | 3,735 | 28.73% |
| 80 | FEE_A/S2 | LONG | 142 | 28.87 | -14,240 | -14,950 | 0.7632 | -105.28 | 7,025 | 40.27% |
| 80 | FEE_A/S2 | SHORT | 164 | 42.07 | 22,520 | 21,700 | 1.3655 | 132.32 | 3,825 | 26.26% |
| 80 | FEE_B/S0 | LONG | 166 | 28.92 | -13,200 | -14,860 | 0.7936 | -89.52 | 6,770 | 38.44% |
| 80 | FEE_B/S0 | SHORT | 187 | 43.32 | 33,600 | 31,730 | 1.4907 | 169.68 | 3,690 | 28.52% |
| 80 | FEE_B/S1 | LONG | 142 | 28.87 | -12,820 | -14,240 | 0.7726 | -100.28 | 6,940 | 39.59% |
| 80 | FEE_B/S1 | SHORT | 164 | 42.07 | 24,160 | 22,520 | 1.3823 | 137.32 | 3,780 | 26.09% |
| 80 | FEE_B/S2 | LONG | 142 | 28.87 | -14,240 | -15,660 | 0.7539 | -110.28 | 7,110 | 41.03% |
| 80 | FEE_B/S2 | SHORT | 163 | 42.33 | 23,140 | 21,510 | 1.3632 | 131.96 | 3,870 | 26.44% |
| 80.5 | C0 | LONG | 171 | 29.24 | -12,600 | -12,600 | 0.8264 | -73.68 | 7,200 | 33.33% |
| 80.5 | C0 | SHORT | 202 | 43.56 | 37,200 | 37,200 | 1.5439 | 184.16 | 3,600 | 26.09% |
| 80.5 | FEE_A/S0 | LONG | 171 | 29.24 | -12,600 | -13,455 | 0.8162 | -78.68 | 7,275 | 35.66% |
| 80.5 | FEE_A/S0 | SHORT | 202 | 43.56 | 37,200 | 36,190 | 1.5247 | 179.16 | 3,645 | 26.31% |
| 80.5 | FEE_A/S1 | LONG | 150 | 28.00 | -15,900 | -16,650 | 0.7493 | -111.00 | 7,425 | 48.06% |
| 80.5 | FEE_A/S1 | SHORT | 180 | 45.00 | 36,000 | 35,100 | 1.5765 | 195.00 | 3,735 | 26.29% |
| 80.5 | FEE_A/S2 | LONG | 150 | 28.00 | -17,400 | -18,150 | 0.7311 | -121.00 | 7,575 | 50.00% |
| 80.5 | FEE_A/S2 | SHORT | 178 | 45.51 | 35,440 | 34,550 | 1.5699 | 194.10 | 3,825 | 25.86% |
| 80.5 | FEE_B/S0 | LONG | 161 | 28.57 | -13,800 | -15,410 | 0.7803 | -95.71 | 7,350 | 45.95% |
| 80.5 | FEE_B/S0 | SHORT | 190 | 44.21 | 37,200 | 35,300 | 1.5459 | 185.79 | 3,690 | 26.55% |
| 80.5 | FEE_B/S1 | LONG | 150 | 28.00 | -15,900 | -17,400 | 0.7401 | -116.00 | 7,500 | 50.00% |
| 80.5 | FEE_B/S1 | SHORT | 178 | 45.51 | 37,220 | 35,440 | 1.5893 | 199.10 | 3,780 | 25.68% |
| 80.5 | FEE_B/S2 | LONG | 149 | 27.52 | -18,580 | -20,070 | 0.7050 | -134.70 | 7,650 | 50.00% |
| 80.5 | FEE_B/S2 | SHORT | 177 | 45.76 | 36,060 | 34,290 | 1.5670 | 193.73 | 3,870 | 26.06% |

LONG is loss-making in this study; SHORT supplies the aggregate gain. Both remain enabled. A directional subset drawdown is descriptive and is not the actual mixed-strategy account drawdown. No short-only strategy was created.

`realism_results.json` contains all scenario-specific LONG/SHORT breakdowns by contract, year, early/late cohort, regime, available Chicago RTH/ETH session labels, and declared volatility bins, plus four-contract rolling descriptive windows and PnL/trade/drawdown concentration. Session labels describe certified eligible historical hours, not claimed fill quality.

## Independent zero-cost segments

| Contract | Boundary | Opportunities | Accepted | Rejected | Risk vetoes | Completed | Net $ | Peak equity $ | Minimum equity $ | Max DD $ | Largest losing day $ | Longest loss streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JUN22 | 80 | 92 | 34 | 0 | 39 | 34 | 4800.0 | 159005.0 | 148365.0 | 4205.0 | -1200.0 | 5 |
| JUN22 | 80.5 | 87 | 31 | 0 | 40 | 31 | 4800.0 | 159005.0 | 148365.0 | 4205.0 | -1200.0 | 7 |
| SEP22 | 80 | 67 | 63 | 0 | 2 | 63 | 9000.0 | 162975.0 | 149675.0 | 4165.0 | -1200.0 | 6 |
| SEP22 | 80.5 | 61 | 59 | 0 | 0 | 59 | 11400.0 | 163915.0 | 149675.0 | 4240.0 | -1200.0 | 6 |
| DEC22 | 80 | 78 | 9 | 0 | 52 | 9 | 0.0 | 154405.0 | 149815.0 | 4405.0 | -600.0 | 6 |
| DEC22 | 80.5 | 71 | 9 | 0 | 48 | 9 | 0.0 | 154405.0 | 149815.0 | 4405.0 | -600.0 | 6 |
| MAR23 | 80 | 76 | 5 | 0 | 48 | 5 | -3000.0 | 151140.0 | 147000.0 | 4140.0 | -1200.0 | 5 |
| MAR23 | 80.5 | 70 | 5 | 0 | 44 | 5 | -3000.0 | 151140.0 | 147000.0 | 4140.0 | -1200.0 | 5 |
| JUN23 | 80 | 39 | 20 | 0 | 17 | 20 | 600.0 | 154550.0 | 149715.0 | 3950.0 | -600.0 | 6 |
| JUN23 | 80.5 | 37 | 19 | 0 | 16 | 19 | 1200.0 | 155150.0 | 149715.0 | 3950.0 | -600.0 | 5 |
| SEP23 | 80 | 77 | 13 | 0 | 46 | 13 | -4200.0 | 150235.0 | 145800.0 | 4435.0 | -1800.0 | 5 |
| SEP23 | 80.5 | 53 | 32 | 0 | 16 | 32 | -1200.0 | 153080.0 | 146850.0 | 4280.0 | -2400.0 | 4 |
| DEC23 | 80 | 46 | 23 | 0 | 16 | 23 | 2400.0 | 156775.0 | 149455.0 | 4375.0 | -1200.0 | 7 |
| DEC23 | 80.5 | 39 | 21 | 0 | 12 | 21 | 1800.0 | 156175.0 | 149455.0 | 4375.0 | -1200.0 | 7 |
| MAR24 | 80 | 39 | 19 | 0 | 16 | 19 | -2400.0 | 151795.0 | 147600.0 | 4195.0 | -1200.0 | 5 |
| MAR24 | 80.5 | 37 | 18 | 0 | 15 | 18 | -1800.0 | 152395.0 | 148200.0 | 4195.0 | -1200.0 | 5 |
| JUN24 | 80 | 35 | 34 | 0 | 0 | 34 | 1200.0 | 153600.0 | 148275.0 | 3035.0 | -1800.0 | 4 |
| JUN24 | 80.5 | 31 | 30 | 0 | 0 | 30 | 1800.0 | 153600.0 | 147675.0 | 4175.0 | -1800.0 | 6 |
| SEP24 | 80 | 85 | 19 | 0 | 44 | 19 | -2400.0 | 151610.0 | 147600.0 | 4010.0 | -1200.0 | 4 |
| SEP24 | 80.5 | 68 | 40 | 0 | 17 | 40 | -600.0 | 153600.0 | 149080.0 | 4200.0 | -1800.0 | 7 |
| DEC24 | 80 | 39 | 38 | 0 | 0 | 38 | 2400.0 | 152645.0 | 147390.0 | 2685.0 | -1200.0 | 3 |
| DEC24 | 80.5 | 36 | 35 | 0 | 0 | 35 | 600.0 | 150845.0 | 147390.0 | 3075.0 | -1200.0 | 4 |
| MAR25 | 80 | 69 | 44 | 0 | 16 | 44 | 2400.0 | 156600.0 | 148740.0 | 4200.0 | -1800.0 | 7 |
| MAR25 | 80.5 | 62 | 41 | 0 | 14 | 41 | 2400.0 | 156800.0 | 149400.0 | 4400.0 | -1800.0 | 7 |
| JUN25 | 80 | 64 | 33 | 0 | 23 | 33 | 9000.0 | 162930.0 | 149475.0 | 3930.0 | -1800.0 | 4 |
| JUN25 | 80.5 | 63 | 33 | 0 | 22 | 33 | 7200.0 | 161130.0 | 149120.0 | 3930.0 | -1800.0 | 4 |

All 13 boundary-90 controls produce zero opportunities/trades/PnL. Complete daily PnL, final balance/equity, blocks and unresolved-position counts are in each run file. Every cost run has the same per-segment evidence schema.

## Qualification and MVP

- 90: **INSUFFICIENT_EVIDENCE**.
- 80: **INSUFFICIENT_EVIDENCE**.
- 80.5: **SUPPORTED_FOR_PAPER_TRADING_RESEARCH**.

80 reaches the configured $4,500 drawdown limit in JUN22 at FEE_B/S2; the account blocks further acceptance. It therefore fails the predeclared no-hard-limit-reach support condition despite positive aggregate net. 80.5 passes all declared aggregate support checks, with its largest positive contract contribution below 38% in every scenario. This is descriptive support for further PAPER research, not statistical proof of a deployable edge. The criteria were declared before cost outcomes; C0 accounting repair is a new baseline, not a fresh untouched strategy-selection holdout.

The separate `backend/config/paper_research_sprint07r.json` fixes 80.5, EMA10/SL30/TP60, quality85 and FEE_B/S2. It refuses LIVE mode and other uncertified parameters. Its instance-local grade adapter reproduces frozen research while numerical scores and existing vetoes remain untouched.

`PaperResearchSessionV1.run()` explicitly runs the certified historical path once. `create_app(paper_research_provider_v1=service)` exposes only a snapshot through the existing dashboard GET; the existing AccountOverviewWidgetV2 uses the same snapshot. Construction/GET never trades. Snapshots are atomic; RUNNING/FAILED is explicit.

`paper_mvp_evidence.json` proves the real JUN22 pipeline through detectors/HTF/strategy/risk/execution/account/journal and the existing API/widget. It exactly matches all 31 trades and $3,870 net in the frozen highest-cost 80.5 replay. Repeated API reads preserve account and fill state.

## Tests, scope and limitations

1,165 distinct tests passed across the certified baseline, account/execution/lifecycle, inventories, historical research and affected API/dashboard suites. Exact targets and batch results are in `test_evidence.json`; repeated subsets are not counted twice. All 195 completed replay files have per-trade fill/PnL/account reconciliation coverage.

Planned-level fills across gaps retain the existing historical convention; they are not guaranteed executable prices. Fees are sensitivity assumptions. Source provenance retains frozen V31 research limitations. No cross-contract equity splice, forced terminal close, score injection or production threshold/risk-policy change occurred. Legacy counterfactual comparison covers C0; cost runs use the certified canonical implementation with declared costs.

This integration is explicit in-memory offline PAPER research, not a live feed, persistent operational recovery or live-broker deployment. The next priority is an independently specified forward PAPER validation period with authoritative execution costs and reconciliation, preserving this study as frozen evidence.
