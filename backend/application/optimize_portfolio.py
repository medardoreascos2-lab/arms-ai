from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
)


class OptimizePortfolio:
    """
    Caso de uso para ejecutar únicamente la
    optimización de un portafolio.
    """

    def __init__(
        self,
        *,
        builder=PortfolioOptimizationReport,
    ) -> None:
        build_method = getattr(
            builder,
            "build",
            None,
        )

        if not callable(build_method):
            raise TypeError(
                "builder debe exponer un método build."
            )

        self._builder = builder

    def execute(
        self,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
        expected_returns: dict[str, float],
        risk_free_rate: float = 0.0,
    ) -> PortfolioOptimizationReport:
        if not isinstance(
            covariance_matrix,
            PortfolioCovarianceMatrix,
        ):
            raise TypeError(
                "covariance_matrix debe ser "
                "PortfolioCovarianceMatrix."
            )

        if not expected_returns:
            raise ValueError(
                "expected_returns no puede estar vacío."
            )

        return self._builder.build(
            covariance_matrix=covariance_matrix,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
        )
