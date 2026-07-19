from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioOmegaRatioReport:
    """
    Calcula el Omega Ratio respecto a un umbral
    mínimo aceptable.
    """

    omega_ratio: float
    total_gains: float
    total_losses: float
    threshold: float
    sample_size: int

    @classmethod
    def from_returns(
        cls,
        *,
        returns: list[float] | tuple[float, ...],
        threshold: float = 0.0,
    ) -> "PortfolioOmegaRatioReport":
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        normalized_returns = tuple(
            float(value)
            for value in returns
        )
        normalized_threshold = float(
            threshold
        )

        total_gains = sum(
            max(
                0.0,
                value - normalized_threshold,
            )
            for value in normalized_returns
        )

        total_losses = sum(
            max(
                0.0,
                normalized_threshold - value,
            )
            for value in normalized_returns
        )

        total_gains = round(
            total_gains,
            6,
        )
        total_losses = round(
            total_losses,
            6,
        )

        if total_losses == 0:
            omega_ratio = 0.0
        else:
            omega_ratio = (
                total_gains
                / total_losses
            )

        return cls(
            omega_ratio=round(
                omega_ratio,
                6,
            ),
            total_gains=total_gains,
            total_losses=total_losses,
            threshold=normalized_threshold,
            sample_size=len(
                normalized_returns
            ),
        )
