from dataclasses import dataclass
from itertools import combinations

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)


@dataclass(frozen=True)
class PortfolioDiversificationReport:
    """
    Resume el nivel de diversificación de un portafolio
    a partir de su matriz de correlación.
    """

    average_correlation: float
    max_correlation: float
    min_correlation: float
    score: float
    level: str

    @classmethod
    def from_matrix(
        cls,
        matrix: PortfolioCorrelationMatrix,
    ) -> "PortfolioDiversificationReport":
        if not isinstance(
            matrix,
            PortfolioCorrelationMatrix,
        ):
            raise TypeError(
                "matrix debe ser "
                "PortfolioCorrelationMatrix."
            )

        pairs = list(
            combinations(
                matrix.assets,
                2,
            )
        )

        if not pairs:
            return cls(
                average_correlation=0.0,
                max_correlation=0.0,
                min_correlation=0.0,
                score=100.0,
                level="excellent",
            )

        correlations = [
            matrix.correlation(
                first_asset,
                second_asset,
            )
            for first_asset, second_asset in pairs
        ]

        average_correlation = (
            sum(correlations)
            / len(correlations)
        )

        max_correlation = max(
            correlations
        )
        min_correlation = min(
            correlations
        )

        score = (
            1
            - (
                average_correlation + 1
            )
            / 2
        ) * 100

        score = max(
            0.0,
            min(
                100.0,
                score,
            ),
        )

        if score < 25:
            level = "poor"
        elif score < 50:
            level = "fair"
        elif score < 75:
            level = "good"
        else:
            level = "excellent"

        return cls(
            average_correlation=round(
                average_correlation,
                2,
            ),
            max_correlation=round(
                max_correlation,
                6,
            ),
            min_correlation=round(
                min_correlation,
                6,
            ),
            score=round(
                score,
                2,
            ),
            level=level,
        )
