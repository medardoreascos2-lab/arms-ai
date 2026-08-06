from contextlib import asynccontextmanager
from backend.execution.execution_decision_engine_v2 import ExecutionDecisionEngineV2
from backend.intelligence.probability_engine_v2 import ProbabilityEngineV2
from backend.intelligence.confluence_engine_v2 import ConfluenceEngineV2
from backend.intelligence.decision_council_v2 import (
    DecisionCouncilV2,
)
from backend.intelligence.multi_timeframe_decision_engine_v2 import (
    MultiTimeframeDecisionEngineV2,
)
from backend.context.market_context_engine_v2 import (
    MarketContextEngineV2,
)
from backend.market_analysis.market_regime_engine import MarketRegimeEngine
from backend.smart_money.smart_money_engine_v2 import SmartMoneyEngineV2
from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)
from backend.analytics.trade_journal_analytics_v2 import (
    TradeJournalAnalyticsV2,
)
from backend.analytics.trade_journal_breakdown_analytics_v2 import (
    TradeJournalBreakdownAnalyticsV2,
)

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.api.trade_lifecycle_api_v2 import (
    create_trade_lifecycle_router_v2,
)
from backend.api.performance_dashboard_api_v2 import (
    create_performance_dashboard_router_v2,
)
from backend.api.dashboard_live_api_v2 import (
    create_dashboard_live_router_v2,
)
from backend.dashboard.performance_dashboard_engine_v2 import (
    PerformanceDashboardEngineV2,
)
from backend.dashboard.dashboard_live_data_service_v2 import (
    DashboardLiveDataServiceV2,
)
from backend.performance.performance_score_engine_v2 import (
    PerformanceScoreEngineV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)
from backend.execution.trade_planner_v2 import (
    TradePlannerV2,
)
from backend.execution.trade_validator_v2 import (
    TradeValidatorV2,
)
from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
)


from backend.api.dashboard_widgets_api_v2 import (
    create_dashboard_widgets_router_v2,
)

from backend.dashboard.widgets.dashboard_widget_registry_v2 import (
    DashboardWidgetRegistryV2,
)

from backend.dashboard.widgets.performance_score_widget_v2 import (
    PerformanceScoreWidgetV2,
)

from backend.dashboard.widgets.account_overview_widget_v2 import (
    AccountOverviewWidgetV2,
)

from backend.dashboard.widgets.risk_status_widget_v2 import (
    RiskStatusWidgetV2,
)

from backend.dashboard.widgets.performance_overview_widget_v2 import (
    PerformanceOverviewWidgetV2,
)

from backend.dashboard.widgets.portfolio_summary_widget_v2 import (
    PortfolioSummaryWidgetV2,
)

from backend.dashboard.widgets.trade_journal_summary_widget_v2 import (
    TradeJournalSummaryWidgetV2,
)

from backend.dashboard.widgets.analytics_widget_v2 import (
    AnalyticsWidgetV2,
)

from backend.dashboard.widgets.breakdown_widget_v2 import (
    BreakdownWidgetV2,
)



from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import (
    TradeLifecycleDashboardEventPublisherV2,
)


from backend.dashboard.risk_dashboard_event_publisher_v2 import (
    RiskDashboardEventPublisherV2,
)

from backend.dashboard.dashboard_event_bus_v2 import (
    DashboardEventBusV2,
)

from backend.dashboard.dashboard_refresh_service_v2 import (
    DashboardRefreshServiceV2,
)

from backend.dashboard.dashboard_event_dispatcher_v2 import (
    DashboardEventDispatcherV2,
)

from backend.dashboard.dashboard_auto_refresh_engine_v2 import (
    DashboardAutoRefreshEngineV2,
)





from backend.dashboard.dashboard_websocket_broadcaster_v2 import (
    DashboardWebSocketBroadcasterV2,
)

from backend.dashboard.dashboard_websocket_hub_v2 import (
    DashboardWebSocketHubV2,
)

from backend.api.dashboard_websocket_api_v2 import (
    create_dashboard_websocket_router_v2,
)



from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)


from backend.services.price_feed_service_v2 import (
    PriceFeedServiceV2,
)


from backend.market_data.market_data_hub_v2 import (
    MarketDataHubV2,
)

from backend.market_state.market_state_engine_v2 import (
    MarketStateEngineV2,
)

from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
)

from backend.execution.realized_pnl_engine_v2 import (
    RealizedPnLEngineV2,
)

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)

from backend.execution.trailing_stop_engine_v2 import (
    TrailingStopEngineV2,
)

from backend.api.routers.backtesting_jobs_api_v2 import (
    create_backtesting_jobs_router_v2,
)
from backend.api.routers.backtesting_controller_api_v2 import (
    create_backtesting_controller_router_v2,
)
from backend.api.routers.backtesting_dashboard_api_v2 import (
    create_backtesting_dashboard_router_v2,
)
from backend.api.routers.backtesting_metrics_api_v2 import (
    create_backtesting_metrics_router_v2,
)
from backend.backtesting.backtesting_metrics_engine_v2 import (
    BacktestingMetricsEngineV2,
)
from backend.backtesting.backtesting_metrics_provider_v2 import (
    BacktestingMetricsProviderV2,
)
from backend.backtesting.backtesting_performance_report_v2 import (
    BacktestingPerformanceReportV2,
)
from backend.backtesting.backtesting_performance_report_provider_v2 import (
    BacktestingPerformanceReportProviderV2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_executor_v2 import (
    BacktestingJobExecutorV2,
)
from backend.backtesting.backtesting_worker_v2 import (
    BacktestingWorkerV2,
)
from backend.backtesting.backtesting_background_worker_v2 import (
    BacktestingBackgroundWorkerV2,
)
from backend.backtesting.backtesting_controller_v2 import (
    BacktestingControllerV2,
)

from backend.api.routers.backtesting_api_v2 import (
    BacktestingUnavailableOrchestratorV2,
    create_backtesting_router_v2,
)

from fastapi import FastAPI


from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)


from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)

from backend.backtesting.strategy_ranking_service_v2 import (
    StrategyRankingServiceV2,
)


from backend.backtesting.strategy_certification_registry_service_v2 import (
    StrategyCertificationRegistryServiceV2,
)


from backend.backtesting.strategy_ranking_dashboard_provider_v2 import (
    StrategyRankingDashboardProviderV2,
)


from backend.backtesting.strategy_selection_service_v2 import (
    StrategySelectionServiceV2,
)


from backend.backtesting.strategy_selection_dashboard_provider_v2 import (
    StrategySelectionDashboardProviderV2,
)


from backend.backtesting.strategy_selection_engine_v2 import (
    StrategySelectionEngineV2,
)


from backend.backtesting.strategy_recommendation_engine_v2 import (
    StrategyRecommendationEngineV2,
)

from backend.backtesting.strategy_recommendation_service_v2 import (
    StrategyRecommendationServiceV2,
)

from backend.backtesting.strategy_recommendation_dashboard_provider_v2 import (
    StrategyRecommendationDashboardProviderV2,
)

from backend.backtesting.strategy_decision_engine_v2 import (
    StrategyDecisionEngineV2,
)

from backend.backtesting.strategy_decision_service_v2 import (
    StrategyDecisionServiceV2,
)

from backend.backtesting.strategy_decision_dashboard_provider_v2 import (
    StrategyDecisionDashboardProviderV2,
)

from backend.backtesting.trade_plan_engine_v2 import (
    TradePlanEngineV2,
)

from backend.backtesting.trade_plan_service_v2 import (
    TradePlanServiceV2,
)

from backend.backtesting.trade_plan_dashboard_provider_v2 import (
    TradePlanDashboardProviderV2,
)

from backend.backtesting.risk_validation_engine_v2 import (
    RiskValidationEngineV2,
)

from backend.backtesting.risk_validation_service_v2 import (
    RiskValidationServiceV2,
)

from backend.backtesting.risk_validation_dashboard_provider_v2 import (
    RiskValidationDashboardProviderV2,
)

from backend.execution.execution_engine_v2 import (
    ExecutionEngineV2,
)

from backend.execution.execution_service_v2 import (
    ExecutionServiceV2,
)

from backend.execution.execution_dashboard_provider_v2 import (
    ExecutionDashboardProviderV2,
)

from backend.execution.performance_service_v2 import (
    PerformanceServiceV2,
)

from backend.execution.performance_analyzer_v2 import (
    PerformanceAnalyzerV2,
)

from backend.execution.performance_dashboard_provider_v2 import (
    PerformanceDashboardProviderV2,
)

from backend.execution.backtesting_performance_provider_v2 import (
    BacktestingPerformanceProviderV2,
)


from backend.analytics.strategy_performance_analyzer_v2 import (
    StrategyPerformanceAnalyzerV2,
)

from backend.analytics.strategy_performance_service_v2 import (
    StrategyPerformanceServiceV2,
)

from backend.analytics.strategy_performance_dashboard_provider_v2 import (
    StrategyPerformanceDashboardProviderV2,
)


from backend.analytics.backtesting_strategy_performance_provider_v2 import (
    BacktestingStrategyPerformanceProviderV2,
)


from backend.api.routers.strategy_ranking_api_v2 import (
    create_strategy_ranking_router_v2,
)


from backend.api.routers.strategy_recommendation_api_v2 import (
    create_strategy_recommendation_router_v2,
)



from backend.api.router_loader_v2 import (
    register_router_v2,
)




from backend.backtesting.strategy_registry_dashboard_provider_v2 import (
    StrategyRegistryDashboardProviderV2,
)

from backend.api.routers.strategy_registry_api_v2 import (
    create_strategy_registry_router_v2,
)



from fastapi.middleware.cors import CORSMiddleware

from backend.account_risk.account_risk_guard import (
    AccountRiskGuard,
)
from backend.api.error_handlers import (
    register_exception_handlers,
)
from backend.api.logging_middleware import (
    register_logging_middleware,
)
from backend.api.routers.ai import (
    router as ai_router,
)
from backend.api.routers.market import (
    router as market_router,
)
from backend.api.routers.portfolio import (
    router as portfolio_router,
)
from backend.config.api_settings import (
    APISettings,
)
from backend.execution.execution_decision_engine import (
    ExecutionDecisionEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
)
from backend.execution.trade_execution_engine import (
    TradeExecutionEngine,
)
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)

from backend.trend.trend_engine_v2 import (
    TrendEngineV2,
)
from backend.services.live_signal_store import (
    LiveSignalStore,
)
from backend.services.signal_history_store import (
    SignalHistoryStore,
)
from backend.risk_management.position_sizing_engine import (
    PositionSizingEngine,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def create_app(
    settings: APISettings | None = None,
    live_candle_store: LiveCandleStore
    | None = None,
    live_analysis_store: LiveAnalysisStore
    | None = None,
    live_signal_store: LiveSignalStore
    | None = None,
    signal_history_store: SignalHistoryStore
    | None = None,
    signal_execution_manager:
    SignalExecutionManager
    | None = None,
    trade_execution_engine:
    TradeExecutionEngine
    | None = None,
    position_manager:
    PositionManager
    | None = None,
    trade_history_store:
    TradeHistoryStore
    | None = None,
    account_risk_guard:
    AccountRiskGuard
    | None = None,
    position_sizing_engine:
    PositionSizingEngine
    | None = None,
    execution_decision_engine:
    ExecutionDecisionEngine
    | None = None,
    smart_money_engine_v2:
    SmartMoneyEngineV2
    | None = None,
    market_regime_engine:
    MarketRegimeEngine
    | None = None,
    confluence_engine_v2:
    ConfluenceEngineV2
    | None = None,
    probability_engine_v2:
    ProbabilityEngineV2
    | None = None,
    execution_decision_engine_v2:
    ExecutionDecisionEngineV2
    | None = None,
    decision_council_v2:
    DecisionCouncilV2
    | None = None,
    multi_timeframe_decision_engine_v2:
    MultiTimeframeDecisionEngineV2
    | None = None,
    market_context_engine_v2:
    MarketContextEngineV2
    | None = None,
    trade_planner_v2:
    TradePlannerV2
    | None = None,
    trade_validator_v2:
    TradeValidatorV2
    | None = None,
    signal_generator_v2:
    SignalGeneratorV2
    | None = None,
    trade_lifecycle_service_v2:
    TradeLifecycleServiceV2
    | None = None,
    runtime_context:
    RuntimeContextV2
    | None = None,
    backtesting_orchestrator_v2=None,
    backtesting_job_manager_v2=None,
    backtesting_job_queue_v2=None,
    backtesting_job_executor_v2=None,
    backtesting_worker_v2=None,
    backtesting_background_worker_v2=None,
    backtesting_controller_v2=None,
    start_backtesting_background_worker=False,
) -> FastAPI:
    if settings is None:
        settings = APISettings()

    if not isinstance(
        settings,
        APISettings,
    ):
        raise TypeError(
            "settings debe ser APISettings."
        )

    if (
        runtime_context is not None
        and not isinstance(
            runtime_context,
            RuntimeContextV2,
        )
    ):
        raise TypeError(
            "runtime_context debe ser "
            "RuntimeContextV2."
        )

    if runtime_context is not None:
        context_lifecycle_service = (
            runtime_context
            .trade_lifecycle_service
        )

        if (
            trade_lifecycle_service_v2
            is not None
            and trade_lifecycle_service_v2
            is not context_lifecycle_service
        ):
            raise ValueError(
                "trade_lifecycle_service_v2 "
                "entra en conflicto con "
                "runtime_context."
            )

        trade_lifecycle_service_v2 = (
            context_lifecycle_service
        )

    if live_candle_store is None:
        live_candle_store = (
            LiveCandleStore()
        )

    if not isinstance(
        live_candle_store,
        LiveCandleStore,
    ):
        raise TypeError(
            "live_candle_store debe ser "
            "LiveCandleStore."
        )

    if live_analysis_store is None:
        live_analysis_store = (
            LiveAnalysisStore()
        )

    if not isinstance(
        live_analysis_store,
        LiveAnalysisStore,
    ):
        raise TypeError(
            "live_analysis_store debe ser "
            "LiveAnalysisStore."
        )

    if live_signal_store is None:
        live_signal_store = (
            LiveSignalStore()
        )

    if not isinstance(
        live_signal_store,
        LiveSignalStore,
    ):
        raise TypeError(
            "live_signal_store debe ser "
            "LiveSignalStore."
        )

    if signal_history_store is None:
        signal_history_store = (
            SignalHistoryStore()
        )

    if not isinstance(
        signal_history_store,
        SignalHistoryStore,
    ):
        raise TypeError(
            "signal_history_store debe ser "
            "SignalHistoryStore."
        )

    if signal_execution_manager is None:
        signal_execution_manager = (
            SignalExecutionManager(
                cooldown_minutes=15
            )
        )

    if not isinstance(
        signal_execution_manager,
        SignalExecutionManager,
    ):
        raise TypeError(
            "signal_execution_manager debe ser "
            "SignalExecutionManager."
        )

    if trade_execution_engine is None:
        trade_execution_engine = (
            TradeExecutionEngine(
                mode="SIMULATED"
            )
        )

    if not isinstance(
        trade_execution_engine,
        TradeExecutionEngine,
    ):
        raise TypeError(
            "trade_execution_engine debe ser "
            "TradeExecutionEngine."
        )

    if position_manager is None:
        position_manager = (
            PositionManager()
        )

    if not isinstance(
        position_manager,
        PositionManager,
    ):
        raise TypeError(
            "position_manager debe ser "
            "PositionManager."
        )

    if trade_history_store is None:
        trade_history_store = (
            TradeHistoryStore()
        )

    if not isinstance(
        trade_history_store,
        TradeHistoryStore,
    ):
        raise TypeError(
            "trade_history_store debe ser "
            "TradeHistoryStore."
        )

    if account_risk_guard is None:
        account_risk_guard = (
            AccountRiskGuard(
                daily_loss_limit=3000.0,
                max_trades_per_day=4,
                max_consecutive_losses=3,
                max_open_positions=1,
                max_risk_per_trade=250.0,
            )
        )

    if not isinstance(
        account_risk_guard,
        AccountRiskGuard,
    ):
        raise TypeError(
            "account_risk_guard debe ser "
            "AccountRiskGuard."
        )

    if position_sizing_engine is None:
        position_sizing_engine = (
            PositionSizingEngine(
                minimum_contracts=1,
                maximum_contracts=20,
            )
        )

    if not isinstance(
        position_sizing_engine,
        PositionSizingEngine,
    ):
        raise TypeError(
            "position_sizing_engine debe ser "
            "PositionSizingEngine."
        )

    if execution_decision_engine is None:
        execution_decision_engine = (
            ExecutionDecisionEngine(
                minimum_confidence=0.70,
            )
        )

    if not isinstance(
        execution_decision_engine,
        ExecutionDecisionEngine,
    ):
        raise TypeError(
            "execution_decision_engine debe ser "
            "ExecutionDecisionEngine."
        )

    # VALIDACIONES DE MOTORES V2

    if (
        smart_money_engine_v2
        is not None
        and not isinstance(
            smart_money_engine_v2,
            SmartMoneyEngineV2,
        )
    ):
        raise TypeError(
            "smart_money_engine_v2 debe ser "
            "SmartMoneyEngineV2."
        )

    if (
        market_regime_engine
        is not None
        and not isinstance(
            market_regime_engine,
            MarketRegimeEngine,
        )
    ):
        raise TypeError(
            "market_regime_engine debe ser "
            "MarketRegimeEngine."
        )

    if (
        confluence_engine_v2
        is not None
        and not isinstance(
            confluence_engine_v2,
            ConfluenceEngineV2,
        )
    ):
        raise TypeError(
            "confluence_engine_v2 debe ser "
            "ConfluenceEngineV2."
        )

    if (
        probability_engine_v2
        is not None
        and not isinstance(
            probability_engine_v2,
            ProbabilityEngineV2,
        )
    ):
        raise TypeError(
            "probability_engine_v2 debe ser "
            "ProbabilityEngineV2."
        )

    if (
        execution_decision_engine_v2
        is not None
        and not isinstance(
            execution_decision_engine_v2,
            ExecutionDecisionEngineV2,
        )
    ):
        raise TypeError(
            "execution_decision_engine_v2 debe ser "
            "ExecutionDecisionEngineV2."
        )

    if (
        decision_council_v2
        is not None
        and not isinstance(
            decision_council_v2,
            DecisionCouncilV2,
        )
    ):
        raise TypeError(
            "decision_council_v2 debe ser "
            "DecisionCouncilV2."
        )

    if (
        multi_timeframe_decision_engine_v2
        is not None
        and not isinstance(
            multi_timeframe_decision_engine_v2,
            MultiTimeframeDecisionEngineV2,
        )
    ):
        raise TypeError(
            "multi_timeframe_decision_engine_v2 "
            "debe ser "
            "MultiTimeframeDecisionEngineV2."
        )

    if (
        market_context_engine_v2
        is not None
        and not isinstance(
            market_context_engine_v2,
            MarketContextEngineV2,
        )
    ):
        raise TypeError(
            "market_context_engine_v2 debe ser "
            "MarketContextEngineV2."
        )

    # PIPELINE INSTITUCIONAL V2

    if (
        trade_planner_v2
        is not None
        and not isinstance(
            trade_planner_v2,
            TradePlannerV2,
        )
    ):
        raise TypeError(
            "trade_planner_v2 debe ser "
            "TradePlannerV2."
        )

    if (
        trade_validator_v2
        is not None
        and not isinstance(
            trade_validator_v2,
            TradeValidatorV2,
        )
    ):
        raise TypeError(
            "trade_validator_v2 debe ser "
            "TradeValidatorV2."
        )

    if (
        signal_generator_v2
        is not None
        and not isinstance(
            signal_generator_v2,
            SignalGeneratorV2,
        )
    ):
        raise TypeError(
            "signal_generator_v2 debe ser "
            "SignalGeneratorV2."
        )

    if trade_planner_v2 is None:
        trade_planner_v2 = (
            TradePlannerV2(
                minimum_reward_risk_ratio=2.0,
            )
        )

    if trade_validator_v2 is None:
        trade_validator_v2 = (
            TradeValidatorV2(
                minimum_reward_risk_ratio=2.0,
                minimum_stop_points=2.0,
                maximum_stop_points=50.0,
                maximum_spread_points=1.0,
                minimum_atr_points=3.0,
                maximum_signal_age_seconds=30,
            )
        )

    if signal_generator_v2 is None:
        signal_generator_v2 = (
            SignalGeneratorV2(
                minimum_probability=0.80,
                minimum_confluence_score=0.80,
                allowed_grades={
                    "A+",
                    "A",
                },
            )
        )

    # TRADE LIFECYCLE SERVICE V2

    if (
        trade_lifecycle_service_v2
        is not None
        and not isinstance(
            trade_lifecycle_service_v2,
            TradeLifecycleServiceV2,
        )
    ):
        raise TypeError(
            "trade_lifecycle_service_v2 "
            "debe ser TradeLifecycleServiceV2."
        )

    if trade_lifecycle_service_v2 is None:
        account_state_manager_v2 = (
            AccountStateManagerV2(
                starting_balance=17000.0,
                maximum_daily_loss=3000.0,
                maximum_total_drawdown=4500.0,
            )
        )

        portfolio_manager_v2 = (
            PortfolioManagerV2(
                starting_balance=17000.0,
                account_state_manager_v2=(
                    account_state_manager_v2
                ),
            )
        )

        trade_journal_v2 = (
            TradeJournalV2(
                analytics_v2=(
                    TradeJournalAnalyticsV2()
                ),
                breakdown_analytics_v2=(
                    TradeJournalBreakdownAnalyticsV2()
                ),
            )
        )

        trade_lifecycle_service_v2 = (
            TradeLifecycleServiceV2(
                execution_manager=(
                    ExecutionManagerV2(
                        execution_mode="PAPER",
                        maximum_contracts=20,
                    )
                ),
                paper_execution_engine=(
                    PaperExecutionEngineV2(
                        fill_market_orders_immediately=True,
                        slippage_points=0.25,
                    )
                ),
                position_manager=(
                    PositionManagerV2(
                        point_value=2.0,
                    )
                ),
                trade_history_manager=(
                    TradeHistoryManagerV2()
                ),
                performance_analytics=(
                    PerformanceAnalyticsV2(
                        risk_free_rate=0.0,
                        trading_days_per_year=252,
                    )
                ),
                portfolio_manager_v2=(
                    portfolio_manager_v2
                ),
                trade_journal_v2=(
                    trade_journal_v2
                ),
                starting_balance=17000.0,
            )
        )

    @asynccontextmanager
    async def lifespan(app):

        if start_backtesting_background_worker:
            (
                app.state
                .backtesting_background_worker_v2
                .start()
            )

        try:
            yield

        finally:

            if start_backtesting_background_worker:
                (
                    app.state
                    .backtesting_background_worker_v2
                    .stop(
                        timeout=5.0,
                    )
                )

    app = FastAPI(
        lifespan=lifespan,
        title=settings.title,
        version=settings.version,
        debug=settings.debug,
    )

    app.state.strategy_registry_v2 = (
        StrategyRegistryV2()
    )


    app.state.strategy_certification_registry_service_v2 = (
        StrategyCertificationRegistryServiceV2(
            registry=(
                app.state
                .strategy_registry_v2
            ),
        )
    )


    app.state.strategy_certification_registry_service_v2.register_certified_strategy(
        {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "version": "1.0",
            "status": "CERTIFIED",
            "grade": "A",
            "validation_score": 90,
            "performance_score": 95,
        }
    )


    app.state.strategy_registry_dashboard_provider_v2 = (
        StrategyRegistryDashboardProviderV2(
            registry=(
                app.state
                .strategy_registry_v2
            ),
        )
    )

    app.state.strategy_ranking_service_v2 = (
        StrategyRankingServiceV2(
            registry=(
                app.state
                .strategy_registry_v2
            ),
            ranking_engine=(
                StrategyRankingEngineV2()
            ),
        )
    )

    app.state.strategy_ranking_dashboard_provider_v2 = (
        StrategyRankingDashboardProviderV2(
            strategy_ranking_service=(
                app.state
                .strategy_ranking_service_v2
            ),
        )
    )


    app.state.strategy_selection_service_v2 = (
        StrategySelectionServiceV2(
            ranking_service=(
                app.state
                .strategy_ranking_service_v2
            ),
            selection_engine=(
                StrategySelectionEngineV2()
            ),
        )
    )


    app.state.strategy_selection_dashboard_provider_v2 = (
        StrategySelectionDashboardProviderV2(
            strategy_selection_service=(
                app.state
                .strategy_selection_service_v2
            ),
        )
    )


    app.state.strategy_recommendation_dashboard_provider_v2 = (
        StrategyRecommendationDashboardProviderV2(
            recommendation_service=(
                StrategyRecommendationServiceV2(
                    ranking_service=(
                        app.state
                        .strategy_ranking_service_v2
                    ),
                    recommendation_engine=(
                        StrategyRecommendationEngineV2()
                    ),
                )
            ),
        )
    )

    app.state.strategy_decision_service_v2 = (
        StrategyDecisionServiceV2(
            selection_service=(
                app.state
                .strategy_selection_service_v2
            ),
            decision_engine=(
                StrategyDecisionEngineV2()
            ),
        )
    )

    app.state.strategy_decision_dashboard_provider_v2 = (
        StrategyDecisionDashboardProviderV2(
            decision_service=(
                app.state
                .strategy_decision_service_v2
            ),
        )
    )

    app.state.trade_plan_service_v2 = (
        TradePlanServiceV2(
            decision_service=(
                app.state
                .strategy_decision_service_v2
            ),
            trade_plan_engine=(
                TradePlanEngineV2()
            ),
        )
    )

    app.state.risk_validation_service_v2 = (
        RiskValidationServiceV2(
            trade_plan_service=(
                app.state
                .trade_plan_service_v2
            ),
            risk_engine=(
                RiskValidationEngineV2()
            ),
        )
    )

    app.state.execution_service_v2 = (
        ExecutionServiceV2(
            trade_plan_service=(
                app.state
                .trade_plan_service_v2
            ),
            risk_service=(
                app.state
                .risk_validation_service_v2
            ),
            execution_engine=(
                ExecutionEngineV2()
            ),
        )
    )


    app.state.execution_dashboard_provider_v2 = (
        ExecutionDashboardProviderV2(
            execution_service=(
                app.state
                .execution_service_v2
            ),
        )
    )

    app.state.trade_plan_dashboard_provider_v2 = (
        TradePlanDashboardProviderV2(
            trade_plan_service=(
                app.state
                .trade_plan_service_v2
            ),
        )
    )

    app.state.risk_validation_dashboard_provider_v2 = (
        RiskValidationDashboardProviderV2(
            risk_service=(
                RiskValidationServiceV2(
                    trade_plan_service=(
                        TradePlanServiceV2(
                            decision_service=(
                                StrategyDecisionServiceV2(
                                    recommendation_service=(
                                        StrategyRecommendationServiceV2(
                                            ranking_service=(
                                                app.state
                                                .strategy_ranking_service_v2
                                            ),
                                            recommendation_engine=(
                                                StrategyRecommendationEngineV2()
                                            ),
                                        )
                                    ),
                                    decision_engine=(
                                        StrategyDecisionEngineV2()
                                    ),
                                )
                            ),
                            trade_plan_engine=(
                                TradePlanEngineV2()
                            ),
                        )
                    ),
                    risk_engine=(
                        RiskValidationEngineV2()
                    ),
                )
            ),
        )
    )

    app.state.strategy_recommendation_service_v2 = (
        StrategyRecommendationServiceV2(
            ranking_service=(
                app.state
                .strategy_ranking_service_v2
            ),
            recommendation_engine=(
                StrategyRecommendationEngineV2()
            ),
        )
    )

    app.state.runtime_context_v2 = (
        runtime_context
    )

    app.state.smart_money_engine_v2 = (
        smart_money_engine_v2
        or SmartMoneyEngineV2()
    )

    app.state.market_regime_engine = (
        market_regime_engine
        or MarketRegimeEngine(
            trend_threshold=0.60,
            high_volatility_threshold=0.80,
            low_volatility_threshold=0.20,
            compression_threshold=0.15,
        )
    )

    app.state.confluence_engine_v2 = (
        confluence_engine_v2
        or ConfluenceEngineV2()
    )

    app.state.probability_engine_v2 = (
        probability_engine_v2
        or ProbabilityEngineV2(
            minimum_approval_probability=0.80,
            very_high_threshold=0.90,
            high_threshold=0.80,
            medium_threshold=0.65,
        )
    )

    app.state.execution_decision_engine_v2 = (
        execution_decision_engine_v2
        or ExecutionDecisionEngineV2(
            minimum_probability=0.80,
            minimum_confluence_score=0.80,
        )
    )

    app.state.decision_council_v2 = (
        decision_council_v2
        or DecisionCouncilV2()
    )


    app.state.live_candle_store = (
        live_candle_store
    )

    app.state.trend_engine_v2 = (
        TrendEngineV2(
            live_candle_store=(
                app.state.live_candle_store
            ),
            fast_period=10,
            slow_period=50,
            slope_lookback=5,
            sideways_threshold_percent=(
                0.0005
            ),
        )
    )

    app.state.multi_timeframe_decision_engine_v2 = (
        multi_timeframe_decision_engine_v2
        or MultiTimeframeDecisionEngineV2(
            trend_engine=(
                app.state.trend_engine_v2
            ),
            timeframe_weights={
                "1M": 0.10,
                "5M": 0.25,
                "15M": 0.30,
                "1H": 0.35,
            },
            minimum_ready_weight=0.65,
            neutral_threshold=0.15,
            conflict_weight_threshold=0.25,
            dominance_margin=0.35,
        )
    )

    app.state.market_context_engine_v2 = (
        market_context_engine_v2
        or MarketContextEngineV2(
            minimum_candles=5,
            internal_range_lookback=10,
            near_extreme_threshold=0.10,
            equilibrium_tolerance=0.05,
            decision_threshold=0.25,
        )
    )

    app.state.live_analysis_store = (
        live_analysis_store
    )

    app.state.live_signal_store = (
        live_signal_store
    )

    app.state.signal_history_store = (
        signal_history_store
    )

    app.state.signal_execution_manager = (
        signal_execution_manager
    )

    app.state.trade_execution_engine = (
        trade_execution_engine
    )

    app.state.position_manager = (
        position_manager
    )

    app.state.trade_history_store = (
        trade_history_store
    )

    app.state.account_risk_guard = (
        account_risk_guard
    )

    app.state.position_sizing_engine = (
        position_sizing_engine
    )

    app.state.execution_decision_engine = (
        execution_decision_engine
    )

    app.state.trade_lifecycle_service_v2 = (
        trade_lifecycle_service_v2
    )

    app.state.trade_planner_v2 = (
        trade_planner_v2
    )

    app.state.trade_validator_v2 = (
        trade_validator_v2
    )

    app.state.signal_generator_v2 = (
        signal_generator_v2
    )

    app.state.execution_manager_v2 = getattr(
        app.state.trade_lifecycle_service_v2,
        "execution_manager",
        None,
    )

    app.state.paper_execution_engine_v2 = getattr(
        app.state.trade_lifecycle_service_v2,
        "paper_execution_engine",
        None,
    )

    app.state.broker_connector_v2 = getattr(
        app.state.trade_lifecycle_service_v2,
        "broker_connector_v2",
        None,
    )

    if not isinstance(
        app.state.broker_connector_v2,
        BrokerConnectorV2,
    ):
        raise RuntimeError(
            "El lifecycle no expone un "
            "BrokerConnectorV2 válido."
        )

    if not isinstance(
        app.state.execution_manager_v2,
        ExecutionManagerV2,
    ):
        raise RuntimeError(
            "El lifecycle no expone un "
            "ExecutionManagerV2 válido."
        )

    if not isinstance(
        app.state.paper_execution_engine_v2,
        PaperExecutionEngineV2,
    ):
        raise RuntimeError(
            "El lifecycle no expone un "
            "PaperExecutionEngineV2 válido."
        )

    lifecycle_portfolio_manager_v2 = getattr(
        app.state.trade_lifecycle_service_v2,
        "portfolio_manager_v2",
        None,
    )

    lifecycle_trade_journal_v2 = getattr(
        app.state.trade_lifecycle_service_v2,
        "trade_journal_v2",
        None,
    )

    lifecycle_account_state_manager_v2 = (
        getattr(
            lifecycle_portfolio_manager_v2,
            "account_state_manager_v2",
            None,
        )
        if lifecycle_portfolio_manager_v2
        is not None
        else None
    )

    app.state.account_state_manager_v2 = (
        lifecycle_account_state_manager_v2
    )

    app.state.portfolio_manager_v2 = (
        lifecycle_portfolio_manager_v2
    )

    app.state.trade_journal_v2 = (
        lifecycle_trade_journal_v2
    )

    app.state.performance_service_v2 = (
        PerformanceServiceV2(
            journal=(
                app.state
                .trade_journal_v2
            ),
            analyzer=(
                PerformanceAnalyzerV2()
            ),
        )
    )


    app.state.performance_dashboard_provider_v2 = (
        PerformanceDashboardProviderV2(
            performance_service=(
                app.state
                .performance_service_v2
            ),
        )
    )

    app.state.strategy_performance_service_v2 = (
        StrategyPerformanceServiceV2(
            journal=(
                app.state
                .trade_journal_v2
            ),
            analyzer=(
                StrategyPerformanceAnalyzerV2()
            ),
        )
    )


    app.state.strategy_performance_dashboard_provider_v2 = (
        StrategyPerformanceDashboardProviderV2(
            strategy_performance_service=(
                BacktestingStrategyPerformanceProviderV2()
            ),
        )
    )


    app.state.backtesting_performance_provider_v2 = (
        BacktestingPerformanceProviderV2()
    )


    app.state.performance_dashboard_engine_v2 = (
        PerformanceDashboardEngineV2(
            account_state_manager_v2=(
                lifecycle_account_state_manager_v2
            ),
            portfolio_manager_v2=(
                lifecycle_portfolio_manager_v2
            ),
            trade_journal_v2=(
                lifecycle_trade_journal_v2
            ),
            performance_score_engine_v2=(
                PerformanceScoreEngineV2()
            ),
        )
    )

    app.state.dashboard_live_data_service_v2 = (
        DashboardLiveDataServiceV2(
            dashboard_engine_v2=(
                app.state
                .performance_dashboard_engine_v2
            ),
        )
    )

    app.state.live_position_monitor_v2 = (
        LivePositionMonitorV2(
            trade_lifecycle_service=(
                app.state.trade_lifecycle_service_v2
            ),
            partial_take_profit_engine=(
                PartialTakeProfitEngineV2(
                    trigger_profit_points=20.0,
                    close_fraction=0.50,
                )
            ),
            realized_pnl_engine=(
                RealizedPnLEngineV2(
                    point_value=2.0,
                )
            ),
            break_even_engine=(
                BreakEvenEngineV2(
                    trigger_profit_points=15.0,
                    offset_points=1.0,
                )
            ),
            trailing_stop_engine=(
                TrailingStopEngineV2(
                    activation_profit_points=30.0,
                    trailing_distance_points=10.0,
                )
            ),
            portfolio_manager_v2=(
                lifecycle_portfolio_manager_v2
            ),
        )
    )


    app.state.price_feed_service_v2 = (
        PriceFeedServiceV2(
            live_position_monitor_v2=(
                app.state.live_position_monitor_v2
            ),
        )
    )


    app.state.market_state_engine_v2 = (
        MarketStateEngineV2()
    )

    app.state.market_data_hub_v2 = (
        MarketDataHubV2(
            price_feed_service_v2=(
                app.state.price_feed_service_v2
            ),
            market_state_engine_v2=(
                app.state.market_state_engine_v2
            ),
            reject_duplicates=True,
        )
    )


    app.state.dashboard_widget_registry_v2 = (
        DashboardWidgetRegistryV2(
            widgets=[
                PerformanceScoreWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                AccountOverviewWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                RiskStatusWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                PerformanceOverviewWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                PortfolioSummaryWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                TradeJournalSummaryWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                AnalyticsWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
                BreakdownWidgetV2(
                    dashboard_live_data_service_v2=(
                        app.state
                        .dashboard_live_data_service_v2
                    ),
                ),
            ],
        )
    )

    app.state.dashboard_event_bus_v2 = (
        DashboardEventBusV2()
    )


    app.state.dashboard_trade_event_publisher_v2 = (
        TradeLifecycleDashboardEventPublisherV2(
            event_bus_v2=(
                app.state.dashboard_event_bus_v2
            ),
        )
    )

    app.state.trade_lifecycle_service_v2.dashboard_event_publisher_v2 = (
        app.state.dashboard_trade_event_publisher_v2
    )


    app.state.dashboard_risk_event_publisher_v2 = (
        RiskDashboardEventPublisherV2(
            event_bus_v2=(
                app.state.dashboard_event_bus_v2
            ),
        )
    )

    app.state.trade_lifecycle_service_v2.risk_dashboard_event_publisher_v2 = (
        app.state.dashboard_risk_event_publisher_v2
    )

    app.state.dashboard_refresh_service_v2 = (
        DashboardRefreshServiceV2(
            live_data_service_v2=(
                app.state
                .dashboard_live_data_service_v2
            ),
            widget_registry_v2=(
                app.state
                .dashboard_widget_registry_v2
            ),
        )
    )

    app.state.dashboard_websocket_hub_v2 = (
        DashboardWebSocketHubV2()
    )

    app.state.dashboard_websocket_broadcaster_v2 = (
        DashboardWebSocketBroadcasterV2(
            refresh_service_v2=(
                app.state
                .dashboard_refresh_service_v2
            ),
            websocket_hub_v2=(
                app.state
                .dashboard_websocket_hub_v2
            ),
        )
    )

    app.state.dashboard_event_dispatcher_v2 = (
        DashboardEventDispatcherV2(
            event_bus_v2=(
                app.state
                .dashboard_event_bus_v2
            ),
            refresh_service_v2=(
                app.state
                .dashboard_refresh_service_v2
            ),
            websocket_broadcaster_v2=(
                app.state
                .dashboard_websocket_broadcaster_v2
            ),
        )
    )

    app.state.dashboard_auto_refresh_engine_v2 = (
        DashboardAutoRefreshEngineV2(
            event_bus_v2=(
                app.state
                .dashboard_event_bus_v2
            ),
            event_dispatcher_v2=(
                app.state
                .dashboard_event_dispatcher_v2
            ),
            refresh_service_v2=(
                app.state
                .dashboard_refresh_service_v2
            ),
        )
    )

    app.state.dashboard_auto_refresh_start_result_v2 = (
        app.state
        .dashboard_auto_refresh_engine_v2
        .start()
    )

    app.state.webhook_token = (
        settings.webhook_token
    )

    if backtesting_job_manager_v2 is None:
        backtesting_job_manager_v2 = (
            BacktestingJobManagerV2()
        )

    if not isinstance(
        backtesting_job_manager_v2,
        BacktestingJobManagerV2,
    ):
        raise TypeError(
            "backtesting_job_manager_v2 debe ser "
            "BacktestingJobManagerV2."
        )

    app.state.backtesting_job_manager_v2 = (
        backtesting_job_manager_v2
    )

    if backtesting_job_queue_v2 is None:
        backtesting_job_queue_v2 = (
            BacktestingJobQueueV2(
                job_manager=(
                    app.state
                    .backtesting_job_manager_v2
                ),
            )
        )

    if not isinstance(
        backtesting_job_queue_v2,
        BacktestingJobQueueV2,
    ):
        raise TypeError(
            "backtesting_job_queue_v2 debe ser "
            "BacktestingJobQueueV2."
        )

    if (
        backtesting_job_queue_v2.job_manager
        is not app.state.backtesting_job_manager_v2
    ):
        raise ValueError(
            "backtesting_job_queue_v2 debe utilizar "
            "el mismo backtesting_job_manager_v2."
        )

    app.state.backtesting_job_queue_v2 = (
        backtesting_job_queue_v2
    )

    if backtesting_orchestrator_v2 is None:
        backtesting_orchestrator_v2 = (
            BacktestingUnavailableOrchestratorV2()
        )

    if not callable(
        getattr(
            backtesting_orchestrator_v2,
            "run",
            None,
        )
    ):
        raise TypeError(
            "backtesting_orchestrator_v2 "
            "debe implementar run()."
        )

    app.state.backtesting_orchestrator_v2 = (
        backtesting_orchestrator_v2
    )

    if backtesting_job_executor_v2 is None:
        backtesting_job_executor_v2 = (
            BacktestingJobExecutorV2(
                orchestrator=(
                    app.state
                    .backtesting_orchestrator_v2
                ),
            )
        )

    if not isinstance(
        backtesting_job_executor_v2,
        BacktestingJobExecutorV2,
    ):
        raise TypeError(
            "backtesting_job_executor_v2 debe ser "
            "BacktestingJobExecutorV2."
        )

    if (
        backtesting_job_executor_v2.orchestrator
        is not app.state.backtesting_orchestrator_v2
    ):
        raise ValueError(
            "backtesting_job_executor_v2 debe utilizar "
            "el mismo backtesting_orchestrator_v2."
        )

    app.state.backtesting_job_executor_v2 = (
        backtesting_job_executor_v2
    )

    if backtesting_worker_v2 is None:
        backtesting_worker_v2 = (
            BacktestingWorkerV2(
                queue=(
                    app.state
                    .backtesting_job_queue_v2
                ),
                executor=(
                    app.state
                    .backtesting_job_executor_v2
                ),
            )
        )

    if not isinstance(
        backtesting_worker_v2,
        BacktestingWorkerV2,
    ):
        raise TypeError(
            "backtesting_worker_v2 debe ser "
            "BacktestingWorkerV2."
        )

    if (
        backtesting_worker_v2.queue
        is not app.state.backtesting_job_queue_v2
    ):
        raise ValueError(
            "backtesting_worker_v2 debe utilizar "
            "la misma backtesting_job_queue_v2."
        )

    if (
        backtesting_worker_v2.executor
        is not app.state.backtesting_job_executor_v2
    ):
        raise ValueError(
            "backtesting_worker_v2 debe utilizar "
            "el mismo backtesting_job_executor_v2."
        )

    app.state.backtesting_worker_v2 = (
        backtesting_worker_v2
    )

    if backtesting_background_worker_v2 is None:
        backtesting_background_worker_v2 = (
            BacktestingBackgroundWorkerV2(
                worker=(
                    app.state
                    .backtesting_worker_v2
                ),
            )
        )

    if (
        not callable(
            getattr(
                backtesting_background_worker_v2,
                "start",
                None,
            )
        )
        or not callable(
            getattr(
                backtesting_background_worker_v2,
                "stop",
                None,
            )
        )
    ):
        raise TypeError(
            "backtesting_background_worker_v2 debe implementar start() y stop()."
        )

    background_inner_worker = getattr(
        backtesting_background_worker_v2,
        "worker",
        None,
    )

    if (
        background_inner_worker is not None
        and background_inner_worker
        is not app.state.backtesting_worker_v2
    ):
        raise ValueError(
            "backtesting_background_worker_v2 debe utilizar "
            "el mismo backtesting_worker_v2."
        )

    app.state.backtesting_background_worker_v2 = (
        backtesting_background_worker_v2
    )

    if backtesting_controller_v2 is None:
        backtesting_controller_v2 = (
            BacktestingControllerV2(
                job_manager=(
                    app.state
                    .backtesting_job_manager_v2
                ),
                job_queue=(
                    app.state
                    .backtesting_job_queue_v2
                ),
                background_worker=(
                    app.state
                    .backtesting_background_worker_v2
                ),
            )
        )

    if not isinstance(
        backtesting_controller_v2,
        BacktestingControllerV2,
    ):
        raise TypeError(
            "backtesting_controller_v2 debe ser "
            "BacktestingControllerV2."
        )

    if (
        backtesting_controller_v2.job_manager
        is not app.state.backtesting_job_manager_v2
    ):
        raise ValueError(
            "backtesting_controller_v2 debe utilizar "
            "el mismo backtesting_job_manager_v2."
        )

    if (
        backtesting_controller_v2.job_queue
        is not app.state.backtesting_job_queue_v2
    ):
        raise ValueError(
            "backtesting_controller_v2 debe utilizar "
            "la misma backtesting_job_queue_v2."
        )

    if (
        backtesting_controller_v2.background_worker
        is not app.state.backtesting_background_worker_v2
    ):
        raise ValueError(
            "backtesting_controller_v2 debe utilizar "
            "el mismo backtesting_background_worker_v2."
        )

    app.state.backtesting_controller_v2 = (
        backtesting_controller_v2
    )



    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(
        app
    )

    register_logging_middleware(
        app
    )

    app.include_router(
        create_strategy_registry_router_v2(
            registry=(
                app.state
                .strategy_registry_v2
            ),
        )
    )

    register_router_v2(
        app,
        create_strategy_ranking_router_v2(
            ranking_service=(
                app.state
                .strategy_ranking_service_v2
            ),
        ),
    )


    register_router_v2(
        app,
        create_strategy_recommendation_router_v2(
            recommendation_service=(
                app.state
                .strategy_recommendation_service_v2
            ),
        ),
    )

    app.include_router(
        portfolio_router
    )

    app.include_router(
        ai_router
    )

    app.include_router(
        market_router
    )

    app.include_router(
        create_trade_lifecycle_router_v2(
            service=(
                app.state.trade_lifecycle_service_v2
            ),
        )
    )

    app.include_router(
        create_performance_dashboard_router_v2(
            dashboard_engine_v2=(
                app.state
                .performance_dashboard_engine_v2
            ),
        )
    )

    app.include_router(
        create_dashboard_live_router_v2(
            live_data_service_v2=(
                app.state.dashboard_live_data_service_v2
            ),
        )
    )


    app.include_router(
        create_dashboard_widgets_router_v2(
            widget_registry_v2=(
                app.state.dashboard_widget_registry_v2
            ),
        )
    )

    app.include_router(
        create_dashboard_websocket_router_v2(
            websocket_hub_v2=(
                app.state.dashboard_websocket_hub_v2
            ),
            live_data_service_v2=(
                app.state.dashboard_live_data_service_v2
            ),
        )
    )


    app.state.backtesting_metrics_provider_v2 = (
        BacktestingMetricsProviderV2(
            engine=(
                BacktestingMetricsEngineV2()
            ),
        )
    )

    app.state.backtesting_performance_report_provider_v2 = (
        BacktestingPerformanceReportProviderV2(
            metrics_provider=(
                app.state
                .backtesting_metrics_provider_v2
            ),
            report_engine=(
                BacktestingPerformanceReportV2()
            ),
        )
    )

    app.include_router(
        create_backtesting_metrics_router_v2(
            metrics_provider=(
                BacktestingMetricsProviderV2(
            engine=(
                BacktestingMetricsEngineV2()
            ),
        )
            ),
        )
    )

    app.include_router(
        create_backtesting_dashboard_router_v2(
            controller=(
                app.state
                .backtesting_controller_v2
            ),
            job_manager=(
                app.state
                .backtesting_job_manager_v2
            ),
            job_queue=(
                app.state
                .backtesting_job_queue_v2
            ),
            worker=(
                app.state
                .backtesting_worker_v2
            ),
            metrics_provider=(
                app.state
                .backtesting_metrics_provider_v2
            ),
            performance_report_provider=(
                app.state
                .backtesting_performance_report_provider_v2
            ),
            strategy_registry_provider=(
                app.state
                .strategy_registry_dashboard_provider_v2
            ),
            strategy_recommendation_provider=(
                app.state
                .strategy_recommendation_dashboard_provider_v2
            ),
            strategy_decision_provider=(
                app.state
                .strategy_decision_dashboard_provider_v2
            ),
            trade_plan_provider=(
                app.state
                .trade_plan_dashboard_provider_v2
            ),
            risk_validation_provider=(
                app.state
                .risk_validation_dashboard_provider_v2
            ),
            execution_provider=(
                app.state
                .execution_dashboard_provider_v2
            ),
            performance_provider=(
                app.state
                .backtesting_performance_provider_v2
            ),
            strategy_performance_provider=(
                app.state
                .strategy_performance_dashboard_provider_v2
            ),

            strategy_selection_provider=(
                app.state
                .strategy_selection_dashboard_provider_v2
            ),
            strategy_ranking_provider=(
                app.state
                .strategy_ranking_dashboard_provider_v2
            ),
        )
    )

    app.include_router(
        create_backtesting_controller_router_v2(
            controller=(
                app.state
                .backtesting_controller_v2
            ),
        )
    )

    app.include_router(
        create_backtesting_jobs_router_v2(
            job_manager=(
                app.state
                .backtesting_job_manager_v2
            ),
            job_queue=(
                app.state
                .backtesting_job_queue_v2
            ),
            result_provider=(
                app.state
                .backtesting_job_executor_v2
            ),
        )
    )

    app.include_router(
        create_backtesting_router_v2(
            orchestrator=(
                app.state
                .backtesting_orchestrator_v2
            ),
        )
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
