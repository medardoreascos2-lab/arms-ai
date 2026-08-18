from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)

from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)

from backend.connectors.paper_broker_connector_v2 import (
    PaperBrokerConnectorV2,
)

from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)

from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)

from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)

from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)

from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)

from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
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
            "status":
                "APPROVED",

            "account":
                "TEST_ACCOUNT",

            "contracts":
                contracts,

            "risk_used":
                risk_amount,
        }


class FakeBlockedValidator:

    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):

        return {
            "status":
                "BLOCKED",

            "reason":
                "FINAL_RISK_GATE_TEST_BLOCK",
        }


def build_signal():

    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "MNQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19980.0,
        "take_profit": 20040.0,
        "contracts": 1,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "MNQ LONG",
    }


def build_paper_engine():

    return PaperExecutionEngineV2(
        fill_market_orders_immediately=True,
        slippage_points=0.0,
    )


def build_risk_manager():

    return RiskManagerV2(
        position_sizing_engine=(
            PositionSizingEngineV2()
        ),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=5,
    )


def build_service(
    *,
    validator,
):

    paper_engine = (
        build_paper_engine()
    )

    broker = (
        PaperBrokerConnectorV2(
            execution_engine=paper_engine,
            account_id="RISK-GATE-TEST",
            starting_balance=17000.0,
        )
    )

    gate = (
        ExecutionRiskGateV1(
            validator=validator,
            logger=RiskEventLoggerV1(),
        )
    )

    service = (
        TradeLifecycleServiceV2(
            execution_manager=(
                ExecutionManagerV2(
                    execution_mode="PAPER",
                    maximum_contracts=20,
                )
            ),
            paper_execution_engine=(
                paper_engine
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
            risk_manager_v2=(
                build_risk_manager()
            ),
            broker_connector_v2=broker,
            execution_risk_gate_v1=gate,
        )
    )

    return service, broker, gate


def risk_context():

    return {
        "account_balance":
            17000.0,

        "risk_percent":
            0.5,

        "point_value":
            2.0,

        "daily_pnl":
            0.0,

        "total_drawdown":
            0.0,
    }


def test_final_gate_approved_reaches_broker():

    service, broker, gate = (
        build_service(
            validator=(
                FakeApprovedValidator()
            )
        )
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=risk_context(),
    )

    assert result["accepted"] is True

    assert (
        result[
            "execution_risk_gate"
        ][
            "execution"
        ]
        == "APPROVED"
    )

    assert len(
        broker.get_orders()
    ) == 1

    assert len(
        broker.get_fills()
    ) == 1

    assert result["position"] is not None

    events = gate.get_risk_events()

    assert len(events) == 1

    assert (
        events[0]["status"]
        == "APPROVED"
    )


def test_final_gate_blocked_never_reaches_broker():

    service, broker, gate = (
        build_service(
            validator=(
                FakeBlockedValidator()
            )
        )
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=risk_context(),
    )

    assert result["accepted"] is False

    assert (
        result["reason"]
        == "execution_risk_gate_blocked"
    )

    assert (
        result[
            "execution_risk_gate"
        ][
            "execution"
        ]
        == "BLOCKED"
    )

    assert (
        result[
            "execution_risk_gate"
        ][
            "reason"
        ]
        == "FINAL_RISK_GATE_TEST_BLOCK"
    )

    assert broker.get_orders() == []

    assert broker.get_fills() == []

    assert result["execution"] is None

    assert result["position"] is None

    assert (
        result["active_position_id"]
        is None
    )

    events = gate.get_risk_events()

    assert len(events) == 1

    assert (
        events[0]["status"]
        == "BLOCKED"
    )


def test_gate_requires_risk_manager_evaluation():

    paper_engine = (
        build_paper_engine()
    )

    gate = (
        ExecutionRiskGateV1(
            validator=(
                FakeApprovedValidator()
            ),
            logger=(
                RiskEventLoggerV1()
            ),
        )
    )

    service = (
        TradeLifecycleServiceV2(
            execution_manager=(
                ExecutionManagerV2(
                    execution_mode="PAPER",
                    maximum_contracts=20,
                )
            ),
            paper_execution_engine=(
                paper_engine
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
            execution_risk_gate_v1=gate,
        )
    )

    try:

        service.submit_signal(
            signal=build_signal(),
            order_type="MARKET",
        )

    except ValueError as exc:

        assert (
            "risk_evaluation"
            in str(exc)
        )

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )
