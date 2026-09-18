# PH1-REQ-005/006 financial-state ownership and fill synchronization

Package: PH1_REQ005_006_FINANCIAL_STATE_FILL_SYNC
Baseline: `e57c032d09c3bd34558a43e0c80c59600b029b69` on
`refactor/backend-architecture`, freshly fetched with local/remote parity and a
clean tracked worktree. All 83 pre-existing untracked files were hashed.

Baseline V5 regression: 64 passed. Full baseline before production edits:
**5408 passed, 0 failed, 1 skipped** (125.27 seconds). The skip is the existing
unregistered `/api/v2/trades/submit` compatibility route.

## Ownership inventory

The accompanying `backend/tests/phase1_financial_inventory_v6.json` classifies
135 function-level financial mutation/delegation and reconciliation candidates
across 54 production files. It includes initialization, legacy, observational and
configuration candidates so discovery does not silently treat these as canonical
writers. Nested route/decorator functions are counted with their enclosing
function; generated model constructors are schemas, not independent owners.

Discovery scans every production Python function for financial instance-state
writes and financial mutation calls, plus reviewed local-variable, journal,
protection, recovery and calculation boundaries. Each point records exact AST
source evidence, inputs, output fields, writes, local calls, importing callers,
owner, classification, mutation flags, account scope, persistence, recovery
relevance and consumers. Flags include delegated writes. Static import edges are
not proof that every importing module invokes every method; behavioral call-order
and publication tests establish the operational wiring. Source/coverage tests
require review when any identified boundary changes.

Classification counts:

- `CANONICAL_FILL_OWNER`: 6
- `CANONICAL_JOURNAL_OWNER`: 4
- `CANONICAL_PNL_OWNER`: 11
- `CANONICAL_PORTFOLIO_OWNER`: 7
- `CANONICAL_POSITION_OWNER`: 7
- `EXECUTION_ADAPTER`: 21
- `LEGACY_OR_DUPLICATE`: 25
- `OBSERVATIONAL_PROJECTION`: 35
- `OTHER_JUSTIFIED`: 5
- `RECOVERY_REHYDRATION`: 14

## Canonical owners and direction of updates

| Domain | Canonical owner and responsibility |
| --- | --- |
| PAPER fills | PaperBrokerConnectorV2 owns order/fill and broker-position evidence. PaperExecutionEngineV2 calculates the simulated execution result. |
| Operational positions | TradeLifecycleServiceV2 owns the active-position registry and financial application. PositionManagerV2 builds/updates position values without a separate registry. |
| Portfolio | PortfolioManagerV2 owns synchronized open/closed portfolio records and aggregate balance/equity/PnL. |
| Realized trade PnL | TradeLifecycleServiceV2 applies PositionManagerV2 terminal-close calculations and RealizedPnLEngineV2 partial-close calculations. Neither helper keeps an independent ledger. |
| Unrealized PnL | PositionManagerV2 calculates the current position value; PortfolioManagerV2 aggregates the same current price, direction and remaining quantity. |
| Account PnL | AccountStateManagerV2 receives portfolio totals; it owns the daily baseline/adjustment evidence, drawdown and safety reasons. |
| Journal | TradeJournalV2 stores one lifecycle-linked record, updated cumulatively for partial realization and finalized on close. |
| Closed history | TradeHistoryManagerV2 records a completed position once using position-id deduplication. It is an audit/performance projection. |
| Protection/OCO | ProtectiveOrderRegistryV2 and OCOManagerV2 own linked protection metadata under the same lifecycle transaction. |
| Durability/recovery | ExecutionStateStoreV2 and DurableExecutionStateV2 capture/validate the whole participant set; StateRecoveryServiceV2 and PendingOperationReconciliationV2 restore/reconcile proven evidence. |

The canonical runtime has zero competing fill, operational-position or realized
PnL writers. Multiple helper methods and adapters delegate to these owners.
Legacy PositionManager/PositionLifecycleManagerV1/TradeExecutorV2, standalone
journal/history stores and simulation/learning state remain explicitly classified;
this package does not delete them or promote them to canonical runtime owners.

PaperBrokerConnectorV2.get_account exposes adapter identity/startup metadata; its
starting balance fields are not the operational financial ledger. Financial
views use PortfolioManagerV2/AccountStateManagerV2. API/dashboard/intelligence
components may request/delegate an operation or read a projection; they do not
book canonical PnL directly.

## Fill and synchronization contract

The measured opening call order is:

1. Existing account/runtime/risk/market admission and order preparation.
2. PAPER broker submit: create an order, unique entry fill and broker position.
3. Check the reported PAPER order/broker-position identity against existing active
   and closed financial evidence. A replay does not open another local position.
4. PositionManagerV2 builds one position using the actual filled price, including
   configured slippage; the lifecycle assigns it to the active registry.
5. Create linked protection and OCO records.
6. PortfolioManagerV2.add_position synchronizes AccountStateManagerV2.
7. TradeJournalV2 records `journal-<position_id>` once.
8. Publish observational events; validate and commit the enclosing durable state.

PAPER order IDs and broker-position IDs are retained in existing financial
records and recover with those records. Duplicate delivery is rejected by either
identity, before position/protection/portfolio/journal application, even when an
adapter omits its idempotent-replay flag. This uses existing account-scoped
history; it introduces no second identity registry or persistence format.

Request retry suppression, broker client-order idempotency and financial-fill
idempotency are different contracts. The lifecycle's existing request retry
window remains unchanged. A new request that actually produces a different
broker fill is not defined as replaying the same fill. Scale-in is explicitly
rejected while an operational position is already open, before preparation.
The current PAPER engine does not produce a series of partial entry fills or
weighted-average scale-ins; those capabilities are not invented or certified.

A partial close appends a uniquely identified `PARTIAL_CLOSE` fill, reduces
quantity, and applies cumulative realized PnL. Repeating the already-applied
position state does not append another partial fill or another journal row.
The monitor's calculation helpers delegate through replace_active_position;
intermediate updates are enclosed in the same durable operation.

Full close uses terminal broker-position evidence, rather than adding another
entry/partial-fill row. It closes protection/OCO, records completed history,
closes the portfolio record, synchronizes account state, finalizes the journal
and removes the active position. Repeated close is rejected before mutation.
Historical `quantity` is the last lot size used in the final close equation;
it is not active exposure. Active quantity and journal.remaining_quantity become
zero. Closed portfolio unrealized PnL and published close-event unrealized PnL
are zero.

## Reconciliation equations

Let `s` be +1 for LONG and -1 for SHORT, `E` the actual entry fill price, `V` the
instrument point value, and `(q_i, X_i)` the demonstrated partial-close lots and
prices. Let `Q` be remaining quantity before final close and `M` the current mark.

- Partial realized PnL = sum of `s * (X_i - E) * q_i * V`.
- Open unrealized PnL = `s * (M - E) * Q * V`.
- Final realized PnL = partial realized + `s * (final_exit - E) * Q * V`.
- Portfolio realized = realized PnL of closed positions plus realized portions of
  positions still open. Account realized equals this total.
- Portfolio unrealized = sum of unrealized PnL on open remaining quantities only.
- Account balance = starting balance + portfolio realized.
- Account equity = starting balance + portfolio realized + portfolio unrealized.
- Daily PnL = dated realized changes since the authoritative trading-day baseline
  plus explicit, validated same-day account adjustments.
- Journal PnL is cumulative per position. Closed-history aggregate excludes
  realized partial PnL on positions that are still open; adding that open partial
  amount reconciles closed-history PnL to total portfolio/account realized PnL.

These are the existing gross PAPER equations. The engine has no separate
commission/fee/settlement ledger; this package does not claim net returns after
costs or invent a fee policy. Recovery validates the execution-derived economic
PnL rather than accepting arbitrary supplied totals.

## Market, risk, account and recovery boundaries

PriceFeedServiceV2 owns admission of finite, positive, dated, fresh and ordered
operational marks; it delegates accepted updates to LivePositionMonitorV2 and the
lifecycle. Price projections and GET/dashboard reads do not call this mutation
path. An operational price update can legitimately trigger an existing stop or
take-profit; a read of unrealized PnL cannot. Invalid, stale and future marks leave
financial state unchanged. V4 market-availability regressions remain required.

Risk consumes canonical portfolio balance, account daily PnL and drawdown. It does
not keep a competing PnL ledger. Existing V5 tests retain safety-block precedence,
condition-owned reset semantics and sizing boundaries.

Account identity belongs to the runtime/checkpoint namespace and PAPER broker;
journal and history records belong to that namespace. A's closed trade and PnL
restore on A/B/A without appearing in B. Retired A cannot settle into B, and
failed-switch/pending recovery tests retain admission containment.

Durable mutation writes PENDING evidence before financial work, validates the
participant set and writes COMMITTED evidence on success. Validated PAPER rollback
and uncertain fail-closed states remain distinct. PENDING files require proven
reconciliation before recovery. The existing crash-window/process-exit suite is
part of direct and full certification. New tests recover the last automatic
checkpoint after open/partial marks, replay without duplicate application, then
close profitably or at a loss for both directions.

Dashboard events are observational notifications, not independent ledger writes
or durable commit acknowledgements. This package corrects their economic payload
and synchronization order; it does not add a durable event delivery/outbox system.
Recovery reconstructs canonical financial records rather than replaying dashboard
notifications as economic operations.

## Demonstrated defects and corrections

Before production changes, 14 initial V6 cases passed and three failed: two
LONG/SHORT close-event probes retained nonzero unrealized PnL, and one mark-event
subscriber saw position unrealized PnL 4.0 while portfolio/account still showed
0.0. The lifecycle zeroed/synchronized those values only after publication.
The correction moves those existing operations before the corresponding events.

A separate duplicate-delivery probe showed an already settled execution being
assigned a new local position UUID before checkpoint validation failed. Existing
semantic validation prevented a valid commit but left an uncertain in-memory
application. The new PAPER identity check rejects the duplicate before financial
application. Tests exercise order identity, broker-position identity and both,
with and without restart, and require unchanged financial state and no failed
runtime after rejection.

No policy/threshold or broker execution implementation was changed. Diff review
also caught and removed a Windows encoding-only edit artifact; certification was
restarted after correction. Existing tests were not weakened.

## Exact scope and justification

- `backend/services/trade_lifecycle_service_v2.py`: duplicate PAPER application guard
  and existing financial synchronization moved before event publication.
- `backend/tests/phase1_risk_authority_inventory_v5.json`: refresh exact source/call
  evidence for the changed submit function; preserve V5 ownership and assertions.
- `backend/tests/test_phase1_financial_state_sync_v6.py`: 28 behavioral/inventory cases.
- `backend/tests/phase1_financial_inventory_v6.py`: repository-wide discovery helper.
- `backend/tests/phase1_financial_inventory_v6.json`: reviewed owners and boundaries.
- This document: evidence, equations, supported scope, limitations and certificate.

## Validation

Tests use the existing process-local POLICY and isolated PAPER fixtures:

```powershell
python -c "import os,sys,pytest; from backend.tests.test_account_switch_safety_containment_v2 import POLICY; os.environ.update(POLICY); sys.exit(pytest.main(sys.argv[1:]))" -q -p no:cacheprovider --tb=short <modules below>
```

Full backend uses `backend/tests` in place of the module list. The evidence runner
records exact node IDs/outcomes. Syntax validation uses `python -m py_compile` on
the three changed/new Python files. Diff checks and exact staging checks are
required before commit. The 404 direct modules include V5 risk, PH1-REQ-008/009,
market ownership, WebSocket/account isolation and recovery/CLI contracts.

## Remaining scope and next action

Certification applies to the supported canonical PAPER runtime and the reviewed
retained paths. No LIVE execution, new scale-in, fee model, partial-entry engine,
or durable notification transport is certified. The master matrix's broader
Phase-1 closure is not implied by this package. Next: PH1-REQ-001/002/003 runtime
and execution ownership coverage across ASGI, factory, CLI and retained adapters.

## Pre-staging financial-state certificate

Direct regression: **3488 passed, 0 failed, 1 skipped** across 404 modules
(156.05 seconds). Full backend: **5436 passed, 0 failed, 1 skipped**
(127.91 seconds), including all 28 new V6 cases. The skipped node is identical to
the baseline. Both suites retain the two existing pytest import-rewrite warnings.
All three changed/new Python files passed `python -m py_compile`; diff and
whitespace checks passed. The reviewed scope is exactly six files, and all 83
unrelated untracked files retain their baseline hashes.

```text
TOTAL_FINANCIAL_MUTATION_POINTS=135
CLASSIFIED_FINANCIAL_MUTATION_POINTS=135
UNCLASSIFIED_FINANCIAL_MUTATION_POINTS=0
CANONICAL_FILL_OWNER=PaperBrokerConnectorV2
CANONICAL_POSITION_OWNER=TradeLifecycleServiceV2
CANONICAL_PORTFOLIO_OWNER=PortfolioManagerV2
CANONICAL_REALIZED_PNL_OWNER=TradeLifecycleServiceV2 (PositionManagerV2/RealizedPnLEngineV2 calculations)
CANONICAL_UNREALIZED_PNL_OWNER=PositionManagerV2 (PortfolioManagerV2 aggregation)
CANONICAL_JOURNAL_OWNER=TradeJournalV2
DUPLICATE_FILL_WRITERS=0
DUPLICATE_POSITION_WRITERS=0
DUPLICATE_REALIZED_PNL_WRITERS=0
OPEN_POSITION_SYNC=GREEN
PARTIAL_CLOSE_SYNC=GREEN
FULL_CLOSE_SYNC=GREEN
DUPLICATE_FILL_IDEMPOTENCY=GREEN
REALIZED_PNL_RECONCILIATION=GREEN
UNREALIZED_PNL_RECONCILIATION=GREEN
JOURNAL_SYNC=GREEN
ACCOUNT_ISOLATION=GREEN
RECOVERY_FINANCIAL_CONSISTENCY=GREEN
RISK_FINANCIAL_CONSISTENCY=GREEN
PH1_REQ004_REGRESSION=GREEN
PH1_REQ008_REGRESSION=GREEN
PH1_REQ009_REGRESSION=GREEN
MARKET_OWNERSHIP_REGRESSION=GREEN
RECOVERY_CLI_REGRESSION=GREEN
INITIAL_BACKEND_FAILURES=0
FINAL_BACKEND_FAILURES=0
LIVE_EXECUTION=NO
```

The certificate uses the inventory/counting and supported-runtime definitions
above; it does not certify unrelated future or LIVE capabilities.

## Exact direct regression modules

```text
backend/tests/test_account_config_manager_v2.py
backend/tests/test_account_contract_enforcement_v2.py
backend/tests/test_account_contract_exposure_runtime_v2.py
backend/tests/test_account_contract_position_sizing_runtime_v2.py
backend/tests/test_account_contract_runtime_limits_v2.py
backend/tests/test_account_contract_symbol_aware_v2.py
backend/tests/test_account_manager_api_v2.py
backend/tests/test_account_overview_widget_v2.py
backend/tests/test_account_performance_router.py
backend/tests/test_account_performance_service.py
backend/tests/test_account_risk_guard.py
backend/tests/test_account_risk_guard_daily_loss_authority_v2.py
backend/tests/test_account_risk_guard_internal_policy_authority_v2.py
backend/tests/test_account_risk_guard_max_risk_authority_v2.py
backend/tests/test_account_runtime_transition_v2.py
backend/tests/test_account_state_manager_v2.py
backend/tests/test_account_switch_api_v2.py
backend/tests/test_account_switch_safety_containment_v2.py
backend/tests/test_account_switch_safety_v2.py
backend/tests/test_admin_account_trade_boundary_v2.py
backend/tests/test_admin_market_boundary_v2.py
backend/tests/test_ai_decision_memory_canonical_journal_e2e_v2.py
backend/tests/test_ai_learning_canonical_journal_e2e_v2.py
backend/tests/test_ai_pattern_canonical_journal_e2e_v2.py
backend/tests/test_analyze_portfolio.py
backend/tests/test_api_settings_quote_freshness_policy_v2.py
backend/tests/test_asgi_runtime_integration_v2.py
backend/tests/test_backtest_account_config_v2_migration.py
backend/tests/test_backtest_account_contract_runtime_v2.py
backend/tests/test_backtest_dashboard_exporter.py
backend/tests/test_backtest_execution_simulator_v2.py
backend/tests/test_backtest_execution_stage.py
backend/tests/test_backtest_market_stage.py
backend/tests/test_backtest_risk_adapter_factory_v2.py
backend/tests/test_backtest_risk_compatibility_adapter_integration_v2.py
backend/tests/test_backtest_session_auto_position_updates_v2.py
backend/tests/test_backtest_trade_lifecycle_e2e_v2.py
backend/tests/test_backtest_trade_lifecycle_position_updates_v2.py
backend/tests/test_backtesting_background_worker_lifecycle_v2.py
backend/tests/test_backtesting_dashboard_api_v2.py
backend/tests/test_backtesting_dashboard_app_registration_v2.py
backend/tests/test_backtesting_dashboard_execution_v2.py
backend/tests/test_backtesting_dashboard_job_counts_v2.py
backend/tests/test_backtesting_dashboard_metrics_v2.py
backend/tests/test_backtesting_dashboard_performance_report_v2.py
backend/tests/test_backtesting_dashboard_performance_v2.py
backend/tests/test_backtesting_dashboard_queue_worker_v2.py
backend/tests/test_backtesting_dashboard_read_safety_v2.py
backend/tests/test_backtesting_dashboard_risk_validation_v2.py
backend/tests/test_backtesting_dashboard_shared_manager_v2.py
backend/tests/test_backtesting_dashboard_shared_queue_v2.py
backend/tests/test_backtesting_dashboard_shared_worker_v2.py
backend/tests/test_backtesting_dashboard_strategy_decision_v2.py
backend/tests/test_backtesting_dashboard_strategy_performance_v2.py
backend/tests/test_backtesting_dashboard_strategy_ranking_v2.py
backend/tests/test_backtesting_dashboard_strategy_recommendation_v2.py
backend/tests/test_backtesting_dashboard_strategy_registry_v2.py
backend/tests/test_backtesting_dashboard_strategy_selection_v2.py
backend/tests/test_backtesting_dashboard_trade_plan_v2.py
backend/tests/test_broker_position_id_bridge_v2.py
backend/tests/test_certified_economic_news_data_lifecycle_v2.py
backend/tests/test_certified_market_calendar_v2.py
backend/tests/test_certified_market_hours_app_loading_v2.py
backend/tests/test_certified_market_hours_data_lifecycle_v2.py
backend/tests/test_certified_market_hours_refresh_api_v2.py
backend/tests/test_certified_market_hours_refresh_app_wiring_v2.py
backend/tests/test_certified_market_hours_runtime_provider_v2.py
backend/tests/test_certified_market_hours_runtime_refresh_service_v2.py
backend/tests/test_certified_market_hours_snapshot_loader_v2.py
backend/tests/test_certified_market_hours_versioned_data_v2.py
backend/tests/test_csv_backtest_lifecycle_e2e_v2.py
backend/tests/test_daily_pnl_safety_v2.py
backend/tests/test_daily_session_reset_safety_v2.py
backend/tests/test_dashboard_app_dependency_wiring_v2.py
backend/tests/test_dashboard_app_realtime_e2e_v2.py
backend/tests/test_dashboard_auto_refresh_engine_v2.py
backend/tests/test_dashboard_event_bus_v2.py
backend/tests/test_dashboard_event_dispatcher_v2.py
backend/tests/test_dashboard_event_dispatcher_websocket_integration_v2.py
backend/tests/test_dashboard_execution_manager_read_only_v2.py
backend/tests/test_dashboard_execution_pipeline_read_only_v3.py
backend/tests/test_dashboard_live_api_v2.py
backend/tests/test_dashboard_live_data_service_v2.py
backend/tests/test_dashboard_read_execution_safety_v2.py
backend/tests/test_dashboard_read_side_effects_v2.py
backend/tests/test_dashboard_realtime_pipeline_v2.py
backend/tests/test_dashboard_refresh_service_v2.py
backend/tests/test_dashboard_strategy_intelligence_read_only_v2.py
backend/tests/test_dashboard_websocket_api_v2.py
backend/tests/test_dashboard_websocket_broadcaster_v2.py
backend/tests/test_dashboard_websocket_hub_v2.py
backend/tests/test_dashboard_widget_registry_v2.py
backend/tests/test_dashboard_widgets_api_v2.py
backend/tests/test_drawdown_analytics.py
backend/tests/test_drawdown_analytics_router.py
backend/tests/test_durable_crash_recovery_v2.py
backend/tests/test_economic_news_runtime_provider_v2.py
backend/tests/test_execution_approval_daily_loss_authority_v2.py
backend/tests/test_execution_dashboard_provider_v2.py
backend/tests/test_execution_decision_app.py
backend/tests/test_execution_decision_engine.py
backend/tests/test_execution_decision_engine_v2.py
backend/tests/test_execution_decision_legacy_confidence_authority_v2.py
backend/tests/test_execution_engine_v2.py
backend/tests/test_execution_manager_v2.py
backend/tests/test_execution_pipeline_account_balance_authority_v2.py
backend/tests/test_execution_pipeline_account_size_authority_v2.py
backend/tests/test_execution_pipeline_daily_pnl_authority_v2.py
backend/tests/test_execution_pipeline_point_value_authority_v2.py
backend/tests/test_execution_pipeline_total_drawdown_authority_v2.py
backend/tests/test_execution_position_bridge_risk_v1.py
backend/tests/test_execution_risk_event_summary_api_v2.py
backend/tests/test_execution_risk_events_api_v2.py
backend/tests/test_execution_risk_gate_v1.py
backend/tests/test_execution_risk_validation_integration_v2.py
backend/tests/test_execution_service_v2.py
backend/tests/test_execution_stage.py
backend/tests/test_execution_state_store_v2.py
backend/tests/test_external_market_data_provider_v2.py
backend/tests/test_filled_position_atomicity_v2.py
backend/tests/test_intelligence_stage.py
backend/tests/test_intelligence_v2_app.py
backend/tests/test_latest_market_analysis_router.py
backend/tests/test_latest_market_signal_router.py
backend/tests/test_live_analysis_trade_lifecycle_integration_v2.py
backend/tests/test_live_market_analysis_decision_council_v2.py
backend/tests/test_live_market_analysis_directional_confluence_v2.py
backend/tests/test_live_market_analysis_early_confluence_authority_v2.py
backend/tests/test_live_market_analysis_ema_directional_confluence_v2.py
backend/tests/test_live_market_analysis_equal_level_pool_semantics_v2.py
backend/tests/test_live_market_analysis_execution_v2_runtime_authority_v2.py
backend/tests/test_live_market_analysis_liquidity_directional_confluence_v2.py
backend/tests/test_live_market_analysis_market_context_v2.py
backend/tests/test_live_market_analysis_market_regime_quality_semantics_v2.py
backend/tests/test_live_market_analysis_news_authority_wiring_v2.py
backend/tests/test_live_market_analysis_order_block_direction_semantics_v2.py
backend/tests/test_live_market_analysis_probability_evidence_independence_v2.py
backend/tests/test_live_market_analysis_probability_independence_v2.py
backend/tests/test_live_market_analysis_probability_v2_runtime_authority_v2.py
backend/tests/test_live_market_analysis_probability_volume_authority_v2.py
backend/tests/test_live_market_analysis_router.py
backend/tests/test_live_market_analysis_runtime_spread_wiring_v2.py
backend/tests/test_live_market_analysis_service.py
backend/tests/test_live_market_analysis_signal_freshness_v2.py
backend/tests/test_live_market_analysis_validator_atr_authority_v2.py
backend/tests/test_live_market_analysis_validator_daily_limit_authority_v2.py
backend/tests/test_live_market_analysis_validator_open_position_authority_v2.py
backend/tests/test_live_market_analysis_validator_session_authority_v2.py
backend/tests/test_live_market_analysis_validator_spread_authority_v2.py
backend/tests/test_live_market_analysis_volume_quality_semantics_v2.py
backend/tests/test_live_market_hours_wiring_v2.py
backend/tests/test_live_market_trade_planner_reward_risk_authority_v2.py
backend/tests/test_live_position_monitor_app_integration_v2.py
backend/tests/test_live_position_monitor_break_even_v2.py
backend/tests/test_live_position_monitor_broker_partial_close_sync_v2.py
backend/tests/test_live_position_monitor_broker_protection_sync_v2.py
backend/tests/test_live_position_monitor_partial_take_profit_v2.py
backend/tests/test_live_position_monitor_point_value_v2.py
backend/tests/test_live_position_monitor_portfolio_sync_v2.py
backend/tests/test_live_position_monitor_realized_pnl_v2.py
backend/tests/test_live_position_monitor_realtime_e2e_v2.py
backend/tests/test_live_position_monitor_trade_learning_e2e_v2.py
backend/tests/test_live_position_monitor_trailing_stop_v2.py
backend/tests/test_live_position_monitor_v2.py
backend/tests/test_main_runtime_integration.py
backend/tests/test_market_auto_point_value_authority_v2.py
backend/tests/test_market_context_engine_v2.py
backend/tests/test_market_context_policy_authority_v2.py
backend/tests/test_market_data.py
backend/tests/test_market_data_analysis.py
backend/tests/test_market_data_hub_v2.py
backend/tests/test_market_hours_app_wiring_v2.py
backend/tests/test_market_hours_service_v2.py
backend/tests/test_market_hours_special_hours_integration_v2.py
backend/tests/test_market_quote_router_v2.py
backend/tests/test_market_regime_engine.py
backend/tests/test_market_regime_trend_policy_authority_v2.py
backend/tests/test_market_regime_volatility_policy_authority_v2.py
backend/tests/test_market_router_economic_news_authority_injection_v2.py
backend/tests/test_market_signal_history_router.py
backend/tests/test_market_stage.py
backend/tests/test_market_state_engine_v2.py
backend/tests/test_market_structure_engine_v3.py
backend/tests/test_market_webhook_auth.py
backend/tests/test_market_webhook_auto_close_e2e_v2.py
backend/tests/test_market_webhook_dashboard_realtime_e2e_v2.py
backend/tests/test_market_webhook_institutional_pipeline_e2e_v2.py
backend/tests/test_market_webhook_journal_dashboard_sync_e2e_v2.py
backend/tests/test_market_webhook_market_data_hub_e2e_v2.py
backend/tests/test_market_webhook_market_state_e2e_v2.py
backend/tests/test_market_webhook_position_closed_dashboard_e2e_v2.py
backend/tests/test_market_webhook_router.py
backend/tests/test_market_webhook_trend_engine_e2e_v2.py
backend/tests/test_maximum_open_positions_policy_authority_v2.py
backend/tests/test_maximum_open_positions_runtime_backtest_parity_v2.py
backend/tests/test_monte_carlo_dashboard_exporter.py
backend/tests/test_oco_manager_v2.py
backend/tests/test_open_position_router.py
backend/tests/test_optimize_portfolio.py
backend/tests/test_paper_broker_partial_close_v2.py
backend/tests/test_paper_execution_engine_v2.py
backend/tests/test_paper_execution_fill_policy_authority_v2.py
backend/tests/test_paper_execution_slippage_policy_authority_v2.py
backend/tests/test_parameter_stability_dashboard_exporter.py
backend/tests/test_partial_take_profit_engine.py
backend/tests/test_partial_take_profit_engine_v2.py
backend/tests/test_partial_take_profit_policy_authority_v2.py
backend/tests/test_performance_dashboard_api_v2.py
backend/tests/test_performance_dashboard_engine_v2.py
backend/tests/test_performance_dashboard_provider_v2.py
backend/tests/test_performance_dashboard_score_integration_v2.py
backend/tests/test_performance_intelligence_canonical_journal_e2e_v2.py
backend/tests/test_ph1_req008_pending_applicability_v2.py
backend/tests/test_ph1_req008_startup_behavior_v2.py
backend/tests/test_ph1_req008_startup_pending_fail_closed_v2.py
backend/tests/test_ph1_req008_startup_pending_order_v2.py
backend/tests/test_ph1_req008_startup_pending_recovery_v2.py
backend/tests/test_phase1_account_isolation_characterization_v2.py
backend/tests/test_phase1_account_switch_full_containment_v2.py
backend/tests/test_phase1_api_authorization_observational_contract_v2.py
backend/tests/test_phase1_api_ownership_characterization_v2.py
backend/tests/test_phase1_api_route_account_scope_contract_v2.py
backend/tests/test_phase1_asgi_cli_equivalence_v2.py
backend/tests/test_phase1_duplicate_fill_idempotency_v2.py
backend/tests/test_phase1_fill_atomicity_v2.py
backend/tests/test_phase1_financial_state_sync_v6.py
backend/tests/test_phase1_financial_sync_characterization_v2.py
backend/tests/test_phase1_global_duplicate_submission_idempotency_v2.py
backend/tests/test_phase1_market_ownership_availability_v4.py
backend/tests/test_phase1_paper_execution_characterization_v2.py
backend/tests/test_phase1_paper_live_isolation_v2.py
backend/tests/test_phase1_parallel_execution_equivalence_v2.py
backend/tests/test_phase1_recovery_characterization_v2.py
backend/tests/test_phase1_recovery_execution_blocking_v2.py
backend/tests/test_phase1_rejected_signal_zero_side_effect_v2.py
backend/tests/test_phase1_risk_authority_characterization_v2.py
backend/tests/test_phase1_risk_authority_integration_v2.py
backend/tests/test_phase1_risk_precedence_v5.py
backend/tests/test_phase1_route_lifecycle_contract_v2.py
backend/tests/test_phase1_route_lifecycle_delegation_v2.py
backend/tests/test_phase1_runtime_characterization_v2.py
backend/tests/test_phase1_safety_closure_v2.py
backend/tests/test_phase1_websocket_account_isolation_characterization_v2.py
backend/tests/test_phase1_websocket_authorization_contract_v2.py
backend/tests/test_portfolio.py
backend/tests/test_portfolio_account_state_integration_v2.py
backend/tests/test_portfolio_analysis_engine.py
backend/tests/test_portfolio_analysis_service.py
backend/tests/test_portfolio_asset_allocation.py
backend/tests/test_portfolio_backtest.py
backend/tests/test_portfolio_backtest_router.py
backend/tests/test_portfolio_beta_report.py
backend/tests/test_portfolio_calmar_ratio_report.py
backend/tests/test_portfolio_concentration_report.py
backend/tests/test_portfolio_correlation_matrix.py
backend/tests/test_portfolio_covariance_matrix.py
backend/tests/test_portfolio_csv_exporter.py
backend/tests/test_portfolio_cvar_report.py
backend/tests/test_portfolio_dashboard_exporter.py
backend/tests/test_portfolio_diversification_report.py
backend/tests/test_portfolio_efficient_frontier.py
backend/tests/test_portfolio_exposure_report.py
backend/tests/test_portfolio_information_ratio_report.py
backend/tests/test_portfolio_json_exporter.py
backend/tests/test_portfolio_manager_v2.py
backend/tests/test_portfolio_market_router.py
backend/tests/test_portfolio_maximum_sharpe_optimizer.py
backend/tests/test_portfolio_minimum_variance_optimizer.py
backend/tests/test_portfolio_monte_carlo_engine.py
backend/tests/test_portfolio_omega_ratio_report.py
backend/tests/test_portfolio_optimization_exporter.py
backend/tests/test_portfolio_optimization_recommendation.py
backend/tests/test_portfolio_optimization_report.py
backend/tests/test_portfolio_position.py
backend/tests/test_portfolio_rebalancing_engine.py
backend/tests/test_portfolio_report.py
backend/tests/test_portfolio_risk_contribution.py
backend/tests/test_portfolio_risk_engine_v2.py
backend/tests/test_portfolio_risk_parity_optimizer.py
backend/tests/test_portfolio_router.py
backend/tests/test_portfolio_scenario_analysis.py
backend/tests/test_portfolio_sharpe_ratio_report.py
backend/tests/test_portfolio_snapshot.py
backend/tests/test_portfolio_sortino_ratio_report.py
backend/tests/test_portfolio_statistics.py
backend/tests/test_portfolio_stress_test.py
backend/tests/test_portfolio_summary_widget_v2.py
backend/tests/test_portfolio_tracking_error_report.py
backend/tests/test_portfolio_treynor_ratio_report.py
backend/tests/test_portfolio_var_report.py
backend/tests/test_portfolio_volatility_report.py
backend/tests/test_position_filter_v1.py
backend/tests/test_position_manager.py
backend/tests/test_position_manager_v2.py
backend/tests/test_position_monitor.py
backend/tests/test_position_sizing_app.py
backend/tests/test_position_sizing_contract_limit_authority_v2.py
backend/tests/test_position_sizing_engine.py
backend/tests/test_position_sizing_engine_v2.py
backend/tests/test_position_v2.py
backend/tests/test_protective_order_registry_v2.py
backend/tests/test_realized_pnl_engine_v2.py
backend/tests/test_rebalance_portfolio.py
backend/tests/test_rec003_cli_startup_owner_v2.py
backend/tests/test_recovery_cli_pending_contract_v2.py
backend/tests/test_recovery_consistency_v2.py
backend/tests/test_replay_market_data_bridge_v2.py
backend/tests/test_risk_analytics.py
backend/tests/test_risk_analytics_market_router.py
backend/tests/test_risk_analytics_router.py
backend/tests/test_risk_compatibility_adapter_v2.py
backend/tests/test_risk_contribution.py
backend/tests/test_risk_contribution_router.py
backend/tests/test_risk_dashboard_analytics_integration_v2.py
backend/tests/test_risk_dashboard_event_publisher_v2.py
backend/tests/test_risk_event_analytics_v2.py
backend/tests/test_risk_event_logger_persistence_v2.py
backend/tests/test_risk_event_query_filtering_v2.py
backend/tests/test_risk_event_runtime_persistence_wiring_v2.py
backend/tests/test_risk_event_store_v2.py
backend/tests/test_risk_manager_v2.py
backend/tests/test_risk_stage.py
backend/tests/test_risk_status_widget_v2.py
backend/tests/test_risk_validation_dashboard_provider_v2.py
backend/tests/test_risk_validation_engine_v2.py
backend/tests/test_risk_validation_service_v2.py
backend/tests/test_risk_validation_trade_plan_integration_v2.py
backend/tests/test_run_portfolio.py
backend/tests/test_runtime_account_capital_authority_v2.py
backend/tests/test_runtime_context_account_contract_v2.py
backend/tests/test_runtime_context_app_integration_v2.py
backend/tests/test_runtime_context_internal_daily_loss_policy_v2.py
backend/tests/test_runtime_context_v2.py
backend/tests/test_runtime_lifecycle_manager_v2.py
backend/tests/test_runtime_quote_authority_v2.py
backend/tests/test_runtime_quote_production_wiring_v2.py
backend/tests/test_runtime_risk_percent_authority_v2.py
backend/tests/test_runtime_spread_authority_v2.py
backend/tests/test_safe003_execution_v2_risk_authority_wiring_v2.py
backend/tests/test_safe003_final_cross_path_risk_authority_v2.py
backend/tests/test_safe003_missing_runtime_risk_authority_v2.py
backend/tests/test_shared_account_policy_runtime_wiring_v2.py
backend/tests/test_signal_execution_cooldown_policy_authority_v2.py
backend/tests/test_signal_execution_manager.py
backend/tests/test_simulate_portfolio.py
backend/tests/test_spread_authority_v2.py
backend/tests/test_startup_coordinator_v2.py
backend/tests/test_state_recovery_service_v2.py
backend/tests/test_strategy_decision_dashboard_provider_v2.py
backend/tests/test_strategy_decision_engine_v2.py
backend/tests/test_strategy_decision_selection_integration_v2.py
backend/tests/test_strategy_decision_service_v2.py
backend/tests/test_strategy_intelligence_orchestrator_v2.py
backend/tests/test_strategy_intelligence_read_only_v2.py
backend/tests/test_strategy_performance_dashboard_provider_v2.py
backend/tests/test_strategy_ranking_dashboard_provider_v2.py
backend/tests/test_strategy_selection_block_safety_v2.py
backend/tests/test_strategy_selection_dashboard_provider_v2.py
backend/tests/test_takeprofit_account_profiles_v2.py
backend/tests/test_topstep_account_profiles_v2.py
backend/tests/test_trade_accounting_safety_v2.py
backend/tests/test_trade_execution_engine.py
backend/tests/test_trade_history_manager_v2.py
backend/tests/test_trade_history_router.py
backend/tests/test_trade_history_store.py
backend/tests/test_trade_journal_analytics_integration_v2.py
backend/tests/test_trade_journal_analytics_v2.py
backend/tests/test_trade_journal_breakdown_analytics_v2.py
backend/tests/test_trade_journal_breakdown_integration_v2.py
backend/tests/test_trade_journal_exporter.py
backend/tests/test_trade_journal_profit_factor_json_v2.py
backend/tests/test_trade_journal_summary_widget_v2.py
backend/tests/test_trade_lifecycle_a_plus_confluence_policy_v2.py
backend/tests/test_trade_lifecycle_a_plus_policy_v2.py
backend/tests/test_trade_lifecycle_a_plus_probability_policy_v2.py
backend/tests/test_trade_lifecycle_api_v2.py
backend/tests/test_trade_lifecycle_app_integration_v2.py
backend/tests/test_trade_lifecycle_broker_connector_integration_v2.py
backend/tests/test_trade_lifecycle_close_sync_v2.py
backend/tests/test_trade_lifecycle_dashboard_event_publisher_v2.py
backend/tests/test_trade_lifecycle_execution_risk_gate_v1.py
backend/tests/test_trade_lifecycle_exposure_integration_v2.py
backend/tests/test_trade_lifecycle_oco_integration_v2.py
backend/tests/test_trade_lifecycle_order_validation_integration_v2.py
backend/tests/test_trade_lifecycle_portfolio_manager_integration_v2.py
backend/tests/test_trade_lifecycle_portfolio_risk_integration_v2.py
backend/tests/test_trade_lifecycle_protective_registry_integration_v2.py
backend/tests/test_trade_lifecycle_restore_active_position_v2.py
backend/tests/test_trade_lifecycle_risk_manager_integration_v2.py
backend/tests/test_trade_lifecycle_service_v2.py
backend/tests/test_trade_lifecycle_signal_blocking_reasons_policy_v2.py
backend/tests/test_trade_lifecycle_signal_decision_policy_v2.py
backend/tests/test_trade_lifecycle_signal_status_policy_v2.py
backend/tests/test_trade_lifecycle_signal_submission_target_v2.py
backend/tests/test_trade_lifecycle_trade_journal_integration_v2.py
backend/tests/test_trade_plan_dashboard_provider_v2.py
backend/tests/test_trade_risk_validator_instruments_v2.py
backend/tests/test_trade_risk_validator_v2.py
backend/tests/test_trade_validator_policy_settings_v2.py
backend/tests/test_trade_validator_v2.py
backend/tests/test_trading_intelligence.py
backend/tests/test_trading_memory_canonical_journal_e2e_v2.py
backend/tests/test_walk_forward_dashboard_exporter.py
backend/tests/test_walk_forward_optimization_dashboard_exporter.py
```
