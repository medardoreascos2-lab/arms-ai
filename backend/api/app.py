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
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
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

from fastapi import FastAPI
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
    trade_lifecycle_service_v2:
    TradeLifecycleServiceV2
    | None = None,
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

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        debug=settings.debug,
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


    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
