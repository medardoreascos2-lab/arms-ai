import pytest

from backend.ai.recommendation_engine import (
    RecommendationEngine,
)


def test_returns_portfolio_score_and_risk():
    result = RecommendationEngine().analyze(
        weights={
            "AAPL": 0.40,
            "MSFT": 0.35,
            "NVDA": 0.25,
        },
        volatility=0.18,
        sharpe_ratio=1.25,
        beta=1.10,
    )

    assert "score" in result
    assert "risk_level" in result
    assert "recommendations" in result
    assert "alerts" in result


def test_score_is_between_zero_and_one_hundred():
    result = RecommendationEngine().analyze(
        weights={
            "AAPL": 0.40,
            "MSFT": 0.35,
            "NVDA": 0.25,
        },
        volatility=0.18,
        sharpe_ratio=1.25,
        beta=1.10,
    )

    assert 0 <= result["score"] <= 100


def test_detects_high_concentration():
    result = RecommendationEngine().analyze(
        weights={
            "AAPL": 0.60,
            "MSFT": 0.25,
            "NVDA": 0.15,
        },
        volatility=0.20,
        sharpe_ratio=1.00,
        beta=1.20,
    )

    assert any(
        "concentración" in alert.lower()
        for alert in result["alerts"]
    )


def test_detects_low_sharpe_ratio():
    result = RecommendationEngine().analyze(
        weights={
            "AAPL": 0.40,
            "MSFT": 0.35,
            "NVDA": 0.25,
        },
        volatility=0.22,
        sharpe_ratio=0.50,
        beta=1.15,
    )

    assert any(
        "sharpe" in recommendation.lower()
        for recommendation
        in result["recommendations"]
    )


def test_classifies_high_risk():
    result = RecommendationEngine().analyze(
        weights={
            "AAPL": 0.40,
            "MSFT": 0.35,
            "NVDA": 0.25,
        },
        volatility=0.40,
        sharpe_ratio=0.70,
        beta=1.80,
    )

    assert result["risk_level"] == "high"


def test_rejects_invalid_weight_sum():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        RecommendationEngine().analyze(
            weights={
                "AAPL": 0.30,
                "MSFT": 0.20,
            },
            volatility=0.20,
            sharpe_ratio=1.00,
            beta=1.00,
        )


def test_rejects_empty_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        RecommendationEngine().analyze(
            weights={},
            volatility=0.20,
            sharpe_ratio=1.00,
            beta=1.00,
        )
