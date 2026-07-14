from typing import Any

from backend.intelligence.confluence_engine import ConfluenceEngine
from backend.intelligence.decision_council import DecisionCouncil
from backend.intelligence.probability_engine import ProbabilityEngine
from backend.intelligence.reasoning_engine import ReasoningEngine


class DecisionStage:
    """
    Ejecuta los motores finales de decisión de ARMS AI:

    - ConfluenceEngine
    - ReasoningEngine
    - ProbabilityEngine
    - DecisionCouncil
    """

    REQUIRED_KEYS = (
        "trend",
        "current_price",
        "ema",
        "rsi",
        "atr",
        "market_structure",
        "bos",
        "choch",
        "liquidity",
        "validator",
    )

    def __init__(
        self,
        reward_risk_ratio: float = 2.0,
    ) -> None:
        self.reward_risk_ratio = reward_risk_ratio

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        trend = context["trend"]
        current_price = context["current_price"]
        ema = context["ema"]
        rsi = context["rsi"]
        atr = context["atr"]
        market_structure = context["market_structure"]
        bos = context["bos"]
        choch = context["choch"]
        liquidity = context["liquidity"]
        validator = context["validator"]

        session_allowed = context.get(
            "session_allowed",
            True,
        )

        # ==============================
        # CONFLUENCE ENGINE
        # ==============================
        ema_direction = (
            "ALCISTA"
            if current_price > ema.ema
            else "BAJISTA"
            if current_price < ema.ema
            else "NEUTRAL"
        )

        liquidity_data = {
            "sweep_detected": liquidity.sweep_detected,
            "direction": liquidity.sweep_direction,
        }

        atr_data = {
            "value": atr.atr,
            "status": atr.status,
        }

        risk_data = {
            "approved": validator.is_valid,
        }

        confluence = ConfluenceEngine()

        confluence_result = confluence.evaluate(
            trend=trend.trend,
            ema=ema_direction,
            rsi=rsi.rsi,
            atr=atr_data,
            structure=market_structure.structure,
            bos=(
                bos.direction
                if str(bos.bos).upper() == "SÍ"
                else "NEUTRAL"
            ),
            choch=(
                choch.direction
                if str(choch.choch).upper() == "SÍ"
                else "NEUTRAL"
            ),
            liquidity=liquidity_data,
            risk=risk_data,
        )

        # ==============================
        # REASONING ENGINE
        # ==============================
        liquidity_confirmed = (
            liquidity.sweep_detected is True
            or str(liquidity.sweep_detected).upper() == "SÍ"
        )

        reasoning = ReasoningEngine()

        reasoning_result = reasoning.evaluate(
            trend=trend.trend,
            market_structure=market_structure.structure,
            bos_direction=(
                bos.direction
                if str(bos.bos).upper() == "SÍ"
                else "NINGUNA"
            ),
            choch_direction=(
                choch.direction
                if str(choch.choch).upper() == "SÍ"
                else "NINGUNA"
            ),
            liquidity_confirmed=liquidity_confirmed,
            rsi_status=rsi.status,
            atr_status=atr.status,
            reward_risk_ratio=self.reward_risk_ratio,
            risk_allowed=validator.is_valid,
            session_allowed=session_allowed,
        )

        # ==============================
        # PROBABILITY ENGINE
        # ==============================
        probability_engine = ProbabilityEngine()

        probability_result = probability_engine.evaluate(
            confluence=confluence_result,
        )

        # ==============================
        # DECISION COUNCIL
        # ==============================
        council = DecisionCouncil()

        council_result = council.evaluate(
            confluence=confluence_result,
            probability=probability_result,
            reasoning=reasoning_result,
            risk_allowed=validator.is_valid,
            session_allowed=session_allowed,
        )

        context.update(
            {
                "confluence_result": confluence_result,
                "reasoning_result": reasoning_result,
                "probability_result": probability_result,
                "council_result": council_result,
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
                    f"DecisionStage requiere '{key}'."
                )
