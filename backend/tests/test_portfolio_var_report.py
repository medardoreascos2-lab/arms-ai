import pytest

from backend.portfolio.portfolio_var_report import (
    PortfolioVaRReport,
)


def test_var_report_calculates_historical_var():
    report = PortfolioVaRReport.from_returns(
        returns=[
            -0.05,
            -0.03,
            -0.02,
            -0.01,
            0.00,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
        confidence=0.95,
    )

    assert report.confidence == 0.95
    assert report.historical_var == pytest.approx(
        0.05,
        abs=0.01,
    )


def test_var_report_calculates_expected_shortfall():
    report = PortfolioVaRReport.from_returns(
        returns=[
            -0.08,
            -0.05,
            -0.03,
            -0.02,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
            0.06,
        ],
        confidence=0.80,
    )

    assert report.expected_shortfall >= report.historical_var


@pytest.mark.parametrize(
    "confidence",
    [
        0.0,
        1.0,
        -0.5,
        2.0,
    ],
)
def test_var_report_rejects_invalid_confidence(
    confidence,
):
    with pytest.raises(
        ValueError,
        match="confidence",
    ):
        PortfolioVaRReport.from_returns(
            returns=[0.01, -0.01],
            confidence=confidence,
        )


def test_var_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioVaRReport.from_returns(
            returns=[],
            confidence=0.95,
        )


def test_var_report_is_immutable():
    report = PortfolioVaRReport.from_returns(
        returns=[
            -0.01,
            0.02,
        ],
        confidence=0.95,
    )

    with pytest.raises(
        AttributeError,
    ):
        report.historical_var = 0.0
