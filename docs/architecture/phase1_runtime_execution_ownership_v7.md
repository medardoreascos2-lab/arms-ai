# PH1-REQ-001/002/003 runtime and execution ownership

Package: `PH1_REQ001_002_003_RUNTIME_EXECUTION_OWNERSHIP`.
Baseline: `f5be126fd781274741799dea8ff3609f9207f683` on
`refactor/backend-architecture`, verified synchronized before edits.
LIVE execution was neither enabled nor exercised.

## Completed and root cause

The compatibility `create_app()` path independently assembled the operational
account, portfolio, journal, risk manager, execution manager, PAPER simulator,
position manager and lifecycle. CLI and coordinated ASGI startup already used
`build_runtime_context`. The prepatch delegation/identity characterization failed
because standalone API creation called the canonical builder zero times; the
other seven initial ownership checks passed. This was a demonstrated duplicate
composition path, not a need to replace the existing execution architecture.

The API now delegates core composition to `build_runtime_context`, passing the
active account profile and existing PAPER fill/slippage settings. The factory
accepts the API settings object so its risk manager preserves the configured
maximum-open-position limit. Existing API exposure, portfolio-risk, order
validation, journal analytics and risk logging remain attached to the same
lifecycle. API sizing delegates contract resolution to the canonical execution
manager. Its account switch safety reuses the context's durability binding.

No broker, lifecycle, financial or recovery implementation was changed. Five
obsolete core-constructor imports were removed from the API module. Six existing
test modules were updated to assert the delegated ownership path rather than
require duplicate constructors/local variables or a missing runtime context.
Their policy-value assertions remain in place and custom runtime behavior is
also tested. No previous risk/financial inventory classification was changed.

## Construction inventory and scope

`backend/tests/phase1_runtime_execution_inventory_v7.json` records 18 reviewed
construction boundaries and 105 execution boundaries, with callers, ownership,
account/generation scope, created services, downstream effects and AST source
fingerprints. Its companion discovery helper scans production backend Python,
scripts and tools, including module entry points and enclosing route factories.
It includes explicitly reviewed recovery, admission, market and strategy methods
whose names do not use order terminology. Test builders/fakes are excluded.

Counts are boundary functions/module entry points, not constructor invocations.
They include compatibility delegates, isolated replay construction, a temporary
snapshot-validation clone and non-trading keyword matches so exclusions remain
visible. Lexical caller candidates are search evidence, not inferred dynamic
dispatch. Concrete composition, source inspection and behavioral tests establish
operational reachability. Source changes or new discovered boundaries fail the
inventory regression until reviewed.

| Intended runtime | Composition and publication owner | Execution and financial scope |
| --- | --- | --- |
| Account PAPER runtime | `build_runtime_context`; `AccountRuntimeCoordinatorV2` binds account namespace/generation, restores then publishes | One lifecycle, broker/simulator, risk, portfolio/account, journal/history and protection/OCO graph per generation |
| Compatibility API | `create_app` delegates to `build_runtime_context` | Same operational core; composition alone does not imply managed recovery/startup |
| Injected ASGI application | Retains supplied context, attaches canonical runtime lifespan | Startup/recovery/shutdown use that context's store and lifecycle |
| CLI | `backend.main.main` delegates to `build_runtime_context` | Canonical recovery graph; CLI analysis pipeline separately produces simulation reports |
| Historical backtest | `build_strategy_backtest_pipeline` / `build_lifecycle` | Isolated PAPER replay uses `TradeLifecycleServiceV2`; no shared operational portfolio/account/journal ledger |

Legacy V1 position helpers and `ExecutionPipelineV2` remain present. The latter
is not executed by registered dashboard reads. The dashboard's separate
`ExecutionServiceV2 -> ExecutionEngineV2` chain returns ephemeral plan/result
dictionaries, with no broker or financial mutation; its legacy `EXECUTED` label
does not establish a fill. Live analysis has old standalone simulator fallbacks,
but the production app supplies its canonical lifecycle and follows the lifecycle
submission branch. These retained simulation/compatibility components are not
additional operational account owners.

## Canonical call graph and identity

```text
ASGI coordinator / compatibility API / CLI
  -> build_runtime_context
  -> one account-bound RuntimeContextV2

Trade API / LiveMarketAnalysisService / configured backtest signal target
  -> TradeLifecycleServiceV2.submit_signal
  -> account and runtime admission, signal validation
  -> RiskManagerV2, configured exposure/portfolio/order guards
  -> ExecutionRiskGateV1
  -> ExecutionManagerV2.prepare_order
  -> PaperBrokerConnectorV2.submit_order
  -> PaperExecutionEngineV2.execute
  -> accepted FILLED response
  -> PositionManagerV2 + lifecycle active-position map
  -> ProtectiveOrderRegistryV2 + OCOManagerV2
  -> PortfolioManagerV2 -> AccountStateManagerV2
  -> TradeJournalV2 (open), TradeHistoryManagerV2 (close)

PriceFeedServiceV2 -> LivePositionMonitorV2
  -> TradeLifecycleServiceV2.update_position / replace_active_position
  -> PAPER broker close/partial/modify and canonical financial synchronization

RuntimeLifecycleManagerV2 -> StartupCoordinatorV2 -> StateRecoveryServiceV2
  -> pending reconciliation where applicable -> ExecutionStateStoreV2 restore
  -> the same lifecycle/account/portfolio/journal/protection graph
```

The trace regression observes actual successful PAPER calls in the order shown:
risk, execution guard, prepare, broker, simulator, position, protection, OCO,
portfolio, account and journal. Rejection tests forbid preparation, broker and
simulator calls. The previous V5/V6 suites additionally check financial surfaces,
protection/OCO, history, events, duplicate delivery and rollback.

Identity tests cover lifecycle dependencies, app-state services, market feed and
monitor, account/portfolio linkage, broker/simulator linkage, protection/OCO,
store/recovery/startup/shutdown linkage, and shared durability participants.
Coordinated account switches retain isolation, retire the old graph and publish
a higher generation. Old/failed/switching contexts cannot acquire permission
from a new runtime. PH1-REQ-009 route isolation and WebSocket checks are preserved.

## Order and economic state ownership

| Event/state | Authority and handoff |
| --- | --- |
| Order preparation | `ExecutionManagerV2`, invoked after lifecycle authorization |
| Submission, acceptance, rejection | Lifecycle orchestrates; PAPER adapter/simulator return protocol status and retain broker evidence |
| Unfilled accepted order | Adapter order record only; lifecycle does not book a filled position |
| Full fill | Lifecycle consumes `FILLED`, creates position/protection/OCO and synchronizes portfolio/account/journal once |
| Partial fill | No separate operational partial-entry-fill ingestion path is provided by the current PAPER simulator; this package does not invent or certify one |
| Cancel/modify | PAPER adapter owns protocol records; lifecycle uses modify for position/protection changes; no independent registered cancel route was introduced |
| Protection/OCO | Shared lifecycle registries, created after fill and updated/cancelled by lifecycle on exit |
| Partial close | Monitor requests lifecycle replacement; broker partial result, remaining quantity, portfolio/account and journal synchronize through existing owner |
| Full close | Lifecycle broker close plus portfolio/account, journal/history and protection/OCO completion |
| Recovery | Store reconstructs validated state; never resubmits or rebooks a restored economic event |

Broker order/fill evidence and lifecycle/portfolio/journal records describe one
transaction under shared durability. They are not independently competing
financial authorities. V6 replay guards and financial reconciliation remain
unchanged. No claim is made that unimplemented LIVE or partial-entry-fill
capabilities were exercised.

## Tests executed and failure attribution

Baseline V5/V6 regressions: **92 passed**. Initial full backend: **5,436 passed,
0 failed, 1 unchanged skip**. Initial new characterization: **1 failed, 7 passed**
(the API did not delegate composition). Focused postpatch ownership/runtime tests:
**27 passed**.

The first postpatch full run produced **10 failed, 5,434 passed, 1 skipped**.
Nine failures required constructors/variables that intentionally moved to the
canonical factory; one required `app.state.runtime_context_v2 is None`. Updating
those structural assertions preserved their policy contracts. A new test also
initially used a nonexistent public starting-balance attribute; it now checks
the account's published state. A draft daily-limit test incorrectly assumed an
environment variable configured `ArmsSettings`; that test now verifies the actual
profile-based authority. Neither test mistake justified production changes.

The final new suite has **18 passing tests**, including custom API settings,
successful execution ordering, five fail-closed conditions, source inventory,
broker entry restrictions, simulation isolation, account graph identity, actual
CLI/ASGI fresh and recovered factories, and real subprocess crash windows.
The latter leave PENDING evidence before operation entry and after a completed
fill, then reconstruct canonical services without broker resubmission.

The machine-readable manifest records the exact direct-test module list.
Tests run through `pytest.main(["-q", "-p", "no:cacheprovider", "--tb=short", ...])`
with the repository's existing process-local `POLICY` environment fixture loaded
before collection. No production configuration file or credential was changed.
The existing warnings are pytest import-rewrite/Starlette dependency warnings.
Final direct/full results and the pre-staging certificate follow below.

## Files changed and diff justification

- `backend/api/app.py`: replace duplicate core assembly with canonical delegation; retain API-specific guards/projections.
- `backend/services/runtime_context_v2.py`: accept explicit API settings for the existing maximum-open-position authority.
- `backend/tests/test_maximum_open_positions_policy_authority_v2.py`: follow API settings through the factory to risk.
- `backend/tests/test_paper_execution_fill_policy_authority_v2.py`: verify fill policy at factory delegation.
- `backend/tests/test_paper_execution_slippage_policy_authority_v2.py`: verify slippage policy at factory delegation.
- `backend/tests/test_point_value_policy_authority_v2.py`: inspect the moved position constructor in its canonical owner.
- `backend/tests/test_position_sizing_contract_limit_authority_v2.py`: follow canonical context limits/resolver and shared risk/execution constructor authority.
- `backend/tests/test_runtime_context_app_integration_v2.py`: require standalone app ownership identity instead of a missing context.
- `backend/tests/test_phase1_runtime_execution_ownership_v7.py`: 18 behavioral/inventory regressions.
- `backend/tests/phase1_runtime_execution_inventory_v7.py`: discovery contract and source evidence.
- `backend/tests/phase1_runtime_execution_inventory_v7.json`: reviewed construction/execution classifications and direct-test list.
- `docs/architecture/phase1_runtime_execution_ownership_v7.md`: root cause, ownership, test evidence, scope and certificate.

## Remaining issues and next recommended step

This certificate concerns the current operational PAPER graph and its identified
simulation boundaries. Legacy simulation modules remain intact. Static discovery
does not prove arbitrary dynamically injected implementations safe. Compatibility
API composition does not itself run managed startup; deployments requiring
recovery use the coordinated ASGI/CLI lifespan paths. LIVE and partial-entry-fill
features remain outside the verified capabilities.

Next: consolidated Phase-1 acceptance and remaining-gap review, including the
PH1-REQ-007 account/generation evidence alongside the V3-V7 certificates. This
package alone does not assert closure of every Phase-1 requirement.


## Pre-staging certificate

Direct certification: **3,617 passed, 0 failed, 1 unchanged skip** across 424 modules.
Full backend: **5,454 passed, 0 failed, 1 unchanged skip**. All 10 changed/new
Python files passed `python -m py_compile`; `git diff --check` passed.
All 83 unrelated untracked files matched their baseline SHA-256 hashes.

The unchanged skip is
`backend/tests/test_phase1_risk_authority_integration_v2.py::test_incomplete_trade_submission_fails_before_execution[/api/v2/trades/submit]`.

```text
TOTAL_RUNTIME_BUILDERS=18
CLASSIFIED_RUNTIME_BUILDERS=18
UNCLASSIFIED_RUNTIME_BUILDERS=0
UNSAFE_DUPLICATE_RUNTIME_BUILDERS=0
CANONICAL_RUNTIME_OWNER=backend.services.runtime_context_v2.build_runtime_context
CANONICAL_EXECUTION_OWNER=TradeLifecycleServiceV2
CANONICAL_ORDER_LIFECYCLE_OWNER=TradeLifecycleServiceV2
TOTAL_EXECUTION_DECISION_POINTS=105
CLASSIFIED_EXECUTION_DECISION_POINTS=105
UNCLASSIFIED_EXECUTION_DECISION_POINTS=0
DIRECT_BROKER_BYPASS=0
UNAUTHORIZED_EXECUTION_ENTRY=0
INTELLIGENCE_EXECUTION_BYPASS=0
STRATEGY_EXECUTION_BYPASS=0
LIVE_EXECUTION=NO
RUNTIME_SERVICE_GRAPH=GREEN
RISK_BEFORE_EXECUTION=GREEN
RISK_REJECTION_FAIL_CLOSED=GREEN
PAPER_FILL_TO_LIFECYCLE=GREEN
PAPER_FINANCIAL_SYNC=GREEN
EXECUTION_TO_FILL_OWNER=GREEN
FILL_TO_FINANCIAL_OWNER=GREEN
NO_DOUBLE_FINANCIAL_APPLICATION=GREEN
STARTUP_RUNTIME_EQUIVALENCE=GREEN
RECOVERED_RUNTIME_EQUIVALENCE=GREEN
PH1_REQ004_REGRESSION=GREEN
PH1_REQ005_006_REGRESSION=GREEN
PH1_REQ008_REGRESSION=GREEN
PH1_REQ009_REGRESSION=GREEN
MARKET_OWNERSHIP_REGRESSION=GREEN
RECOVERY_CLI_REGRESSION=GREEN
STALE_RUNTIME_EXECUTION=BLOCKED
CROSS_ACCOUNT_EXECUTION=BLOCKED
INITIAL_BACKEND_FAILURES=0
FINAL_BACKEND_FAILURES=0
DIRECT_TESTS=3617 passed, 0 failed, 1 unchanged skip; 424 modules
FULL_BACKEND=5454 passed, 0 failed, 1 unchanged skip
PY_COMPILE=10 passed
DIFF_CHECK=PASS
UNRELATED_UNTRACKED_PRESERVED=83
```

The exact 12-file scope above is the authorized staging set. The direct module
list is rerun after verifying index/worktree blob equivalence; commit and push
require its success and an unchanged remote baseline.
