# PH1-REQ-004 risk authority and precedence

Package: PH1_REQ004_RISK_AUTHORITY_PRECEDENCE
Baseline: `d1e4ed4197b158d09487ebc3a9e2c571cfbb6569` on
`refactor/backend-architecture`, fetched with exact local/remote parity and no
tracked changes. All 83 unrelated untracked files were hashed before work.
Previous-package regressions passed 104 tests. Full baseline: **5344 passed,
0 failed, 1 skipped** before production edits.

## Inventory and counting

`backend/tests/phase1_risk_authority_inventory_v5.json` classifies **134**
function-level risk/permission decision and authority points, including retained
legacy, strategy and observational candidates. The companion discovery helper
scans every production Python module for decision vocabulary and includes
explicitly reviewed boolean, exception and delegation boundaries. The regression
requires exact identity and AST evidence equality, not merely a numeric count.

Each row records owner, signature inputs, output fields, block/unblock/size
capabilities, account/runtime/strategy/execution scope, persistence, importing
callers, local calls and downstream effect. Import references are static evidence,
not a claim that every importing module executes every method. Runtime object
identity and registered-route regression tests establish the operational wiring.

The count is not 134 independently final risk authorities. Seven methods directly
write the persistent account block state; four can clear their owned conditions.
Delegating callers and ephemeral response reasons are not counted again as
persistent writers. Strategy cooldown permission is explicitly distinct from a
persistent account/runtime unblock.

## Canonical ownership and precedence

The existing canonical quantitative risk owner is
`backend.execution.risk_manager_v2.RiskManagerV2`. The execution composition owner
is `TradeLifecycleServiceV2`; its risk approval is subject to account/runtime
admission and additional vetoes. No new risk manager, API risk owner, or block
registry was introduced.

Operational precedence is an intersection of vetoes, not a universal numeric
ranking of unrelated reasons:

1. The durable admission barrier rejects retired/switching generations; the
   account-safety owner verifies current publication, selector, identity, profile,
   and risk/balance context. Failed/stopped durability rejects execution.
2. Existing-position and rejected-signal checks may return first inside the
   lifecycle. A rejected signal never invokes sizing or order preparation.
3. AccountStateManagerV2 advances the trading day when operationally required.
   Persistent account blocks veto before quantitative risk or preparation.
4. RiskManagerV2 evaluates finite inputs, canonical account daily PnL and drawdown,
   sizing, projected daily/drawdown capacity, open-position and contract limits.
   Its ordered reason list remains unchanged: sizing, daily, drawdown,
   open-position, contract-limit reasons. Sizing approval is not permission.
5. Exposure and portfolio-risk guards retain independent vetoes. Submission
   idempotency remains before the final gate, preserving duplicate behavior.
6. ExecutionRiskGateV1 uses TradeRiskValidatorV2 and the current account profile;
   the existing order guard validates non-executable candidate fields. Either
   rejection returns no prepared executable order.
7. Only after these permissions does ExecutionManagerV2 prepare an order for the
   existing broker path. Broker/position/protection behavior is unchanged.

Strategy selection, confluence, probability, intelligence, news, market-hours,
quote freshness and signal freshness are upstream recommendations/constraints.
They cannot clear canonical account/runtime blocks. News and market constraints
remain with their existing authorities; missing/stale data behavior is covered
by the preserved V4 suite. Analytics and dashboards remain observational.
Standalone legacy simulation components retain their documented compatibility
role; they are not the owner of the registered canonical PAPER submit route.

## Limit ownership

- AccountConfigManagerV2/FundingFirmProfile owns account risk percent, contract
  classes and firm limits. Runtime composition resolves the effective daily limit
  as the minimum configured firm/internal limit, preserving `None` semantics.
- AccountStateManagerV2 owns current daily PnL, high-water equity/drawdown and
  persistent condition reasons. RiskManagerV2 uses the same resolved limits.
- Current operational total-loss enforcement uses profile `max_drawdown`.
  Shipped profiles also expose `maximum_loss_limit` with the same values; this
  package does not reinterpret that metadata as another competing risk limit.
- PositionSizingEngineV2 owns canonical quantity calculation. The live-analysis
  sizing adapter and dynamic/CLI calculators do not grant final permission.
- AccountSwitchSafetyV2 rejects profile/limit drift and stale identity; publication
  creates/reconstructs the new account generation. A/B/A retains A's daily block
  without transferring it to B or silently resetting it.

## Block writers and valid clear conditions

| Direct writer | Condition and clear authority |
| --- | --- |
| AccountStateManagerV2.__init__ | Initializes new state; never clears an existing account. |
| update_from_portfolio | Recomputes its drawdown condition from finite portfolio evidence; preserves other reasons. |
| _record_daily_pnl | Recomputes its daily-loss condition from validated accounting input; preserves other reasons. |
| reset_daily_state | Only a forward authoritative trading-day transition clears daily loss; same-day reset is a no-op. Drawdown and foreign reasons remain. |
| _preserve_unclassified_block | Converts an unexplained active block into a sticky explicit reason; never unblocks. |
| restore_state | Validates account snapshot consistency; canonical recovery rejects weaker/contradictory current-state replacement. Same-operation PAPER rollback uses separately validated financial evidence. |
| DurableExecutionStateV2.fail_closed | Adds durability_consistency_unproven and fails operational admission; no lower layer clears it. |

Recovery, reconciliation and rollback remain distinct. The low-level account
snapshot method is not a general public unblock API. Recovery must go through
ExecutionStateStoreV2/StateRecoveryServiceV2 and their applicability and consistency
checks. A valid new-day daily reset does not clear structural or durability blocks.

## Demonstrated defects and minimal corrections

| Root cause | Failing evidence before correction | Change |
| --- | --- | --- |
| Caller drawdown overrode current account drawdown when below the hard limit but above projected capacity. | A real prior PAPER loss plus next-day reset left insufficient drawdown capacity; a new submission with caller drawdown zero reached the preparation spy. | Lifecycle now resolves drawdown from the same account snapshot already authoritative for daily PnL. |
| Account mutations accepted NaN/infinity, allowing NaN comparisons to clear a daily block or corrupt risk state. | 16 invalid daily-PnL, portfolio and open-risk probes failed; negative-infinity checks already present for two cases passed. | Reject nonfinite values before clock advancement, adjustment records or financial mutation. |
| Final risk gate ran after executable preparation. | A blocked validator returned accepted=false with approved READY_TO_SUBMIT/SUBMIT_ORDER prepared data. | Existing final risk gate runs before preparation and returns prepared_order=None on rejection. |
| Order guard rejected closed/missing market context after executable preparation. | Two preparation spies showed calls before rejection/exception. | Existing validator shares one field-validation implementation between candidate and strict prepared-order entry points. Lifecycle calls candidate validation before preparation. |

The candidate contains no approved/status/decision/execution_mode fields. It is
not an executable order and cannot pass the pre-existing strict prepared-order
validation entry point. MARKET/LIMIT candidate equivalence tests retain the
existing field and market checks. No thresholds or risk policy were relaxed.

Two probe issues were corrected as test defects: a first drawdown probe collided
with retry deduplication until it used the existing submission_id contract; a
runtime-failure probe initially changed an observational phase label instead of
the authoritative coordinator.failed flag. Neither correction required a
production workaround. Existing tests were not removed or weakened.

## Safety evidence

New tests cover account blocks against strategy/signal/execution permission,
failed/stopped/switching/retired/unpublished runtime admission, drawdown spoofing,
finite state mutation, foreign-block preservation, same-day/new-day reset,
A/B/A restoration, canonical owner identity, contract limits, invalid sizing,
sizing approval under exhausted loss capacity, and risk/order rejection before
preparation. Captures/spies check orders, fills, positions, protections/OCO,
portfolio, account, journal, and execution events. Risk diagnostic events remain
permitted; a diagnostic risk approval never clears a persistent block.

PH1-REQ-008, PH1-REQ-009, market ownership, WebSocket authorization/isolation and
recovery/CLI modules are included in the direct/full regressions. The only
baseline skip is the existing unregistered `/api/v2/trades/submit` compatibility
route in test_phase1_risk_authority_integration_v2; it must remain unchanged.

No real-broker connector or LIVE implementation/configuration is changed or
connected. Tests exercise PAPER and existing rejection contracts only.

## Scope justification

- `account_state_manager_v2.py`: finite inputs before existing block/state mutations.
- `trade_lifecycle_service_v2.py`: authoritative drawdown and guards before preparation.
- `order_validation_engine_v2.py`: reuse existing guard rules on non-executable fields;
  strict validation of prepared orders remains unchanged.
- New V5 tests, inventory helper and JSON: behavioral and source/owner certification.
- This document: root causes, precedence, limits, writer/clearer ownership and evidence.

## Validation command

```powershell
python -c "import os,sys,pytest; from backend.tests.test_account_switch_safety_containment_v2 import POLICY; os.environ.update(POLICY); sys.exit(pytest.main(sys.argv[1:]))" -q -p no:cacheprovider --tb=short <direct modules below>
```

Full backend replaces the module list with `backend/tests`. Test policy is
process-local and uses existing isolated PAPER fixtures; no production
configuration file is changed. The evidence runner also records node IDs and
outcomes as JSON. Syntax uses `python -m py_compile` on every changed/new Python
file, followed by `git diff --check` and staged diff verification.

## Next evidenced Phase-1 work

Review PH1-REQ-005/006 financial ownership and fill synchronization against the
current durable recovery and atomicity evidence. The master matrix still records
broader cross-subsystem ownership coverage as unresolved; this package does not
claim a full Phase-1 or LIVE certification.

## Pre-staging risk authority certificate

Final direct regression: **2591 passed, 0 failed, 1 skipped** across 289 modules
(135.44 seconds). Full backend: **5408 passed, 0 failed, 1 skipped**
(124.63 seconds), including all 64 new V5 cases. The skipped node is identical to
the baseline. Both runs retain the two existing pytest import-rewrite warnings.

All five changed/new Python files passed `python -m py_compile`.
`git diff --check` passed. The production diff and four new evidence/test files
were reviewed; the exact seven-file scope is listed below. All 83 unrelated
untracked files retain their baseline SHA-256 hashes.

```text
TOTAL_RISK_DECISION_POINTS=134
CLASSIFIED_RISK_DECISION_POINTS=134
UNCLASSIFIED_RISK_DECISION_POINTS=0
CANONICAL_RISK_OWNER=RiskManagerV2 (TradeLifecycleServiceV2 composition; account/runtime vetoes)
BLOCK_WRITERS=7
BLOCK_CLEARERS=4
UNAUTHORIZED_BLOCK_CLEAR=0
DUPLICATE_FINAL_RISK_AUTHORITIES=0
ACCOUNT_CROSS_CONTAMINATION=0
SAFETY_BLOCK_PRECEDENCE=GREEN
RUNTIME_FAIL_CLOSED=GREEN
DAILY_LOSS_PRECEDENCE=GREEN
TOTAL_LOSS_PRECEDENCE=GREEN
STRATEGY_CANNOT_OVERRIDE=GREEN
SIGNAL_CANNOT_OVERRIDE=GREEN
EXECUTION_CANNOT_OVERRIDE=GREEN
POSITION_SIZING_BOUNDARY=GREEN
ACCOUNT_ISOLATION=GREEN
PH1_REQ008_REGRESSION=GREEN
PH1_REQ009_REGRESSION=GREEN
MARKET_OWNERSHIP_REGRESSION=GREEN
RECOVERY_CLI_REGRESSION=GREEN
INITIAL_BACKEND_FAILURES=0
FINAL_BACKEND_FAILURES=0
LIVE_EXECUTION=NO
```

These counts apply to the reviewed inventory and registered canonical PAPER
runtime. They do not certify unimplemented LIVE execution or close unrelated
Phase-1 requirements. Remaining work is stated above.

Exact package files:

- `backend/account/account_state_manager_v2.py`
- `backend/execution/order_validation_engine_v2.py`
- `backend/services/trade_lifecycle_service_v2.py`
- `backend/tests/phase1_risk_authority_inventory_v5.json`
- `backend/tests/phase1_risk_authority_inventory_v5.py`
- `backend/tests/test_phase1_risk_precedence_v5.py`
- `docs/architecture/phase1_risk_authority_precedence_v5.md`

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
backend/tests/test_certified_market_calendar_v2.py
backend/tests/test_certified_market_hours_app_loading_v2.py
backend/tests/test_certified_market_hours_data_lifecycle_v2.py
backend/tests/test_certified_market_hours_refresh_api_v2.py
backend/tests/test_certified_market_hours_refresh_app_wiring_v2.py
backend/tests/test_certified_market_hours_runtime_provider_v2.py
backend/tests/test_certified_market_hours_runtime_refresh_service_v2.py
backend/tests/test_certified_market_hours_snapshot_loader_v2.py
backend/tests/test_certified_market_hours_versioned_data_v2.py
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
backend/tests/test_intelligence_stage.py
backend/tests/test_intelligence_v2_app.py
backend/tests/test_latest_market_analysis_router.py
backend/tests/test_latest_market_signal_router.py
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
backend/tests/test_maximum_open_positions_runtime_backtest_parity_v2.py
backend/tests/test_monte_carlo_dashboard_exporter.py
backend/tests/test_paper_execution_engine_v2.py
backend/tests/test_paper_execution_fill_policy_authority_v2.py
backend/tests/test_paper_execution_slippage_policy_authority_v2.py
backend/tests/test_parameter_stability_dashboard_exporter.py
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
backend/tests/test_portfolio_account_state_integration_v2.py
backend/tests/test_portfolio_dashboard_exporter.py
backend/tests/test_portfolio_market_router.py
backend/tests/test_portfolio_risk_contribution.py
backend/tests/test_portfolio_risk_engine_v2.py
backend/tests/test_portfolio_risk_parity_optimizer.py
backend/tests/test_position_sizing_app.py
backend/tests/test_position_sizing_contract_limit_authority_v2.py
backend/tests/test_position_sizing_engine.py
backend/tests/test_position_sizing_engine_v2.py
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
backend/tests/test_trade_lifecycle_dashboard_event_publisher_v2.py
backend/tests/test_trade_lifecycle_execution_risk_gate_v1.py
backend/tests/test_trade_lifecycle_portfolio_risk_integration_v2.py
backend/tests/test_trade_lifecycle_risk_manager_integration_v2.py
backend/tests/test_trade_plan_dashboard_provider_v2.py
backend/tests/test_trade_risk_validator_instruments_v2.py
backend/tests/test_trade_risk_validator_v2.py
backend/tests/test_trade_validator_policy_settings_v2.py
backend/tests/test_trade_validator_v2.py
backend/tests/test_trading_intelligence.py
backend/tests/test_walk_forward_dashboard_exporter.py
backend/tests/test_walk_forward_optimization_dashboard_exporter.py
```
