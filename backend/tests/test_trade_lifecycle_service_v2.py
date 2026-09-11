from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.dashboard.risk_dashboard_event_publisher_v2 import RiskDashboardEventPublisherV2
from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import TradeLifecycleDashboardEventPublisherV2
from backend.execution.exposure_manager_v2 import ExposureManagerV2
from backend.execution.order_validation_engine_v2 import OrderValidationEngineV2
from backend.execution.portfolio_risk_engine_v2 import PortfolioRiskEngineV2
from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
from backend.journal.trade_journal_v2 import TradeJournalV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class FakeApprovedValidator:

    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):
        return {
            "status": "APPROVED",
            "account": "LIFECYCLE-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }


def build_service(**dependencies) -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
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
        starting_balance=17000.0,
        risk_manager_v2=RiskManagerV2(
            position_sizing_engine=PositionSizingEngineV2(),
            maximum_daily_loss=3000.0,
            maximum_total_drawdown=4500.0,
            maximum_contracts=20,
            maximum_open_positions=1,
        ),
        execution_risk_gate_v1=(
            ExecutionRiskGateV1(
                validator=FakeApprovedValidator(),
                logger=RiskEventLoggerV1(),
            )
        ),
        **dependencies,
    )


def build_valid_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


@pytest.fixture
def observed_service(monkeypatch):
    account = AccountStateManagerV2(
        starting_balance=17000.0,
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
    )
    event_bus = Mock()
    event_bus.publish.return_value = {"published": True}
    service = build_service(
        instrument_profile_engine=InstrumentProfileEngine(),
        exposure_manager_v2=ExposureManagerV2(
            maximum_total_open_risk=1000.0,
            maximum_symbol_open_risk=1000.0,
            maximum_total_contracts=20,
            maximum_symbol_contracts=20,
        ),
        portfolio_risk_engine_v2=PortfolioRiskEngineV2(
            maximum_total_open_risk=1000.0,
            maximum_floating_loss=1000.0,
            maximum_long_risk=1000.0,
            maximum_short_risk=1000.0,
            maximum_symbol_risk=1000.0,
        ),
        order_validation_engine_v2=OrderValidationEngineV2(
            minimum_reward_risk_ratio=1.0,
            minimum_stop_points=1.0,
            maximum_stop_points=100.0,
            allowed_symbols={"MNQ"},
        ),
        portfolio_manager_v2=PortfolioManagerV2(
            starting_balance=17000.0,
            account_state_manager_v2=account,
        ),
        trade_journal_v2=TradeJournalV2(),
        dashboard_event_publisher_v2=TradeLifecycleDashboardEventPublisherV2(
            event_bus_v2=event_bus,
        ),
        risk_dashboard_event_publisher_v2=RiskDashboardEventPublisherV2(
            event_bus_v2=event_bus,
        ),
    )
    calls = {}
    for dependency, method in (
        (service.instrument_profile_engine, "get_profile"),
        (service.risk_manager_v2, "evaluate"),
        (service.exposure_manager_v2, "evaluate"),
        (service.portfolio_risk_engine_v2, "evaluate"),
        (service.order_validation_engine_v2, "validate"),
        (service.execution_risk_gate_v1, "evaluate_trade"),
        (service.execution_manager, "prepare_order"),
        (service.broker_connector_v2, "submit_order"),
        (service.paper_execution_engine, "execute"),
        (service.position_manager, "open_position"),
        (service.protective_order_registry_v2, "create_protection"),
        (service.oco_manager_v2, "create_group"),
        (service.portfolio_manager_v2, "add_position"),
        (account, "update_from_portfolio"),
        (service.trade_journal_v2, "record_open_trade"),
        (service.trade_journal_v2, "record"),
        (service.trade_history_manager, "record"),
        (service.dashboard_event_publisher_v2, "publish_trade_opened"),
        (service.dashboard_event_publisher_v2, "publish_portfolio_updated"),
        (service.risk_dashboard_event_publisher_v2, "publish_risk_updated"),
        (service.risk_dashboard_event_publisher_v2, "publish_open_risk_updated"),
    ):
        spy = Mock(wraps=getattr(dependency, method))
        monkeypatch.setattr(dependency, method, spy)
        calls[f"{type(dependency).__name__}.{method}"] = spy
    calls["event_bus.publish"] = event_bus.publish
    return service, calls


def execution_state(service):
    broker = service.broker_connector_v2
    portfolio = service.portfolio_manager_v2
    return deepcopy({
        "orders": broker.get_orders(),
        "fills": broker.get_fills(),
        "broker_positions": broker.get_positions(),
        "broker_account": broker.get_account(),
        "positions": service.get_active_positions(),
        "protections": service.protective_order_registry_v2.list_protections(),
        "oco": service.oco_manager_v2.list_groups(),
        "portfolio": portfolio.get_summary(),
        "portfolio_positions": portfolio.get_open_positions(),
        "portfolio_closed_positions": portfolio.get_closed_positions(),
        "journal": service.trade_journal_v2.get_trades(),
        "history": service.get_trade_history(),
        "risk_events": service.execution_risk_gate_v1.get_risk_events(),
    })


@pytest.mark.parametrize("order_type", ["MARKET", "LIMIT"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("blocking_reasons", ["high_impact_news"], id="news"),
        pytest.param("status", "BLOCKED", id="non_ready"),
        pytest.param("status", None, id="missing_status"),
        pytest.param("probability", 0.79, id="low_probability"),
        pytest.param("approved", False, id="not_approved"),
        pytest.param("grade", "A", id="non_a_plus"),
        pytest.param("confluence_score", 0.79, id="low_confluence"),
    ],
)
def test_blocked_signal_stops_before_execution(
    observed_service, order_type, field, value,
):
    service, calls = observed_service
    signal = build_valid_signal()
    signal["symbol"] = "MNQ"
    if value is None:
        signal.pop(field)
    else:
        signal[field] = value
    original_signal = deepcopy(signal)
    before = execution_state(service)

    # Missing downstream contexts must not prevent rejection of a blocked signal.
    result = service.submit_signal(signal=signal, order_type=order_type)

    assert result["accepted"] is False
    assert {name: spy.call_count for name, spy in calls.items()} == dict.fromkeys(calls, 0)
    assert execution_state(service) == before
    assert signal == original_signal
    assert result["reason"] == "signal_not_approved"
    for field in (
        "risk_evaluation", "exposure_evaluation", "portfolio_risk_evaluation",
        "order_validation", "execution_risk_gate", "prepared_order",
        "execution", "position", "active_position_id",
    ):
        assert result[field] is None, field
    assert result["portfolio_summary"] == before["portfolio"]
    assert result["trade_journal_summary"] == service.trade_journal_v2.get_summary()


def test_valid_signal_executes_with_observed_dependencies(observed_service):
    service, calls = observed_service
    signal = build_valid_signal()
    signal.update(symbol="MNQ", probability=0.80, confluence_score=0.80)

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
        order_context={"market_is_open": True},
    )

    assert result["accepted"] is True
    assert result["execution"]["status"] == "FILLED"
    for name in (
        "ExecutionManagerV2.prepare_order", "PaperBrokerConnectorV2.submit_order",
        "PaperExecutionEngineV2.execute", "PositionManagerV2.open_position",
        "ProtectiveOrderRegistryV2.create_protection", "OCOManagerV2.create_group",
        "PortfolioManagerV2.add_position", "TradeJournalV2.record_open_trade",
        "AccountStateManagerV2.update_from_portfolio",
        "TradeLifecycleDashboardEventPublisherV2.publish_trade_opened",
    ):
        assert calls[name].call_count == 1, name
    after = execution_state(service)
    for field in (
        "orders", "fills", "broker_positions", "positions", "protections",
        "oco", "portfolio_positions", "journal",
    ):
        assert len(after[field]) == 1, field
    assert calls["event_bus.publish"].call_count > 0


def test_submits_signal_and_opens_position():
    service = build_service()

    result = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    assert result["accepted"] is True

    assert (
        result["prepared_order"][
            "approved"
        ]
        is True
    )

    assert (
        result["execution"][
            "status"
        ]
        == "FILLED"
    )

    assert (
        result["position"][
            "status"
        ]
        == "OPEN"
    )

    assert (
        result["position"][
            "direction"
        ]
        == "LONG"
    )

    assert (
        result["active_position_id"]
        == result["position"][
            "position_id"
        ]
    )


def test_rejects_blocked_signal_without_position():
    service = build_service()

    signal = build_valid_signal()

    signal.update(
        {
            "approved": False,
            "status": "BLOCKED",
            "decision": "DO_NOT_SEND",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "contracts": 0,
        }
    )

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    assert result["accepted"] is False

    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert service.broker_connector_v2.get_orders() == []
    assert service.broker_connector_v2.get_fills() == []
    assert service.broker_connector_v2.get_positions() == []
    assert service.get_active_positions() == []

    assert result["position"] is None
    assert result["active_position_id"] is None


def test_updates_open_position():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    position_id = submitted[
        "active_position_id"
    ]

    result = service.update_position(
        position_id=position_id,
        current_price=105.25,
    )

    assert result["updated"] is True

    assert (
        result["position"][
            "status"
        ]
        == "OPEN"
    )

    assert (
        result["position"][
            "current_price"
        ]
        == 105.25
    )

    assert (
        result["position"][
            "unrealized_points"
        ]
        == 5.0
    )

    assert (
        result["position"][
            "unrealized_pnl"
        ]
        == 20.0
    )

    assert result["trade_record"] is None


def test_closes_position_and_records_trade():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    position_id = submitted[
        "active_position_id"
    ]

    result = service.update_position(
        position_id=position_id,
        current_price=110.0,
    )

    assert result["updated"] is True

    assert (
        result["position"][
            "status"
        ]
        == "CLOSED"
    )

    assert (
        result["position"][
            "close_reason"
        ]
        == "TAKE_PROFIT"
    )

    assert (
        result["trade_record"][
            "recorded"
        ]
        is True
    )

    assert (
        result["trade_record"][
            "trade"
        ][
            "result"
        ]
        == "WIN"
    )

    assert (
        result["active_position_removed"]
        is True
    )


def test_recalculates_performance_after_close():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    result = service.update_position(
        position_id=submitted[
            "active_position_id"
        ],
        current_price=110.0,
    )

    metrics = result[
        "performance_metrics"
    ]

    assert metrics["total_trades"] == 1
    assert metrics["wins"] == 1
    assert metrics["losses"] == 0
    assert metrics["net_pnl"] > 0
    assert metrics["ending_balance"] > 17000.0


def test_returns_active_positions():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    positions = service.get_active_positions()

    assert len(positions) == 1

    assert (
        positions[0][
            "position_id"
        ]
        == submitted[
            "active_position_id"
        ]
    )


def test_removes_position_after_close():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    service.update_position(
        position_id=submitted[
            "active_position_id"
        ],
        current_price=110.0,
    )

    positions = service.get_active_positions()

    assert positions == []


def test_returns_trade_history():
    service = build_service()

    submitted = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    service.update_position(
        position_id=submitted[
            "active_position_id"
        ],
        current_price=110.0,
    )

    history = service.get_trade_history()

    assert len(history) == 1
    assert history[0]["symbol"] == "NQ"
    assert history[0]["result"] == "WIN"


def test_returns_current_performance_metrics():
    service = build_service()

    metrics = service.get_performance_metrics()

    assert metrics["total_trades"] == 0
    assert metrics["starting_balance"] == 17000.0
    assert metrics["ending_balance"] == 17000.0


def test_blocks_second_position_when_one_is_open():
    service = build_service()

    first = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    second = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    assert first["accepted"] is True
    assert second["accepted"] is False

    assert (
        second["reason"]
        == "position_already_open"
    )


def test_supports_short_position_lifecycle():
    service = build_service()

    signal = build_valid_signal()

    signal.update(
        {
            "direction": "SHORT",
            "entry_price": 100.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }
    )

    submitted = service.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
            "current_price": 100.0,
        },
    )

    assert (
        submitted["position"][
            "direction"
        ]
        == "SHORT"
    )

    result = service.update_position(
        position_id=submitted[
            "active_position_id"
        ],
        current_price=90.0,
    )

    assert (
        result["position"][
            "status"
        ]
        == "CLOSED"
    )

    assert (
        result["position"][
            "realized_pnl"
        ]
        > 0
    )


def test_rejects_invalid_signal_type():
    service = build_service()

    with pytest.raises(
        TypeError,
        match="signal",
    ):
        service.submit_signal(
            signal=object(),
            order_type="MARKET",
        )


def test_rejects_unknown_position_id():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        service.update_position(
            position_id="missing-position",
            current_price=105.0,
        )


def test_rejects_empty_position_id():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="position_id",
    ):
        service.update_position(
            position_id="",
            current_price=105.0,
        )


def test_rejects_invalid_starting_balance():
    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
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
            starting_balance=0.0,
            execution_risk_gate_v1=(
                ExecutionRiskGateV1(
                    validator=FakeApprovedValidator(),
                    logger=RiskEventLoggerV1(),
                )
            ),
        )


@pytest.mark.parametrize(
    (
        "argument_name",
        "invalid_value",
    ),
    [
        (
            "execution_manager",
            object(),
        ),
        (
            "paper_execution_engine",
            object(),
        ),
        (
            "position_manager",
            object(),
        ),
        (
            "trade_history_manager",
            object(),
        ),
        (
            "performance_analytics",
            object(),
        ),
    ],
)
def test_rejects_invalid_dependency(
    argument_name: str,
    invalid_value: object,
):
    arguments = {
        "execution_manager": (
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        "paper_execution_engine": (
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        "position_manager": (
            PositionManagerV2(
                point_value=2.0,
            )
        ),
        "trade_history_manager": (
            TradeHistoryManagerV2()
        ),
        "performance_analytics": (
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
        ),
        "starting_balance": 17000.0,
        "execution_risk_gate_v1": (
            ExecutionRiskGateV1(
                validator=FakeApprovedValidator(),
                logger=RiskEventLoggerV1(),
            )
        ),
    }

    arguments[
        argument_name
    ] = invalid_value

    with pytest.raises(
        TypeError,
        match=argument_name,
    ):
        TradeLifecycleServiceV2(
            **arguments,
        )
