from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.risk.risk_compatibility_adapter_v2 import (
    RiskCompatibilityAdapterV2,
    RiskCompatibilityResultV2,
)


def build_adapter() -> RiskCompatibilityAdapterV2:
    manager = RiskManagerV2(
        position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
        maximum_contracts=20,
        maximum_open_positions=1,
    )

    return RiskCompatibilityAdapterV2(
        risk_manager=manager,
    )


def test_adapter_returns_legacy_compatible_approved_result():
    adapter = build_adapter()

    result = adapter.evaluate(
        account_balance=150000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=0.0,
        total_drawdown=0.0,
        open_positions=0,
        symbol="NQ",
    )

    assert isinstance(
        result,
        RiskCompatibilityResultV2,
    )

    assert result.allowed is True
    assert result.contracts == 18
    assert result.risk_amount == 750.0
    assert result.reason == (
        "RISK PIPELINE APPROVED"
    )


def test_adapter_blocks_when_risk_is_too_small():
    adapter = build_adapter()

    result = adapter.evaluate(
        account_balance=150000.0,
        risk_percent=0.5,
        stop_points=1000.0,
        point_value=2.0,
        daily_pnl=0.0,
        total_drawdown=0.0,
        open_positions=0,
        symbol="NQ",
    )

    assert isinstance(
        result,
        RiskCompatibilityResultV2,
    )

    assert result.allowed is False
    assert result.contracts == 0
    assert result.risk_amount == 750.0
    assert result.reason == (
        "position_sizing_not_approved"
    )


def test_adapter_preserves_daily_loss_block():
    adapter = build_adapter()

    result = adapter.evaluate(
        account_balance=150000.0,
        risk_percent=0.5,
        stop_points=20.0,
        point_value=2.0,
        daily_pnl=-3000.0,
        total_drawdown=0.0,
        open_positions=0,
        symbol="NQ",
    )

    assert result.allowed is False
    assert result.contracts == 18
    assert result.risk_amount == 750.0
    assert result.reason == (
        "daily_loss_limit_reached"
    )


def test_adapter_rejects_invalid_manager():
    try:
        RiskCompatibilityAdapterV2(
            risk_manager=object(),
        )
    except TypeError as exc:
        assert str(exc) == (
            "risk_manager debe ser RiskManagerV2."
        )
    else:
        raise AssertionError(
            "Expected TypeError"
        )
