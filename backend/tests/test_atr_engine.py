from datetime import datetime, timedelta

import pytest

from backend.indicators.atr_engine import ATREngine
from backend.models.candle import Candle


def build_candles(
    total: int,
    candle_range: float,
) -> list[Candle]:
    candles = []
    timestamp = datetime(2026, 1, 1, 9, 30)
    price = 100.0

    for index in range(total):
        candles.append(
            Candle(
                symbol="TEST",
                timeframe="1m",
                open=price,
                high=price + candle_range / 2,
                low=price - candle_range / 2,
                close=price,
                volume=1000,
                timestamp=timestamp + timedelta(minutes=index),
            )
        )

    return candles


def test_atr_engine_uses_default_thresholds():
    engine = ATREngine(period=14)

    engine.atr = 4.9
    engine._update_status()
    assert engine.status == "VOLATILIDAD BAJA"

    engine.atr = 5.0
    engine._update_status()
    assert engine.status == "VOLATILIDAD MEDIA"

    engine.atr = 15.0
    engine._update_status()
    assert engine.status == "VOLATILIDAD ALTA"


def test_atr_engine_accepts_custom_thresholds():
    engine = ATREngine(
        period=14,
        low_threshold=2.0,
        high_threshold=6.0,
    )

    engine.atr = 1.9
    engine._update_status()
    assert engine.status == "VOLATILIDAD BAJA"

    engine.atr = 2.3
    engine._update_status()
    assert engine.status == "VOLATILIDAD MEDIA"

    engine.atr = 6.0
    engine._update_status()
    assert engine.status == "VOLATILIDAD ALTA"


def test_atr_engine_rejects_invalid_thresholds():
    with pytest.raises(
        ValueError,
        match="threshold",
    ):
        ATREngine(
            low_threshold=5.0,
            high_threshold=2.0,
        )


def test_atr_engine_calculates_with_custom_thresholds():
    engine = ATREngine(
        period=14,
        low_threshold=2.0,
        high_threshold=6.0,
    )

    engine.calculate(
        build_candles(
            total=20,
            candle_range=2.5,
        )
    )

    assert engine.atr == pytest.approx(2.5)
    assert engine.status == "VOLATILIDAD MEDIA"
