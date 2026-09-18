# Phase 1 runtime market and risk admission — V8.1

Package: `PHASE1_RUNTIME_MARKET_RISK_ADMISSION`. Baseline:
`d40745fa0bc1a481ef2d171753e392890b9109e0`, branch
`refactor/backend-architecture`. LIVE execution remains disabled.

## Root cause and completed repair

The two original V8 rejection tests were reproduced individually before any
production change. Both observed `accepted=True`, `prepared_order=True`,
`broker_calls=1`, and `fills_changed=True` with no quote, unavailable certified
market hours, and blocked economic-news permission. The original V8 Python test
file is byte-identical to the supplied workspace version.

The operational lifecycle did not require the application's market authorities.
Its caller-supplied market flag could not establish quote freshness or news
permission. Coordinated/injected construction also omitted exposure, portfolio
risk, and order validators installed by standalone API construction.

`TradeLifecycleServiceV2.submit_signal` now owns mandatory operational admission.
`bind_runtime_admission` composes the existing authorities once for the canonical
runtime and exposes the same instances to API/analysis callers. It preserves
explicitly injected guards and installs missing guards using the existing policy.
It adds no risk model, freshness policy, financial ledger, or alternate broker.

## Actual submission graph and delegation

```text
Authenticated POST /v2/trades/submit       Direct runtime lifecycle call
                    \                     /
              TradeLifecycleServiceV2.submit_signal
              shared durable account admission barrier
                 | AccountSwitchSafetyV2: identity, publication, generation,
                 | switching/failed state, retired runtime
                 | AccountStateManagerV2: canonical persistent trading block
                 | RuntimeQuoteAuthorityV2 + RuntimeSpreadAuthorityV2:
                 | quote availability, freshness, future timestamp rejection
                 | SpreadAuthorityV2 + existing API spread limit
                 | certified market-hours and economic-news lifecycle providers
                 | RiskManagerV2 + sizing + ExposureManagerV2
                 | PortfolioRiskEngineV2 + ExecutionRiskGateV1
                 | OrderValidationEngineV2, including explicit caller veto
                 | recheck account/market immediately before preparation
                 v
              execution scope -> ExecutionManagerV2.prepare_order
                 -> PaperBrokerConnectorV2.submit_order
                 -> PaperExecutionEngineV2.execute
                 -> existing fill/position/protection/OCO synchronization
                 -> portfolio/account/journal/events/durable checkpoint
```

`RuntimeAdmissionV2` holds composition and delegates validation; it is not a
second decision owner. Quote freshness is extracted from the existing spread
authority so spread reads and admission use the same check. Request prices,
timestamps, and positive market flags cannot substitute for runtime evidence.
Current quote midpoint supplies the existing price-sensitive execution gate.
Provider lookup follows the active certified lifecycle, including refresh.

Direct calls to account-bound preparation, broker submission, and PAPER execution
must carry the lifecycle's execution scope. A separate reproduced compatibility
gap allowed `ExecutionPipelineV2.execute` to add an unadmitted OPEN journal trade.
That facade now rejects use with the operational journal before any counter or
journal mutation. Its isolated simulation behavior remains available.

The production call-path review covers the V7 builder/execution inventory, V5
risk inventory, V6 financial inventory, registered trade/market/strategy routes,
analysis and dashboard facades, broker/simulator, startup and recovery. Legacy
market adapters retain explicit unavailable responses where incompatible;
observational dashboard execution services remain observational. Historical
backtest lifecycles use isolated ledgers and are explicitly outside operational
admission. No registered operational entry selects a replay bypass. Recovery
restores validated records without creating a new submission or requiring a
historical quote to be treated as current.

There is one admission owner and zero duplicate admission authorities. Reviewed
inventories now contain 19 construction boundaries, 109 execution boundaries,
140 risk decision points, and 135 financial mutation points, all classified.
Persistent block writers/clearers remain 7/4; financial ownership is unchanged.

## Behavioral evidence and fixture attribution

`test_runtime_admission_v81.py` verifies HTTP/direct equivalence for missing,
stale/future quotes, wide spreads, closed/unknown hours, blocked/out-of-coverage
news, projected daily-loss rejection, persistent account blocks, failed/switching
runtimes, missing admission/guards, foreign accounts, stale/invalid generations,
exposure and portfolio vetoes, invalid orders, explicit negative/ambiguous caller
flags, and a quote expiring during risk evaluation. Rejections assert zero calls
to preparation/broker/simulator and unchanged captured financial state/fills.
Additional tests prove one valid PAPER fill and synchronized position/journal,
duplicate rejection, retired references, direct lower-level containment,
refresh revocation, empty market caches after A-to-B-to-A, and facade containment.

Positive integration fixtures now publish explicitly labeled test-certified
calendar/news snapshots and quotes through actual authorities before submitting.
No fixture installs blanket approval and the V8 missing-market fixture stays
empty. Contract-policy unit fixtures first prove that operational preparation
rejects a direct call, then exercise the same policy on an isolated preparer.
Dashboard read tests seed activity through a real admitted lifecycle submission.
Structural wiring tests and source fingerprints were updated for the relocated
shared composition; original behavioral assertions remain in place.

The first broad patch run had 71 fixture/source-inventory failures. A subsequent
consolidated run left three constructor-location assertions, which were corrected
to inspect shared composition. Full backend then identified one additional
constructor-location assertion in admission price safety; its module was repaired
and added to the complete consolidated selection. These failures were repaired, not
excluded. The facade reproducer failed before its repair. Existing pytest import
warnings and TestClient deprecation are unchanged. The single retained skip is
the unregistered `/api/v2/trades/submit` alias; the registered `/v2/trades/submit`
is tested by both unchanged V8 rejection tests and new positive/negative tests.

## Certification results

Focused certification: **187 passed, 0 failed**. Consolidated certification:
**3,803 passed, 0 failed, 1 unchanged skip** across 432 modules.
Full backend: **5,508 passed, 0 failed, 1 unchanged skip**.
All 37 changed/new Python files compile, and `git diff --check` passes.

**PHASE1_STATUS=CLOSED**: 12 CLOSED_CERTIFIED; zero partial, blocked,
documentation-only or unclassified requirements. All acceptance gates are green.

Final results are recorded in
`backend/tests/phase1_consolidated_acceptance_v8.json`. That manifest preserves
the historical V8 RED certificate and exact failure observations separately.
It lists every consolidated test module, all 12 requirement titles/statuses,
101 application state bindings, 21 account-owner domains, exact changed files,
test arguments, result counts, and log hashes.

The common invocation installs the repository's explicit test `POLICY` from
`test_account_switch_safety_containment_v2` and calls pytest with
`-q -p no:cacheprovider --tb=short`. Direct certification runs the V8.1 admission,
V8 consolidated, quote wiring, admission price safety, V5 risk, V6 financial and V7 runtime test modules.
Consolidated certification runs the manifest's 432 explicit modules; the full
backend gate runs `backend/tests`. Every changed/new Python file is compiled.

Raw individual RED, focused, intermediate, consolidated and full results are in
`C:/Users/THECRA~1/AppData/Local/Temp/arms-admission-v81-3e9_5nh2/`.
The staged delivery gate checks that index content equals the tested working files
and repeats direct admission and the complete consolidated selection.

## Scope and limits

The seven supplied V8 package files are retained, with historical findings
preserved and current documentation advanced only on green acceptance. All 83
unrelated untracked files are checked against their initial SHA-256 hashes.
Only explicit reviewed package paths are eligible for staging; no destructive
Git operation, credential change, dependency addition or real broker connection
is part of this work.

This certifies the defined Phase 1 operational PAPER architecture and safety
contracts. It does not authorize LIVE execution, external broker integration,
or a product release. Isolated simulations and historical evidence retain their
documented scope. The next planned phase after closure is Phase 2, Data and
Market Intelligence.

Remaining Phase 1 issues: **NONE within the documented PAPER scope**.
Next recommended action: **PHASE2 — Data and Market Intelligence**.
