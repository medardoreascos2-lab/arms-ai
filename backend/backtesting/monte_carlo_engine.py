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
    method: str = "shuffle"

    @property
    def total_simulations(self) -> int:
        return len(self.simulations)


class MonteCarloEngine:
    """
    Ejecuta simulaciones Monte Carlo sobre una secuencia
    histórica de resultados.

    Métodos disponibles:

    - shuffle:
      Reordena todos los trades sin reemplazo. Conserva
      siempre el beneficio neto total.

    - bootstrap:
      Muestrea trades con reemplazo. Puede cambiar el
      beneficio final de cada simulación.
    """

    VALID_METHODS = {
        "shuffle",
        "bootstrap",
    }

    def __init__(
        self,
        simulations: int = 1000,
        seed: int | None = None,
        method: str = "shuffle",
    ) -> None:
        if simulations <= 0:
            raise ValueError(
                "simulations debe ser mayor que cero."
            )

        if method not in self.VALID_METHODS:
            raise ValueError(
                "method debe ser 'shuffle' o 'bootstrap'."
            )

        self.simulations = simulations
        self.seed = seed
        self.method = method

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
            sequence = self._build_sequence(
                pnls=normalized_pnls,
                random_generator=random_generator,
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
            method=self.method,
        )

    def _build_sequence(
        self,
        pnls: list[float],
        random_generator: random.Random,
    ) -> list[float]:
        if self.method == "shuffle":
            sequence = list(pnls)

            random_generator.shuffle(
                sequence
            )

            return sequence

        return [
            random_generator.choice(pnls)
            for _ in range(len(pnls))
        ]

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
