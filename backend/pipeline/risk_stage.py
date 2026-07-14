from typing import Any

from backend.risk import RiskManager
from backend.risk_management.dynamic_risk_engine import DynamicRiskEngine
from backend.risk_management.trade_levels import TradeLevels
from backend.risk_management.trade_validator import TradeValidator


class RiskStage:
    """
    Calcula el riesgo, los niveles de la operación y valida
    si la configuración puede continuar dentro de ARMS AI.
    """

    REQUIRED_KEYS = (
        "current_price",
        "atr",
        "rsi",
        "decision",
        "intelligence",
    )

    def __init__(
        self,
        account_balance: float = 17000,
        risk_percent: float = 0.5,
        stop_atr_multiplier: float = 1.5,
        reward_risk_ratio: float = 2.0,
        point_value: float = 2.0,
    ) -> None:
        self.account_balance = account_balance
        self.risk_percent = risk_percent
        self.stop_atr_multiplier = stop_atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.point_value = point_value

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        current_price = context["current_price"]
        atr = context["atr"]
        rsi = context["rsi"]
        decision = context["decision"]
        intelligence = context["intelligence"]

        risk_manager = RiskManager(
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
        )

        dynamic_risk = DynamicRiskEngine(
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
            stop_atr_multiplier=self.stop_atr_multiplier,
            reward_risk_ratio=self.reward_risk_ratio,
        )

        dynamic_risk.calculate(
            atr=atr.atr,
            point_value=self.point_value,
        )

        trade_levels = TradeLevels()
        trade_levels.calculate(
            direction=decision.decision,
            entry_price=current_price,
            stop_distance=dynamic_risk.stop_distance,
            take_profit_distance=dynamic_risk.take_profit_distance,
        )

        validator = TradeValidator()
        validator.validate(
            decision=decision.decision,
            confidence=intelligence.confidence,
            contracts=dynamic_risk.contracts,
            rsi_status=rsi.status,
            atr_status=atr.status,
        )

        context.update(
            {
                "risk_manager": risk_manager,
                "dynamic_risk": dynamic_risk,
                "trade_levels": trade_levels,
                "validator": validator,
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
                    f"RiskStage requiere '{key}'."
                )
