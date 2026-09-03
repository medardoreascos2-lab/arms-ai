from __future__ import annotations

import pytest

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


EXPECTED_PRIMARY_WEIGHTS = {
    "trend": 15.0 / 85.0 * 100.0,
    "structure": 15.0 / 85.0 * 100.0,
    "liquidity": 10.0 / 85.0 * 100.0,
    "fvg": 10.0 / 85.0 * 100.0,
    "ema_alignment": 10.0 / 85.0 * 100.0,
    "market_regime": 15.0 / 85.0 * 100.0,
    "volume": 10.0 / 85.0 * 100.0,
}


def _build_service() -> LiveMarketAnalysisService:
    service = object.__new__(
        LiveMarketAnalysisService
    )
    service.confluence_engine_v2 = (
        ConfluenceEngineV2()
    )
    service.smart_money_engine_v2 = None
    return service


def _base_result(
    probability: float,
) -> dict[str, object]:
    return {
        "trend": {
            "trend": "ALCISTA",
        },
        "ema": {
            "direction": "ALCISTA",
        },
        "market_structure": {
            "direction": "ALCISTA",
            "bos": True,
            "choch": False,
        },
        "smart_money": {
            "direction": "ALCISTA",
        },
        "probability": probability,
    }


def _evaluate_runtime(
    probability: float,
) -> dict[str, object]:
    return (
        _build_service()
        ._evaluate_confluence_v2(
            result=_base_result(
                probability
            ),
            candles=[],
            risk_approved=True,
            sizing_approved=True,
            market_regime_result=None,
        )
    )


def _evaluate_uniform_quality(
    quality: float,
    probability_score: float,
) -> dict[str, object]:
    engine = ConfluenceEngineV2()

    return engine.evaluate(
        trend_score=quality,
        structure_score=quality,
        liquidity_score=quality,
        fvg_score=quality,
        ema_alignment_score=quality,
        market_regime_score=quality,
        probability_score=probability_score,
        volume_score=quality,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )


def test_probability_argument_remains_accepted_for_compatibility():
    engine = ConfluenceEngineV2()

    result = engine.evaluate(
        trend_score=1.0,
        structure_score=1.0,
        liquidity_score=1.0,
        fvg_score=1.0,
        ema_alignment_score=1.0,
        market_regime_score=1.0,
        probability_score=0.25,
        volume_score=1.0,
        risk_approved=True,
        sizing_approved=True,
        market_tradable=True,
    )

    assert result["score"] == 100.0
    assert result["grade"] == "A+"


def test_probability_has_no_confluence_weight_authority():
    engine = ConfluenceEngineV2()

    assert (
        "probability"
        not in engine.WEIGHTS
    )

    assert (
        sum(
            engine.WEIGHTS.values()
        )
        == pytest.approx(100.0)
    )

    for key, expected in (
        EXPECTED_PRIMARY_WEIGHTS.items()
    ):
        assert (
            engine.WEIGHTS[key]
            == pytest.approx(expected)
        )


@pytest.mark.parametrize(
    "quality,expected_score,expected_grade",
    [
        (1.00, 100.0, "A+"),
        (0.90, 90.0, "A+"),
        (0.80, 80.0, "A"),
        (0.50, 50.0, "C"),
    ],
)
def test_primary_quality_preserves_canonical_scale(
    quality: float,
    expected_score: float,
    expected_grade: str,
):
    low_probability = (
        _evaluate_uniform_quality(
            quality,
            0.0,
        )
    )
    high_probability = (
        _evaluate_uniform_quality(
            quality,
            1.0,
        )
    )

    assert (
        low_probability["score"]
        == pytest.approx(
            expected_score
        )
    )
    assert (
        high_probability["score"]
        == pytest.approx(
            expected_score
        )
    )

    assert (
        low_probability["grade"]
        == expected_grade
    )
    assert (
        high_probability["grade"]
        == expected_grade
    )


def test_runtime_legacy_probability_cannot_change_confluence():
    low = _evaluate_runtime(10.0)
    high = _evaluate_runtime(95.0)

    assert (
        low["score"]
        == high["score"]
    )
    assert (
        low["grade"]
        == high["grade"]
    )
    assert (
        low["approved"]
        == high["approved"]
    )
    assert (
        low["status"]
        == high["status"]
    )
    assert (
        low["decision"]
        == high["decision"]
    )


def test_probability_is_not_reported_as_confluence_contribution():
    result = _evaluate_uniform_quality(
        1.0,
        1.0,
    )

    assert (
        "probability"
        not in result["contributions"]
    )
    assert (
        "probability"
        not in result["weights"]
    )
