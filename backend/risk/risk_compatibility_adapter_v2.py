from __future__ import annotations

from dataclasses import dataclass

from backend.execution.risk_manager_v2 import RiskManagerV2


@dataclass(frozen=True)
class RiskCompatibilityResultV2:
    """
    Resultado compatible con el contrato consumido
    actualmente por BacktestSessionV2.

    Traduce el resultado moderno de RiskManagerV2
    a una interfaz simple equivalente a:

        allowed
        contracts
        risk_amount
        reason
    """

    allowed: bool
    contracts: int
    risk_amount: float
    reason: str


class RiskCompatibilityAdapterV2:
    """
    Adaptador entre RiskManagerV2 y consumidores
    que utilizan el contrato legacy de riesgo.

    El adaptador NO modifica la decisión de riesgo.
    Solamente traduce el resultado.
    """

    def __init__(
        self,
        *,
        risk_manager: RiskManagerV2,
    ) -> None:
        if not isinstance(risk_manager, RiskManagerV2):
            raise TypeError(
                "risk_manager debe ser RiskManagerV2."
            )

        self.risk_manager = risk_manager

    def evaluate(
        self,
        *,
        account_balance: float,
        risk_percent: float,
        stop_points: float,
        point_value: float,
        daily_pnl: float,
        total_drawdown: float,
        open_positions: int,
        symbol: str | None = None,
    ) -> RiskCompatibilityResultV2:
        result = self.risk_manager.evaluate(
            account_balance=account_balance,
            risk_percent=risk_percent,
            stop_points=stop_points,
            point_value=point_value,
            daily_pnl=daily_pnl,
            total_drawdown=total_drawdown,
            open_positions=open_positions,
            symbol=symbol,
        )

        approved = bool(
            result.get("approved", False)
        )

        contracts = int(
            result.get("contracts", 0)
        )

        risk_amount = float(
            result.get("risk_amount", 0.0)
        )

        if approved:
            reason = "RISK PIPELINE APPROVED"
        else:
            blocking_reasons = result.get(
                "blocking_reasons",
                [],
            )

            if blocking_reasons:
                reason = str(
                    blocking_reasons[0]
                )
            else:
                reason = "RISK BLOCKED"

        return RiskCompatibilityResultV2(
            allowed=approved,
            contracts=contracts,
            risk_amount=risk_amount,
            reason=reason,
        )
