import pytest

from backend.portfolio.risk_analytics import (
    RiskAnalytics,
)


def build_returns() -> list[float]:
    return [
        0.01,
        -0.02,
        0.015,
        -0.01,
        0.02,
        -0.03,
        0.01,
        0.005,
    ]


def test_returns_core_metrics():
    result = RiskAnalytics().calculate(
        returns=build_returns(),
        risk_free_rate=0.02,
    )

    assert "annualized_return" in result
    assert "annualized_volatility" in result
    assert "sharpe_ratio" in result
    assert "sortino_ratio" in result
    assert "maximum_drawdown" in result
    assert "calmar_ratio" in result
    assert "value_at_risk_95" in result
    assert "conditional_value_at_risk_95" in result


def test_var_is_non_positive():
    result = RiskAnalytics().calculate(
        returns=build_returns(),
    )

    assert result["value_at_risk_95"] <= 0.0


def test_cvar_is_not_greater_than_var():
    result = RiskAnalytics().calculate(
        returns=build_returns(),
    )

    assert (
        result[
            "conditional_value_at_risk_95"
        ]
        <= result["value_at_risk_95"]
    )


def test_maximum_drawdown_is_non_positive():
    result = RiskAnalytics().calculate(
        returns=build_returns(),
    )

    assert result["maximum_drawdown"] <= 0.0


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        RiskAnalytics().calculate(
            returns=[],
        )
