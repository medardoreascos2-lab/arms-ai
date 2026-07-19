from backend.portfolio.portfolio_analysis_engine import (
    PortfolioAnalysisEngine,
)
from backend.portfolio.portfolio_analysis_service import (
    PortfolioAnalysisService,
)


class AnalyzePortfolio:
    """
    Caso de uso para ejecutar análisis de portafolio
    desde cualquier interfaz de entrada.
    """

    def __init__(
        self,
        *,
        service: PortfolioAnalysisService | None = None,
    ) -> None:
        if service is None:
            service = PortfolioAnalysisService()

        if not isinstance(
            service,
            PortfolioAnalysisService,
        ):
            raise TypeError(
                "service debe ser "
                "PortfolioAnalysisService."
            )

        self._service = service

    def execute(
        self,
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
    ) -> dict:
        return self._service.analyze(
            returns=returns,
            volatilities=volatilities,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
            current_weights=current_weights,
            tolerance=tolerance,
        )

    def execute_detailed(
        self,
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
    ) -> PortfolioAnalysisEngine:
        return self._service.analyze_detailed(
            returns=returns,
            volatilities=volatilities,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
            current_weights=current_weights,
            tolerance=tolerance,
        )
