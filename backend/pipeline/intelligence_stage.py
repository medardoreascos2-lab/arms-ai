from typing import Any

from backend.intelligence.trading_intelligence import TradingIntelligence
from backend.strategy.decision_engine import DecisionEngine
from backend.trend_analyzer import TrendAnalyzer


class IntelligenceStage:
    """
    Analiza la tendencia y genera la recomendación técnica inicial
    usando los datos producidos por las etapas anteriores.
    """

    REQUIRED_KEYS = (
        "current_price",
        "ema",
        "rsi",
        "atr",
        "market_structure",
        "bos",
        "choch",
    )

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        current_price = context["current_price"]
        ema = context["ema"]
        rsi = context["rsi"]
        atr = context["atr"]
        market_structure = context["market_structure"]
        bos = context["bos"]
        choch = context["choch"]

        trend = TrendAnalyzer()
        trend.analyze(
            current_price=current_price,
            ema50=ema.ema,
        )

        intelligence = TradingIntelligence()
        intelligence.analyze(
            trend=trend.trend,
            current_price=current_price,
            ema=ema.ema,
            rsi=rsi.rsi,
            rsi_status=rsi.status,
            atr=atr.atr,
            atr_status=atr.status,
            market_structure=market_structure.structure,
            bos_detected=bos.bos,
            bos_direction=bos.direction,
            choch_detected=choch.choch,
            choch_direction=choch.direction,
        )

        decision = DecisionEngine()
        decision.analyze(
            intelligence_recommendation=(
                intelligence.recommendation
            )
        )

        context.update(
            {
                "trend": trend,
                "intelligence": intelligence,
                "decision": decision,
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
                    f"IntelligenceStage requiere '{key}'."
                )
