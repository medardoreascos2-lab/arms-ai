# V29R canonical MVP historical market-data time contract

This is a **new architectural contract authorized in V29R**, not an inference
about previous ARMS AI behavior or NinjaTrader export settings.

The original V29R input is the existing normalized historical CSV. Interpret naive
timestamps as America/Chicago local wall time at the aggregation boundary.
Offset-aware timestamps convert to Chicago. Preserve raw CSV timestamps and
source Candle objects exactly. Ambiguous/nonexistent naive DST labels fail
closed and require explicit offsets; do not guess a DST fold. Offset-aware
repeated hours are separate buckets, ordered by their UTC instants.

## V31 native export amendment (Sprint 05, explicit opt-in)

The original CSV convention above is preserved for frozen V30 reproducibility;
it must not be applied directly to native NinjaTrader export text. Research-grade
control evidence supports native **UTC end-of-bar** labels for JUN22–JUN25.
`HistoricalEligibilityV31` parses that source label as UTC, subtracts exactly
60 elapsed seconds, then converts the open instant to America/Chicago. Availability
is the original UTC end. Both raw row and source file/hash/row/contract remain in
the immutable observation. DST conversion never localizes a naive Chicago label.
Execution Candle timestamps use the resulting explicit Chicago offset, preserving
UTC ordering through a fold even in legacy datetime comparison consumers.

Source validity, strategy-context eligibility, execution-price eligibility and
session-accounting eligibility are separate metadata. Valid source observations
are always retained. The injected, hash-identified CME US Index Futures ETH
calendar includes explicit full/partial holidays. Reviewed contract termination
clips eligibility at 08:30 Chicago on the reviewed expiry date; the last interval
ending at termination is eligible. Dates/contracts outside the reviewed domain
fail closed. Current template and matched controls provide research-grade evidence,
not a claim of provider-level or archived-calendar certification.

Under the conservative policy, an interval outside a permitted session or after
termination is ineligible for all three consumers. Such rows remain in the source
and research lineage stream; they cannot mark positions, trigger SL/TP, complete
lifecycle trades, advance cooldown, enter history or contribute HTF OHLCV. The
single-contract executable view filters them before the existing single-pass
engine, including its future-price view. This is not price repair or deletion.
Canonical timestamp gaps still invalidate incomplete HTF buckets; no filling or
retroactive changes to prior decisions occur. Prior complete bars remain available.

During a temporary closure the position remains unresolved; only the next eligible
price of the same contract may resume evaluation. A segment/contract boundary
ends the independent experiment with an explicit unresolved terminal position.
No forced exit, cross-contract prices, continuous account or spliced equity curve
is introduced. Existing simulator END_OF_DATA valuations use only the final
eligible price and are reported separately as censored, never as completed fills.
Simulator SL/TP completion and authoritative lifecycle completion are reported
separately, without summing their PnL. All segment/threshold combinations require
fresh composition and identical risk configuration. Default production/live
wiring, the original CSV contract and frozen V30 artifacts are unchanged.

`Candle.timestamp` is the interval **open label** under this historical
contract. A 09:30 1m candle covers [09:30, 09:31) and is complete at 09:31.
Historical replay supplies completed Candle objects; processing the 09:30
object therefore corresponds to availability at 09:31, not an event at 09:30.
The monotonic candle index and entry price remain unchanged. Single-pass
context additionally exposes `decision_time` as that aware completion time.
A future event-time caller must wait for interval completion before calling
`update_completed`; passing an in-progress candle violates that API contract.
This phase does not rewire live ingestion or claim its timestamp semantics
were already equivalent.

## Buckets and visibility

Both timeframes use Chicago wall-clock boundaries, not session-relative origins.
15m starts at HH:00/:15/:30/:45; 1h starts at HH:00. HTF output retains its open
label and uses aware Chicago timestamps with metadata 15m or 1h.

| Input completed minutes | Output | First visibility |
|---|---|---|
|09:30 through09:44, all15 slots|09:30 15m covering[09:30,09:45)|After09:44 completes, at09:45|
|09:00 through09:59, all60 slots|09:00 1h covering[09:00,10:00)|After09:59 completes, at10:00|
|09:30..09:44 with09:37 absent|No09:30 15m bar|Never|
|Maintenance gap16:00..16:59|No16:00 hourly bar; complete prior bars retained|17:00 bucket starts independently|
|Dataset starts09:32|No partial09:30 15m or09:00 1h|Next complete buckets only|
|Dataset ends09:42|No partial09:30 15m or09:00 1h|No end-of-data flush|

Every expected minute must occur once in chronological order: exactly15 or60
slots. Duplicate/backward/off-minute inputs raise. A missing minute invalidates
that bucket; no carry from another bucket completes it. Session/weekend/holiday
gaps follow this same data-completeness rule, without inferring exchange hours
or synthesizing candles. Prior complete history remains available across gaps.

OHLCV is first open, max high, min low, last close, summed volume. Flat minutes
are real inputs and count toward completeness. No filling, interpolation,
price mutation, or dropped source observations is permitted. The opt-in V31
eligibility view excludes ineligible observations from aggregation while retaining
them in source lineage. Completed HTF snapshots
are detached; future inputs and changes to caller snapshots cannot alter them.

## Integration and warm-up

`ClosedBarAggregatorV1` processes two fixed accumulators once per completed
minute. It retains at most `analysis_window` completed bars per timeframe.
Snapshots are bounded, so total work is O(n * analysis_window), with fixed
window 50 in production. No repeated full-history resampling occurs.

Only explicit single-pass backtesting uses this new contract. Legacy
BacktestEngine.run/session replay semantics remain unchanged. Single-pass
`history` retains original 1m dictionaries; `history_15m` and `history_1h`
contain only completed aggregate bars in separate lists. Warm-up and the final
non-entry candle still feed aggregation. Future simulator suffixes never feed it.

TrendContextEngineV2 delegates both HTF inputs to MarketStructureEngineV3.
That consumer returns UNKNOWN for fewer than 10 bars and needs two confirmed
swing highs and lows for direction. Thus at least 10 completed bars of **each**
HTF are required, but 10 alone does not guarantee readiness. The existing
neutral direction, quality gate, and HOLD behavior enforce this; no new numeric
warm-up constant or threshold is introduced. EMA10 still uses the 1m history.

Live TrendEngineV2 is a different consumer (default 50 bars). A future live
adapter can reuse this completion-notification contract and must retain its
own consumer requirements. No live execution or broker wiring changes here.

The V27A accepted-is-True veto, V27B chronological decision count/future suffix
isolation/statistics, and V27C flat-candle behavior remain authoritative.

## V29R empirical validation

Dataset `data/backtest/nq_sep26_1m_certified.csv`, SHA256
`793ed9a8f5b013d693bb2925a180de8ba2620c9d09ef702d2ba2819d0bb2b14f`.
Parameters remain EMA10/SL30/TP60; A+ 90, quality 85, weights and risk limits
unchanged. No source row was rewritten or removed.

All 47,178 candles and 399 flat candles completed. Valid HTF totals: 3,022 15m
and 717 1h. An independent batch oracle verified every timestamp and OHLCV
against complete expected-minute sets; 187 nonempty 15m buckets and 111 nonempty
1h buckets were incomplete. Entirely absent buckets are not counted there.

Decision-eligible: 47,173; confluence evaluated: 47,168 (five EMA-warm-up decisions).
Scores: min 9.61 / max 81.33 / mean 40.2263254749. Grades: C 46,658 / B 471 / A 39 / A+ 0.
Trade quality remains at most 60 without A+, below 85. Controller never reached;
all 47,173 actions HOLD. Signals, plans, submissions, acceptances, rejections,
independent simulations and completed lifecycle trades are all 0. Net profit 0,
drawdown 0, final equity 17,000. Classification: EXPECTED_STRATEGY_STRICTNESS for
this dataset and these unchanged parameters under the newly authorized contract.
The timeframe bug is repaired but does not resolve zero signals. The next
blocking condition is A+ confluence 90; no threshold adjustment is proposed.

All V28 funnel counters and 20 near misses are in
`backend/tests/v29r_htf_funnel_evidence.json`. Existing V28 JSON/analysis artifacts
remain unchanged. Its observer and regression are extended to verify separate
HTF histories, availability, and the newly required warm-up. The 350-minute
synthetic fixture no longer falsely satisfies ten completed hourly bars; its
old positive-trade assertion is replaced by explicit HOLD/zero-side-effect
assertions. Existing V17 legacy positive controls and V27A accepted/standalone
execution tests remain in the regression set.

Full-run invariants: 47,168 score/field/scale mappings reconciled; HTF trend
matches a fresh TrendContextEngineV2 on actual closed histories; structure and
liquidity match fresh engines. Timestamp availability and bounded disjoint
histories are asserted at every decision. Alias count 0. All decisions,
statistics, equity and trade count match a fresh uninstrumented production run.
Instrumented time 35.0228s; uninstrumented 17.7021s, excluding loading. HTF
snapshot/analysis adds work versus the V27 baseline, while processing remains
single-pass and bounded; no performance equivalence to the old 5s run is claimed.

The directional labels, symbol NQ, base/HTF warm-up, scale conversions, default
evidence, chronological clock and SL/TP/sizing separation retain their V28
contracts. A+ policy authorities still have the same benchmark settings (.8/.8
in SignalGenerator, fixed A+/ .8/.8 admission in lifecycle); no authority was
bypassed or reconfigured. The controller and execution are not the zero-signal
cause. Contract/gap/lookahead/DST tests cover the corrected timeframe invariant.

## Regression commands

`py -m pytest <the following targets> -q` (certified V28 environment):

- `backend/tests/test_backtest_single_pass_v27b.py`
- `backend/tests/test_backtest_engine.py`
- `backend/tests/test_backtest_session_v2.py`
- `backend/tests/test_backtest_session_signal_submission_v2.py`
- `backend/tests/test_backtest_session_trade_executor_integration_v2.py`
- `backend/tests/test_backtest_session_auto_position_updates_v2.py`
- `backend/tests/test_backtest_session_multiple_trades_v2.py`
- `backend/tests/test_backtest_session_signal_generation_v2.py`
- `backend/tests/test_backtest_session_build_report_v2.py`
- `backend/tests/test_backtest_pipeline_v2.py`
- `backend/tests/test_backtest_pipeline_real_e2e_v2.py`
- `backend/tests/test_backtest_runner_v2.py`
- `backend/tests/test_backtest_runner_v2_observer.py`
- `backend/tests/test_replay_engine_v2.py`
- `backend/tests/test_replay_market_data_bridge_v2.py`
- `backend/tests/test_csv_replay_runner_integration_v2.py`
- `backend/tests/test_phase1_risk_precedence_v5.py::test_risk_inventory_covers_current_decision_and_writer_evidence`
- `backend/tests/test_phase1_financial_state_sync_v6.py::test_financial_inventory_matches_reviewed_source_and_ownership`
- `backend/tests/test_phase1_runtime_execution_ownership_v7.py::test_inventory_matches_all_reviewed_production_boundaries`
- `backend/tests/test_flat_candle_contract_v27c.py`
- `backend/tests/test_zero_signal_funnel_v28.py`
- `backend/tests/test_parameterized_strategy_runner_safety_v2.py`
- `backend/tests/test_trade_quality_engine_v1.py`
- `backend/tests/test_confluence_engine_v2.py`
- `backend/tests/test_trend_context_engine_v2.py`
- `backend/tests/test_signal_controller_v2.py`
- `backend/tests/test_backtest_a_plus_policy_settings_authority_v2.py`
- `backend/tests/test_closed_bar_aggregation_v29r.py`

The combined run passed 224 tests. Subsequent final aggregation tests passed 18
and observer/financial-evidence checks passed; two newly added boundary/context
tests bring this group's distinct total to 226.

V17 command: `py -m pytest backend/tests/test_production_certified_outcome_v17.py backend/tests/test_real_market_structure_detectors_v17.py -q`.
Result: 15 passed in 284.58s. Total distinct tests across final checks: 241
passed, zero failures. The existing Starlette/httpx deprecation warning remains.

Only the `BacktestSessionV2.run` row's source hash and calls changed in the
financial inventory. Ownership classifications, risk and execution inventories
are unchanged; all three exactness checks pass.

Final source review confirms submission, independent execution, and lifecycle
position-update methods are AST-identical to HEAD. `git diff --check` and
new-file whitespace checks pass. No staging, commit, push, live execution, or
external broker interaction occurred.
