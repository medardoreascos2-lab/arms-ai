from __future__ import annotations


class TradePlannerV2:
    """
    Construye un plan de trading a partir
    de una decisión de ejecución aprobada.
    """

    EXECUTION_DECISIONS = {
        "EXECUTE_LONG",
        "EXECUTE_SHORT",
    }

    def __init__(
        self,
        *,
        minimum_reward_risk_ratio: float,
    ) -> None:
        normalized_minimum_ratio = float(
            minimum_reward_risk_ratio
        )

        if normalized_minimum_ratio <= 0:
            raise ValueError(
                "minimum_reward_risk_ratio "
                "debe ser mayor que cero."
            )

        self.minimum_reward_risk_ratio = (
            normalized_minimum_ratio
        )

    def build(
        self,
        *,
        decision: str,
        current_price: float,
        stop_loss: float,
        contracts: int,
        probability: float,
        confluence_score: float,
        grade: str,
        reward_risk_ratio: float
        | None = None,
    ) -> dict[str, object]:
        normalized_decision = (
            str(
                decision
            )
            .strip()
            .upper()
        )

        normalized_current_price = float(
            current_price
        )

        normalized_stop_loss = float(
            stop_loss
        )

        normalized_contracts = int(
            contracts
        )

        normalized_probability = float(
            probability
        )

        normalized_confluence_score = float(
            confluence_score
        )

        normalized_grade = (
            str(
                grade
            )
            .strip()
            .upper()
        )

        if reward_risk_ratio is None:
            normalized_reward_risk_ratio = (
                self.minimum_reward_risk_ratio
            )
        else:
            normalized_reward_risk_ratio = float(
                reward_risk_ratio
            )

        if not (
            0.0
            <= normalized_probability
            <= 1.0
        ):
            raise ValueError(
                "probability debe estar "
                "entre 0 y 1."
            )

        if not (
            0.0
            <= normalized_confluence_score
            <= 1.0
        ):
            raise ValueError(
                "confluence_score debe estar "
                "entre 0 y 1."
            )

        if (
            normalized_reward_risk_ratio
            < self.minimum_reward_risk_ratio
        ):
            raise ValueError(
                "reward_risk_ratio no puede ser "
                "menor que el mínimo configurado."
            )

        if (
            normalized_decision
            not in self.EXECUTION_DECISIONS
        ):
            return {
                "approved": False,
                "status": "INACTIVE",
                "direction": None,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "risk_points": 0.0,
                "reward_points": 0.0,
                "reward_risk_ratio": (
                    normalized_reward_risk_ratio
                ),
                "contracts": 0,
                "probability": (
                    normalized_probability
                ),
                "confluence_score": (
                    normalized_confluence_score
                ),
                "grade": normalized_grade,
                "reason": (
                    "execution_not_approved"
                ),
            }

        if normalized_current_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
            )

        if normalized_stop_loss <= 0:
            raise ValueError(
                "stop_loss debe ser "
                "mayor que cero."
            )

        if normalized_contracts <= 0:
            raise ValueError(
                "contracts debe ser "
                "mayor que cero."
            )

        if (
            normalized_decision
            == "EXECUTE_LONG"
        ):
            if (
                normalized_stop_loss
                >= normalized_current_price
            ):
                raise ValueError(
                    "stop_loss debe estar por "
                    "debajo de current_price "
                    "para una operación LONG."
                )

            direction = "LONG"

            risk_points = (
                normalized_current_price
                - normalized_stop_loss
            )

            reward_points = (
                risk_points
                * normalized_reward_risk_ratio
            )

            take_profit = (
                normalized_current_price
                + reward_points
            )

        else:
            if (
                normalized_stop_loss
                <= normalized_current_price
            ):
                raise ValueError(
                    "stop_loss debe estar por "
                    "encima de current_price "
                    "para una operación SHORT."
                )

            direction = "SHORT"

            risk_points = (
                normalized_stop_loss
                - normalized_current_price
            )

            reward_points = (
                risk_points
                * normalized_reward_risk_ratio
            )

            take_profit = (
                normalized_current_price
                - reward_points
            )

        risk_points = round(
            risk_points,
            10,
        )

        reward_points = round(
            reward_points,
            10,
        )

        take_profit = round(
            take_profit,
            10,
        )

        return {
            "approved": True,
            "status": "ACTIVE",
            "direction": direction,
            "entry_price": (
                normalized_current_price
            ),
            "stop_loss": (
                normalized_stop_loss
            ),
            "take_profit": take_profit,
            "risk_points": risk_points,
            "reward_points": (
                reward_points
            ),
            "reward_risk_ratio": (
                normalized_reward_risk_ratio
            ),
            "contracts": (
                normalized_contracts
            ),
            "probability": (
                normalized_probability
            ),
            "confluence_score": (
                normalized_confluence_score
            ),
            "grade": normalized_grade,
            "reason": None,
        }
