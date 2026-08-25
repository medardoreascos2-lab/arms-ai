import pytest

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)
from backend.connectors.paper_broker_connector_v2 import (
    PaperBrokerConnectorV2,
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
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
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


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 23000.0,
        "stop_loss": 22980.0,
        "take_profit": 23040.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "NQ LONG",
    }


def build_paper_engine(
) -> PaperExecutionEngineV2:
    return PaperExecutionEngineV2(
        fill_market_orders_immediately=True,
        slippage_points=0.25,
    )


def build_risk_manager() -> RiskManagerV2:
    return RiskManagerV2(
        position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=1,
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
            "account": "BROKER-INTEGRATION-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }


def build_service(
    *,
    broker_connector_v2=None,
) -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
            )
        ),
        paper_execution_engine=(
            build_paper_engine()
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
        risk_manager_v2=build_risk_manager(),
        starting_balance=17000.0,
        broker_connector_v2=(
            broker_connector_v2
        ),
        execution_risk_gate_v1=(
            ExecutionRiskGateV1(
                validator=FakeApprovedValidator(),
                logger=RiskEventLoggerV1(),
            )
        ),
    )


def test_creates_automatic_paper_broker():
    service = build_service()

    assert isinstance(
        service.broker_connector_v2,
        BrokerConnectorV2,
    )

    assert isinstance(
        service.broker_connector_v2,
        PaperBrokerConnectorV2,
    )

    assert (
        service.broker_connector_v2
        .is_connected
        is True
    )


def test_lifecycle_executes_through_broker():
    service = build_service()

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    assert result["accepted"] is True

    execution = result["execution"]

    assert execution is not None
    assert execution["accepted"] is True
    assert execution["status"] == "FILLED"
    assert execution["broker"] == "ARMS_PAPER"
    assert execution["execution_mode"] == "PAPER"

    assert result["position"] is not None
    assert result["active_position_id"]


def test_uses_injected_broker_connector():
    connector = PaperBrokerConnectorV2(
        execution_engine=(
            build_paper_engine()
        ),
        account_id="CUSTOM-PAPER",
        starting_balance=25000.0,
    )

    service = build_service(
        broker_connector_v2=connector,
    )

    assert (
        service.broker_connector_v2
        is connector
    )

    assert connector.is_connected is True

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
    )

    assert result["accepted"] is True
    assert len(
        connector.get_orders()
    ) == 1

    assert len(
        connector.get_fills()
    ) == 1


def test_connects_injected_disconnected_broker():
    connector = PaperBrokerConnectorV2(
        execution_engine=(
            build_paper_engine()
        ),
    )

    assert connector.is_connected is False

    service = build_service(
        broker_connector_v2=connector,
    )

    assert (
        service.broker_connector_v2
        .is_connected
        is True
    )


def test_rejects_invalid_broker_connector():
    with pytest.raises(
        TypeError,
        match="broker_connector_v2",
    ):
        build_service(
            broker_connector_v2=object(),
        )
