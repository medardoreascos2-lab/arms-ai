from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PortfolioCVaRReport:
    """
    Calcula VaR histórico y Conditional VaR
    sobre una serie de rendimientos.
    """

    confidence: float
    var_threshold: float
    conditional_var: float
    tail_observations: int
    sample_size: int

    @classmethod
    def from_returns(
        cls,
        *,
        returns: list[float] | tuple[float, ...],
        confidence: float,
    ) -> "PortfolioCVaRReport":
        if not 0 < confidence < 1:
            raise ValueError(
                "confidence debe estar entre 0 y 1."
            )

        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        normalized_returns = sorted(
            float(value)
            for value in returns
        )

        tail_count = max(
            1,
            math.ceil(
                (1 - confidence)
                * len(normalized_returns)
            ),
        )

        tail_returns = normalized_returns[
            :tail_count
        ]

        var_return = tail_returns[-1]

        var_threshold = max(
            0.0,
            -var_return,
        )

        conditional_var = max(
            0.0,
            -(
                sum(tail_returns)
                / len(tail_returns)
            ),
        )

        return cls(
            confidence=float(confidence),
            var_threshold=round(
                var_threshold,
                6,
            ),
            conditional_var=round(
                conditional_var,
                6,
            ),
            tail_observations=len(
                tail_returns
            ),
            sample_size=len(
                normalized_returns
            ),
        )
