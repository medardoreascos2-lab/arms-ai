import pytest

from backend.config_settings import ArmsSettings
from backend.services.runtime_context_v2 import (
    build_runtime_context,
)


def test_default_internal_daily_loss_policy_preserves_firm_contract():
    context = build_runtime_context()

    assert (
        context
        .account_state_manager_v2
        .maximum_daily_loss
        is None
    )

    assert (
        context
        .risk_manager_v2
        .maximum_daily_loss
        is None
    )


def test_internal_daily_loss_limit_applies_when_firm_limit_is_none():
    settings = ArmsSettings(
        internal_daily_loss_limit=3000.0,
    )

    context = build_runtime_context(
        settings=settings,
    )

    assert context.settings is settings

    assert (
        context
        .account_state_manager_v2
        .maximum_daily_loss
        == 3000.0
    )

    assert (
        context
        .risk_manager_v2
        .maximum_daily_loss
        == 3000.0
    )


def test_internal_daily_loss_limit_blocks_at_configured_limit():
    settings = ArmsSettings(
        internal_daily_loss_limit=3000.0,
    )

    context = build_runtime_context(
        settings=settings,
    )

    result = context.risk_manager_v2.evaluate(
        account_balance=150000.0,
        risk_percent=0.1,
        stop_points=30.0,
        point_value=2.0,
        daily_pnl=-3000.0,
        total_drawdown=0.0,
        open_positions=0,
    )

    assert result["approved"] is False

    assert (
        "daily_loss_limit_reached"
        in result["blocking_reasons"]
    )


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        -1.0,
        -3000.0,
    ],
)
def test_internal_daily_loss_limit_must_be_positive(
    value,
):
    with pytest.raises(
        ValueError,
        match="internal_daily_loss_limit",
    ):
        ArmsSettings(
            internal_daily_loss_limit=value,
        )
