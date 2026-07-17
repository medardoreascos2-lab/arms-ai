import pytest

from backend.portfolio.portfolio_cvar_report import (
    PortfolioCVaRReport,
)


def test_cvar_report_calculates_expected_shortfall():
    report = PortfolioCVaRReport.from_returns(
        returns=[
            -0.10,
            -0.08,
            -0.05,
            -0.03,
            -0.01,
            0.00,
            0.02,
            0.03,
            0.04,
            0.05,
        ],
        confidence=0.80,
    )

    assert report.confidence == 0.80
    assert report.var_threshold == pytest.approx(
        0.08,
        abs=0.01,
    )
    assert report.conditional_var == pytest.approx(
        0.09,
        abs=0.01,
    )
    assert report.tail_observations == 2


def test_cvar_is_never_lower_than_var():
    report = PortfolioCVaRReport.from_returns(
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

    assert report.conditional_var >= report.var_threshold


def test_cvar_report_handles_positive_only_returns():
    report = PortfolioCVaRReport.from_returns(
        returns=[
            0.01,
            0.02,
            0.03,
            0.04,
        ],
        confidence=0.95,
    )

    assert report.var_threshold == 0.0
    assert report.conditional_var == 0.0
    assert report.tail_observations == 1


@pytest.mark.parametrize(
    "confidence",
    [
        0.0,
        1.0,
        -0.1,
        1.5,
    ],
)
def test_cvar_report_rejects_invalid_confidence(
    confidence,
):
    with pytest.raises(
        ValueError,
        match="confidence",
    ):
        PortfolioCVaRReport.from_returns(
            returns=[
                -0.01,
                0.02,
            ],
            confidence=confidence,
        )


def test_cvar_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioCVaRReport.from_returns(
            returns=[],
            confidence=0.95,
        )


def test_cvar_report_is_immutable():
    report = PortfolioCVaRReport.from_returns(
        returns=[
            -0.02,
            -0.01,
            0.01,
        ],
        confidence=0.95,
    )

    with pytest.raises(
        AttributeError,
    ):
        report.conditional_var = 0.0
