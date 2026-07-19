import pytest

from backend.application.optimize_portfolio import (
    OptimizePortfolio,
)
from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
)


def build_covariance_matrix():
    correlation = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [0.01, 0.02, 0.03, 0.04],
            "B": [0.02, 0.01, 0.03, 0.05],
            "C": [0.03, 0.01, 0.02, 0.04],
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


def build_expected_returns():
    return {
        "A": 0.08,
        "B": 0.12,
        "C": 0.18,
    }


def test_use_case_returns_optimization_report():
    use_case = OptimizePortfolio()

    report = use_case.execute(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
        risk_free_rate=0.02,
    )

    assert isinstance(
        report,
        PortfolioOptimizationReport,
    )


def test_use_case_builds_all_strategies():
    use_case = OptimizePortfolio()

    report = use_case.execute(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert report.minimum_variance is not None
    assert report.maximum_sharpe is not None
    assert report.risk_parity is not None


def test_use_case_preserves_assets():
    use_case = OptimizePortfolio()

    report = use_case.execute(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert report.assets == (
        "A",
        "B",
        "C",
    )


def test_use_case_accepts_injected_builder():
    class FakeBuilder:
        @staticmethod
        def build(
            *,
            covariance_matrix,
            expected_returns,
            risk_free_rate=0.0,
        ):
            return PortfolioOptimizationReport.build(
                covariance_matrix=covariance_matrix,
                expected_returns=expected_returns,
                risk_free_rate=risk_free_rate,
            )

    use_case = OptimizePortfolio(
        builder=FakeBuilder,
    )

    report = use_case.execute(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert isinstance(
        report,
        PortfolioOptimizationReport,
    )


def test_use_case_rejects_invalid_builder():
    with pytest.raises(
        TypeError,
        match="builder",
    ):
        OptimizePortfolio(
            builder=object(),
        )


def test_use_case_rejects_invalid_matrix():
    use_case = OptimizePortfolio()

    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        use_case.execute(
            covariance_matrix=object(),
            expected_returns=build_expected_returns(),
        )


def test_use_case_rejects_empty_expected_returns():
    use_case = OptimizePortfolio()

    with pytest.raises(
        ValueError,
        match="expected_returns",
    ):
        use_case.execute(
            covariance_matrix=build_covariance_matrix(),
            expected_returns={},
        )
