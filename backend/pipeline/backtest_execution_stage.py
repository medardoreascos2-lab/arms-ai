from typing import Any

from backend.services.execution_simulator import ExecutionSimulator


class BacktestExecutionStage:
    """
    Ejecuta un TradePlan contra la vela histórica siguiente.

    Esta etapa no registra archivos ni imprime resultados.
    Solo añade al contexto:

    - simulated_trade
    - execution_status
    - execution_simulator
    """

    REQUIRED_KEYS = (
        "trade_plan",
        "backtest_next_candle",
    )

    def __init__(
        self,
        point_value: float = 2.0,
    ) -> None:
        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        self.point_value = point_value

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        trade_plan = context["trade_plan"]
        next_candle = context["backtest_next_candle"]

        simulator = ExecutionSimulator(
            point_value=self.point_value,
        )

        simulated_trade = simulator.execute(
            trade_plan=trade_plan,
            next_candle=next_candle,
        )

        context.update(
            {
                "execution_simulator": simulator,
                "execution_status": simulator.status_message,
                "simulated_trade": simulated_trade,
            }
        )

        return context

    def _validate_context(
        self,
        context: dict[str, Any],
    ) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in context:
                raise KeyError(
                    f"BacktestExecutionStage requiere '{key}'."
                )
