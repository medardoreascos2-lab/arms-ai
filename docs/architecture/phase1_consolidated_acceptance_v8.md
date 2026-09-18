# Phase 1 consolidated acceptance V8 — historical RED evidence

This document preserves the V8 baseline findings. Subsequent repair and current
acceptance are recorded in [V8.1 admission certification](phase1_runtime_market_risk_admission_v81.md).
The historical RED results below are not the current implementation status.

Package: `PHASE1_CONSOLIDATED_ACCEPTANCE`.
Baseline: `d40745fa0bc1a481ef2d171753e392890b9109e0` on
`refactor/backend-architecture`; synchronized with origin before edits.
This is a negative acceptance certificate and an uncommitted audit artifact.
It does **not** authorize Phase 2, PAPER MVP approval, or LIVE execution.

## Result and root cause

Phase 1 remains **OPEN**. The baseline suite passes, but new behavioral evidence
shows a production admission gap: both authenticated `POST /v2/trades/submit`
and direct submission to the published account lifecycle prepare an order, call
the PAPER broker once, and add a fill when no quote is available, market hours
are denied, and the economic-news authority reports blocked.

The reproducer uses the real coordinated application, canonical account/profile,
valid risk context, real lifecycle and PAPER adapter, with isolated test account
namespaces. The broker spy wraps the real implementation; it does not manufacture
a fill. No real broker is connected. Both tests assert **zero** preparation,
broker calls and fills, and deliberately remain failing. They are not skipped,
xfail-marked, or changed to accept the unsafe behavior.

Verified causes:

1. `backend/api/trade_lifecycle_api_v2.py:create_trade_lifecycle_router_v2`
   passes signal, order type and risk context directly to the lifecycle. It does
   not consult the app's quote, calendar or news authorities.
2. `backend/services/trade_lifecycle_service_v2.py:TradeLifecycleServiceV2.submit_signal`
   does not require those authorities. When an order validator is configured it
   accepts `order_context.market_is_open`; that caller boolean is not certified
   quote/news authorization. Account admission and existing financial risk checks
   do not provide the missing market admission.
3. `backend/services/runtime_context_v2.py:build_runtime_context` supplies the
   core risk manager and execution gate, but not the optional exposure manager,
   portfolio risk engine or order validation engine. `backend/api/app.py:create_app`
   attaches those three only when it builds the context itself. The coordinated
   application injects its existing lifecycle and skips that branch.
4. `LiveMarketAnalysisService` has upstream market/calendar/news constraints;
   reaching the lifecycle directly avoids them. The coordinated legacy market
   routes fail closed on incompatible legacy position ownership; their 503
   behavior is safe but is not positive proof of a working validated-market path.

The V7 core identity repair remains valid. Its green call-order tests did not
certify mandatory market admission, and its statement that API guards remain
attached applies to standalone construction. V5 correctly mapped upstream
constraints but did not prove they were unavoidable at every submission entry.
This V8 evidence limits any broader interpretation of those prior certificates.

## Scope stop

No production patch was made. V8 section H requires stopping before a large
cross-module redesign not already supported by the architecture. A route-only
check leaves the demonstrated direct-runtime bypass. Merely attaching the
optional order validator leaves quote/news certification absent and makes the
current API request contract incomplete. A complete repair needs one mandatory
operational admission contract shared by runtime construction, lifecycle, API
and analysis callers, with an explicit boundary for isolated historical replay.
It must bind market evidence to the current account generation and precede order
preparation. That is the exact remaining package, not authorization to rewrite
execution or weaken tests. Canonical financial/execution owners are known; the
missing integration is not an excuse to introduce a second ledger or broker.

## Authoritative inventory

The requirements matrix contains **12** Phase 1 requirements. All twelve are
listed in the companion JSON with their exact authoritative titles, source,
implementation/test/certification status, remaining gap, blocker and evidence.
The classifications here are V8 acceptance classifications, separate from the
historical closure-wave labels in older documentation.

- CLOSED_CERTIFIED: 8, within the documented PAPER and requirement scope.
- PARTIAL_REAL_GAP: 3.
- BLOCKED: 1 (PH1-REQ-002 requires the integration package described above).
- DOCUMENTATION_ONLY_GAP: 0.
- UNCLASSIFIED: 0.

A scoped CLOSED_CERTIFIED ownership, isolation or documentation requirement does
not claim the application-wide trading path is safe to release.

| Requirement | V8 classification | Remaining gap |
| --- | --- | --- |
| PH1-REQ-001 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-002 | BLOCKED | Authenticated HTTP and direct lifecycle submissions accept and fill without a quote or certified market/news permission. No universally enforced validated-market-to-PAPER path. |
| PH1-REQ-003 | PARTIAL_REAL_GAP | Core owner identity is unified, but coordinated/injected factory lifecycle omits optional order, exposure and portfolio-risk guards attached by standalone API composition. |
| PH1-REQ-004 | PARTIAL_REAL_GAP | Account loss/drawdown guards pass existing tests; freshness/calendar/news constraints are upstream and bypassed by direct/API submit; optional guards vary by composition. |
| PH1-REQ-005 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-006 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-007 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-008 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-009 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-010 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |
| PH1-REQ-011 | PARTIAL_REAL_GAP | New cross-contract rejection tests fail; prior successful order tests intentionally bypass unavailable market providers. Full acceptance cannot be certified. |
| PH1-REQ-012 | CLOSED_CERTIFIED | NONE within the documented PAPER scope |

PH1-REQ-001 certifies the repository-derived graph, including the missing edge;
PH1-REQ-009 certifies exhaustive route/authorization/account-scope classification,
including the execution-capable route implicated above. Neither substitutes for
PH1-REQ-002/004 behavioral admission. PH1-REQ-011 remains partial because executable
coverage now exposes a failing safety contract, not because failures were hidden.

## Integrated path

```text
request / direct signal
  -> published account + generation validation                         GREEN
  -X mandatory quote / certified calendar / news authorization         RED
  -> configured risk checks (optional guard composition differs)       RED
  -> canonical lifecycle -> prepare -> PAPER adapter -> simulator
  -> fill -> position/protection/OCO -> portfolio -> account/PnL        GREEN*
  -> journal/history -> API/dashboard                                 GREEN*
  -> durable checkpoint -> validated recovery without reapplication    GREEN*
```

`GREEN*` certifies state ownership/synchronization after an admitted operation;
it does not repair the admission gap. Existing rejection, duplicate, partial
close, rollback, recovery and read-only tests remain part of the consolidated
selection. No production code changed, so those tests are revalidation rather
than evidence of a new implementation fix.

| Integrated contract | Result and scope |
| --- | --- |
| Runtime ownership | GREEN: same canonical operational core per publication |
| Execution ownership | RED: validation/guard composition varies by entry point |
| Order lifecycle | GREEN: existing PAPER submit/fill/close/protection semantics; no claim for unsupported LIVE or external partial-entry-fill ingestion |
| Risk authority | RED: required market/news/freshness permission can be bypassed |
| Financial state / fill synchronization | GREEN: canonical ownership, replay prevention, rollback and recovery |
| Account isolation | GREEN: explicit PAPER account identity, generation, namespace and publication containment |
| Market ownership | GREEN: registered market endpoints use reviewed authorities or explicit unavailable/demo responses |
| Market availability | RED: endpoint freshness tests pass, but submission does not require availability |
| API ownership / authorization | GREEN: complete classification and admin enforcement; admin authentication is not market authorization |
| WebSocket authorization | GREEN: canonical authorization before accept and no execution side effects |
| Startup / pending reconciliation / durability | GREEN: existing lifecycle, validated reconstruction and fail-closed failures |
| CLI/runtime equivalence | GREEN for core ownership/startup/recovery, as in V3/V7; not certified-market trading equivalence |

`NO_API_EXECUTION_BYPASS` and `NO_RISK_BYPASS` are **not satisfied**.
The existing dashboard/intelligence read-side no-execution, financial no-double-
application, account isolation and recovery no-reapplication evidence passes
within its stated scope. The certificate does not generalize read-side tests
into permission for direct signal execution.

## PH1-REQ-007 account-state inventory

The companion JSON inventories **101 direct `app.state` bindings** and **21
logical account-owner domains**, including nested durable owners. Each row names
identity and generation sources, cross-account read/mutation behavior, switch,
recovery and stale-reference behavior. The new executable test compares the
inventory with every direct app-state assignment in `create_app`, switches a
real coordinated account A to B, and checks every mutable binding is replaced.
The shared coordinator is an explicit control-plane exception; immutable policy
values may match. Two nested lifecycle publisher assignments are covered by the
lifecycle/event graph, not mistaken for top-level app-state attributes.

Common account identity is the catalog's opaque account ID plus selected profile.
Common runtime generation is the published bundle and shared durable admission
generation. Fresh construction prevents auxiliary state from being inherited;
financial and execution mutations additionally pass the publication/durability
barrier. Old Python references can still read their own retired account data;
that is not permission to read or mutate B. The ASGI publication wrapper and
WebSocket generation checks prevent old API/socket consumers projecting B.

| Domain | Canonical owner / layer | Switch and recovery behavior |
| --- | --- | --- |
| runtime | `RuntimeContextV2` | Immutable bundle replaced on switch; recovered before publication |
| runtime_generation | `PublishedAccountRuntimeV2 / DurableExecutionStateV2` | Catalog generation plus admission epoch; old generation retires |
| account_balance_equity_pnl_drawdown | `AccountStateManagerV2` | Account namespace snapshot reconstructed and semantically reconciled |
| portfolio_positions_exposure | `PortfolioManagerV2` | One account-linked portfolio; financial snapshot restore |
| positions | `TradeLifecycleServiceV2 / PositionManagerV2` | Active position map and position manager restored through one store |
| orders_fills | `PaperBrokerConnectorV2 / PaperExecutionEngineV2` | Broker evidence restored without order resubmission |
| risk_limits_sizing_blocks | `RiskManagerV2 / ExecutionRiskGateV1 / AccountSwitchSafetyV2` | Profile-bound limits, canonical balance/PnL; GAP: optional exposure/order/portfolio guards and market admission not universally wired |
| risk_event_history | `RiskEventLoggerV1 / RiskEventStoreV2` | Per-account risk-events.json; switch and restart preserve correct account |
| journal | `TradeJournalV2` | Canonical account journal restored and projected; no cross-account history |
| closed_history | `TradeHistoryManagerV2` | Canonical closed-trade history restored once |
| protective_orders | `ProtectiveOrderRegistryV2` | Lifecycle/store share registry; active protection blocks account switch |
| oco | `OCOManagerV2` | Lifecycle/store share groups; active groups block switch |
| pending_execution_idempotency | `TradeLifecycleServiceV2 / DurableExecutionStateV2` | Pending mutation blocks switch; account identity/semantic checks precede reconciliation |
| recovery_state | `ExecutionStateStoreV2 / StateRecoveryServiceV2` | Account path and identity verified before operational reconstruction; no successful recovery label on invalid state |
| startup_shutdown_readiness | `StartupCoordinatorV2 / RuntimeLifecycleManagerV2 / GracefulShutdownServiceV2` | Publication requires readiness; failed/uncertain runtime cannot admit |
| strategy_learning_analysis_jobs | `Per-application strategy, learning, analysis stores and backtest job owners` | Fresh objects on switch; volatile auxiliary analysis/jobs intentionally not recovered as trading ledger |
| events_dashboard | `Per-application dashboard event bus, providers, widgets and dispatcher` | New bus and providers project only new graph; old object can read old account but not new account |
| websocket_projection | `DashboardWebSocketHubV2 / AccountRuntimeApplicationV2` | New hub per app; old socket closes 1012 on publication; unavailable socket closes 1013 |
| api_scope | `AccountRuntimeApplicationV2 / registered route factories` | Request binds one bundle; in-flight request excludes switch; failures reject before handler |
| market_account_cache | `RuntimeQuoteAuthorityV2 / spread / candle / signal / analysis stores` | Fresh app market caches on switch; no previous-account auxiliary cache transfer; quote authority not mandatory at submit (OPEN) |
| credentials_configuration | `AccountConfigManagerV2.for_runtime / process AdminAuthorizationV2` | Profile-bound PAPER config; process admin/webhook policy intentionally global; no LIVE/broker secrets certified |

Account-specific broker credentials are not present in this PAPER runtime.
Process admin/webhook authorization policy is intentionally shared, not a copied
account secret. This audit did not read or change real credentials and does not
certify a future LIVE credential-isolation implementation. CLI/legacy compatibility
runtimes do not provide a second live account selector: cross-account transition
belongs to the coordinator, and old compatibility boundaries reject unsupported
transitions. Isolated replay/simulation state is classified separately.

Executable evidence covers:

- A-to-B-to-A financial/PnL, position, journal/history and risk-event isolation;
  distinct account IDs even when profiles are identical; correct namespaced
  reconstruction after restart; wrong/missing identity and legacy-global snapshot
  rejection (`test_account_runtime_transition_v2.py`).
- Open positions, protective/OCO activity and pending operations block switching;
  precommit failure preserves A; postcommit uncertainty fails closed; old lifecycle,
  execution manager, PAPER engine, broker and persistence references cannot execute
  (`test_phase1_account_switch_full_containment_v2.py` and transition tests).
- Every registered account route binds the new publication; switching/failed
  HTTP returns 409; authorized account reads cannot trade; journal/jobs/analysis
  do not leak (`test_phase1_api_route_account_scope_contract_v2.py`).
- Real WebSockets retire with 1012, a new socket receives only B's projection,
  unavailable states reject before dispatch, and old hub connections drain
  (`test_phase1_websocket_account_isolation_characterization_v2.py`).
- All 101 application bindings are inventoried and rebound, including auxiliary
  strategy, market, dashboard and job state (new V8 test). Object isolation is
  structural evidence; the behavioral tests above establish economic containment.

## Compatibility and documentation baseline

The consolidated compatibility/supersession register is the union of reviewed,
source-fingerprinted V7 construction/execution, V5 risk, V6 financial and V4 market
inventories. V7 records 18 construction and 105 execution boundaries; V5 records
134 risk points; V6 records 135 financial points. Their classifications preserve
canonical operational owners, explicit layered delegates, isolated backtests,
legacy/simulation helpers, observational matches and justified non-runtime uses.
V2 records all registered routes and their state/closure owners. Each retained
path remains in the selection; classification does not authorize deletion.

Specific retained distinctions: `ExecutionPipelineV2` and V1 position helpers
remain compatibility modules; dashboard `ExecutionServiceV2 -> ExecutionEngineV2`
returns ephemeral results rather than broker fills; historical backtest factories
own isolated PAPER replay; recovery validation clones are temporary, not a second
published runtime. V8 adds the unresolved mandatory-admission conflict above to
this register instead of relabeling it green.

Canonical supporting documents:

- `phase1_api_route_account_scope_v2.md`: route and account-scope baseline.
- `phase1_recovery_cli_baseline_closure_v3.md`: recovery/CLI attribution and closure.
- `phase1_market_ownership_availability_v4.md`: endpoint ownership/availability.
- `phase1_risk_authority_precedence_v5.md`: risk inventory and precedence.
- `phase1_financial_state_fill_sync_v6.md`: financial ownership/idempotence.
- `phase1_runtime_execution_ownership_v7.md`: runtime/execution call graph.
- This V8 certificate and JSON: current integrated status and remaining blocker.

## Tests and failure attribution

| Run | Passed | Failed | Skipped | Result |
| --- | ---: | ---: | ---: | --- |
| Baseline full backend before new tests | 5,454 | 0 | 1 | GREEN; 134.76 seconds |
| Final new V8 test module | 1 | 2 | 0 | Account binding passes; HTTP/direct admission fail |
| Consolidated selection: 430 explicit test modules | 3,735 | 2 | 1 | RED; 184.91 seconds |
| Full backend: `backend/tests` | 5,455 | 2 | 1 | RED; 134.16 seconds |

Only these two node IDs fail in both consolidated and full runs:

- `backend/tests/test_phase1_consolidated_acceptance_v8.py::test_submission_without_market_authority_cannot_reach_paper[http]`
- `backend/tests/test_phase1_consolidated_acceptance_v8.py::test_submission_without_market_authority_cannot_reach_paper[direct]`

Each reports `accepted=True`, `prepared_order=True`, `broker_calls=1`,
`fills_changed=True`; required values are false/false/zero/false. These are
pre-existing production defects exposed by new coverage, not new production
regressions or acceptable baseline exclusions. All existing tests retain their
baseline outcomes. The 5,455 passes include the new 101-binding account test.

Exact pytest arguments are `-q -p no:cacheprovider --tb=short`, followed by the
JSON's `direct_test_modules` for consolidated acceptance, or `backend/tests` for
the full run. A pytest report hook records per-node outcomes without changing
selection or execution. Policy is installed from
`backend.tests.test_account_switch_safety_containment_v2.POLICY` before pytest.
The final direct module run uses the same arguments and its single file path.

`python -m py_compile backend/tests/test_phase1_consolidated_acceptance_v8.py`,
`git diff --check`, and `git diff --cached --check` pass (index is empty). New
artifact whitespace/schema/path checks and final scope review pass. The fresh
fetch still resolves local and remote to the recorded baseline, ahead/behind 0/0.
All 83 unrelated untracked files match their initial SHA-256 hashes. No file is
staged and no commit/push was attempted.

Machine results and log SHA-256 hashes are preserved in the companion JSON.
Raw runner, logs and per-node evidence are under
`C:/Users/THECRA~1/AppData/Local/Temp/arms-phase1-v8-f1xo_nx0/`.


The initial broad binding test mistakenly treated two nested lifecycle publisher
attributes as direct app-state attributes. Its AST selection was corrected to
match exactly `app.state`, with no production change. Its final result is separate
from the two demonstrated production safety failures. Existing warnings are
pytest import-rewrite notices and the installed TestClient transport deprecation;
they are not hidden failures. The existing skip is the unregistered
`/api/v2/trades/submit` alias, not the registered `/v2/trades/submit` reproducer.

The JSON stores the exact 430-module selection and every final failure node ID.
Tests use the repository's explicit test POLICY before importing the app, with
isolated temporary PAPER configuration/namespaces. No production defaults,
credentials or LIVE settings were changed to obtain results.

## Diff, preservation and next package

Changes are limited to the new behavioral test, requirement/account inventory,
this negative certificate, and current-status pointers in the requirements
matrix, roadmap, memory and decision log. No production implementation changed.
The authoritative matrix retains exact requirement text and acceptance criteria;
V8 statuses replace stale Phase 1 closure-wave status interpretation. Historical
counts remain labeled historical.

The package is not eligible for staging, commit or push: full acceptance is red
and no self-contained production fix was certified. All 83 pre-existing untracked
files must remain byte-identical. Final preservation/parity checks are recorded
with the final test results.

Next package: **PHASE1_RUNTIME_MARKET_RISK_ADMISSION_INTEGRATION**. Establish the
shared mandatory operational admission contract; converge optional guard wiring;
prove missing/stale/uncertified/blocked inputs cause zero prepare/broker/fill/
financial/protection/journal effects at HTTP, direct runtime and analysis paths;
prove a certified valid market request succeeds once; rerun financial, isolation,
recovery, consolidated and full backend gates. Preserve explicit historical replay
semantics and keep LIVE disabled. V8's scope stop does not authorize this redesign.
