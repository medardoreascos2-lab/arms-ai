from backend.portfolio.portfolio_analysis_engine import (
    PortfolioAnalysisEngine,
)


class PortfolioAnalysisService:
    """
    Fachada de aplicación para ejecutar análisis
    de portafolio desde API, CLI o dashboard.
    """

    def analyze(
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
        result = self.analyze_detailed(
            returns=returns,
            volatilities=volatilities,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
            current_weights=current_weights,
            tolerance=tolerance,
        )

        return self._copy_payload(
            result.export
        )

    def analyze_detailed(
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
        return PortfolioAnalysisEngine.analyze(
            returns=returns,
            volatilities=volatilities,
            expected_returns=expected_returns,
            risk_free_rate=risk_free_rate,
            current_weights=current_weights,
            tolerance=tolerance,
        )

    @staticmethod
    def _copy_payload(
        payload: dict,
    ) -> dict:
        rebalancing = payload[
            "rebalancing"
        ]

        if rebalancing is None:
            rebalancing_copy = None
        else:
            rebalancing_copy = {
                "assets": list(
                    rebalancing["assets"]
                ),
                "current_weights": dict(
                    rebalancing["current_weights"]
                ),
                "target_weights": dict(
                    rebalancing["target_weights"]
                ),
                "trades": dict(
                    rebalancing["trades"]
                ),
                "turnover": rebalancing["turnover"],
                "overweight_assets": list(
                    rebalancing["overweight_assets"]
                ),
                "underweight_assets": list(
                    rebalancing["underweight_assets"]
                ),
                "tolerance": rebalancing["tolerance"],
            }

        return {
            "strategy": payload["strategy"],
            "risk_level": payload["risk_level"],
            "target_weights": dict(
                payload["target_weights"]
            ),
            "explanation": payload["explanation"],
            "metrics": dict(
                payload["metrics"]
            ),
            "rebalancing": rebalancing_copy,
        }
