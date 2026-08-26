from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.risk.account_profile_v1 import (
    AccountProfileFactory,
)
from backend.risk.risk_compatibility_adapter_v2 import (
    RiskCompatibilityAdapterV2,
)


def build_adapter():
    profile = AccountProfileFactory.topstep_150k()

    manager = RiskManagerV2(
        position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=profile.daily_loss_limit,
        maximum_total_drawdown=profile.max_drawdown,
        maximum_contracts=20,
        maximum_open_positions=1,
    )

    return RiskCompatibilityAdapterV2(
        risk_manager=manager,
    )


def test_backtest_adapter_matches_legacy_approved_contract():
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

    assert result.allowed is True
    assert result.contracts == 18
    assert result.risk_amount == 750.0
    assert result.reason == "RISK PIPELINE APPROVED"


def test_backtest_adapter_blocks_risk_too_small():
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

    assert result.allowed is False
    assert result.contracts == 0
    assert result.risk_amount == 750.0
    assert result.reason == "position_sizing_not_approved"
