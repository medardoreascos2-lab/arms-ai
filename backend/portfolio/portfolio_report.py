from dataclasses import dataclass
from statistics import mean

from backend.portfolio.portfolio_snapshot import (
    PortfolioSnapshot,
)


@dataclass(frozen=True)
class PortfolioReport:
    """
    Resume la evolución histórica de un portafolio
    a partir de una secuencia ordenada de snapshots.
    """

    snapshots: tuple[PortfolioSnapshot, ...]

    total_snapshots: int

    initial_equity: float
    final_equity: float
    net_profit: float
    return_percent: float

    peak_equity: float
    max_drawdown: float
    max_drawdown_percent: float

    average_gross_exposure: float
    max_gross_exposure: float

    average_net_exposure: float
    max_net_exposure: float
    min_net_exposure: float

    @classmethod
    def from_snapshots(
        cls,
        snapshots: list[PortfolioSnapshot]
        | tuple[PortfolioSnapshot, ...],
    ) -> "PortfolioReport":
        normalized_snapshots = tuple(snapshots)

        if not normalized_snapshots:
            raise ValueError(
                "snapshots no puede estar vacío."
            )

        for snapshot in normalized_snapshots:
            if not isinstance(
                snapshot,
                PortfolioSnapshot,
            ):
                raise TypeError(
                    "snapshots debe contener "
                    "PortfolioSnapshot."
                )

        for previous, current in zip(
            normalized_snapshots,
            normalized_snapshots[1:],
        ):
            if current.timestamp < previous.timestamp:
                raise ValueError(
                    "snapshots debe estar ordenado por timestamp."
                )

        equities = [
            float(snapshot.equity)
            for snapshot in normalized_snapshots
        ]

        gross_exposures = [
            float(snapshot.gross_exposure)
            for snapshot in normalized_snapshots
        ]

        net_exposures = [
            float(snapshot.net_exposure)
            for snapshot in normalized_snapshots
        ]

        initial_equity = equities[0]
        final_equity = equities[-1]
        net_profit = final_equity - initial_equity

        if initial_equity == 0:
            return_percent = 0.0
        else:
            return_percent = (
                net_profit
                / initial_equity
                * 100
            )

        peak_equity = equities[0]
        max_drawdown = 0.0
        max_drawdown_percent = 0.0

        for equity in equities:
            peak_equity = max(
                peak_equity,
                equity,
            )

            drawdown = (
                peak_equity
                - equity
            )

            if peak_equity == 0:
                drawdown_percent = 0.0
            else:
                drawdown_percent = (
                    drawdown
                    / peak_equity
                    * 100
                )

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )

            max_drawdown_percent = max(
                max_drawdown_percent,
                drawdown_percent,
            )

        return cls(
            snapshots=normalized_snapshots,
            total_snapshots=len(
                normalized_snapshots
            ),
            initial_equity=round(
                initial_equity,
                2,
            ),
            final_equity=round(
                final_equity,
                2,
            ),
            net_profit=round(
                net_profit,
                2,
            ),
            return_percent=round(
                return_percent,
                2,
            ),
            peak_equity=round(
                max(equities),
                2,
            ),
            max_drawdown=round(
                max_drawdown,
                2,
            ),
            max_drawdown_percent=round(
                max_drawdown_percent,
                2,
            ),
            average_gross_exposure=round(
                mean(gross_exposures),
                2,
            ),
            max_gross_exposure=round(
                max(gross_exposures),
                2,
            ),
            average_net_exposure=round(
                mean(net_exposures),
                2,
            ),
            max_net_exposure=round(
                max(net_exposures),
                2,
            ),
            min_net_exposure=round(
                min(net_exposures),
                2,
            ),
        )
