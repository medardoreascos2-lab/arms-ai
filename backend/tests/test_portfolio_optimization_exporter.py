import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_optimization_exporter import (
    PortfolioOptimizationExporter,
)
from backend.portfolio.portfolio_optimization_recommendation import (
    PortfolioOptimizationRecommendation,
)
from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
)


def build_recommendation(
    *,
    with_rebalancing: bool = True,
):
    correlation = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4],
            "B": [1, 2, 3, 4],
            "C": [1, 2, 3, 4],
        }
    )

    covariance = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        correlation_matrix=correlation,
    )

    report = PortfolioOptimizationReport.build(
        covariance_matrix=covariance,
        expected_returns={
            "A": 0.08,
            "B": 0.12,
            "C": 0.18,
        },
        risk_free_rate=0.02,
    )

    current_weights = None

    if with_rebalancing:
        current_weights = {
            "A": 50.0,
            "B": 30.0,
            "C": 20.0,
        }

    return PortfolioOptimizationRecommendation.from_report(
        report=report,
        current_weights=current_weights,
    )


def test_exporter_builds_serializable_payload():
    payload = PortfolioOptimizationExporter.to_dict(
        recommendation=build_recommendation(),
    )

    assert isinstance(
        payload,
        dict,
    )
    assert payload["strategy"]
    assert payload["risk_level"]
    assert isinstance(
        payload["target_weights"],
        dict,
    )


def test_exporter_includes_metrics():
    payload = PortfolioOptimizationExporter.to_dict(
        recommendation=build_recommendation(),
    )

    metrics = payload["metrics"]

    assert "expected_return" in metrics
    assert "portfolio_volatility" in metrics
    assert "sharpe_ratio" in metrics


def test_exporter_includes_rebalancing():
    payload = PortfolioOptimizationExporter.to_dict(
        recommendation=build_recommendation(),
    )

    rebalancing = payload["rebalancing"]

    assert rebalancing is not None
    assert "trades" in rebalancing
    assert "turnover" in rebalancing


def test_exporter_handles_missing_rebalancing():
    payload = PortfolioOptimizationExporter.to_dict(
        recommendation=build_recommendation(
            with_rebalancing=False,
        ),
    )

    assert payload["rebalancing"] is None


def test_exporter_preserves_explanation():
    recommendation = build_recommendation()

    payload = PortfolioOptimizationExporter.to_dict(
        recommendation=recommendation,
    )

    assert (
        payload["explanation"]
        == recommendation.explanation
    )


def test_exporter_returns_independent_dictionaries():
    recommendation = build_recommendation()

    first = PortfolioOptimizationExporter.to_dict(
        recommendation=recommendation,
    )
    second = PortfolioOptimizationExporter.to_dict(
        recommendation=recommendation,
    )

    first["target_weights"]["A"] = 0.0

    assert (
        second["target_weights"]["A"]
        != 0.0
    )


def test_exporter_rejects_invalid_recommendation():
    with pytest.raises(
        TypeError,
        match="PortfolioOptimizationRecommendation",
    ):
        PortfolioOptimizationExporter.to_dict(
            recommendation=object(),
        )
