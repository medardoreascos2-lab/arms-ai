from backend.portfolio.portfolio_monte_carlo_engine import (
    PortfolioMonteCarloEngine,
)


class SimulatePortfolio:
    """
    Caso de uso para ejecutar simulaciones Monte Carlo
    de un portafolio.
    """

    def __init__(
        self,
        *,
        engine=PortfolioMonteCarloEngine,
    ) -> None:
        run_method = getattr(
            engine,
            "run",
            None,
        )

        if not callable(run_method):
            raise TypeError(
                "engine debe exponer un método run."
            )

        self._engine = engine

    def execute(
        self,
        *,
        initial_value: float,
        mean_return: float,
        volatility: float,
        periods: int,
        simulations: int,
        seed: int | None = None,
    ) -> PortfolioMonteCarloEngine:
        return self._engine.run(
            initial_value=initial_value,
            mean_return=mean_return,
            volatility=volatility,
            periods=periods,
            simulations=simulations,
            seed=seed,
        )
