import pytest

from backend.portfolio.fama_french_analytics import (
    FamaFrenchAnalytics,
)


def portfolio_returns():
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


def market():
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


def smb():
    return [
        0.003,
        -0.001,
        0.002,
        0.001,
        -0.002,
        0.003,
        0.001,
        0.000,
    ]


def hml():
    return [
        -0.002,
        0.001,
        -0.001,
        0.002,
        0.001,
        -0.002,
        0.000,
        0.001,
    ]


def test_returns_factor_loadings():
    result = FamaFrenchAnalytics().calculate(
        portfolio_returns=portfolio_returns(),
        market_returns=market(),
        smb_returns=smb(),
        hml_returns=hml(),
        risk_free_rate=0.02,
    )

    assert "alpha" in result
    assert "beta_market" in result
    assert "beta_smb" in result
    assert "beta_hml" in result
    assert "r_squared" in result
    assert "expected_return" in result


def test_r_squared_between_zero_and_one():
    result = FamaFrenchAnalytics().calculate(
        portfolio_returns=portfolio_returns(),
        market_returns=market(),
        smb_returns=smb(),
        hml_returns=hml(),
    )

    assert 0 <= result["r_squared"] <= 1


def test_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="misma longitud",
    ):
        FamaFrenchAnalytics().calculate(
            portfolio_returns=[0.01],
            market_returns=[0.01],
            smb_returns=[],
            hml_returns=[],
        )


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        FamaFrenchAnalytics().calculate(
            portfolio_returns=[],
            market_returns=[],
            smb_returns=[],
            hml_returns=[],
        )
