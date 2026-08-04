from backend.backtesting.backtesting_builder_v2 import (
    build_backtest_engine,
)

from backend.backtesting.backtest_engine import (
    BacktestEngine,
)

from backend.config_settings import (
    ArmsSettings,
)


def test_build_backtest_engine():

    settings = ArmsSettings()

    engine = build_backtest_engine(
        settings=settings,
    )

    assert isinstance(
        engine,
        BacktestEngine,
    )


def test_engine_configuration():

    settings = ArmsSettings()

    engine = build_backtest_engine(
        settings=settings,
    )

    assert (
        engine.initial_balance
        == settings.account_balance
    )

    assert (
        engine.minimum_candles
        >= settings.ema_period
    )

    assert engine.pipeline is not None
