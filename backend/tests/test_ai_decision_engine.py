from backend.ai.ai_decision_engine import (
    AIDecisionEngine,
)


def build_metrics() -> dict[str, float]:
    return {
        "volatility": 0.22,
        "sharpe_ratio": 0.75,
        "beta": 1.20,
        "drawdown": -0.18,
    }


def build_weights() -> dict[str, float]:
    return {
        "AAPL": 0.50,
        "MSFT": 0.30,
        "NVDA": 0.20,
    }


def test_returns_complete_decision_payload():
    result = AIDecisionEngine().analyze(
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert "score" in result
    assert "risk_level" in result
    assert "alerts" in result
    assert "recommendations" in result
    assert "explanations" in result
    assert "summary" in result


def test_explanations_include_supported_metrics():
    result = AIDecisionEngine().analyze(
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert set(result["explanations"]) == {
        "volatility",
        "sharpe_ratio",
        "beta",
        "drawdown",
        "portfolio_score",
    }


def test_summary_mentions_risk_level():
    result = AIDecisionEngine().analyze(
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert result["risk_level"] in (
        result["summary"].lower()
    )


def test_propagates_recommendation_alerts():
    result = AIDecisionEngine().analyze(
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert any(
        "concentración" in alert.lower()
        for alert in result["alerts"]
    )


def test_rejects_missing_required_metric():
    try:
        AIDecisionEngine().analyze(
            weights=build_weights(),
            metrics={
                "volatility": 0.20,
                "sharpe_ratio": 1.00,
                "beta": 1.00,
            },
        )
    except ValueError as error:
        assert "metrics" in str(error)
    else:
        raise AssertionError(
            "Se esperaba ValueError."
        )
