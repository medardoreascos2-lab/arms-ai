from typing import Any

from backend.services.execution_simulator import ExecutionSimulator
from backend.services.plan_history_analyzer import PlanHistoryAnalyzer
from backend.services.simulated_trade_logger import SimulatedTradeLogger
from backend.services.trade_logger import TradeLogger


class ExecutionStage:
    """
    Registra el TradePlan, analiza el historial y ejecuta
    la simulación final de ARMS AI.
    """

    REQUIRED_KEYS = (
        "trade_plan",
        "collector",
        "latest_candle",
    )

    def __init__(
        self,
        trade_log_path: str = "data/trade_plans.jsonl",
        simulated_log_path: str = "data/simulated_trades.jsonl",
        point_value: float = 2.0,
    ) -> None:
        self.trade_log_path = trade_log_path
        self.simulated_log_path = simulated_log_path
        self.point_value = point_value

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        trade_plan = context["trade_plan"]
        collector = context["collector"]
        latest_candle = context["latest_candle"]

        # ==============================
        # REGISTRO DEL PLAN
        # ==============================
        logger = TradeLogger(
            file_path=self.trade_log_path
        )
        logger.save(trade_plan)

        # ==============================
        # ANÁLISIS DEL HISTORIAL
        # ==============================
        history_analyzer = PlanHistoryAnalyzer(
            file_path=self.trade_log_path
        )
        history_analyzer.analyze()

        # ==============================
        # SIMULACIÓN
        # ==============================
        simulator = ExecutionSimulator(
            point_value=self.point_value
        )

        next_candle = collector.get_latest_candle(
            symbol=latest_candle.symbol,
            timeframe=latest_candle.timeframe,
        )

        simulated_trade = simulator.execute(
            trade_plan=trade_plan,
            next_candle=next_candle,
        )

        simulated_trade_logger = None

        if simulated_trade is not None:
            simulated_trade_logger = SimulatedTradeLogger(
                file_path=self.simulated_log_path
            )
            simulated_trade_logger.save(simulated_trade)

        context.update(
            {
                "trade_logger": logger,
                "history_analyzer": history_analyzer,
                "execution_simulator": simulator,
                "simulated_trade": simulated_trade,
                "simulated_trade_logger": simulated_trade_logger,
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
                    f"ExecutionStage requiere '{key}'."
                )
