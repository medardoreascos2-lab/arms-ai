from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from backend.execution.position_lifecycle_manager_v1 import (
    PositionLifecycleManagerV1,
)

from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)


@dataclass
class ExecutionBridgeResult:

    executed: bool

    reason: str

    risk_result: dict[str, Any] | None = None


class ExecutionPositionBridgeV1:
    """
    Puente protegido entre decisiones
    y ejecución ARMS AI.

    Ninguna posición BUY / SELL puede
    abrirse sin aprobación previa del
    ExecutionRiskGateV1.
    """


    def __init__(
        self,
        *,
        lifecycle: Any | None = None,
        risk_gate: Any | None = None,
    ) -> None:

        self.lifecycle = (
            lifecycle
            if lifecycle is not None
            else PositionLifecycleManagerV1()
        )

        self.risk_gate = (
            risk_gate
            if risk_gate is not None
            else ExecutionRiskGateV1()
        )


    def execute(
        self,
        *,
        decision,
        price: float,
        symbol: str,
        contracts: int,
        risk_amount: float,
    ) -> ExecutionBridgeResult:

        action = (
            str(
                decision.action.value
            )
            .strip()
            .upper()
        )


        if action not in {
            "BUY",
            "SELL",
        }:

            return ExecutionBridgeResult(
                executed=False,
                reason="NO EXECUTION",
                risk_result=None,
            )


        metadata = getattr(
            decision,
            "metadata",
            None,
        )


        if not isinstance(
            metadata,
            dict,
        ):

            raise TypeError(
                "decision.metadata debe ser dict."
            )


        if "stop_loss" not in metadata:

            raise ValueError(
                "decision.metadata requiere stop_loss."
            )


        if "take_profit" not in metadata:

            raise ValueError(
                "decision.metadata requiere take_profit."
            )


        risk_result = (
            self.risk_gate
            .evaluate_trade(
                symbol=symbol,
                side=action,
                contracts=contracts,
                risk_amount=risk_amount,
            )
        )


        if (
            risk_result.get(
                "execution"
            )
            != "APPROVED"
        ):

            return ExecutionBridgeResult(
                executed=False,
                reason=(
                    risk_result.get(
                        "reason",
                        "RISK BLOCKED",
                    )
                ),
                risk_result=risk_result,
            )


        direction = (
            "LONG"
            if action == "BUY"
            else "SHORT"
        )


        self.lifecycle.open_position(
            direction=direction,
            entry_price=float(
                price
            ),
            stop_loss=float(
                metadata[
                    "stop_loss"
                ]
            ),
            take_profit=float(
                metadata[
                    "take_profit"
                ]
            ),
        )


        return ExecutionBridgeResult(
            executed=True,
            reason=(
                f"{direction} OPENED"
            ),
            risk_result=risk_result,
        )
