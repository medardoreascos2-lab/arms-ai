from types import SimpleNamespace

from backend.intelligence.trade_quality_engine_v1 import (
    TradeQualityEngineV1,
)


def test_a_plus_complete_setup_is_approved():

    engine = TradeQualityEngineV1()

    result = engine.evaluate(
        confluence=SimpleNamespace(
            grade="A+",
        ),
        market_structure=SimpleNamespace(
            structure="HH_HL",
            bos=True,
            choch=False,
        ),
        trend_context=SimpleNamespace(
            aligned=True,
        ),
    )

    assert result.score == 100
    assert result.approved is True


def test_opposite_choch_hard_blocks_trade():

    engine = TradeQualityEngineV1()

    result = engine.evaluate(
        confluence=SimpleNamespace(
            grade="A+",
        ),
        market_structure=SimpleNamespace(
            structure="HH_HL",
            bos=True,
            choch=True,
        ),
        trend_context=SimpleNamespace(
            aligned=True,
        ),
    )

    assert result.score == 0
    assert result.approved is False

    assert result.reasons == [
        "Opposite CHOCH detected",
    ]


def test_weak_setup_is_blocked():

    engine = TradeQualityEngineV1()

    result = engine.evaluate(
        confluence=SimpleNamespace(
            grade="B",
        ),
        market_structure=SimpleNamespace(
            structure="RANGE",
            bos=False,
            choch=True,
        ),
        trend_context=SimpleNamespace(
            aligned=False,
        ),
    )

    assert result.score == 0
    assert result.approved is False


def test_clean_a_plus_remains_approved():

    engine = TradeQualityEngineV1()

    result = engine.evaluate(
        confluence=SimpleNamespace(
            grade="A+",
        ),
        market_structure=SimpleNamespace(
            structure="LH_LL",
            bos=True,
            choch=False,
        ),
        trend_context=SimpleNamespace(
            aligned=True,
        ),
    )

    assert result.score == 100
    assert result.approved is True
