import pytest

from backend.portfolio.rolling_analytics import (
    RollingAnalytics,
)


def build_returns() -> list[float]:
    return [
        0.010,
        -0.005,
        0.012,
        0.008,
        -0.010,
        0.015,
        0.004,
        -0.006,
        0.011,
        0.009,
    ]


def test_returns_rolling_metrics():
    result = RollingAnalytics().calculate(
        returns=build_returns(),
        window=4,
        risk_free_rate=0.02,
    )

    assert "rolling_volatility" in result
    assert "rolling_sharpe" in result
    assert "rolling_drawdown" in result


def test_rolling_series_have_expected_length():
    result = RollingAnalytics().calculate(
        returns=build_returns(),
        window=4,
    )

    expected_length = (
        len(build_returns()) - 4 + 1
    )

    assert (
        len(result["rolling_volatility"])
        == expected_length
    )
    assert (
        len(result["rolling_sharpe"])
        == expected_length
    )
    assert (
        len(result["rolling_drawdown"])
        == expected_length
    )


def test_rolling_volatility_is_non_negative():
    result = RollingAnalytics().calculate(
        returns=build_returns(),
        window=4,
    )

    assert all(
        value >= 0.0
        for value
        in result["rolling_volatility"]
    )


def test_rolling_drawdown_is_non_positive():
    result = RollingAnalytics().calculate(
        returns=build_returns(),
        window=4,
    )

    assert all(
        value <= 0.0
        for value
        in result["rolling_drawdown"]
    )


def test_rejects_invalid_window():
    with pytest.raises(
        ValueError,
        match="window",
    ):
        RollingAnalytics().calculate(
            returns=build_returns(),
            window=20,
        )


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        RollingAnalytics().calculate(
            returns=[],
            window=3,
        )
