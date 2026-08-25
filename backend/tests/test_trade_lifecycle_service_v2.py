import pytest

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


def build_service() -> TradeLifecycleServiceV2:
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

    assert (
        result["prepared_order"][
            "status"
        ]
        == "BLOCKED"
    )

    assert (
        result["execution"][
            "status"
        ]
        == "REJECTED"
    )

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
