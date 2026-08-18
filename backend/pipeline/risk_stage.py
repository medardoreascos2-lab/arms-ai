from typing import Any

from backend.risk import RiskManager
from backend.risk_management.dynamic_risk_engine import DynamicRiskEngine
from backend.risk_management.trade_levels import TradeLevels
from backend.risk_management.trade_validator import TradeValidator
from backend.models.execution_status import ExecutionStatus


class RiskStage:
    """
    Calcula el riesgo, los niveles de la operación y valida
    si la configuración puede continuar dentro de ARMS AI.
    """

    REQUIRED_KEYS = (
        "current_price",
        "atr",
        "rsi",
        "technical_decision",
        "intelligence",
    )

    def __init__(
        self,
        account_balance: float = 17000,
        risk_percent: float = 0.5,
        stop_atr_multiplier: float = 1.5,
        reward_risk_ratio: float = 2.0,
        instrument: str = "MNQ",
        point_value: float = 2.0,
    ) -> None:
        self.account_balance = account_balance
        self.risk_percent = risk_percent
        self.stop_atr_multiplier = stop_atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.instrument = instrument.upper()
        self.point_value = point_value

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_context(context)

        current_price = context["current_price"]
        atr = context["atr"]
        rsi = context["rsi"]
        decision = context["technical_decision"]

        if hasattr(
            decision,
            "decision",
        ):
            decision_value = decision.decision
        else:
            decision_value = decision

        intelligence = context["intelligence"]

        if decision_value == "ESPERAR":
            validator = TradeValidator()

            validator.is_valid = False
            validator.reasons.append(
                "La decisión final es ESPERAR."
            )

            context.update(
                {
                    "risk_manager": None,
                    "dynamic_risk": None,
                    "trade_levels": None,
                    "validator": validator,
                }
            )

            return context

        risk_manager = RiskManager(
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
        )

        dynamic_risk = DynamicRiskEngine(
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
            stop_atr_multiplier=self.stop_atr_multiplier,
            reward_risk_ratio=self.reward_risk_ratio,
            instrument=self.instrument,
        )

        dynamic_risk.calculate(
            atr=atr.atr,
        )

        trade_levels = TradeLevels()

        trade_levels.calculate(
            direction=decision_value,
            entry_price=current_price,
            stop_distance=dynamic_risk.stop_distance,
            take_profit_distance=dynamic_risk.take_profit_distance,
        )

        validator = TradeValidator()

        confluence_result = context.get(
            "confluence_result"
        )

        bos = context.get(
            "bos"
        )

        liquidity = context.get(
            "liquidity"
        )

        validator.validate(
            decision=decision,
            confidence=intelligence.confidence,
            contracts=dynamic_risk.contracts,
            rsi_status=rsi.status,
            atr_status=atr.status,
            confluence_score=(
                confluence_result.score
                if confluence_result
                else 0
            ),
            bos_confirmed=(
                str(bos.bos).upper() == "SÍ"
                if bos
                else False
            ),
            liquidity_confirmed=(
                str(liquidity.sweep_detected).upper() == "SÍ"
                if liquidity
                else False
            ),
        )

        execution_status = ExecutionStatus(
            status=(
                ExecutionStatus.APPROVED
                if validator.is_valid
                else ExecutionStatus.BLOCKED_RISK
            ),
            reason=(
                "Riesgo aprobado."
                if validator.is_valid
                else validator.reasons[0]
            ),
        )

        context.update(
            {
                "risk_manager": risk_manager,
                "dynamic_risk": dynamic_risk,
                "trade_levels": trade_levels,
                "validator": validator,
                "execution_status": execution_status,
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