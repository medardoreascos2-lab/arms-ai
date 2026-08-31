from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.services.runtime_context_v2 import (
    build_runtime_context,
)


def test_account_state_exposes_profit_target():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=1000.0,
        maximum_total_drawdown=2000.0,
        profit_target=3000.0,
    )

    state = manager.get_state()

    assert manager.profit_target == 3000.0
    assert state["profit_target"] == 3000.0


def test_account_state_allows_no_profit_target():
    manager = AccountStateManagerV2(
        starting_balance=50000.0,
        maximum_daily_loss=1000.0,
        maximum_total_drawdown=2000.0,
    )

    state = manager.get_state()

    assert manager.profit_target is None
    assert state["profit_target"] is None


def test_runtime_uses_active_account_profit_target():
    account = (
        AccountConfigManagerV2()
        .get_active_account()
    )

    context = build_runtime_context()

    manager = (
        context.account_state_manager_v2
    )

    state = manager.get_state()

    assert manager.profit_target == float(
        account.profit_target
    )

    assert state["profit_target"] == float(
        account.profit_target
    )


def test_runtime_profit_target_is_nine_thousand():
    context = build_runtime_context()

    state = (
        context.account_state_manager_v2
        .get_state()
    )

    assert state["profit_target"] == 9000.0
