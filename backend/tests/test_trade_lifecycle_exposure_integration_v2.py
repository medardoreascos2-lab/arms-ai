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
from backend.execution.exposure_manager_v2 import (
    ExposureManagerV2,
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


def build_risk_manager() -> RiskManagerV2:
    return RiskManagerV2(
        position_sizing_engine=(
            PositionSizingEngineV2()
        ),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=5,
    )


def build_exposure_manager() -> ExposureManagerV2:
    return ExposureManagerV2(
        maximum_total_open_risk=500.0,
        maximum_symbol_open_risk=300.0,
        maximum_total_contracts=10,
        maximum_symbol_contracts=6,
    )


def build_service(
    *,
    exposure_manager_v2=None,
) -> TradeLifecycleServiceV2:
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
        risk_manager_v2=(
            build_risk_manager()
        ),
        order_validation_engine_v2=None,
        exposure_manager_v2=(
            exposure_manager_v2
        ),
        starting_balance=17000.0,
    )


def build_signal(
    *,
    symbol: str = "NQ",
) -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": symbol,
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "contracts": 99,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
    }


def build_risk_context() -> dict[str, object]:
    return {
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
    }


def test_accepts_none_exposure_manager():
    service = build_service(
        exposure_manager_v2=None,
    )

    assert (
        service.exposure_manager_v2
        is None
    )


def test_accepts_valid_exposure_manager():
    manager = build_exposure_manager()

    service = build_service(
        exposure_manager_v2=manager,
    )

    assert (
        service.exposure_manager_v2
        is manager
    )


def test_rejects_invalid_exposure_manager():
    with pytest.raises(
        TypeError,
        match="exposure_manager_v2",
    ):
        build_service(
            exposure_manager_v2=object(),
        )


def test_submit_signal_uses_exposure_manager():
    service = build_service(
        exposure_manager_v2=(
            build_exposure_manager()
        ),
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True

    assert (
        result["exposure_evaluation"][
            "approved"
        ]
        is True
    )

    assert (
        result["exposure_evaluation"][
            "candidate_contracts"
        ]
        == 4
    )

    assert (
        result["exposure_evaluation"][
            "candidate_risk"
        ]
        == 80.0
    )


def test_submit_signal_blocks_total_exposure():
    manager = ExposureManagerV2(
        maximum_total_open_risk=50.0,
        maximum_symbol_open_risk=50.0,
        maximum_total_contracts=10,
        maximum_symbol_contracts=10,
    )

    service = build_service(
        exposure_manager_v2=manager,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is False
    assert result["reason"] == (
        "exposure_blocked"
    )

    assert (
        "maximum_total_open_risk_exceeded"
        in result["exposure_evaluation"][
            "blocking_reasons"
        ]
    )

    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None


def test_submit_signal_blocks_symbol_exposure():
    manager = ExposureManagerV2(
        maximum_total_open_risk=500.0,
        maximum_symbol_open_risk=50.0,
        maximum_total_contracts=10,
        maximum_symbol_contracts=10,
    )

    service = build_service(
        exposure_manager_v2=manager,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is False

    assert (
        "maximum_symbol_open_risk_exceeded"
        in result["exposure_evaluation"][
            "blocking_reasons"
        ]
    )


def test_submit_signal_works_without_exposure_manager():
    service = build_service(
        exposure_manager_v2=None,
    )

    result = service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert result["accepted"] is True
    assert result["exposure_evaluation"] is None


def test_exposure_uses_active_positions():
    service = build_service(
        exposure_manager_v2=(
            build_exposure_manager()
        ),
    )

    first_result = service.submit_signal(
        signal=build_signal(
            symbol="NQ",
        ),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert first_result["accepted"] is True

    first_position_id = first_result[
        "active_position_id"
    ]

    service._active_positions[
        first_position_id
    ]["symbol"] = "ES"

    second_result = service.submit_signal(
        signal=build_signal(
            symbol="NQ",
        ),
        order_type="MARKET",
        risk_context=build_risk_context(),
    )

    assert second_result["accepted"] is False
    assert (
        second_result["reason"]
        == "position_already_open"
    )
