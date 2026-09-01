from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)
from backend.backtesting.backtest_risk_adapter_factory_v2 import (
    BacktestRiskAdapterFactoryV2,
)
from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)


class FakeBacktestRunner:
    def run(self, *, on_candle):
        return 0


class FakeStrategyRunner:
    def run(self, context):
        raise AssertionError(
            "No debe ejecutarse durante esta prueba."
        )


def test_backtest_risk_factory_uses_v2_account_contract():
    manager = AccountConfigManagerV2()

    adapter = BacktestRiskAdapterFactoryV2.create(
        account_config=manager,
    )

    risk_manager = adapter.risk_manager

    account = manager.get_active_account()

    assert (
        risk_manager.maximum_daily_loss
        == account.daily_loss_limit
    )

    assert (
        risk_manager.maximum_total_drawdown
        == account.max_drawdown
    )


def test_backtest_session_uses_v2_account_manager():
    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
    )

    assert isinstance(
        session.account_config,
        AccountConfigManagerV2,
    )


def test_topstep_150k_backtest_preserves_none_daily_loss():
    manager = AccountConfigManagerV2()

    account = manager.get_active_account()

    assert (
        manager.get_active_account_name()
        == "TOPSTEP_150K"
    )

    assert account.daily_loss_limit is None
    assert account.max_drawdown == 4500.0

    adapter = BacktestRiskAdapterFactoryV2.create(
        account_config=manager,
    )

    risk_manager = adapter.risk_manager

    assert risk_manager.maximum_daily_loss is None
    assert risk_manager.maximum_total_drawdown == 4500.0
