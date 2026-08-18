from dataclasses import dataclass

from backend.market_structure.market_structure_engine_v3 import (
    MarketStructureEngineV3,
)


@dataclass
class Candle:
    high: float
    low: float
    close: float = 0.0


def bullish_candles():
    """
    Estructura alcista explícita.

    Swing highs:
        110 -> 115

    Swing lows:
        95 -> 100

    Resultado:
        HH + HL
    """
    return [
        Candle(100, 90),
        Candle(105, 92),

        # Swing high 1
        Candle(110, 98),

        Candle(106, 97),

        # Swing low 1
        Candle(108, 95),

        Candle(112, 99),

        # Swing high 2 = Higher High
        Candle(115, 104),

        Candle(111, 103),

        # Swing low 2 = Higher Low
        Candle(113, 100),

        Candle(114, 102),

        # Current candle
        Candle(118, 105),
    ]


def bearish_candles():
    return [
        Candle(120, 110),
        Candle(118, 108),
        Candle(116, 105),
        Candle(117, 107),
        Candle(115, 106),
        Candle(112, 100),
        Candle(113, 102),
        Candle(111, 101),
        Candle(108, 95),
        Candle(109, 97),
        Candle(106, 90),
    ]


def test_insufficient_candles_returns_unknown():

    result = MarketStructureEngineV3().analyze(
        bullish_candles()[:5]
    )

    assert result.trend == "UNKNOWN"
    assert result.structure == "NONE"
    assert result.bos is False
    assert result.choch is False
    assert result.score == 0.0


def test_bullish_structure():

    result = MarketStructureEngineV3().analyze(
        bullish_candles()
    )

    assert result.trend == "BULLISH"
    assert result.structure == "HH_HL"
    assert result.score >= 50


def test_bearish_structure():

    result = MarketStructureEngineV3().analyze(
        bearish_candles()
    )

    assert result.trend == "BEARISH"
    assert result.structure == "LH_LL"
    assert result.score >= 50


def test_dictionary_candles_supported():

    candles = [
        {
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
        }
        for candle in bullish_candles()
    ]

    result = MarketStructureEngineV3().analyze(
        candles
    )

    assert result.trend == "BULLISH"
    assert result.structure == "HH_HL"
