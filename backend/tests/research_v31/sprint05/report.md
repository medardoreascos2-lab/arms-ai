# Sprint 05 — historical eligibility and independent fresh validation

## Contract and root cause

Source validity does not authorize execution. The existing Candle normalization
drops advisory flags, while lifecycle marking and the independent simulator consume
prices supplied to them. Sprint 04 demonstrated a post-termination Sunday price
creating a hypothetical take-profit. This sprint adds an explicit opt-in historical
policy before both consumers; default engine, session, simulator and live wiring
are unchanged.

`HistoricalEligibilityV31` retains immutable source observations with four separate
concepts: valid source evidence, strategy context eligibility, execution price
eligibility and session accounting eligibility. This conservative policy sets the
last three false for intervals outside the reviewed calendar or contract lifecycle.
The execution view contains only eligible candles from one contract. A mixed-contract
request fails before replay. All original rows and OHLCV remain in source lineage.

The native mapping is UTC end minus 60 elapsed seconds, converted to Chicago open.
Availability remains the original UTC end. Explicit offsets preserve DST fold
ordering. The V29R document distinguishes this new native path from the old normalized
CSV convention, which remains unchanged for frozen V30 reproducibility.

Ineligible rows cannot advance strategy, cooldown, history, HTF, marking, SL/TP or
lifecycle completion. Gaps discard incomplete HTF buckets without deleting prior
complete history. Same-contract eligible prices can resume unresolved positions.
Contract boundaries start fresh compositions; no old position sees new-contract
prices and no artificial exit is generated. END_OF_DATA is a separate censored
valuation, not a completed SL/TP fill.

## Source and rollover certification

All 1,269,052 rows in the 13 JUN22–JUN25 source contracts are structurally valid.
1,268,757 are eligible and 295 are ineligible for strategy, execution and accounting.
All 295 anomalies are preserved with individual classifications in
`certification.json`. Of these, 59 have direct matching control-export rows; the
remaining 236 share the supported cohort interpretation. Direct reproduction is
not incorrectly claimed for all 295. The local ETH calendar snapshot has explicit
full/partial holiday overrides. Calendar/version and provenance limitations remain
research-grade, not provider-level or archived export-time certification.

All 12 seams satisfy the predeclared completed-session total-volume AND shared-minute
volume rule on two consecutive valid sessions. The next valid session opening is
the switch, with boundary source coverage checked. There is no price adjustment,
intraday splice, filling, synthetic price or outcome-based boundary selection.
The complete evidence for each session and seam is in `certification.json`.

The selected scope has 1,163,522 observations: 1,163,256 eligible and 266 ineligible.
The difference from source totals is contract selection, not source deletion. The
other 29 anomalies remain in the full-source classification evidence. Thirteen
ignored JSONL streams under `data/backtest/v31_sprint05` preserve selected raw rows,
source row numbers, canonical/availability times and eligibility metadata; manifest
entries supply immutable source file/hash/contract and stream hash. No market
dataset is intended for Git.

All four leakage tests are zero: source identity, exact raw row identity,
timestamp plus numerical OHLCV, and comparable canonical timestamp plus OHLCV.
The canonical comparison checks native UTC/end and frozen V30 Chicago conventions.
SEP26 and its alias are excluded. Original exports, controls and V30 artifacts are
checked separately for preservation.

## Frozen experiment and reporting repair

`predeclared_experiment.json` was written before any fresh candidate replay, at
2026-09-19T16:43:13.378591Z. SHA256:
`4ecc850f632b73825955f513b37874984ac206b87d0995957027ed9171c20e6e`.
Boundaries are exactly 90, 80, 80.5; quality stays 85 and SL/TP stay 30/60.
Numerical scores, weights, detector algorithms, risk, submission safety, SL-first
precedence, flat candles and complete HTF semantics are unchanged. The existing
V30 instance-local hypothetical grade classifier is reused; production remains 90.
The declaration pins the calendar, source/stream hashes, exact risk configuration,
independent segment boundaries and descriptive sample/classification rules.

The first 90 run passed observer/plain equality. The first 80 run exposed a new
observer-reporting error: the existing session appends both submission dictionaries
and independent SimulatedTrade objects to `submission_results`. Counting all entries
as submissions is invalid. `observer_repair.json` preserves the original declaration
and helper hash, pins the repaired helper and the already completed control output,
and explains the dictionary filtering correction. A regression uses actual accepted,
rejected and simulated outcome records. No candidate result was selected or threshold
changed in response. Three isolated workers run the remaining frozen combinations;
each job still constructs its own observed and plain engines.

Every run compares all decisions, simulator trades, statistics, equity state,
acceptance sequence and lifecycle completion count against a fresh plain replay.
The observer checks historical/HTF availability against decision time. Results count
opportunities, lifecycle submissions, accepted/rejected submissions, independent
simulated outcomes, completed SL/TP outcomes, censored valuations and lifecycle
completions separately. The two execution/accounting paths are never summed.

## Interpretation limits

Aggregate PnL means RESEARCH_SUM_OF_INDEPENDENT_EXPERIMENTS, not a continuous account.
There is no aggregate equity curve or spliced drawdown. Segment drawdown is computed
from completed independent simulator outcomes in decision order, not mark-to-market
risk or a live portfolio. END_OF_DATA PnL is excluded from completed-trade metrics.
Terminal lifecycle positions and unresolved independent valuations are separate
diagnostics and may differ because the existing authorities have different rules.

The unchanged historical factory supplies daily_pnl=0 and total_drawdown=0 to its
risk context. This study does not certify continuous daily/account risk behavior.
Existing simulator fill assumptions, SL-first precedence, and lack of a new cost or
slippage model are retained. Sample adequacy/classification is descriptive research,
not statistical certification, production promotion or a claim of live profitability.
The 2022–2025 contracts are previously unused validation observations relative to V30;
they are not chronologically later than V30's 2026 data.

## Reproduction and scope

Run `py -m backend.tests.research_fresh_validation_v31 prepare` with the prior local
Sprint03/Sprint04 source/control evidence and original native files available.
Outputs use exclusive creation and must not overwrite the frozen study. Replay uses
`py -m backend.tests.research_fresh_validation_v31 replay` and verifies the declaration,
policy/helper hashes, source hashes and ignored stream hashes. Native market files
and generated streams are intentionally not repository fixtures. Tests use synthetic
observations and need no local market dataset.

Changed implementation/test paths are `backend/backtesting/historical_eligibility_v31.py`,
`backend/tests/research_fresh_validation_v31.py`,
`backend/tests/test_historical_eligibility_v31.py`,
`backend/tests/test_research_fresh_validation_v31.py`, and
`docs/architecture/canonical_historical_time_contract_v29r.md`.
All new research evidence is confined to this Sprint05 directory. Earlier research,
unrelated diagnostics, datasets, factories, strategies, inventories, credentials and
live/broker wiring are not modified. Final test and integrity evidence is recorded
in `verification.json`.

## Regression and safety proof

The final full 38-target recertification run passed **352 distinct tests, zero
failures**, in 347.99 seconds. It covers V17, V27A/B/C, V28, V29R, frozen V30,
all existing V31 provenance/control suites, ownership inventories, engine/session,
pipeline/replay, strategy/confluence/controller/policy and the new eligibility and
research tests. All three inventory exactness tests pass without inventory edits.
The reporting repair also passed a focused 53-test run before resumed replay.
There is one existing Starlette/httpx TestClient deprecation warning.

Deterministic fixtures prove eligible SL and TP, flat-candle preservation, excluded
entry/mark/exit/lifecycle effects, raw lineage retention, same-contract resumption,
terminal unresolved behavior, cross-contract rejection, incomplete HTF exclusion,
future perturbation invariance, UTC/DST mapping, tamper/order/hash rejection,
standalone execution, HOLD, and V27A malformed/rejected acceptance protection.
The full suite retains the explicit accepted-submission risk-veto regression.
The exact Sprint04 post-expiry Sunday TP witness produces NO_DATA with zero PnL
when it is the only future observation, and cannot complete a trade. With a prior
eligible price, only that price may provide an END_OF_DATA censored valuation.

## Final results and robustness

All **39 segment/boundary runs** completed. Each passed its fresh uninstrumented
comparison (78 composition runs supporting the certified outputs). All count, outcome and aggregation
reconciliations passed. There were no censored valuations or terminal unresolved
positions in these actual runs; those paths are covered by deterministic tests.
The maximum control confluence was 86.76; all 13 controls at 90 had zero trades.

| Boundary | Completed | Wins / losses | Net simulated PnL | PF | Expectancy | Classification |
|---|---:|---:|---:|---:|---:|---|
| 90 | 0 | 0 / 0 | $0 | undefined | undefined | INSUFFICIENT_EVIDENCE |
| 80 | 611 | 228 / 383 | $43,800 | 1.1906 | $71.69 | SUPPORTED_FOR_FURTHER_RESEARCH |
| 80.5 | 569 | 210 / 359 | $36,600 | 1.1699 | $64.32 | SUPPORTED_FOR_FURTHER_RESEARCH |

| Contract | 80 completed | 80 PnL | 80.5 completed | 80.5 PnL |
|---|---:|---:|---:|---:|
| JUN22 | 60 | $12600 | 59 | $11400 |
| SEP22 | 63 | $9000 | 57 | $10800 |
| DEC22 | 52 | $1200 | 48 | $-1800 |
| MAR23 | 40 | $4800 | 39 | $5400 |
| JUN23 | 35 | $-3000 | 34 | $-2400 |
| SEP23 | 51 | $1800 | 45 | $1800 |
| DEC23 | 36 | $0 | 32 | $600 |
| MAR24 | 33 | $3600 | 31 | $3000 |
| JUN24 | 33 | $1800 | 30 | $1800 |
| SEP24 | 60 | $-5400 | 55 | $-4200 |
| DEC24 | 38 | $2400 | 35 | $600 |
| MAR25 | 57 | $9000 | 52 | $4800 |
| JUN25 | 53 | $6000 | 52 | $4800 |

At 80, 10 segments were profitable, two losing and one breakeven; all had trades.
At 80.5, 10 were profitable and three losing; all had trades. Median segment trade
counts were 51 and 45, median expectancies $63.16 and $60.00, and median PFs 1.1667
and 1.1579. Maximum individual-segment drawdown was $8,400 for both. Largest shares
of positive segment PnL were 24.14% and 25.33%, below the frozen 50% screen.
No aggregate equity curve or aggregate drawdown was created.

The descriptive sample screen passed for both candidates. The clustering analysis
found 620 opportunities / 612 episodes at 80 and 580 / 571 at 80.5. Raising the
boundary by 0.5 removed 42 completed trades and $7,200 net simulated PnL. These are
paired sensitivity observations, not a new threshold search or PnL winner selection.

**Directional dependence is material:** at 80, SELL contributed $43,800 while BUY
was breakeven; at 80.5, SELL contributed $42,600 while BUY lost $6,000. RANGE accounts
for 532/611 and 496/569 completed trades respectively; only five trades per candidate
were in explicit TREND regimes. Those trend-regime samples are inadequate for
generalization. HIGH_VOLATILITY contributed 74 and 68 trades. RTH-labelled trades
contributed $28,200 and $29,400, compared with $15,600 and $7,200 outside that window.
RTH labels are an analytical 08:30–15:00 Chicago grouping, not a new admission rule.

| Entry year | 80 completed / PnL | 80.5 completed / PnL |
|---|---:|---:|
|2022|180 / $19,800|168 / $18,000|
|2023|159 / $5,400|147 / $7,200|
|2024|168 / $3,600|155 / $2,400|
|2025|104 / $15,000|99 / $9,000|

Year aggregates are positive but 2024's PFs are only 1.0545 and 1.0392. The modest
overall PFs and strong directional/regime dependence remain material limitations.
SUPPORTED_FOR_FURTHER_RESEARCH is the frozen descriptive classification, not
broad strategy certification. Control 90 is INSUFFICIENT_EVIDENCE because it has
no completed trades. Production remains 90 and quality remains 85.

The DEC22 80.5 run recorded one duplicate-submission rejection: 49 submissions,
48 acceptances and exactly 48 simulator outcomes. The rejected submission produced
no extra independent trade. No execution/risk rule was changed to recover it.

## Final preservation and next step

All 21 original/control exports, 124 protected artifacts (including frozen V30 and
the three original datasets), the calendar snapshot and all 13 generated stream
hashes passed preservation checks. The V29R document is the sole intentionally
changed pre-existing tracked file; all other implementation paths are new and
opt-in. No inventory update was necessary. Exact test commands and the intended
50-file local commit scope are in `verification.json`. Market datasets and all
earlier/unrelated untracked artifacts are excluded from that scope.

The original prepare/replay commands above record this study's execution. Frozen
outputs deliberately use exclusive creation. For an independent repeat, use
`replay_job(calendar, segment, boundary)` with the frozen manifest's segment plus
its risk_configuration and save results to a separate evidence location; do not
overwrite the completed study. The original exports and hash-matching local
streams remain required research inputs.

The next priority is independent cost/slippage and account-risk validation of
these fixed hypotheses, including their short-side dependence. This sprint does
not authorize production threshold changes or live deployment.
