from __future__ import annotations

import math


class PositionSizingEngineV2:
    """
    Calcula automáticamente el número de contratos
    permitidos según el riesgo configurado.
    """

    def calculate(
        self,
        *,
        account_balance: float,
        risk_percent: float,
        stop_points: float,
        point_value: float,
    ) -> dict[str, object]:

        account_balance = float(account_balance)
        risk_percent = float(risk_percent)
        stop_points = float(stop_points)
        point_value = float(point_value)

        if account_balance <= 0:
            raise ValueError(
                "account_balance debe ser mayor que cero."
            )

        if risk_percent <= 0:
            raise ValueError(
                "risk_percent debe ser mayor que cero."
            )

        if stop_points <= 0:
            raise ValueError(
                "stop_points debe ser mayor que cero."
            )

        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        risk_amount = round(
            account_balance * (risk_percent / 100.0),
            10,
        )

        risk_per_contract = (
            stop_points * point_value
        )

        contracts = math.floor(
            risk_amount / risk_per_contract
        )

        if contracts <= 0:
            return {
                "approved": False,
                "contracts": 0,
                "risk_amount": risk_amount,
                "actual_risk": 0.0,
                "remaining_risk": risk_amount,
                "reason": "risk_too_small",
            }

        actual_risk = round(
            contracts * risk_per_contract,
            10,
        )

        remaining_risk = round(
            risk_amount - actual_risk,
            10,
        )

        return {
            "approved": True,
            "contracts": contracts,
            "risk_amount": risk_amount,
            "actual_risk": actual_risk,
            "remaining_risk": remaining_risk,
            "risk_per_contract": risk_per_contract,
            "account_balance": account_balance,
            "risk_percent": risk_percent,
            "stop_points": stop_points,
            "point_value": point_value,
        }
