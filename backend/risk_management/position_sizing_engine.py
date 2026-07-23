from __future__ import annotations

from math import floor


class PositionSizingEngine:
    """
    Calcula el número de contratos permitido
    según el riesgo de la cuenta y la distancia
    entre la entrada y el Stop Loss.
    """

    def __init__(
        self,
        *,
        minimum_contracts: int,
        maximum_contracts: int,
    ) -> None:
        if minimum_contracts <= 0:
            raise ValueError(
                "minimum_contracts debe ser mayor que cero."
            )

        if maximum_contracts < minimum_contracts:
            raise ValueError(
                "maximum_contracts no puede ser menor "
                "que minimum_contracts."
            )

        self.minimum_contracts = int(
            minimum_contracts
        )

        self.maximum_contracts = int(
            maximum_contracts
        )

    def calculate(
        self,
        *,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss: float,
        point_value: float,
    ) -> dict[str, object]:
        balance = float(
            account_balance
        )

        risk_percentage = float(
            risk_percent
        )

        normalized_entry = float(
            entry_price
        )

        normalized_stop = float(
            stop_loss
        )

        normalized_point_value = float(
            point_value
        )

        if balance <= 0:
            raise ValueError(
                "account_balance debe ser mayor que cero."
            )

        if not (
            0.0
            < risk_percentage
            <= 100.0
        ):
            raise ValueError(
                "risk_percent debe ser mayor que cero "
                "y menor o igual a 100."
            )

        if normalized_point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        stop_distance = abs(
            normalized_entry
            - normalized_stop
        )

        if stop_distance <= 0:
            raise ValueError(
                "stop_distance debe ser mayor que cero."
            )

        risk_budget = (
            balance
            * risk_percentage
            / 100.0
        )

        risk_per_contract = (
            stop_distance
            * normalized_point_value
        )

        raw_contracts = floor(
            risk_budget
            / risk_per_contract
        )

        if (
            raw_contracts
            < self.minimum_contracts
        ):
            return {
                "approved": False,
                "status": (
                    "INSUFFICIENT_RISK_BUDGET"
                ),
                "contracts": 0,
                "risk_budget": risk_budget,
                "stop_distance": (
                    stop_distance
                ),
                "risk_per_contract": (
                    risk_per_contract
                ),
                "planned_risk": 0.0,
                "remaining_risk": (
                    risk_budget
                ),
            }

        capped = (
            raw_contracts
            > self.maximum_contracts
        )

        contracts = min(
            raw_contracts,
            self.maximum_contracts,
        )

        planned_risk = (
            contracts
            * risk_per_contract
        )

        remaining_risk = (
            risk_budget
            - planned_risk
        )

        return {
            "approved": True,
            "status": (
                "CAPPED_AT_MAXIMUM"
                if capped
                else "APPROVED"
            ),
            "contracts": contracts,
            "risk_budget": risk_budget,
            "stop_distance": (
                stop_distance
            ),
            "risk_per_contract": (
                risk_per_contract
            ),
            "planned_risk": (
                planned_risk
            ),
            "remaining_risk": (
                remaining_risk
            ),
        }
