# V30 offline calibration research

Completed on 2026-09-19. Research only; production thresholds remain A+ 90 and quality 85. No production source, configuration, weights, scores, risk rules, execution rules or datasets were changed. No stage, commit, push, live execution or external broker interaction.

**Provenance and scope.** HEAD `76c1883d5fbe8de314c0272c644f99f352e21b49`, branch `refactor/backend-architecture`. Dataset `data\backtest\nq_sep26_1m_certified.csv`; SHA-256 `793ed9a8f5b013d693bb2925a180de8ba2620c9d09ef702d2ba2819d0bb2b14f`. All 47,178 candles and 399 flat candles preserved; canonical aggregation produced 3,022 complete 15m and 717 complete 1h bars. EMA 10, SL 30, TP 60 throughout. Five of 47,173 decision-eligible bars are EMA warm-up; 47,168 confluence evaluations. Scores are recorded in [scores.csv](scores.csv), with distributions and counts in [score_analysis.json](score_analysis.json). These are derived research evidence, not replacement market data.

**A — Complete scoring contract.** The production caller is [ParameterizedStrategyRunnerV2](../../strategies/parameterized_strategy_runner_v2.py); authorities are [ConfluenceEngineV2](../../intelligence/confluence_engine_v2.py), [MarketStructureEngineV3](../../market_structure/market_structure_engine_v3.py), [TrendContextEngineV2](../../trend/trend_context_engine_v2.py), [LiquidityEngineV2](../../smart_money/liquidity_engine_v2.py), [SmartMoneyEngineV2](../../smart_money/smart_money_engine_v2.py), and [MarketRegimeEngine](../../market_analysis/market_regime_engine.py).

The seven base weights sum to 85 and are multiplied by 100/85. Score = round(sum(weight × normalized component), 2). Individual reported contributions are rounded separately, so their printed sum can differ by a cent. The compatibility argument probability_score is validated but has **zero scoring weight**. It is not an independent calibrated probability; outgoing confidence is confluence/100.

| Component | Raw evidence → normalization | Weight | Canonical max contribution | Direction / regime dependence; neutral |
| --- | --- | --- | --- | --- |
| Trend | 1h and 15m structure agree bullish/bearish → 1; otherwise .5 | 17.65 | 17.65 | Direction from both HTFs; independent of 1m regime; neutral earns half |
| Structure | 1m swing HH_HL or LH_LL +50; BOS +25; CHOCH −10; no-swings 20; divide by 100 | 17.65 | 13.24 | Symmetric bull/bear; no explicit direction match with HTF; RANGE may be 0, NO_SWINGS .2 |
| Liquidity | Real sweep at fourth-last candle over recent 8: matching direction 1, no sweep .5, opposed/no allowed direction 0 | 11.76 | 11.76 | Lookback 5, equality tolerance 1 unchanged; no explicit regime dependence; neutral half |
| FVG | Latest three 1m bars: matching FVG 1, none .5, opposed/no allowed direction 0 | 11.76 | 11.76 | Direction dependent; no regime dependence; neutral half. Helper fallback .25 for unknown FVG direction is unreachable with current detector |
| EMA alignment | Current close versus EMA10 agrees with allowed LONG/SHORT → 1, else 0 | 11.76 | 11.76 | Direction dependent; no explicit regime dependence; neutral zero |
| Market regime | Trend: abs(net close movement / sum(abs close changes)); RANGE/HIGH_VOL .5; nontradable 0 | 17.65 | 17.65 | Absolute direction efficiency, not necessarily HTF direction; neutral tradable regimes half |
| Volume | Latest volume / mean of preceding available volumes in trailing 20 / 2, clipped [0,1] | 11.76 | 11.76 | Neither direction nor regime dependent; insufficient volume/nonpositive prior mean → .5 |
| Probability compatibility input | Clamped directional strategy heuristic; accepted for compatibility | 0 | 0 | No influence on confluence total |

The current structure engine cannot return 100: its maximum is 50 + 25 = 75. Therefore the canonical maximum is (15 + 15×.75 + 10 + 10 + 10 + 15 + 10)×100/85 = **95.588235…**, displayed as **95.59**. Global, bullish and bearish maxima are all 95.59. The generic ConfluenceEngine API permits 100 for all-one inputs, but the canonical structure caller cannot supply that vector.

| Actual regime | Regime component | Canonical maximum | Can reach 90? | Empirical count / maximum |
| --- | --- | --- | --- | --- |
| TREND_UP | efficiency in [.6,1] | 95.59 | Yes; constructive unchanged-detector witness | 2 / 71.78 |
| TREND_DOWN | efficiency in [.6,1] | 95.59 | Yes; mirrored witness | 30 / 71.15 |
| RANGE | 0.50 | 86.76 | No; upper bound below 90 | 35967 / 81.33 |
| HIGH_VOLATILITY | 0.50 | 86.76 | No; upper bound below 90 | 1568 / 75.55 |
| LOW_VOLATILITY | 0 | 77.94 | No; additionally market_not_tradable | 8943 / 77.94 |
| NO_TRADE | 0 | 77.94 | No; additionally market_not_tradable | 658 / 65.27 |

All six maxima have **constructive OHLCV witnesses** in [test_research_calibration_v30.py](../test_research_calibration_v30.py), using actual production detectors, canonical 1m→15m/1h aggregation, and the real factory. They contain no injected component scores and are explicitly synthetic tests, not additional observations. The bullish witness has monotonic closes and oscillating wicks, legitimate higher swings/BOS, a historical low sweep, aligned FVG, and doubled final volume; reflecting prices proves the bearish case. Controlled candle variations prove the four other regime maxima. The blocked-regime witnesses also assert the market veto remains present.

At all other component maxima, an unrounded score of 90 needs regime evidence ≥0.683333…; rounding can classify values ≥89.995 as 90 (boundary precision depends on floating representation). Only 32/47,168 evaluations are TREND_UP/DOWN. Regime classification gives compression ≥.85 priority as NO_TRADE, then normalized volatility ≥.8 as HIGH_VOL, ≤.2 as LOW_VOL, then close efficiency ≥.6/≤−.6 as trend. Volatility is mean candle range / mean close ×1000; compression is one minus the last-ten range / full bounded-history range. These existing rules, including their priority, are unchanged.

**Contribution losses explaining the observed ceiling.**

| Component | Canonical max | Empirical max | Mean contribution | Mean deficit to canonical max |
| --- | --- | --- | --- | --- |
| trend | 17.65 | 17.65 | 10.37 | 7.28 |
| structure | 13.24 | 13.24 | 5.88 | 7.35 |
| liquidity | 11.76 | 11.76 | 5.51 | 6.26 |
| fvg | 11.76 | 11.76 | 4.79 | 6.97 |
| ema_alignment | 11.76 | 11.76 | 1.03 | 10.74 |
| market_regime | 17.65 | 14.18 | 7.03 | 10.62 |
| volume | 11.76 | 11.76 | 5.62 | 6.15 |

EMA alignment and regime evidence have the largest mean contribution deficits (10.74 and 10.62 points). HTF-neutral direction occurs in 38,909 evaluated rows (82.49%); it halves trend evidence, makes EMA alignment zero, and prevents aligned liquidity/FVG scores. Structure normalization permanently removes 4.41 points relative to a generic all-one formula. These marginal means are descriptive, not causal independence estimates.

The empirical maximum at 2026-09-16 16:47:00-05:00 has trend=1, structure=.75, liquidity=1, FVG=1, EMA=1, regime=.5 and volume=0.5379834254143646. Relative to the 95.588235 theoretical maximum, regime costs 8.823529 points and volume costs 5.435489, giving 81.33 after rounding. In RANGE, even maximum volume can only raise it to 86.76.

**B — Empirical distribution.** Linear-interpolated percentiles use sorted rank (n−1)×p/100; input scores already carry production rounding. Full subgroup histograms are in score_analysis.json.

| Group | N | Mean | P50 | P75 | P80 | P85 | P90 | P95 | P97 | P99 | P99.5 | MAX |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 47168 | 40.23 | 40.02 | 45.82 | 47.87 | 49.83 | 53.45 | 60.84 | 64.07 | 70.52 | 74.14 | 81.33 |
| LONG | 4754 | 54.14 | 53.91 | 61.76 | 63.24 | 65.88 | 68.16 | 71.76 | 74.26 | 76.97 | 79.52 | 81.33 |
| NONE | 38909 | 37.30 | 37.10 | 42.52 | 43.68 | 45.59 | 47.49 | 49.22 | 50.82 | 54.41 | 54.41 | 56.29 |
| SHORT | 3505 | 53.87 | 53.52 | 61.61 | 62.81 | 64.66 | 67.65 | 70.39 | 73.31 | 76.47 | 79.21 | 80.88 |
| TRENDING combined | 32 | 53.03 | 53.39 | 61.36 | 65.22 | 66.70 | 67.68 | 70.56 | 71.19 | 71.58 | 71.68 | 71.78 |
| HIGH_VOLATILITY | 1568 | 42.92 | 42.26 | 47.57 | 48.67 | 50.94 | 54.41 | 62.17 | 64.42 | 69.17 | 72.77 | 75.55 |
| LOW_VOLATILITY | 8943 | 32.56 | 31.65 | 37.56 | 39.69 | 41.60 | 45.59 | 52.43 | 56.52 | 64.41 | 66.18 | 77.94 |
| NO_TRADE | 658 | 30.81 | 30.34 | 34.57 | 36.59 | 39.90 | 43.78 | 51.69 | 52.97 | 58.79 | 59.58 | 65.27 |
| RANGE | 35967 | 42.18 | 41.18 | 47.23 | 48.53 | 50.88 | 54.41 | 61.76 | 65.74 | 71.69 | 74.71 | 81.33 |
| TREND_DOWN | 30 | 52.30 | 50.01 | 60.73 | 63.49 | 66.08 | 67.56 | 69.01 | 70.22 | 70.84 | 70.99 | 71.15 |
| TREND_UP | 2 | 64.03 | 64.03 | 67.91 | 68.68 | 69.46 | 70.23 | 71.01 | 71.32 | 71.63 | 71.70 | 71.78 |

| Score bucket | Count |
| --- | --- |
| 0-49.99 | 40219 |
| 50-59.99 | 4399 |
| 60-64.99 | 1264 |
| 65-69.99 | 776 |
| 70-74.99 | 348 |
| 75-79.99 | 123 |
| 80-84.99 | 39 |
| 85-89.99 | 0 |
| 90+ | 0 |

Direction means canonical HTF allowed_direction: LONG=bullish, SHORT=bearish, NONE=neutral; it is distinct from the 1m regime's directional label. No canonical intraday session classification or certified historical holiday calendar is attached to the strategy context, so no inferred RTH/ETH split is introduced. Trading dates use MarketHoursServiceV2.trading_day_for on the **aware completed-bar decision time**, including its 17:00 Chicago roll; this label does not prove the market was open. There are 35 represented canonical trading dates, including dates with no candidate. The factory's existing historical market_is_open context is preserved.

**C — Score-only sensitivity.** Passing candles are opportunities, not trades. Neutral passes are zero for this grid. Blocked LOW_VOLATILITY/NO_TRADE rows remain visible here; this table does not authorize them.

| Cutoff | Passing | % | BUY side | SELL side | Dates | Regimes (count) |
| --- | --- | --- | --- | --- | --- | --- |
| 90 | 0 | 0.0000 | 0 | 0 | 0 | none |
| 87.50 | 0 | 0.0000 | 0 | 0 | 0 | none |
| 85 | 0 | 0.0000 | 0 | 0 | 0 | none |
| 82.50 | 0 | 0.0000 | 0 | 0 | 0 | none |
| 80 | 39 | 0.0827 | 23 | 16 | 17 | RANGE:39 |
| 77.50 | 73 | 0.1548 | 43 | 30 | 25 | RANGE:72, LOW_VOLATILITY:1 |
| 75 | 162 | 0.3435 | 97 | 65 | 31 | RANGE:157, LOW_VOLATILITY:2, HIGH_VOLATILITY:3 |
| 72.50 | 328 | 0.6954 | 202 | 126 | 33 | RANGE:317, HIGH_VOLATILITY:9, LOW_VOLATILITY:2 |
| 70 | 510 | 1.0812 | 318 | 192 | 34 | RANGE:473, LOW_VOLATILITY:20, HIGH_VOLATILITY:14, TREND_UP:1, TREND_DOWN:2 |
| 67.50 | 929 | 1.9696 | 557 | 372 | 34 | RANGE:859, LOW_VOLATILITY:32, HIGH_VOLATILITY:33, TREND_UP:1, TREND_DOWN:4 |
| 65 | 1286 | 2.7264 | 778 | 508 | 34 | RANGE:1158, LOW_VOLATILITY:77, HIGH_VOLATILITY:43, NO_TRADE:1, TREND_UP:1, TREND_DOWN:6 |
| 60 | 2550 | 5.4062 | 1513 | 1037 | 34 | RANGE:2275, LOW_VOLATILITY:159, HIGH_VOLATILITY:104, NO_TRADE:2, TREND_UP:1, TREND_DOWN:9 |

**D — Quality contract and matrix.** [TradeQualityEngineV1](../../intelligence/trade_quality_engine_v1.py) immediately returns 0/rejected for CHOCH. Otherwise it adds A+ grade 40, valid structure 20, BOS 15, no CHOCH 15, HTF alignment 10. Therefore non-A+ quality ≤60, and no quality threshold in (60,85] can pass the current non-A+ observations. With A+, scores ≥85 require valid structure plus BOS or HTF alignment; a non-CHOCH aligned valid structure without BOS scores exactly 85. Quality is a discrete checklist, not a continuous transformation of confluence. Observed quality counts: 0=7429, 15=15894, 25=3317, 35=9106, 45=1895, 50=7798, 60=1729.

The following matrix retains production **A+ classification at 90**. Cells count recorded opportunities satisfying the proposed score cutoff AND unchanged quality evidence ≥ the column cutoff, with CHOCH veto retained. This is static eligibility to reach the controller, not a stateful replay count. In production the quality gate is before controller evaluation, while final confluence approval/tradability is checked after it; a controller visit alone is not permission to execute. Changing a later final confluence cutoff does not itself change the total number of controller invocations. Below-80 rows would still face the unchanged final approved-grade floor and downstream .8 admission floor. No grade bonus is fabricated in this matrix.

| Score cutoff | Q85 | Q80 | Q75 | Q70 | Q60 |
| --- | --- | --- | --- | --- | --- |
| 90 | 0 | 0 | 0 | 0 | 0 |
| 85 | 0 | 0 | 0 | 0 | 0 |
| 80 | 0 | 0 | 0 | 0 | 37 |
| 75 | 0 | 0 | 0 | 0 | 147 |
| 70 | 0 | 0 | 0 | 0 | 372 |

**E — Analytical temporal independence.** Sort passing opportunities in canonical decision order. A consecutive cluster requires the same direction and canonical trading date, adjacent decision indices, and exactly one elapsed minute. A setup episode links passing observations with the same direction/date and ≤10 elapsed minutes since the previous passing observation; larger gaps, direction changes, or date changes split it. Median spacing is elapsed minutes between episode starts, including overnight gaps. This single-linkage estimate can merge a long chain and is **not proof of statistical independence**. The ten-minute analytical rule is never fed to the strategy; no new production cooldown exists.

| Cutoff | Raw | Consecutive clusters | Episodes | Dates | Median spacing min | Episodes LONG/SHORT |
| --- | --- | --- | --- | --- | --- | --- |
| 80 | 39 | 32 | 28 | 17 | 1268 | 15/13 |
| 77.50 | 73 | 61 | 51 | 25 | 604 | 30/21 |
| 75 | 162 | 117 | 86 | 31 | 264 | 51/35 |
| 72.50 | 328 | 224 | 158 | 33 | 107 | 94/64 |
| 70 | 510 | 307 | 199 | 34 | 77 | 116/83 |
| 67.50 | 929 | 489 | 250 | 34 | 56 | 143/107 |
| 65 | 1286 | 586 | 275 | 34 | 48.50 | 155/120 |
| 60 | 2550 | 973 | 257 | 34 | 67 | 140/117 |

**F — Predeclared isolated replay.** [predeclared_grid.json](predeclared_grid.json) was written before candidate PnL was examined. Grid: A+ boundaries **80, 80.5, 81**, all with quality **85**. Selection used only score/date coverage: 39/35/1 raw candidates on 17/16/1 dates, respectively. 80 preserves the downstream .8 floor; 80.5 tests local sensitivity; 81 is a sparse cliff control. Production boundary 90 remains the verified zero-trade control.

This is an explicitly hypothetical **classification-boundary** experiment. An instance-local wrapper calls the real confluence evaluator once and changes only its grade label when score ≥ the research boundary. Numerical scores, weights, risk flags, blocking reasons, approved/status/decision fields, and every detector remain unchanged. The real quality engine then applies its existing grade-dependent bonus. No risk or execution rejection is overridden. The real generator/lifecycle .8 floors, quality85, V27A same-decision acceptance gate, V27B replay, V29R closed-bar HTF, controller cooldown and all other policies remain intact. The wrapper is restored on exit and is never applied to production settings or class-global methods. Thus these runs answer a different, clearly stated hypothesis than the fixed-grade matrix.

An executor observer asserts explicit accepted=True for the same decision before calling the real executor. The engine statistics/equity derive from the independent simulator; completed lifecycle count is reported separately and never added to simulator PnL. Simulated outcomes use the existing future-only suffix for SL/TP resolution, invisible to analysis. Lifecycle close-driven accounting and independent intrabar simulation are distinct existing authorities. All candidates use the existing account sizing/context, including factory-supplied risk context, without adding a new PnL feedback mechanism. Consequently this does not certify dynamic account-limit synchronization or live market-hours enforcement. Reported PnL is the existing simulator model, with no new commission/slippage model; lifecycle paper slippage does not make that simulator cost-adjusted.

| A+ boundary | Signals | Accepted | Rejected | Simulated | Completed lifecycle | Win % | Net PnL | PF | Expectancy | Max DD | Trades/day | LONG/SHORT | Regimes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | 24 | 24 | 0 | 24 | 24 | 29.17 | -1800 | 0.82 | -75 | 4200 | 0.69 | 12/12 | {"RANGE":24} |
| 80.50 | 21 | 21 | 0 | 21 | 21 | 33.33 | 0 | 1 | 0 | 3600 | 0.60 | 12/9 | {"RANGE":21} |
| 81 | 1 | 1 | 0 | 1 | 1 | 0 | -600 | 0 | -600 | 600 | 0.03 | 1/0 | {"RANGE":1} |

All figures are IN-SAMPLE exploratory outcomes, not a strategy certification. Zero candidate rejections here does not weaken the rejection contract: the direct session suites cover accepted, rejected, missing/malformed acceptance, standalone execution, HOLD and risk veto. Candidate evidence includes per-trade decision index/time/score/regime and exit reason in [replay_results.json](replay_results.json). Trades/day uses all 35 represented dates, not only winning or active dates. PF is null if no losing trades (including empty samples). Drawdown is realized simulator equity drawdown in decision order, not mark-to-market drawdown.

**G — Descriptive robustness screen.** Predeclared adequacy: ≥30 simulated trades total and ≥10 in each first-half, second-half, odd-date and even-date cohort. No candidate passes. The partition results below are still reported for transparency, not statistical inference. First half uses entry decision index ≤23,589, second half >23,589. Odd/even is ordinal in the sorted 35 canonical trading dates (first date odd). Continuous replay state is preserved; these are entry cohorts, not reset account backtests. A shared boundary date can appear in both halves, and exits can cross the half boundary. Cohort cumulative PnL starts at zero solely for independent descriptive metrics. None is out-of-sample; no candidate was selected using a holdout.

| Boundary | Cohort | N | Win % | Net PnL | PF | Expectancy | Max DD | Trades/day | LONG/SHORT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | first_half | 14 | 28.57 | -1200 | 0.80 | -85.71 | 3600 | 0.78 | 8/6 |
| 80 | second_half | 10 | 30 | -600 | 0.86 | -60 | 3600 | 0.56 | 4/6 |
| 80 | odd_dates | 15 | 40 | 1800 | 1.33 | 120 | 2400 | 0.83 | 9/6 |
| 80 | even_dates | 9 | 11.11 | -3600 | 0.25 | -400 | 3600 | 0.53 | 3/6 |
| 80.50 | first_half | 14 | 28.57 | -1200 | 0.80 | -85.71 | 3600 | 0.78 | 8/6 |
| 80.50 | second_half | 7 | 42.86 | 1200 | 1.50 | 171.43 | 1800 | 0.39 | 4/3 |
| 80.50 | odd_dates | 12 | 50 | 3600 | 2 | 300 | 1800 | 0.67 | 9/3 |
| 80.50 | even_dates | 9 | 11.11 | -3600 | 0.25 | -400 | 3600 | 0.53 | 3/6 |
| 81 | first_half | 0 | — | 0 | — | — | 0 | 0 | 0/0 |
| 81 | second_half | 1 | 0 | -600 | 0 | -600 | 600 | 0.06 | 1/0 |
| 81 | odd_dates | 1 | 0 | -600 | 0 | -600 | 600 | 0.06 | 1/0 |
| 81 | even_dates | 0 | — | 0 | — | — | 0 | 0 | 0/0 |

**H — Interpretation and next experiment.** No production winner is selected. All three candidates fail sample adequacy; all are 100% RANGE and have no trending/high-volatility execution evidence. At 80, odd/even PnL is +1,800/−3,600; at 80.5 it is +3,600/−3,600, and first/second-half expectancy reverses sign. These are descriptive instability flags from tiny samples, not significance tests. Max drawdowns 4,200 and 3,600 equal 24.71% and 21.18% of the engine's 17,000 initial equity basis; that basis is distinct from the factory's lifecycle account capital. Moving 80.5→81 reduces raw coverage from 35 to 1 (97.14% loss), a pathological cliff. Do not prefer 80.5 merely because its total PnL is higher.

For a later **fresh-data feasibility experiment only**, retain the paired hypotheses **80 and 80.5**, with quality85 and a production90 negative control; exclude 81 as a calibration candidate. This pairing is based on the largest coverage that preserves existing admission rules and a local sensitivity comparison, not a profit ranking. Neither meets the current statistical readiness screen. Before formal calibration, gather enough untouched periods to satisfy a prospectively declared sample target, cover multiple regimes/directions, and assess cost and account-state limitations under a separately authorized scope. Freeze formulas/grid before new observations; do not retune this sample. Production recommendation: **UNCHANGED (A+90, quality85)**. READY_FOR_FORMAL_CALIBRATION_EXPERIMENT=NO under the declared sample/robustness screen; research deliverables are complete.

**Verification.** The full real baseline observer matches an uninstrumented production run on every decision, statistics, complete equity state and trades. All three candidates are additionally repeated from fresh factories and compared with uninstrumented engines under the same hypothetical boundary; see verification.json. New unit/regression tests cover interpolation, histogram edges, clustering/date boundaries, discrete quality/CHOCH veto, unchanged score/risk fields, admission-floor bounds, method restoration (including exceptions), non-overwriting outputs, metrics, and six constructive canonical maxima. Existing V27A/HTF/flat-candle/session/controller/confluence/quality/ownership suites are also run. See test_evidence.json for exact test targets, commands, counts and final scope verification.

**Reproduction.** From the repository root with the same established test environment, run `py -m backend.tests.research_calibration_v30 baseline --dataset data/backtest/nq_sep26_1m_certified.csv --output <new-research-directory>`. Inspect score-only evidence and create a predeclared_grid.json before any candidate replay, then run the same module with phase `replay`. Outputs use exclusive creation; existing evidence cannot be silently overwritten. The script requires downstream settings .8/.8 and does not set thresholds. The canonical test environment and exact invocation are recorded in test_evidence.json. Source hashes in score_analysis/replay_results identify their original helper version; verification.json identifies the later helper version that adds the uninstrumented candidate comparison without altering analytical or replay policy logic.
