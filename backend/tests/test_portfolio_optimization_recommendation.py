import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_optimization_recommendation import (
    PortfolioOptimizationRecommendation,
)
from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
)


def build_covariance_matrix():
    correlation = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4],
            "B": [1, 2, 3, 4],
            "C": [1, 2, 3, 4],
        }
    )

    return PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        correlation_matrix=correlation,
    )


def build_report():
    return PortfolioOptimizationReport.build(
        covariance_matrix=build_covariance_matrix(),
        expected_returns={
            "A": 0.08,
            "B": 0.12,
            "C": 0.18,
        },
        risk_free_rate=0.02,
    )


def test_recommendation_preserves_selected_strategy():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    assert recommendation.strategy in {
        "minimum_variance",
        "maximum_sharpe",
        "risk_parity",
    }


def test_recommendation_exposes_target_weights():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    assert set(recommendation.target_weights) == {
        "A",
        "B",
        "C",
    }

    assert sum(
        recommendation.target_weights.values()
    ) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_recommendation_classifies_risk():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    assert recommendation.risk_level in {
        "conservative",
        "moderate",
        "aggressive",
    }


def test_recommendation_builds_explanation():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    assert recommendation.explanation
    assert recommendation.strategy in (
        recommendation.explanation
    )


def test_recommendation_builds_rebalancing_plan():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
            current_weights={
                "A": 50.0,
                "B": 30.0,
                "C": 20.0,
            },
        )
    )

    assert recommendation.rebalancing is not None
    assert set(
        recommendation.rebalancing.trades
    ) == {
        "A",
        "B",
        "C",
    }


def test_recommendation_allows_missing_current_weights():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    assert recommendation.rebalancing is None


def test_recommendation_rejects_invalid_report():
    with pytest.raises(
        TypeError,
        match="PortfolioOptimizationReport",
    ):
        PortfolioOptimizationRecommendation.from_report(
            report=object(),
        )


def test_recommendation_is_immutable():
    recommendation = (
        PortfolioOptimizationRecommendation.from_report(
            report=build_report(),
        )
    )

    with pytest.raises(
        AttributeError,
    ):
        recommendation.strategy = ""
