from dataclasses import dataclass

from backend.portfolio.portfolio import (
    Portfolio,
)


@dataclass(frozen=True)
class PortfolioExposureReport:
    """
    Resume la exposición long, short, bruta y neta
    de un portafolio.
    """

    long_exposure: float
    short_exposure: float
    gross_exposure: float
    net_exposure: float

    long_percent: float
    short_percent: float
    net_percent: float

    @classmethod
    def from_portfolio(
        cls,
        portfolio: Portfolio,
    ) -> "PortfolioExposureReport":
        if not isinstance(
            portfolio,
            Portfolio,
        ):
            raise TypeError(
                "portfolio debe ser Portfolio."
            )

        long_exposure = float(
            portfolio.long_exposure
        )
        short_exposure = float(
            portfolio.short_exposure
        )
        gross_exposure = float(
            portfolio.gross_exposure
        )
        net_exposure = float(
            portfolio.net_exposure
        )

        if gross_exposure == 0:
            long_percent = 0.0
            short_percent = 0.0
            net_percent = 0.0
        else:
            long_percent = (
                long_exposure
                / gross_exposure
                * 100
            )
            short_percent = (
                short_exposure
                / gross_exposure
                * 100
            )
            net_percent = (
                net_exposure
                / gross_exposure
                * 100
            )

        return cls(
            long_exposure=round(
                long_exposure,
                2,
            ),
            short_exposure=round(
                short_exposure,
                2,
            ),
            gross_exposure=round(
                gross_exposure,
                2,
            ),
            net_exposure=round(
                net_exposure,
                2,
            ),
            long_percent=round(
                long_percent,
                2,
            ),
            short_percent=round(
                short_percent,
                2,
            ),
            net_percent=round(
                net_percent,
                2,
            ),
        )
