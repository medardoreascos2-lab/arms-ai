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
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_service(
    risk_manager=None,
):
    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=PaperExecutionEngineV2(
            fill_market_orders_immediately=True,
            slippage_points=0.25,
        ),
        position_manager=PositionManagerV2(
            point_value=2.0,
        ),
        trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=252,
        ),
        risk_manager_v2=risk_manager,
        starting_balance=17000.0,
    )


def build_risk_manager():
    return RiskManagerV2(
        position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=1,
    )


def build_signal():
    return {
        "approved": True,
        "symbol": "NQ",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 80.0,
        "take_profit": 140.0,
    }


def test_accepts_none_risk_manager():
    service = build_service()

    assert service.risk_manager_v2 is None


def test_accepts_valid_risk_manager():
    manager = build_risk_manager()

    service = build_service(
        risk_manager=manager,
    )

    assert service.risk_manager_v2 is manager


def test_rejects_invalid_risk_manager():

    with pytest.raises(
        TypeError,
        match="risk_manager_v2",
    ):
        build_service(
            risk_manager=object(),
        )


def build_risk_signal():
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 80.0,
        "take_profit": 140.0,
        "contracts": 99,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def test_submit_signal_uses_risk_manager_contracts():
    service = build_service(
        risk_manager=build_risk_manager(),
    )

    result = service.submit_signal(
        signal=build_risk_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -500.0,
            "total_drawdown": 1000.0,
        },
    )

    assert result["accepted"] is True

    assert (
        result["risk_evaluation"][
            "approved"
        ]
        is True
    )

    assert (
        result["risk_evaluation"][
            "contracts"
        ]
        == 2
    )

    assert (
        result["prepared_order"][
            "quantity"
        ]
        == 2
    )


def test_submit_signal_blocks_when_risk_manager_blocks():
    service = build_service(
        risk_manager=build_risk_manager(),
    )

    result = service.submit_signal(
        signal=build_risk_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -3000.0,
            "total_drawdown": 1000.0,
        },
    )

    assert result["accepted"] is False
    assert result["reason"] == "risk_blocked"

    assert (
        result["risk_evaluation"][
            "approved"
        ]
        is False
    )

    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None


def test_submit_signal_requires_risk_context_when_manager_configured():
    service = build_service(
        risk_manager=build_risk_manager(),
    )

    with pytest.raises(
        ValueError,
        match="risk_context",
    ):
        service.submit_signal(
            signal=build_risk_signal(),
            order_type="MARKET",
        )


def test_submit_signal_works_without_risk_manager():
    service = build_service(
        risk_manager=None,
    )

    signal = build_risk_signal()
    signal["contracts"] = 2

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
    )

    assert result["accepted"] is True
    assert result["risk_evaluation"] is None
