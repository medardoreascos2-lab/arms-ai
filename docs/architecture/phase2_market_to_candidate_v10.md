# Phase 2 canonical market-to-candidate certification — V10

Baseline: `2aa50801a8902c1cea2ba752dec6147a19352db6` on synchronized branch
`refactor/backend-architecture`. V9 is committed; Phase 1 remains closed.
This package connects controlled application-level PAPER market input to the
existing intelligence stack and the canonical submission contract. It does not
claim a complete browser MVP, paid feed, profitable strategy or LIVE execution.

## Reproduction and root causes

The committed V9 module passed six boundary characterizations. Two new V10
behavior tests then failed before production changes: `/market/webhook` returned
`503 legacy_position_manager_unavailable` instead of storing an authenticated
candle. `/market/analyze` had the same boundary. The coordinated application
publishes `PositionManagerV2`, while the legacy route dependency requires
`PositionManager` and its symbol/timeframe API. This was deliberate Phase 1
containment, not evidence that the canonical runtime itself was broken.

The existing analysis service combines analytical decisions with optional
execution delegates. Merely widening the type check would leave incompatible
position calls and implicit submission. Its generated request also lacked the
coordinated account/profile/generation context. V10 uses the canonical lifecycle
for position reads and separates candidate evaluation from submission.

A second input-wiring defect appeared in the real qualifying scenario: Copilot
puts the calculated EMA in `indicators`, but confluence reads an explicit
`ema_alignment` result. The missing connection left EMA at its neutral fallback.
The canonical candidate path now supplies the actual calculated EMA and the
existing trend owner's direction. No indicator algorithm, score weight, grade,
probability threshold, risk limit or execution veto was reduced.

## Ownership and application contract

| Responsibility | Existing/canonical owner and delegation |
| --- | --- |
| Application orchestration | `CanonicalMarketPipelineV2`; holds references, no separate market ledger |
| OHLC state | Published `LiveCandleStore`; `ingest` serializes closed-candle append and derived analysis |
| Explicit L1 quote | `RuntimeQuoteAuthorityV2`, shared with `RuntimeAdmissionV2` |
| Quote freshness/spread | Existing `RuntimeSpreadAuthorityV2` and `SpreadAuthorityV2` |
| Operational position price | Existing dedicated price API -> `PriceFeedServiceV2` -> canonical lifecycle monitor |
| Intelligence | `LiveMarketAnalysisService`, existing stages and configured v2 delegates |
| Candidate | `SignalGeneratorV2` signal dictionary, enriched with provenance and current account context |
| Execution permission | Existing `TradeLifecycleServiceV2.submit_signal` and Phase 1 admission/risk/account guards |

Authenticated `POST /market/webhook` accepts the existing candle payload and
returns stored/duplicate status, count and trend. At 50 candles it evaluates the
real pipeline and returns `analysis`. A duplicate does not rerun analysis or
append signal history. Conflicting values at an existing timestamp and late
unseen candles return 409. Future, naive, nonfinite or invalid price/volume
inputs reject before storage. Historical ordered candles may warm indicators;
they cannot manufacture bid/ask or update current position-price monitoring.
OHLC input represents closed candles; mutable intrabar corrections are not this
contract. The existing replacing `add` API remains for isolated replay and
compatibility callers.

The existing administrative `POST /market/analyze` evaluates the same published
store. The legacy request schema is retained, but canonical account balance,
risk percentage, instrument point value and configured reward/risk policy come
from the actual account/runtime owners. Caller fields cannot override them.
Both commands are candidate-only in the coordinated application. The legacy
compatibility composition and its disconnected-position containment remain.

Quote input remains independent through authenticated `POST /market/quote`.
The existing authority rejects backward timestamps before overwriting its
snapshot; the route now reports that validation failure as HTTP 400. No
parallel freshness implementation or synthetic spread is introduced.

## Intelligence graph and candidate contract

```text
authenticated OHLC -> published LiveCandleStore
  -> BacktestMarketStage (read snapshot, isolated calculation context)
  -> IndicatorStage: EMA50 / RSI14 / ATR14
  -> SmartMoneyStage: structure / BOS / CHOCH / liquidity
  -> IntelligenceStage -> existing risk/decision stages
  -> SmartMoneyEngineV2: structure / FVG / order block / price zone
  -> ConfluenceEngineV2 -> ProbabilityEngineV2
  -> ExecutionDecisionEngineV2 / multi-timeframe / market context / council
  -> TradePlannerV2 -> TradeValidatorV2 -> SignalGeneratorV2
  -> account-bound admission_request
  -> separate explicit POST /v2/trades/submit
  -> existing Phase 1 runtime admission -> PAPER execution only if admitted
```

The pipeline calculates from the actual stored candles. Multi-timeframe trend
analysis reads that same store through the existing `TrendEngineV2`; it has no
separate manually populated indicator state. FVG is already active in the
existing smart-money/confluence stack. Named Asia/London/New York overlays and
session-high/low research remain deferred as in V9. Exchange hours and economic
news remain mandatory through the configured existing authorities, resolved
again at evaluation time; runtime admission independently rechecks current
permission when submission is requested.

The existing signal dictionary contains `approved`, `status`, `decision`,
`symbol`, `timeframe`, `direction`, `entry_price`, `stop_loss`, `take_profit`,
`contracts`, `probability`, `confluence_score`, `grade`, `warnings`,
`blocking_reasons` and `summary`. V10 adds `generated_at`, source label, a
`source_hash` of the primary consumed OHLC window, stable `submission_id`, and
the existing account/profile/runtime-generation identity fields. The detailed
analysis retains indicator, structure, multi-timeframe and reasoning results.
The source hash is provenance, not a signature or a strategy certification.

`admission_request` has exactly the existing HTTP submission schema:
`signal`, `order_type`, `risk_context`. It can be submitted unchanged. Candidate
approval expresses the existing strategy/validator result; it is neither risk
permission nor an execution receipt. Generation cannot prepare an executable
order, submit to the broker simulator, fill, settle journal entries or mutate
positions/PnL. The explicit submission command owns those decisions and effects.

## Behavioral acceptance

Tests use the real coordinated account application. All candles and quotes enter
through HTTP. The deterministic qualifying case supplies 50 candles on each of
the configured 1m/5m/15m/1h timeframes, a current explicit quote and dated
test-certified hours/news JSON files through the existing configuration paths.
Only time is fixed; indicator state, intelligence owners, approvals, candidates
and fills are not injected. These are explicit synthetic test market inputs,
not live vendor data or real economic-calendar evidence.

The sequence yields a 94.12 confluence score and an A+ READY candidate with
unchanged configured policies. Execution tripwires verify that generating it
never calls submission/preparation/broker/fill/financial mutators. Its returned
request then passes the real admission path and creates exactly one PAPER fill
and position. Immediate resubmission cannot create another fill. Existing
lifecycle idempotency and durability contracts remain unchanged.

Further acceptance covers flat no-trade input even with valid permission,
missing quotes/calendar/news, explicit closed-session and high-impact-news
vetoes, expired quotes after READY generation, changed account risk context,
retired A/B/A generations, invalid candles, conflicting/late observations,
concurrent duplicates, repeated analysis with adversarial caller risk fields,
and backward quote rejection. Rejection compares complete economic snapshots,
broker fills and execution tripwires, not only response booleans.

The V9 and Phase 1 route characterizations are updated from expected 503 to
canonical storage/insufficient-candle behavior while retaining their financial
non-mutation assertions. The Phase 1 manifests refresh only reviewed source
evidence and the changed route dispositions; ownership, authorization and
runtime risk contracts are preserved.

## Capability result and limitations

V10 closes MVP-005/006/007/008 for the controlled application-input boundary:
18 of 24 mandatory capability groups are now certified, or **75%**. Across all
30 reviewed groups, two require integration/proof, four remain partial and six
are post-MVP. **P0=0, P1=5, P2=1.** This is scoped capability evidence, not an
effort estimate or a complete product acceptance claim.

Sustained source provisioning, operator calendar/news maintenance and a complete
public-input/browser/restart smoke remain in operational acceptance. Browser
HTTP/WebSocket authorization and mandatory dashboard views remain unconnected.
Research dataset/strategy validation provenance is still partial; this package
does not certify arbitrary historical strategies. No paid provider or external
credential is required for the demonstrated controlled PAPER input boundary.

Next package: **PHASE2_AUTHORIZED_PAPER_DASHBOARD**, followed by
**PHASE2_PAPER_MVP_OPERATIONAL_ACCEPTANCE**. LIVE execution remains disabled.

## Verification

- V9 baseline reproduction: 6 passed; new pre-patch V10 ingestion tests: 2 RED
  on the verified legacy 503 boundary.
- V10 acceptance: 19 passed, including concurrent ingestion and actual generated
  candidate PAPER handoff.
- Direct regressions: 251 modules, **2,327 passed / 0 failed / 1 unchanged skip**.
- Additional trend regressions: 3 modules, **57 passed / 0 failed**.
- Full backend: **5,533 passed / 0 failed / 1 unchanged skip**, 142.44 seconds.
- The unchanged skip is the unregistered compatibility `/api/v2/trades/submit`
  case in `test_phase1_risk_authority_integration_v2.py`; canonical submission is
  exercised directly. Two pytest import-rewrite warnings remain environmental.
- All seven changed/new Python files compile; `git diff --check` passes.

The first direct run had two failures from historical Phase 1 tests expecting
503; 2,325 passed and one skipped. Updating those two behavior expectations
retained storage-call and zero-execution tripwires. The same 251 modules then
passed. During focused test development, the HTTP envelope was corrected to
match SubmitTradeRequestV2 (no order_context field), the fixed clock retained
datetime type compatibility, and assertions used the actual EMA projection and
execution-spy scope. None required weakening production validation.

The manifest contains every direct module and the exact full-suite invocation.
All runs set the existing isolated test POLICY then use pytest with
`-q -p no:cacheprovider --tb=short --show-capture=no`. Full selection is
`backend/tests`; the staged certification selection is the nine modules in
`v10_test_execution.staged_certification_modules`. Temporary-directory access
is required by the Windows test environment. Per-test outcomes and hashes are
recorded under `C:/Users/THECRA~1/AppData/Local/Temp/arms-v10-gc5t70ah/`.
No frontend code changed; this package does not claim new frontend verification.

## Exact scope and justification

| File | Purpose |
| --- | --- |
| `backend/api/routers/market.py` | Delegate coordinated ingestion/analysis to existing-owner orchestration; report quote validation as 400 |
| `backend/services/canonical_market_pipeline_v2.py` | Candidate-only orchestration, authoritative account parameters, provenance and compatible admission request |
| `backend/services/live_candle_store.py` | Serialized idempotent closed-candle ingestion and conflict/order/input validation |
| `backend/services/live_market_analysis_service.py` | Non-executing candidate mode, canonical position reads, computed EMA alignment and explicit missing-quote veto |
| `backend/tests/test_market_to_candidate_v10.py` | Nineteen real-owner application acceptance cases |
| `backend/tests/test_phase1_api_route_account_scope_contract_v2.py` | Replace obsolete 503 expectations while retaining zero-execution assertions |
| `backend/tests/test_phase2_mvp_acceptance_v9.py` | Update repaired boundary evidence; preserve V9 safety and inventory checks |
| `backend/tests/phase1_api_route_inventory_v2.json` | Reviewed source evidence for three changed market handlers |
| `backend/tests/phase1_market_route_inventory_v4.json` | Current canonical market owner/availability dispositions |
| `backend/tests/phase1_risk_authority_inventory_v5.json` | Updated analysis source evidence and delegation description |
| `backend/tests/phase1_financial_inventory_v6.json` | Updated analysis source evidence and candidate-only financial boundary |
| `backend/tests/phase1_runtime_execution_inventory_v7.json` | Updated handler/analysis execution evidence and explicit handoff description |
| `backend/tests/phase2_mvp_capability_inventory_v9.json` | Preserve V9 history; record V10 closure, transitions, source classes, certificate and tests |
| `docs/architecture/phase2_market_to_candidate_v10.md` | This root-cause/behavior/certification report |
| `docs/master/ARMS_AI_MASTER_MEMORY.md` | Current V10 status and remaining limitations |
| `docs/master/ARMS_AI_MASTER_ROADMAP.md` | Evidence-based next package sequence |
| `docs/master/ARMS_AI_REQUIREMENTS_MATRIX.md` | Current mandatory capability closure/counts |
| `docs/master/ARMS_AI_DECISION_LOG.md` | DEC-0021 records the authorized integration decision |

All 83 baseline unrelated untracked files were preserved by SHA-256 comparison.
Only the exact 18 package paths may be staged. Staged checks and certification,
fresh remote-baseline verification, exact-parent/scope commit checks and normal
push parity are required delivery gates; final delivery evidence is saved in
the same temporary evidence directory without adding unrelated repository files.
