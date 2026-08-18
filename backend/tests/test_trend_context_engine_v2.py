from types import SimpleNamespace

from backend.trend.trend_context_engine_v2 import (
    TrendContextEngineV2,
)


class FakeMarketStructureEngine:

    def __init__(
        self,
        results,
    ):
        self.results = list(results)


    def analyze(
        self,
        candles,
    ):
        return self.results.pop(0)


def structure(
    trend,
    name,
    bos=False,
):

    return SimpleNamespace(
        trend=trend,
        structure=name,
        bos=bos,
        choch=False,
    )


def build_engine(
    first,
    second,
):

    engine = TrendContextEngineV2()

    engine.market_structure = (
        FakeMarketStructureEngine(
            [first, second]
        )
    )

    return engine


def test_bullish_alignment_allows_long():

    engine = build_engine(
        structure(
            "BULLISH",
            "HH_HL",
            True,
        ),
        structure(
            "BULLISH",
            "HH_HL",
            True,
        ),
    )

    result = engine.analyze(
        [],
        [],
    )

    assert result.aligned is True
    assert result.allowed_direction == "LONG"
    assert result.score == 100


def test_bearish_alignment_allows_short():

    engine = build_engine(
        structure(
            "BEARISH",
            "LH_LL",
            True,
        ),
        structure(
            "BEARISH",
            "LH_LL",
            True,
        ),
    )

    result = engine.analyze(
        [],
        [],
    )

    assert result.aligned is True
    assert result.allowed_direction == "SHORT"
    assert result.score == 100


def test_mixed_context_blocks_direction():

    engine = build_engine(
        structure(
            "BULLISH",
            "HH_HL",
        ),
        structure(
            "BEARISH",
            "LH_LL",
        ),
    )

    result = engine.analyze(
        [],
        [],
    )

    assert result.aligned is False
    assert result.allowed_direction == "NONE"
