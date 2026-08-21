from __future__ import annotations

from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)


class RiskManagerV2:
    """
    Evalúa si una operación puede ejecutarse
    según el tamaño de posición y los límites
    generales de riesgo de la cuenta.
    """

    def __init__(
        self,
        *,
        position_sizing_engine:
        PositionSizingEngineV2,
        maximum_daily_loss: float | None,
        maximum_total_drawdown: float,
        maximum_contracts: int,
        maximum_open_positions: int,
        contract_limit_resolver=None,
    ) -> None:
        if not isinstance(
            position_sizing_engine,
            PositionSizingEngineV2,
        ):
            raise TypeError(
                "position_sizing_engine debe ser "
                "PositionSizingEngineV2."
            )

        normalized_daily_loss = (
            None
            if maximum_daily_loss is None
            else float(maximum_daily_loss)
        )

        normalized_drawdown = float(
            maximum_total_drawdown
        )

        normalized_maximum_contracts = int(
            maximum_contracts
        )

        normalized_maximum_open_positions = int(
            maximum_open_positions
        )

        if (
            normalized_daily_loss is not None
            and normalized_daily_loss <= 0
        ):
            raise ValueError(
                "maximum_daily_loss debe ser "
                "mayor que cero cuando está definido."
            )

        if normalized_drawdown <= 0:
            raise ValueError(
                "maximum_total_drawdown debe ser "
                "mayor que cero."
            )

        if normalized_maximum_contracts <= 0:
            raise ValueError(
                "maximum_contracts debe ser "
                "mayor que cero."
            )

        if (
            normalized_maximum_open_positions
            <= 0
        ):
            raise ValueError(
                "maximum_open_positions debe ser "
                "mayor que cero."
            )

        self.position_sizing_engine = (
            position_sizing_engine
        )

        self.maximum_daily_loss = (
            normalized_daily_loss
        )

        self.maximum_total_drawdown = (
            normalized_drawdown
        )

        self.maximum_contracts = (
            normalized_maximum_contracts
        )

        self.maximum_open_positions = (
            normalized_maximum_open_positions
        )
        self.contract_limit_resolver = (
            contract_limit_resolver
        )

    def get_contract_limit(
        self,
        symbol: str,
    ) -> int:
        if self.contract_limit_resolver is None:
            return self.maximum_contracts

        limit = self.contract_limit_resolver(symbol)
        normalized_limit = int(limit)

        if normalized_limit <= 0:
            raise ValueError(
                "contract limit debe ser mayor que cero."
            )

        return normalized_limit

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
    ) -> dict[str, object]:
        normalized_total_drawdown = float(
            total_drawdown
        )

        normalized_open_positions = int(
            open_positions
        )

        normalized_daily_pnl = float(
            daily_pnl
        )

        if normalized_total_drawdown < 0:
            raise ValueError(
                "total_drawdown no puede ser "
                "negativo."
            )

        if normalized_open_positions < 0:
            raise ValueError(
                "open_positions no puede ser "
                "negativo."
            )

        sizing = (
            self.position_sizing_engine.calculate(
                account_balance=(
                    account_balance
                ),
                risk_percent=risk_percent,
                stop_points=stop_points,
                point_value=point_value,
            )
        )

        contracts = int(
            sizing.get(
                "contracts",
                0,
            )
        )

        risk_amount = float(
            sizing.get(
                "risk_amount",
                0.0,
            )
        )

        actual_risk = float(
            sizing.get(
                "actual_risk",
                0.0,
            )
        )

        daily_loss_used = max(
            0.0,
            -normalized_daily_pnl,
        )

        remaining_daily_loss_capacity = (
            None
            if self.maximum_daily_loss is None
            else max(
                0.0,
                self.maximum_daily_loss
                - daily_loss_used,
            )
        )

        remaining_drawdown_capacity = max(
            0.0,
            self.maximum_total_drawdown
            - normalized_total_drawdown,
        )

        projected_daily_loss = (
            daily_loss_used
            + actual_risk
        )

        projected_total_drawdown = (
            normalized_total_drawdown
            + actual_risk
        )

        blocking_reasons: list[str] = []

        if not bool(
            sizing.get(
                "approved",
                False,
            )
        ):
            blocking_reasons.append(
                "position_sizing_not_approved"
            )

        if self.maximum_daily_loss is not None:
            if (
                daily_loss_used
                >= self.maximum_daily_loss
            ):
                blocking_reasons.append(
                    "daily_loss_limit_reached"
                )
            elif (
                projected_daily_loss
                > self.maximum_daily_loss
            ):
                blocking_reasons.append(
                    "projected_daily_loss_exceeded"
                )

        if (
            normalized_total_drawdown
            >= self.maximum_total_drawdown
        ):
            blocking_reasons.append(
                "total_drawdown_limit_reached"
            )
        elif (
            projected_total_drawdown
            > self.maximum_total_drawdown
        ):
            blocking_reasons.append(
                "projected_total_drawdown_exceeded"
            )

        if (
            normalized_open_positions
            >= self.maximum_open_positions
        ):
            blocking_reasons.append(
                "maximum_open_positions_reached"
            )

        allowed_contracts = (
            self.maximum_contracts
            if symbol is None
            else self.get_contract_limit(symbol)
        )

        if contracts > allowed_contracts:
            blocking_reasons.append(
                "maximum_contracts_exceeded"
            )

        approved = not blocking_reasons

        return {
            "approved": approved,
            "status": (
                "APPROVED"
                if approved
                else "BLOCKED"
            ),
            "decision": (
                "ALLOW_TRADE"
                if approved
                else "BLOCK_TRADE"
            ),
            "contracts": contracts,
            "risk_amount": risk_amount,
            "actual_risk": actual_risk,
            "remaining_risk": float(
                sizing.get(
                    "remaining_risk",
                    0.0,
                )
            ),
            "risk_per_contract": sizing.get(
                "risk_per_contract"
            ),
            "daily_pnl": (
                normalized_daily_pnl
            ),
            "daily_loss_used": (
                daily_loss_used
            ),
            "projected_daily_loss": (
                projected_daily_loss
            ),
            "remaining_daily_loss_capacity": (
                remaining_daily_loss_capacity
            ),
            "total_drawdown": (
                normalized_total_drawdown
            ),
            "projected_total_drawdown": (
                projected_total_drawdown
            ),
            "remaining_drawdown_capacity": (
                remaining_drawdown_capacity
            ),
            "open_positions": (
                normalized_open_positions
            ),
            "maximum_open_positions": (
                self.maximum_open_positions
            ),
            "maximum_contracts": (
                self.maximum_contracts
            ),
            "maximum_daily_loss": (
                self.maximum_daily_loss
            ),
            "maximum_total_drawdown": (
                self.maximum_total_drawdown
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
            "position_sizing": sizing,
        }
