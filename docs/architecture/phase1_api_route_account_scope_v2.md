# PH1-REQ-009 route inventory and account-scope certificate

Baseline: `93039c140b7db486d0adab36de383b77dae1b55d`.

Package status: **GREEN under the authorized baseline-debt exclusion.** The fresh
full backend run produced **5,281 passed, 12 failed, and one skipped**. Exactly
those 12 nodes were rerun in an untouched Git archive of the baseline and in the
current workspace, with identical node IDs, exception types, and exception
messages. The full run's failure signatures also match that baseline exactly.
No package regression was found. The user's follow-up explicitly permits package
certification and publication after proving this debt pre-existing; this is not
a claim that the full backend suite is green.

The final directly relevant gate passed **409 tests across 36 files**, including
the previous 335-test package, the new account-scope contracts, and affected
market/backtesting/authorization/router tests. The exact list is recorded under
`regression_gate.directly_related.files` in the manifest. All seven modified/new
Python files passed `py_compile`; `git diff --check` passed. All 83 unrelated
untracked files were preserved with matching SHA-256 hashes.

The reviewed manifest is
[`phase1_api_route_inventory_v2.json`](../../backend/tests/phase1_api_route_inventory_v2.json).
It inventories all 92 registrations produced by `create_app()`, including health,
FastAPI documentation, analytical POSTs, control operations, execution entry
points, and the dashboard WebSocket. GET+HEAD on a metadata route counts as one
registration. Aliases and distinct methods on the same path remain separate.
No route is inferred from an unregistered module or filename.

Each record identifies methods, path, endpoint, owning module, transport,
authorization, account scope, mutation category, service owner, account-switch
effect, and rationale. Live structural evidence includes dependency identity,
factory closure bindings, request-state fields, calls, and an AST digest of the
endpoint and its same-module helpers. A new, removed, duplicated, or changed
registration fails the manifest contract until reviewed. OpenAPI paths are
cross-checked against effective route paths.

| Classification | Registrations |
|---|---:|
| GLOBAL_OBSERVATIONAL | 32 |
| ACCOUNT_OBSERVATIONAL | 44 |
| ACCOUNT_MUTATION | 1 |
| CONTROL_PLANE_ADMIN | 9 |
| EXECUTION_BOUNDARY | 5 |
| WEBSOCKET_OBSERVATIONAL | 1 |
| OTHER_JUSTIFIED / unclassified | 0 |

There are 58 active-runtime routes and two explicit-account switch routes.
Fourteen routes require the existing administrative authority (including the
WebSocket); two market ingestion routes use the existing webhook credential.
The remaining 76 routes have a documented public/read-only rationale. The 77
observational routes include analytical POSTs: an HTTP POST does not itself
prove financial mutation.

## Authoritative boundaries

`AccountRuntimeApplicationV2` admits a request against one published application.
`AccountRuntimeCoordinatorV2` builds that application's services from the target
runtime and its account namespace. Account switching rejects concurrent active
HTTP consumers, validates the target account/profile pair, and publishes the
complete replacement application. Switching or failed runtime states reject
account HTTP requests with 409; WebSockets use the separately certified 1013
admission and 1012 retirement contracts.

Factory-bound service objects and request-state owners are checked for fresh
identity after publication. Canonical lifecycle, portfolio, account, and journal
bindings are checked against the new runtime. Every account-observational HTTP
route is exercised after switching through the published host with a generation
probe and mutation guards. Journal records survive A-to-B-to-A recovery without
leaking into B. A's market-analysis cache and backtest job ID cannot be read or
deleted through B. Volatile caches/jobs are rebuilt when returning to A; this
certificate does not claim their persistence.

The direct `create_app()` factory composes an application; coordinated hosting
and switching are owned by the ASGI runtime wrapper. This certificate does not
claim that independently retaining and serving an old inner application is a
supported account-switching entry point.

## Defects demonstrated and repaired

1. `POST /market/analyze` could enter `LiveMarketAnalysisService.analyze` without
   admin authorization, despite writing analysis/signal stores and being able to
   enter the lifecycle execution path. `POST /api/v2/backtesting/run` likewise
   invoked its mutable/report-writing orchestrator without authorization.
   Missing-token and wrong-token probes reached both owners and returned 200.
   Both route declarations now use `require_admin_authorization_v2`; valid
   credentials still reach their existing owners. No token authority was added.
2. Coordinated applications expose `PositionManagerV2`, while three legacy market
   routes require `PositionManager.get_open_position(symbol, timeframe)` and its
   legacy mutation interface. This previously raised an unhandled exception.
   The webhook had already appended a candle before discovering the mismatch.
   Incompatible composition now returns explicit 503
   `legacy_position_manager_unavailable`, and the webhook checks compatibility
   before the first candle write. Tests verify unchanged financial/account state,
   no mutation calls, and no partial candle write.

## Availability and evidence limits

`/market/analyze`, `/market/webhook`, and `/market/open-position` remain unavailable
in the coordinated V2 composition. Their tested contract here is fail-closed
rejection, not successful legacy execution or a new adapter. Integrating their
legacy position/timeframe interface with canonical lifecycle ownership requires
a separately scoped follow-up. Standard compatible factory compositions retain
their existing behavior, subject to the new admin requirement on analysis.

Several existing dashboard views use fixed demonstration inputs: trade setup,
execution simulator, confidence fusion, and V2 intelligence decision. Execution
approval and V3 intelligence decision combine demonstration inputs with current
account policy. Their classification certifies observational ownership and
account-policy binding, not real market-data provenance or production readiness.
Strategy-intelligence availability views continue to report missing/unverifiable
sources rather than fabricate performance.

Backtesting remains a separately authorized analytical/control surface. This
certificate establishes application/account ownership and authorization, not a
new filesystem sandbox for administrator-supplied report directories.

## Exact package scope review

All nine files are required by PH1-REQ-009:

| File | Required change / evidence |
|---|---|
| `backend/api/routers/backtesting_api_v2.py` | Adds the existing admin dependency before the mutable orchestrator call. Baseline probes with missing and wrong credentials return 200 and reach the owner; both must reject before dispatch. |
| `backend/api/routers/market.py` | Adds the same dependency before analysis/signal mutation; rejects the incompatible legacy position owner with a controlled 503; moves owner validation before candle insertion. Baseline probes reproduce both unauthorized owner dispatch and an actual candle insertion followed by RuntimeError. No replacement position owner is introduced. |
| `backend/tests/test_backtesting_api_v2.py` | Supplies canonical test authority to existing successful standalone-router tests; preserves their behavior assertions. |
| `backend/tests/test_backtesting_app_integration_v2.py` | Supplies isolated admin credentials to the existing application integration tests affected by the new dependency. |
| `backend/tests/test_live_market_analysis_router.py` | Supplies isolated admin credentials so existing analysis/validation assertions continue to exercise authorized requests. |
| `backend/tests/phase1_api_route_inventory_v2.py` | Extracts live registration, dependency, closure/state-owner, and source evidence for exhaustive comparison. Test-only code. |
| `backend/tests/phase1_api_route_inventory_v2.json` | Stores the reviewed route classifications, ownership rationale, certificate counts, exact test list, and baseline failure signatures. |
| `backend/tests/test_phase1_api_route_account_scope_contract_v2.py` | Adds exhaustive inventory, authorization-before-dispatch, account publication/isolation, observational side-effect, and incompatible-owner regression contracts. |
| `docs/architecture/phase1_api_route_account_scope_v2.md` | Records certificate boundaries, demonstrated defects, scope review, reproducible validation, and confirmed baseline debt. |

For the fresh production review, a second archive of the exact baseline received
only the new test helper/manifest/contracts and a temporary diagnostic test.
Production code stayed at the baseline. Four unauthorized-dispatch assertions
failed with 200 instead of 401, while both valid-credential controls passed.
Both incompatible-owner contracts raised RuntimeError instead of returning 503.
The separate diagnostic passed by observing exactly one candle insertion before
that exception. These probes justify every production modification independently
of the passing package gate; they are separate from the untouched baseline
checkout used for failure attribution.

## Reproducible validation

The focused contract can run without preconfigured environment variables:

```powershell
python -m pytest -q -p no:cacheprovider backend/tests/test_phase1_api_route_account_scope_contract_v2.py backend/tests/test_phase1_websocket_authorization_contract_v2.py backend/tests/test_phase1_websocket_account_isolation_characterization_v2.py
```

Its fixtures install the existing isolated PAPER policy and account configuration
before importing the application. Older backend modules import the application
at collection time; the broad regression command explicitly supplies the same
repository policy in the test process only:

```powershell
python -c "import os, sys, pytest; from backend.tests.test_account_switch_safety_containment_v2 import POLICY; os.environ.update(POLICY); sys.exit(pytest.main(sys.argv[1:]))" -q -p no:cacheprovider --tb=short backend/tests
```

Production settings validation, trading admission, PAPER/LIVE separation, and
broker selection are unchanged. LIVE execution is neither enabled nor certified.
This route certificate does not close the entire Phase 1 reliability program.

## Confirmed baseline debt

The attribution checkout was extracted with `git archive --format=tar` at the
exact baseline, without changing the working tree or index. Archive SHA-256:
`58cbc1cefff46ee760d2af3b286134eb378b91e60b8ca5a74fae37a84c2deeb1`.
The starting HEAD, unstaged binary diff, empty staged state, four untracked package
files, and hashes of all 83 unrelated untracked files were recorded before work.
Separate pytest processes used the same interpreter and existing test `POLICY`.
Each exact-node run returned **12 failed, zero passed**. A pytest report hook
captured node ID, phase, outcome, exception type, and exception message; comparison
required literal equality, without filename-based attribution or exception
normalization. The manifest stores all 12 records under
`regression_gate.baseline_reproduction.failures` for repeatable selection and
comparison. The earlier complete-three-file baseline run also yielded 36 passed
and these same 12 failures.

The same failures occur in the working repository and the untouched baseline:

| File | Tests / verified failure |
|---|---|
| `backend/tests/test_durable_crash_recovery_v2.py` | Eight failures: `test_corrupt_or_inflight_state_fails_closed` for pending, pending_open and pending_loss; `test_legacy_snapshot_with_missing_journal_is_not_invented`; `test_empty_legacy_snapshot_migrates_without_inventing_activity`; `test_exact_crash_window_matrix` for window_after_pending, pending_open and window_before_committed. Current reconciliation raises RuntimeError or safely resolves a pending window where these tests expect ValueError; legacy payload mutations fail checksum validation earlier than expected. |
| `backend/tests/test_main_runtime_integration.py` | Three failures: `test_main_starts_and_stops_runtime`, `test_main_stops_runtime_when_pipeline_fails`, and `test_main_does_not_shutdown_when_startup_fails`. Their FakeRuntimeContext lacks the startup_coordinator now called by main. |
| `backend/tests/test_phase1_recovery_characterization_v2.py` | `test_incompatible_recovery_is_rejected_and_execution_remains_blocked` indexes a recovery report that is None when early validation rejects the state. |

No recovery/CLI production or test file was edited to make this package green.
These failures remain open baseline debt, excluded only from this package's
publication gate by the explicit follow-up authorization. The next package should
reconcile these tests and fixtures with the previously shipped startup/recovery
contract, investigate each mismatch without weakening recovery safeguards, and
restore a green full-backend gate.
