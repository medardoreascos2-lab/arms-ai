import pytest

from backend.ai.explanation_engine import (
    ExplanationEngine,
)


def test_explains_sharpe_ratio():
    result = ExplanationEngine().explain_metric(
        metric="sharpe_ratio",
        value=1.40,
    )

    assert result["metric"] == "sharpe_ratio"
    assert result["value"] == 1.40
    assert result["classification"] == "good"
    assert "riesgo" in result["explanation"].lower()


def test_explains_high_beta():
    result = ExplanationEngine().explain_metric(
        metric="beta",
        value=1.70,
    )

    assert result["classification"] == "high"
    assert "mercado" in result["explanation"].lower()


def test_explains_high_volatility():
    result = ExplanationEngine().explain_metric(
        metric="volatility",
        value=0.35,
    )

    assert result["classification"] == "high"
    assert "volatilidad" in result["explanation"].lower()


def test_explains_negative_drawdown():
    result = ExplanationEngine().explain_metric(
        metric="drawdown",
        value=-0.25,
    )

    assert result["classification"] == "severe"
    assert "caída" in result["explanation"].lower()


def test_explains_portfolio_score():
    result = ExplanationEngine().explain_metric(
        metric="portfolio_score",
        value=88,
    )

    assert result["classification"] == "excellent"
    assert "portafolio" in result["explanation"].lower()


def test_rejects_unknown_metric():
    with pytest.raises(
        ValueError,
        match="metric",
    ):
        ExplanationEngine().explain_metric(
            metric="unknown",
            value=1.0,
        )


def test_rejects_non_finite_value():
    with pytest.raises(
        ValueError,
        match="value",
    ):
        ExplanationEngine().explain_metric(
            metric="beta",
            value=float("nan"),
        )
