from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


class _SmartMoneyStub:
    pass


def _candle(volume: float) -> SimpleNamespace:
    return SimpleNamespace(
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=float(volume),
    )


def _service() -> LiveMarketAnalysisService:
    service = object.__new__(
        LiveMarketAnalysisService
    )

    service.confluence_engine_v2 = (
        ConfluenceEngineV2()
    )

    # The volume contract does not require Smart Money
    # semantics. Disable that dependency and replace the
    # evaluator with a stable neutral fixture.
    service.smart_money_engine_v2 = None

    service._evaluate_smart_money_v2 = (
        lambda candles: {
            "structure": {
                "bos": False,
                "choch": False,
                "direction": "RANGE",
            },
            "liquidity": {
                "liquidity_sweep": False,
                "equal_highs": False,
                "equal_lows": False,
                "liquidity_type": "NONE",
            },
            "fvg": {
                "fvg": False,
                "direction": "NONE",
            },
            "order_block": {
                "order_block": False,
                "direction": "NONE",
            },
        }
    )

    return service


def _result() -> dict[str, object]:
    return {
        "trend": {
            "direction": "SIDEWAYS",
        },
        "ema_alignment": {
            "direction": "SIDEWAYS",
        },
        "probability": 0.50,
        "risk_approved": True,
        "sizing_approved": True,
    }


def _market_regime() -> dict[str, object]:
    return {
        "confidence": 0.50,
        "tradable": True,
    }


def _volume_score(
    *,
    prior_volume: float,
    current_volume: float,
) -> float:
    service = _service()

    candles = [
        _candle(prior_volume)
        for _ in range(19)
    ]
    candles.append(_candle(current_volume))

    confluence = service._evaluate_confluence_v2(
        result=_result(),
        candles=candles,
        market_regime_result=_market_regime(),
        risk_approved=True,
        sizing_approved=True,
    )

    return (
        service
        ._calculate_volume_quality_score(
            candles
        )
    )


@pytest.mark.parametrize(
    (
        "prior_volume",
        "current_volume",
        "expected_score",
    ),
    [
        (100.0, 25.0, 0.00),
        (100.0, 50.0, 0.00),
        (100.0, 75.0, 0.25),
        (100.0, 100.0, 0.50),
        (100.0, 110.0, 0.55),
        (100.0, 125.0, 0.625),
        (100.0, 150.0, 0.75),
        (100.0, 175.0, 0.875),
        (100.0, 200.0, 1.00),
        (100.0, 500.0, 1.00),
    ],
)
def test_volume_quality_uses_prior_candle_baseline(
    prior_volume: float,
    current_volume: float,
    expected_score: float,
) -> None:
    actual = _volume_score(
        prior_volume=prior_volume,
        current_volume=current_volume,
    )

    assert actual == pytest.approx(
        expected_score,
        abs=1e-4,
    )


def test_equal_current_volume_is_neutral_not_full_confirmation(
) -> None:
    actual = _volume_score(
        prior_volume=100.0,
        current_volume=100.0,
    )

    assert actual == pytest.approx(
        0.50,
        abs=1e-4,
    )


def test_stronger_volume_scores_above_normal_volume(
) -> None:
    normal = _volume_score(
        prior_volume=100.0,
        current_volume=100.0,
    )

    strong = _volume_score(
        prior_volume=100.0,
        current_volume=150.0,
    )

    assert strong > normal


def test_weak_volume_scores_below_normal_volume(
) -> None:
    weak = _volume_score(
        prior_volume=100.0,
        current_volume=75.0,
    )

    normal = _volume_score(
        prior_volume=100.0,
        current_volume=100.0,
    )

    assert weak < normal
