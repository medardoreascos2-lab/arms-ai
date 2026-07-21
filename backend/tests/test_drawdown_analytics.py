import pytest

from backend.portfolio.drawdown_analytics import (
    DrawdownAnalytics,
)


def build_returns() -> list[float]:
    return [
        0.10,
        -0.05,
        -0.10,
        0.04,
        0.03,
        -0.02,
        0.08,
    ]


def test_returns_drawdown_metrics():
    result = DrawdownAnalytics().calculate(
        returns=build_returns()
    )

    assert "equity_curve" in result
    assert "drawdown_curve" in result
    assert "maximum_drawdown" in result
    assert "maximum_drawdown_duration" in result
    assert "peak_index" in result
    assert "trough_index" in result


def test_curves_include_initial_value():
    result = DrawdownAnalytics().calculate(
        returns=build_returns()
    )

    assert len(result["equity_curve"]) == 8
    assert len(result["drawdown_curve"]) == 8
    assert result["equity_curve"][0] == pytest.approx(
        1.0
    )
    assert result["drawdown_curve"][0] == pytest.approx(
        0.0
    )


def test_maximum_drawdown_is_non_positive():
    result = DrawdownAnalytics().calculate(
        returns=build_returns()
    )

    assert result["maximum_drawdown"] <= 0.0


def test_duration_is_non_negative():
    result = DrawdownAnalytics().calculate(
        returns=build_returns()
    )

    assert (
        result["maximum_drawdown_duration"]
        >= 0
    )


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        DrawdownAnalytics().calculate(
            returns=[]
        )
