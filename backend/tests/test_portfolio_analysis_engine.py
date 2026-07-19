import pytest

from backend.portfolio.portfolio_analysis_engine import (
    PortfolioAnalysisEngine,
)


def test_engine_runs_complete_analysis():
    report = PortfolioAnalysisEngine.analyze(
        returns={
            "A": [0.01, 0.02, 0.03, 0.04],
            "B": [0.02, 0.01, 0.03, 0.05],
            "C": [0.03, 0.01, 0.02, 0.04],
        },
        volatilities={
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        expected_returns={
            "A": 0.08,
            "B": 0.12,
            "C": 0.18,
        },
        risk_free_rate=0.02,
    )

    assert report.optimization is not None
    assert report.recommendation is not None
    assert report.export is not None


def test_engine_preserves_assets():
    report = PortfolioAnalysisEngine.analyze(
        returns={
            "A": [1, 2, 3],
            "B": [1, 2, 3],
        },
        volatilities={
            "A": 0.10,
            "B": 0.20,
        },
        expected_returns={
            "A": 0.08,
            "B": 0.12,
        },
    )

    assert report.assets == (
        "A",
        "B",
    )


def test_engine_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioAnalysisEngine.analyze(
            returns={},
            volatilities={},
            expected_returns={},
        )


def test_engine_is_immutable():
    report = PortfolioAnalysisEngine.analyze(
        returns={
            "A": [1, 2, 3],
        },
        volatilities={
            "A": 0.10,
        },
        expected_returns={
            "A": 0.08,
        },
    )

    with pytest.raises(
        AttributeError,
    ):
        report.assets = ()
