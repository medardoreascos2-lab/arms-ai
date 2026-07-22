from __future__ import annotations

from typing import Any


class TradingCopilotService:
    """
    Convierte el contexto interno de ARMS AI
    en un contexto estructurado para el Trading Copilot.
    """

    REQUIRED_KEYS = (
        "symbol",
        "timeframe",
        "current_price",
        "ema",
        "rsi",
        "atr",
        "trend",
        "market_structure",
        "bos",
        "choch",
        "liquidity",
        "confluence_result",
        "probability_result",
        "validator",
        "dynamic_risk",
        "trade_levels",
    )

    def build_context(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        ema = context["ema"]
        rsi = context["rsi"]
        atr = context["atr"]
        trend = context["trend"]
        market_structure = context["market_structure"]
        bos = context["bos"]
        choch = context["choch"]
        liquidity = context["liquidity"]
        confluence = context["confluence_result"]
        probability = context["probability_result"]
        validator = context["validator"]
        dynamic_risk = context["dynamic_risk"]
        trade_levels = context["trade_levels"]

        return {
            "symbol": context["symbol"],
            "timeframe": context["timeframe"],
            "current_price": context["current_price"],
            "trend": trend.trend,
            "indicators": {
                "ema": ema.ema,
                "ema_period": getattr(
                    ema,
                    "period",
                    None,
                ),
                "rsi": rsi.rsi,
                "rsi_status": getattr(
                    rsi,
                    "status",
                    None,
                ),
                "atr": atr.atr,
                "atr_status": getattr(
                    atr,
                    "status",
                    None,
                ),
            },
            "market_structure": {
                "direction": market_structure.structure,
                "high_type": market_structure.last_high_type,
                "low_type": market_structure.last_low_type,
            },
            "smart_money": {
                "bos": {
                    "detected": self._to_bool(
                        bos.bos
                    ),
                    "direction": bos.direction,
                },
                "choch": {
                    "detected": self._to_bool(
                        choch.choch
                    ),
                    "direction": choch.direction,
                },
                "liquidity": {
                    "detected": self._to_bool(
                        liquidity.sweep_detected
                    ),
                    "direction": liquidity.sweep_direction,
                    "level": liquidity.liquidity_level,
                    "equal_highs": liquidity.equal_highs,
                    "equal_lows": liquidity.equal_lows,
                },
            },
            "decision": {
                "score": confluence.score,
                "grade": confluence.grade,
                "action": confluence.action,
                "direction": confluence.direction,
                "approved": confluence.approved,
                "confirmations": list(
                    confluence.confirmations
                ),
                "warnings": list(
                    confluence.warnings
                ),
            },
            "probability": {
                "value": probability.probability,
                "confidence": probability.confidence,
                "approved": probability.approved,
                "recommendation": probability.recommendation,
                "positive_factors": list(
                    probability.positive_factors
                ),
                "negative_factors": list(
                    probability.negative_factors
                ),
            },
            "risk": {
                "approved": bool(
                    validator.is_valid
                ),
                "risk_amount": dynamic_risk.risk_amount,
                "stop_distance": dynamic_risk.stop_distance,
                "take_profit_distance": (
                    dynamic_risk.take_profit_distance
                ),
                "contracts": dynamic_risk.contracts,
            },
            "trade": {
                "entry_price": trade_levels.entry_price,
                "stop_loss": trade_levels.stop_loss,
                "take_profit": trade_levels.take_profit,
            },
        }

    def _validate_context(
        self,
        context: dict[str, Any],
    ) -> None:
        for key in self.REQUIRED_KEYS:
            if key not in context:
                raise KeyError(
                    f"TradingCopilotService requiere '{key}'."
                )

    def _to_bool(
        self,
        value: Any,
    ) -> bool:
        if isinstance(value, bool):
            return value

        normalized = (
            str(value)
            .strip()
            .upper()
        )

        return normalized in {
            "SÍ",
            "SI",
            "YES",
            "TRUE",
            "1",
        }
