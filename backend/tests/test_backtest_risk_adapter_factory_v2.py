import pytest

from backend.backtesting.backtest_risk_adapter_factory_v2 import (
    BacktestRiskAdapterFactoryV2,
)
from backend.risk.risk_compatibility_adapter_v2 import (
    RiskCompatibilityAdapterV2,
)


def test_factory_builds_modern_risk_adapter():
    adapter = (
        BacktestRiskAdapterFactoryV2.create()
    )

    assert isinstance(
        adapter,
        RiskCompatibilityAdapterV2,
    )


def test_factory_approved_topstep_150k_scenario():
    adapter = (
        BacktestRiskAdapterFactoryV2.create()
    )

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

    assert result.allowed is True
    assert result.contracts == 18
    assert result.risk_amount == 750.0
    assert result.reason == (
        "RISK PIPELINE APPROVED"
    )


def test_factory_blocks_risk_too_small():
    adapter = (
        BacktestRiskAdapterFactoryV2.create()
    )

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

    assert result.allowed is False
    assert result.contracts == 0
    assert result.risk_amount == 750.0
    assert result.reason == (
        "position_sizing_not_approved"
    )


def test_factory_rejects_invalid_contract_limit():
    with pytest.raises(
        ValueError,
        match="maximum_contracts",
    ):
        BacktestRiskAdapterFactoryV2.create(
            maximum_contracts=0,
        )


def test_factory_rejects_invalid_open_position_limit():
    with pytest.raises(
        ValueError,
        match="maximum_open_positions",
    ):
        BacktestRiskAdapterFactoryV2.create(
            maximum_open_positions=0,
        )
