from typing import Any

from backend.services.trade_plan_factory import TradePlanFactory


class TradePlanStage:
    """
    Construye el TradePlan final usando el resultado
    unificado del Decision Council.
    """

    REQUIRED_KEYS = (
        "latest_candle",
        "council_result",
        "trade_levels",
        "dynamic_risk",
    )

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        latest_candle = context["latest_candle"]
        council_result = context["council_result"]
        trade_levels = context["trade_levels"]
        dynamic_risk = context["dynamic_risk"]

        factory = TradePlanFactory()

        trade_plan = factory.create(
            symbol=latest_candle.symbol,
            timeframe=latest_candle.timeframe,
            council_result=council_result,
            entry_price=trade_levels.entry_price,
            stop_loss=trade_levels.stop_loss,
            take_profit=trade_levels.take_profit,
            contracts=dynamic_risk.contracts,
            risk_amount=dynamic_risk.risk_amount,
        )

        context["trade_plan"] = trade_plan

        return context

    def _validate_context(
        self,
        context: dict[str, Any],
    ) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in context:
                raise KeyError(
                    f"TradePlanStage requiere '{key}'."
                )
