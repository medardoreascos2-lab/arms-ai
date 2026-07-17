from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PortfolioVaRReport:
    """
    Calcula Value at Risk histórico y Expected Shortfall
    a partir de una serie de rendimientos.
    """

    confidence: float
    historical_var: float
    expected_shortfall: float
    sample_size: int

    @classmethod
    def from_returns(
        cls,
        *,
        returns: list[float] | tuple[float, ...],
        confidence: float,
    ) -> "PortfolioVaRReport":
        if not 0 < confidence < 1:
            raise ValueError(
                "confidence debe estar entre 0 y 1."
            )

        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        normalized_returns = [
            float(value)
            for value in returns
        ]

        sorted_returns = sorted(
            normalized_returns
        )

        tail_probability = 1 - confidence

        percentile_index = max(
            0,
            math.ceil(
                tail_probability
                * len(sorted_returns)
            )
            - 1,
        )

        var_return = sorted_returns[
            percentile_index
        ]

        tail_returns = [
            value
            for value in sorted_returns
            if value <= var_return
        ]

        historical_var = max(
            0.0,
            -var_return,
        )

        expected_shortfall = max(
            0.0,
            -(
                sum(tail_returns)
                / len(tail_returns)
            ),
        )

        return cls(
            confidence=float(confidence),
            historical_var=round(
                historical_var,
                6,
            ),
            expected_shortfall=round(
                expected_shortfall,
                6,
            ),
            sample_size=len(
                normalized_returns
            ),
        )
