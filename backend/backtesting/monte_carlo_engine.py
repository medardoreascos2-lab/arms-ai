from dataclasses import dataclass
import random


@dataclass(frozen=True)
class MonteCarloSimulation:
    simulation_number: int
    trade_sequence: tuple[float, ...]
    initial_balance: float
    final_balance: float
    net_profit: float
    peak_balance: float
    max_drawdown: float


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: list[MonteCarloSimulation]

    @property
    def total_simulations(self) -> int:
        return len(self.simulations)


class MonteCarloEngine:
    """
    Ejecuta simulaciones Monte Carlo reordenando
    aleatoriamente la secuencia histórica de P&L.
    """

    def __init__(
        self,
        simulations: int = 1000,
        seed: int | None = None,
    ) -> None:
        if simulations <= 0:
            raise ValueError(
                "simulations debe ser mayor que cero."
            )

        self.simulations = simulations
        self.seed = seed

    def run(
        self,
        pnls: list[float],
        initial_balance: float,
    ) -> MonteCarloResult:
        if not pnls:
            raise ValueError(
                "pnls no puede estar vacío."
            )

        if initial_balance <= 0:
            raise ValueError(
                "initial_balance debe ser mayor que cero."
            )

        normalized_pnls = [
            float(pnl)
            for pnl in pnls
        ]

        random_generator = random.Random(
            self.seed
        )

        simulations: list[MonteCarloSimulation] = []

        for simulation_number in range(
            1,
            self.simulations + 1,
        ):
            sequence = list(normalized_pnls)

            random_generator.shuffle(
                sequence
            )

            simulation = self._simulate_sequence(
                simulation_number=simulation_number,
                pnls=sequence,
                initial_balance=float(
                    initial_balance
                ),
            )

            simulations.append(simulation)

        return MonteCarloResult(
            simulations=simulations,
        )

    def _simulate_sequence(
        self,
        simulation_number: int,
        pnls: list[float],
        initial_balance: float,
    ) -> MonteCarloSimulation:
        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0

        for pnl in pnls:
            balance += pnl

            peak_balance = max(
                peak_balance,
                balance,
            )

            drawdown = (
                peak_balance
                - balance
            )

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )

        net_profit = (
            balance
            - initial_balance
        )

        return MonteCarloSimulation(
            simulation_number=simulation_number,
            trade_sequence=tuple(pnls),
            initial_balance=round(
                initial_balance,
                2,
            ),
            final_balance=round(
                balance,
                2,
            ),
            net_profit=round(
                net_profit,
                2,
            ),
            peak_balance=round(
                peak_balance,
                2,
            ),
            max_drawdown=round(
                max_drawdown,
                2,
            ),
        )
