from dataclasses import dataclass

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


@dataclass(frozen=True)
class PortfolioAnalysisEngine:
    """
    Orquesta el pipeline completo de análisis
    y optimización de portafolio.
    """

    assets: tuple[str, ...]
    correlation_matrix: PortfolioCorrelationMatrix
    covariance_matrix: PortfolioCovarianceMatrix
    optimization: PortfolioOptimizationReport
    recommendation: PortfolioOptimizationRecommendation
    export: dict

    @classmethod
    def analyze(
        cls,
        *,
        returns: dict[
            str,
            list[float] | tuple[float, ...],
        ],
        volatilities: dict[str, float],
        expected_returns: dict[str, float],
        risk_free_rate: float = 0.0,
        current_weights: dict[str, float] | None = None,
        tolerance: float = 0.0,
    ) -> "PortfolioAnalysisEngine":
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        normalized_returns = {
            symbol.strip().upper(): values
            for symbol, values in returns.items()
        }

        normalized_volatilities = {
            symbol.strip().upper(): float(value)
            for symbol, value in volatilities.items()
        }

        normalized_expected_returns = {
            symbol.strip().upper(): float(value)
            for symbol, value in expected_returns.items()
        }

        assets = tuple(
            normalized_returns
        )

        asset_set = set(
            assets
        )

        if set(normalized_volatilities) != asset_set:
            raise ValueError(
                "volatilities debe contener "
                "los mismos activos que returns."
            )

        if set(normalized_expected_returns) != asset_set:
            raise ValueError(
                "expected_returns debe contener "
                "los mismos activos que returns."
            )

        correlation_matrix = (
            PortfolioCorrelationMatrix.from_returns(
                normalized_returns
            )
        )

        covariance_matrix = (
            PortfolioCovarianceMatrix.from_inputs(
                volatilities=normalized_volatilities,
                correlation_matrix=correlation_matrix,
            )
        )

        optimization = PortfolioOptimizationReport.build(
            covariance_matrix=covariance_matrix,
            expected_returns=normalized_expected_returns,
            risk_free_rate=risk_free_rate,
        )

        recommendation = (
            PortfolioOptimizationRecommendation.from_report(
                report=optimization,
                current_weights=current_weights,
                tolerance=tolerance,
            )
        )

        export = PortfolioOptimizationExporter.to_dict(
            recommendation=recommendation,
        )

        return cls(
            assets=assets,
            correlation_matrix=correlation_matrix,
            covariance_matrix=covariance_matrix,
            optimization=optimization,
            recommendation=recommendation,
            export=export,
        )
