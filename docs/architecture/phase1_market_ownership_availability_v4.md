# Phase 1 market endpoint ownership and availability

Package: PH1_LEGACY_MARKET_ENDPOINT_OWNERSHIP_AVAILABILITY
Baseline: `f99feb52216f209b16e3b908a6df852153c46281`, synchronized on
`refactor/backend-architecture`. The recovery/CLI closure commit is the baseline.
Before production edits, full backend: **5306 passed, 0 failed, 1 skipped**.
All 83 pre-existing untracked files are preserved by SHA-256 comparison.

## Scope and route inventory

`backend/tests/phase1_market_route_inventory_v4.json` records the actual registered
method, path, endpoint, module, authorization/dependencies, account scope,
read/mutation classification, owner, source, freshness and unavailable behavior.
The inventory includes endpoint/helper AST evidence and calls. It classifies
**27 market routes**: nine `/market` routes, one operational price ingress,
three certified market-hours routes, nine historical provider consumers, one
cached market-plan projection, and four demonstration projections. All other
65 registrations have explicit non-market dispositions; aliases/methods are
counted separately. Unregistered connector/provider modules are not API owners.
`backend/data` does not exist. `backend/market_data` contains the external-provider
contract; `backend/services/market_data.py` is the historical downloader.

Twelve routes are legacy compatibility/demo surfaces (eight `/market` routes
excluding canonical L1 ingress, plus four demonstrations). They remain contained.
No legacy module was deleted. The prior PH1-REQ-009 manifest changes only the
eight affected endpoint evidence records and webhook ownership description;
its 92 route registrations, account scope and authorization classifications remain.

## Verified defects and changes

| Defect demonstrated before production patch | Correction |
| --- | --- |
| Operational market-price route defaulted symbol to NQ and source to MANUAL, ignored supplied timestamp, and accepted stale/future/untimestamped events through the replay/manual path. | Require explicit symbol, positive finite price, aware timestamp and an existing operational source; pass to the existing feed. No router freshness math. |
| Missing feed raised AttributeError. | Established HTTP 503 unavailable response before any mutation. |
| NaN and positive infinity passed the feed's positive-price comparison. | Existing feed now rejects nonfinite prices before state/monitor changes. Negative infinity was already rejected. |
| Cached latest-analysis/latest-signal responses did not disclose current L1 availability. | Add snapshot-only metadata, consulting the existing runtime spread authority; retain historical data and 404 for absent snapshots. |
| Old candle settled a disconnected legacy position before the canonical feed rejected that candle as stale. | Reject legacy open positions before candle writes; remove route-owned TradeManagementEngine evaluation. Canonical feed/lifecycle remains the only price-monitor execution path. |
| Four fixed market dashboards lacked demonstration/live-unavailable disclosure. | Add explicit DEMONSTRATION source and UNAVAILABLE, snapshot-only metadata; retain example outputs. |

Initial price/cache tests: 14 failed and 1 passed. The additional disconnected
legacy-position test failed with a 201 response and a STOP_LOSS close despite the
feed reporting `price_feed_error`. Four demonstration disclosure tests also
failed before their patch. Six old webhook tests expecting disconnected legacy
settlement were corrected to require 503, unchanged positions, no trade history
and no candle writes. Standalone legacy management unit tests remain intact.
A method-key collision in the inventory generation script caused four transient
certification failures; the generator output was corrected using (path, methods),
without changing production or relaxing the pre-existing PH1-REQ-009 assertions.

## Canonical ownership and safety

L1: `RuntimeQuoteAuthorityV2` owns supplied bid/ask and timestamp.
`RuntimeSpreadAuthorityV2` makes the authoritative current-L1 freshness/validity
decision and delegates spread calculation to `SpreadAuthorityV2`.
`APISettings.maximum_quote_age_seconds` / `ARMS_MAXIMUM_QUOTE_AGE_SECONDS` is the
unchanged configured age policy. No second router quote source or age algorithm
was added. Storage acknowledgment (`201 stored`) is not certification of a
current quote: stale/future supplied quotes remain unusable at consumption.

Operational last-price events are a distinct existing domain:
`MarketDataHubV2 -> PriceFeedServiceV2 -> LivePositionMonitorV2 -> TradeLifecycleServiceV2`.
The direct admin market-price route enters the same feed. That feed owns event
age/order checks using the same configured age policy. It does not manufacture
bid/ask quotes. Signal age remains the existing analysis signal gate; certified
market schedules and historical series are not L1 quote sources.

Historical prices come from the existing `download_prices -> yfinance.download`
boundary, with no default-price substitution. Tests stub providers; this package
does not certify an external production data connection. Empty/invalid datasets
raise errors. Generic nonempty quote symbols can be stored; that does not grant
trading support, which remains with InstrumentProfileEngine. Unknown snapshots
return 404 rather than NQ or zero. Existing certified market-hours availability
and refresh contracts remain unchanged.

Market facts are not assigned an account identity. Existing application-bound
quote/feed/cache owners are rebuilt at account publication; the A/B/A test proves
that quote state does not leak across publications. Historical portfolio queries
remain global/request-local analytics. No new account ownership was introduced.
Existing admin authorization and webhook credentials remain the only auth paths.
Public reads remain observational. Captures cover broker orders/fills/positions,
lifecycle positions, protection/OCO, portfolio, account, journal and events.

## Availability limits

The coordinated V2 runtime continues to reject `/market/webhook`, `/market/analyze`
and `/market/open-position` with `legacy_position_manager_unavailable` before any
write. This package certifies safe containment, not restored legacy functionality.
A compatible factory can store historical candles; that acknowledgment does not
mean the operational feed accepted them. The response includes the feed's actual
processed/error result and canonical monitor result. Disconnected legacy positions
are not migrated, ignored, or settled by the webhook.

The execution-manager dashboard exposes an existing plan with original provenance
and analyzed_at, not a current market quote. Demo endpoints explicitly expose no
live availability. No market GET prepares or submits an executable order.
No LIVE execution or real-broker connection was enabled or exercised.

## Certificate and validation

TOTAL_MARKET_ROUTES=27
CLASSIFIED_MARKET_ROUTES=27
UNCLASSIFIED_MARKET_ROUTES=0
LEGACY_MARKET_ROUTES=12
UNSAFE_LEGACY_OWNERSHIP=0
DUPLICATE_FRESHNESS_AUTHORITIES=0
MISSING_DATA_FAIL_CLOSED=GREEN
STALE_DATA_FAIL_CLOSED=GREEN
UNSUPPORTED_SYMBOL_BEHAVIOR=GREEN
PROVIDER_UNAVAILABLE_BEHAVIOR=GREEN
MARKET_OBSERVATIONAL_BOUNDARY=GREEN
MARKET_AUTHORIZATION=GREEN
ACCOUNT_ISOLATION=GREEN
PH1_REQ008_REGRESSION=GREEN
PH1_REQ009_REGRESSION=GREEN

Zero duplicates refers to one decision owner per datum/domain: canonical L1
freshness and operational event admission are not interchangeable data sources.
This does not claim that the repository has one universal market-data object.

Final full backend: **5344 passed, 0 failed, 1 skipped** (118.02 seconds).
The unchanged legitimate skip is
`test_phase1_risk_authority_integration_v2.py::test_incomplete_trade_submission_fails_before_execution[/api/v2/trades/submit]`,
which targets an unregistered compatibility endpoint. Baseline/final node IDs
match exactly. No tests were newly skipped or deselected.

Direct regression: **1915 passed, 0 failed**, 218 modules (116.01 seconds).
Every module listed below was passed to pytest; no tests were deselected.
Invocation uses the repository's process-only PAPER policy fixture:

```powershell
python -c "import os,sys,pytest; from backend.tests.test_account_switch_safety_containment_v2 import POLICY; os.environ.update(POLICY); sys.exit(pytest.main(sys.argv[1:]))" -q -p no:cacheprovider --tb=short <modules below>
```

The full-suite invocation replaces `<modules below>` with `backend/tests`.
The evidence runner additionally records each test's node ID and result as JSON.
The two pytest import-rewrite warnings match baseline; no dependency change is
needed for this package. Syntax compilation of all 10 modified/new Python files
and `git diff --check` passed before staging.

## File justification

- Market router: legacy settlement containment and cached snapshot availability.
- Market-price router, request schema, price feed: enforce the existing operational
  observation contract and reject nonfinite inputs before side effects.
- Four demonstration routers: explicit source/live-availability disclosure only.
- Existing webhook tests: update obsolete route-owned settlement expectations.
- New market tests and manifest: behavior, side effects, inventory and owner proof.
- Prior API manifest: reviewed evidence refresh for affected endpoint bodies only.
- This document: certificate, root cause, test evidence and explicit limitations.

## Next evidenced Phase-1 work

Review PH1-REQ-004 risk authority and precedence gaps against current code and
certification evidence. The master matrix still records incomplete coverage for
risk-limit authority; this package does not close that separate requirement.

## Exact direct regression module list

```text
backend/tests/test_account_contract_exposure_runtime_v2.py
backend/tests/test_account_contract_position_sizing_runtime_v2.py
backend/tests/test_account_contract_runtime_limits_v2.py
backend/tests/test_account_runtime_transition_v2.py
backend/tests/test_account_switch_api_v2.py
backend/tests/test_account_switch_safety_containment_v2.py
backend/tests/test_account_switch_safety_v2.py
backend/tests/test_admin_market_boundary_v2.py
backend/tests/test_api_settings.py
backend/tests/test_api_settings_quote_freshness_policy_v2.py
backend/tests/test_asgi_runtime_integration_v2.py
backend/tests/test_backtest_account_contract_runtime_v2.py
backend/tests/test_backtest_dashboard_exporter.py
backend/tests/test_backtest_execution_simulator_v2.py
backend/tests/test_backtest_market_stage.py
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
backend/tests/test_benchmark_analytics_router.py
backend/tests/test_capm_analytics_router.py
backend/tests/test_certified_economic_news_api_settings_v2.py
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
backend/tests/test_drawdown_analytics_router.py
backend/tests/test_durable_crash_recovery_v2.py
backend/tests/test_economic_news_runtime_provider_v2.py
backend/tests/test_execution_dashboard_provider_v2.py
backend/tests/test_external_market_data_provider_v2.py
backend/tests/test_fama_french_analytics_router.py
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
backend/tests/test_parameter_stability_dashboard_exporter.py
backend/tests/test_performance_dashboard_api_v2.py
backend/tests/test_performance_dashboard_engine_v2.py
backend/tests/test_performance_dashboard_provider_v2.py
backend/tests/test_performance_dashboard_score_integration_v2.py
backend/tests/test_ph1_req008_startup_pending_recovery_v2.py
backend/tests/test_phase1_account_isolation_characterization_v2.py
backend/tests/test_phase1_account_switch_full_containment_v2.py
backend/tests/test_phase1_api_authorization_observational_contract_v2.py
backend/tests/test_phase1_api_ownership_characterization_v2.py
backend/tests/test_phase1_asgi_cli_equivalence_v2.py
backend/tests/test_phase1_market_ownership_availability_v4.py
backend/tests/test_phase1_recovery_characterization_v2.py
backend/tests/test_phase1_recovery_execution_blocking_v2.py
backend/tests/test_phase1_route_lifecycle_contract_v2.py
backend/tests/test_phase1_route_lifecycle_delegation_v2.py
backend/tests/test_phase1_runtime_characterization_v2.py
backend/tests/test_phase1_websocket_account_isolation_characterization_v2.py
backend/tests/test_phase1_websocket_authorization_contract_v2.py
backend/tests/test_portfolio_backtest_router.py
backend/tests/test_portfolio_dashboard_exporter.py
backend/tests/test_portfolio_market_router.py
backend/tests/test_portfolio_router.py
backend/tests/test_price_feed_service_v2.py
backend/tests/test_rec003_cli_startup_owner_v2.py
backend/tests/test_recovery_cli_pending_contract_v2.py
backend/tests/test_recovery_consistency_v2.py
backend/tests/test_replay_market_data_bridge_v2.py
backend/tests/test_risk_analytics_market_router.py
backend/tests/test_risk_analytics_router.py
backend/tests/test_risk_dashboard_analytics_integration_v2.py
backend/tests/test_risk_dashboard_event_publisher_v2.py
backend/tests/test_risk_event_runtime_persistence_wiring_v2.py
backend/tests/test_risk_validation_dashboard_provider_v2.py
backend/tests/test_rolling_analytics_router.py
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
backend/tests/test_safe003_missing_runtime_risk_authority_v2.py
backend/tests/test_shared_account_policy_runtime_wiring_v2.py
backend/tests/test_spread_authority_v2.py
backend/tests/test_state_recovery_service_v2.py
backend/tests/test_strategy_decision_dashboard_provider_v2.py
backend/tests/test_strategy_performance_dashboard_provider_v2.py
backend/tests/test_strategy_ranking_dashboard_provider_v2.py
backend/tests/test_strategy_selection_dashboard_provider_v2.py
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
backend/tests/test_walk_forward_dashboard_exporter.py
backend/tests/test_walk_forward_optimization_dashboard_exporter.py
```
