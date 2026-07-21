import pytest

from backend.portfolio.capm_analytics import (
    CapmAnalytics,
)


def build_portfolio_returns() -> list[float]:
    return [
        0.012,
        -0.008,
        0.015,
        0.004,
        -0.010,
        0.018,
        0.006,
        -0.003,
    ]


def build_market_returns() -> list[float]:
    return [
        0.010,
        -0.006,
        0.011,
        0.003,
        -0.008,
        0.013,
        0.004,
        -0.002,
    ]


def test_returns_capm_metrics():
    result = CapmAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        market_returns=build_market_returns(),
        risk_free_rate=0.02,
    )

    assert "beta" in result
    assert "jensens_alpha" in result
    assert "capm_expected_return" in result
    assert "market_risk_premium" in result
    assert "treynor_ratio" in result
    assert "modigliani_m2" in result


def test_beta_is_finite():
    result = CapmAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        market_returns=build_market_returns(),
    )

    assert result["beta"] == pytest.approx(
        float(result["beta"])
    )


def test_capm_expected_return_uses_beta():
    result = CapmAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        market_returns=build_market_returns(),
        risk_free_rate=0.02,
    )

    expected = (
        0.02
        + result["beta"]
        * result["market_risk_premium"]
    )

    assert result["capm_expected_return"] == pytest.approx(
        expected
    )


def test_rejects_different_series_lengths():
    with pytest.raises(
        ValueError,
        match="misma longitud",
    ):
        CapmAnalytics().calculate(
            portfolio_returns=[0.01, 0.02],
            market_returns=[0.01],
        )


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        CapmAnalytics().calculate(
            portfolio_returns=[],
            market_returns=[],
        )
