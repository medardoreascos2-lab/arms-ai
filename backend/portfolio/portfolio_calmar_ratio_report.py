from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioCalmarRatioReport:
    """
    Calcula el Calmar Ratio a partir de una
    curva de equity.
    """

    calmar_ratio: float
    annualized_return: float
    max_drawdown: float
    cumulative_return: float
    sample_size: int
    periods_per_year: int

    @classmethod
    def from_equity_curve(
        cls,
        *,
        equity_curve: list[float] | tuple[float, ...],
        periods_per_year: int = 1,
    ) -> "PortfolioCalmarRatioReport":
        if not equity_curve:
            raise ValueError(
                "equity_curve no puede estar vacío."
            )

        if len(equity_curve) < 2:
            raise ValueError(
                "equity_curve debe contener al menos 2 valores."
            )

        if periods_per_year <= 0:
            raise ValueError(
                "periods_per_year debe ser mayor que cero."
            )

        normalized_equity = tuple(
            float(value)
            for value in equity_curve
        )

        if any(
            value <= 0
            for value in normalized_equity
        ):
            raise ValueError(
                "Cada valor de equity debe ser mayor que cero."
            )

        cumulative_return = (
            normalized_equity[-1]
            / normalized_equity[0]
            - 1.0
        )

        periods = len(
            normalized_equity
        ) - 1

        annualized_return = (
            (
                normalized_equity[-1]
                / normalized_equity[0]
            )
            ** (
                periods_per_year
                / periods
            )
            - 1.0
        )

        peak = normalized_equity[0]
        max_drawdown = 0.0

        for equity in normalized_equity:
            peak = max(
                peak,
                equity,
            )

            drawdown = (
                peak - equity
            ) / peak

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )

        if max_drawdown == 0:
            calmar_ratio = 0.0
        else:
            calmar_ratio = (
                annualized_return
                / max_drawdown
            )

        return cls(
            calmar_ratio=round(
                calmar_ratio,
                6,
            ),
            annualized_return=round(
                annualized_return,
                6,
            ),
            max_drawdown=round(
                max_drawdown,
                6,
            ),
            cumulative_return=round(
                cumulative_return,
                6,
            ),
            sample_size=len(
                normalized_equity
            ),
            periods_per_year=int(
                periods_per_year
            ),
        )
