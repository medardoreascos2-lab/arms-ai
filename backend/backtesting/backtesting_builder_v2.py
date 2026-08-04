from __future__ import annotations

from backend.backtesting.backtest_engine import (
    BacktestEngine,
)
from backend.config_settings import (
    ArmsSettings,
)
from backend.pipeline.pipeline_factory import (
    PipelineFactory,
)
from backend.pipeline.pipeline_mode import (
    PipelineMode,
)


def build_backtest_engine(
    *,
    settings: ArmsSettings,
    collector=None,
) -> BacktestEngine:
    """
    Construye el BacktestEngine estándar de ARMS AI
    reutilizando la configuración institucional.
    """

    if not isinstance(
        settings,
        ArmsSettings,
    ):
        raise TypeError(
            "settings debe ser ArmsSettings."
        )

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create(
        mode=PipelineMode.BACKTEST,
    )

    minimum_candles = max(
        settings.ema_period,
        settings.rsi_period + 1,
        settings.atr_period + 1,
    )

    return BacktestEngine(
        pipeline=pipeline,
        minimum_candles=minimum_candles,
        initial_balance=settings.account_balance,
    )
