from dataclasses import dataclass

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.config_settings import ArmsSettings
from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)
from backend.services.graceful_shutdown_service_v2 import (
    GracefulShutdownServiceV2,
)
from backend.services.runtime_lifecycle_manager_v2 import (
    RuntimeLifecycleManagerV2,
)
from backend.services.startup_coordinator_v2 import (
    StartupCoordinatorV2,
)
from backend.services.state_recovery_service_v2 import (
    StateRecoveryServiceV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)



@dataclass(frozen=True, slots=True)
class RuntimeContextV2:
    settings: ArmsSettings

    execution_manager: ExecutionManagerV2
    paper_execution_engine: PaperExecutionEngineV2
    position_manager: PositionManagerV2
    trade_history_manager: TradeHistoryManagerV2
    performance_analytics: PerformanceAnalyticsV2

    account_state_manager_v2: (
        AccountStateManagerV2
    )
    portfolio_manager_v2: (
        PortfolioManagerV2
    )
    position_sizing_engine_v2: (
        PositionSizingEngineV2
    )
    risk_manager_v2: RiskManagerV2

    protective_order_registry: (
        ProtectiveOrderRegistryV2
    )
    oco_manager: OCOManagerV2

    trade_lifecycle_service: (
        TradeLifecycleServiceV2
    )
    execution_state_store: ExecutionStateStoreV2
    state_recovery_service: StateRecoveryServiceV2
    startup_coordinator: StartupCoordinatorV2
    graceful_shutdown_service: (
        GracefulShutdownServiceV2
    )
    runtime_lifecycle_manager: (
        RuntimeLifecycleManagerV2
    )


def build_runtime_context(
    *,
    settings: ArmsSettings | None = None,
    execution_mode: str = "PAPER",
    maximum_contracts: int | None = None,
    fill_market_orders_immediately: bool = True,
    slippage_points: float = 0.0,
    risk_free_rate: float = 0.0,
    trading_days_per_year: int = 252,
) -> RuntimeContextV2:
    settings_were_explicit = (
        settings is not None
    )

    resolved_settings = settings or ArmsSettings()

    from backend.accounts.account_config_manager_v2 import (
        AccountConfigManagerV2,
    )
    from backend.instruments.instrument_profile_engine import (
        InstrumentProfileEngine,
    )

    active_account = (
        AccountConfigManagerV2()
        .get_active_account()
    )

    active_starting_balance = (
        float(resolved_settings.account_balance)
        if settings_were_explicit
        else float(active_account.account_size)
    )

    active_maximum_daily_loss = (
        None
        if active_account.daily_loss_limit is None
        else float(
            active_account.daily_loss_limit
        )
    )

    active_maximum_total_drawdown = float(
        active_account.max_drawdown
    )

    active_profit_target = (
        None
        if active_account.profit_target is None
        else float(active_account.profit_target)
    )

    active_account_stage = (
        None
        if active_account.account_stage is None
        else str(active_account.account_stage)
    )

    instrument_profiles = (
        InstrumentProfileEngine()
    )

    contract_limit_resolver = None

    if maximum_contracts is None:
        def resolve_contract_limit(
            symbol: str,
        ) -> int:
            profile = (
                instrument_profiles
                .get_profile(symbol=symbol)
            )

            return active_account.get_contract_limit(
                profile["contract_class"]
            )

        resolved_maximum_contracts = min(
            active_account.get_contract_limit("MINI"),
            active_account.get_contract_limit("MICRO"),
        )

        contract_limit_resolver = (
            resolve_contract_limit
        )
    else:
        resolved_maximum_contracts = (
            maximum_contracts
        )

    execution_manager = ExecutionManagerV2(
        execution_mode=execution_mode,
        maximum_contracts=(
            resolved_maximum_contracts
        ),
        contract_limit_resolver=(
            contract_limit_resolver
        ),
    )

    account_state_manager_v2 = (
        AccountStateManagerV2(
            starting_balance=(
                active_starting_balance
            ),
            maximum_daily_loss=(
                active_maximum_daily_loss
            ),
            maximum_total_drawdown=(
                active_maximum_total_drawdown
            ),
            profit_target=(
                active_profit_target
            ),
            account_stage=(
                active_account_stage
            ),
        )
    )

    portfolio_manager_v2 = (
        PortfolioManagerV2(
            starting_balance=(
                active_starting_balance
            ),
            account_state_manager_v2=(
                account_state_manager_v2
            ),
        )
    )

    position_sizing_engine_v2 = (
        PositionSizingEngineV2()
    )

    risk_manager_v2 = RiskManagerV2(
        position_sizing_engine=(
            position_sizing_engine_v2
        ),
        maximum_daily_loss=(
            active_maximum_daily_loss
        ),
        maximum_total_drawdown=(
            active_maximum_total_drawdown
        ),
        maximum_contracts=(
            resolved_maximum_contracts
        ),
        maximum_open_positions=1,
        contract_limit_resolver=(
            contract_limit_resolver
        ),
    )

    paper_execution_engine = PaperExecutionEngineV2(
        fill_market_orders_immediately=(
            fill_market_orders_immediately
        ),
        slippage_points=slippage_points,
    )

    position_manager = PositionManagerV2(
        point_value=resolved_settings.point_value,
    )

    trade_history_manager = TradeHistoryManagerV2()

    performance_analytics = PerformanceAnalyticsV2(
        risk_free_rate=risk_free_rate,
        trading_days_per_year=(
            trading_days_per_year
        ),
    )

    protective_order_registry = (
        ProtectiveOrderRegistryV2()
    )

    oco_manager = OCOManagerV2()

    trade_journal_v2 = TradeJournalV2()

    trade_lifecycle_service = TradeLifecycleServiceV2(
        execution_manager=execution_manager,
        paper_execution_engine=(
            paper_execution_engine
        ),
        position_manager=position_manager,
        trade_history_manager=(
            trade_history_manager
        ),
        performance_analytics=(
            performance_analytics
        ),
        risk_manager_v2=(
            risk_manager_v2
        ),
        portfolio_manager_v2=(
            portfolio_manager_v2
        ),
        starting_balance=(
            active_starting_balance
        ),
        protective_order_registry_v2=(
            protective_order_registry
        ),
        oco_manager_v2=oco_manager,
        trade_journal_v2=trade_journal_v2,
    )

    execution_state_store = ExecutionStateStoreV2(
        trade_lifecycle_service=(
            trade_lifecycle_service
        ),
        protective_order_registry=(
            protective_order_registry
        ),
        oco_manager=oco_manager,
    )

    state_recovery_service = StateRecoveryServiceV2(
        execution_state_store=execution_state_store,
    )

    startup_coordinator = StartupCoordinatorV2(
        state_recovery_service=(
            state_recovery_service
        ),
    )

    graceful_shutdown_service = (
        GracefulShutdownServiceV2(
            execution_state_store=(
                execution_state_store
            ),
        )
    )

    runtime_lifecycle_manager = (
        RuntimeLifecycleManagerV2(
            startup_coordinator=(
                startup_coordinator
            ),
            graceful_shutdown_service=(
                graceful_shutdown_service
            ),
        )
    )

    return RuntimeContextV2(
        settings=resolved_settings,
        execution_manager=execution_manager,
        paper_execution_engine=(
            paper_execution_engine
        ),
        position_manager=position_manager,
        trade_history_manager=(
            trade_history_manager
        ),
        performance_analytics=(
            performance_analytics
        ),
        account_state_manager_v2=(
            account_state_manager_v2
        ),
        portfolio_manager_v2=(
            portfolio_manager_v2
        ),
        position_sizing_engine_v2=(
            position_sizing_engine_v2
        ),
        risk_manager_v2=(
            risk_manager_v2
        ),
        protective_order_registry=(
            protective_order_registry
        ),
        oco_manager=oco_manager,
        trade_lifecycle_service=(
            trade_lifecycle_service
        ),
        execution_state_store=(
            execution_state_store
        ),
        state_recovery_service=(
            state_recovery_service
        ),
        startup_coordinator=(
            startup_coordinator
        ),
        graceful_shutdown_service=(
            graceful_shutdown_service
        ),
        runtime_lifecycle_manager=(
            runtime_lifecycle_manager
        ),
    )
