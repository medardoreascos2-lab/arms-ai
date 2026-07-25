from __future__ import annotations


class PortfolioRiskEngineV2:
    """
    Evalúa el riesgo global del portafolio,
    incluyendo riesgo abierto, riesgo por dirección,
    riesgo por símbolo y pérdida flotante.
    """

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        maximum_total_open_risk: float,
        maximum_floating_loss: float,
        maximum_long_risk: float,
        maximum_short_risk: float,
        maximum_symbol_risk: float,
    ) -> None:
        normalized_total_risk = float(
            maximum_total_open_risk
        )

        normalized_floating_loss = float(
            maximum_floating_loss
        )

        normalized_long_risk = float(
            maximum_long_risk
        )

        normalized_short_risk = float(
            maximum_short_risk
        )

        normalized_symbol_risk = float(
            maximum_symbol_risk
        )

        if normalized_total_risk <= 0:
            raise ValueError(
                "maximum_total_open_risk debe ser "
                "mayor que cero."
            )

        if normalized_floating_loss <= 0:
            raise ValueError(
                "maximum_floating_loss debe ser "
                "mayor que cero."
            )

        if normalized_long_risk <= 0:
            raise ValueError(
                "maximum_long_risk debe ser "
                "mayor que cero."
            )

        if normalized_short_risk <= 0:
            raise ValueError(
                "maximum_short_risk debe ser "
                "mayor que cero."
            )

        if normalized_symbol_risk <= 0:
            raise ValueError(
                "maximum_symbol_risk debe ser "
                "mayor que cero."
            )

        if normalized_long_risk > normalized_total_risk:
            raise ValueError(
                "maximum_long_risk no puede ser "
                "mayor que maximum_total_open_risk."
            )

        if normalized_short_risk > normalized_total_risk:
            raise ValueError(
                "maximum_short_risk no puede ser "
                "mayor que maximum_total_open_risk."
            )

        if normalized_symbol_risk > normalized_total_risk:
            raise ValueError(
                "maximum_symbol_risk no puede ser "
                "mayor que maximum_total_open_risk."
            )

        self.maximum_total_open_risk = (
            normalized_total_risk
        )

        self.maximum_floating_loss = (
            normalized_floating_loss
        )

        self.maximum_long_risk = (
            normalized_long_risk
        )

        self.maximum_short_risk = (
            normalized_short_risk
        )

        self.maximum_symbol_risk = (
            normalized_symbol_risk
        )

    def evaluate(
        self,
        *,
        open_positions: list[
            dict[str, object]
        ],
        candidate_symbol: str,
        candidate_direction: str,
        candidate_contracts: int,
        candidate_entry_price: float,
        candidate_current_price: float,
        candidate_stop_loss: float,
        candidate_point_value: float,
    ) -> dict[str, object]:
        if not isinstance(
            open_positions,
            list,
        ):
            raise TypeError(
                "open_positions debe ser una lista."
            )

        normalized_symbol = (
            str(
                candidate_symbol
            )
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "candidate_symbol es obligatorio."
            )

        normalized_direction = (
            str(
                candidate_direction
            )
            .strip()
            .upper()
        )

        if (
            normalized_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "candidate_direction debe ser "
                "LONG o SHORT."
            )

        normalized_contracts = int(
            candidate_contracts
        )

        normalized_entry_price = float(
            candidate_entry_price
        )

        normalized_current_price = float(
            candidate_current_price
        )

        normalized_stop_loss = float(
            candidate_stop_loss
        )

        normalized_point_value = float(
            candidate_point_value
        )

        if normalized_contracts <= 0:
            raise ValueError(
                "candidate_contracts debe ser "
                "mayor que cero."
            )

        if normalized_entry_price <= 0:
            raise ValueError(
                "candidate_entry_price debe ser "
                "mayor que cero."
            )

        if normalized_current_price <= 0:
            raise ValueError(
                "candidate_current_price debe ser "
                "mayor que cero."
            )

        if normalized_stop_loss <= 0:
            raise ValueError(
                "candidate_stop_loss debe ser "
                "mayor que cero."
            )

        if normalized_point_value <= 0:
            raise ValueError(
                "candidate_point_value debe ser "
                "mayor que cero."
            )

        current_total_open_risk = 0.0
        current_long_risk = 0.0
        current_short_risk = 0.0
        current_symbol_risk = 0.0
        current_floating_pnl = 0.0

        for position in open_positions:
            if not isinstance(
                position,
                dict,
            ):
                raise TypeError(
                    "position debe ser un dict."
                )

            status = (
                str(
                    position.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if status != "OPEN":
                continue

            direction = (
                str(
                    position.get(
                        "direction",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if direction not in self.VALID_DIRECTIONS:
                raise ValueError(
                    "position direction inválida."
                )

            symbol = (
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            quantity = int(
                position.get(
                    "quantity",
                    0,
                )
            )

            entry_price = float(
                position.get(
                    "entry_price",
                    0.0,
                )
            )

            current_price = float(
                position.get(
                    "current_price",
                    entry_price,
                )
            )

            stop_loss = float(
                position.get(
                    "stop_loss",
                    0.0,
                )
            )

            point_value = float(
                position.get(
                    "point_value",
                    0.0,
                )
            )

            position_risk = round(
                abs(
                    entry_price
                    - stop_loss
                )
                * quantity
                * point_value,
                10,
            )

            if direction == "LONG":
                floating_points = (
                    current_price
                    - entry_price
                )
            else:
                floating_points = (
                    entry_price
                    - current_price
                )

            floating_pnl = round(
                floating_points
                * quantity
                * point_value,
                10,
            )

            current_total_open_risk += (
                position_risk
            )

            current_floating_pnl += (
                floating_pnl
            )

            if direction == "LONG":
                current_long_risk += (
                    position_risk
                )
            else:
                current_short_risk += (
                    position_risk
                )

            if symbol == normalized_symbol:
                current_symbol_risk += (
                    position_risk
                )

        current_total_open_risk = round(
            current_total_open_risk,
            10,
        )

        current_long_risk = round(
            current_long_risk,
            10,
        )

        current_short_risk = round(
            current_short_risk,
            10,
        )

        current_symbol_risk = round(
            current_symbol_risk,
            10,
        )

        current_floating_pnl = round(
            current_floating_pnl,
            10,
        )

        current_floating_loss = round(
            max(
                0.0,
                -current_floating_pnl,
            ),
            10,
        )

        candidate_risk = round(
            abs(
                normalized_entry_price
                - normalized_stop_loss
            )
            * normalized_contracts
            * normalized_point_value,
            10,
        )

        projected_total_open_risk = round(
            current_total_open_risk
            + candidate_risk,
            10,
        )

        projected_long_risk = (
            current_long_risk
        )

        projected_short_risk = (
            current_short_risk
        )

        if normalized_direction == "LONG":
            projected_long_risk = round(
                projected_long_risk
                + candidate_risk,
                10,
            )
        else:
            projected_short_risk = round(
                projected_short_risk
                + candidate_risk,
                10,
            )

        projected_symbol_risk = round(
            current_symbol_risk
            + candidate_risk,
            10,
        )

        blocking_reasons: list[str] = []

        if (
            projected_total_open_risk
            > self.maximum_total_open_risk
        ):
            blocking_reasons.append(
                "maximum_total_open_risk_exceeded"
            )

        if (
            current_floating_loss
            > self.maximum_floating_loss
        ):
            blocking_reasons.append(
                "maximum_floating_loss_exceeded"
            )

        if (
            projected_long_risk
            > self.maximum_long_risk
        ):
            blocking_reasons.append(
                "maximum_long_risk_exceeded"
            )

        if (
            projected_short_risk
            > self.maximum_short_risk
        ):
            blocking_reasons.append(
                "maximum_short_risk_exceeded"
            )

        if (
            projected_symbol_risk
            > self.maximum_symbol_risk
        ):
            blocking_reasons.append(
                "maximum_symbol_risk_exceeded"
            )

        approved = not blocking_reasons

        if normalized_direction == "LONG":
            direction_limit = (
                self.maximum_long_risk
            )

            projected_direction_risk = (
                projected_long_risk
            )
        else:
            direction_limit = (
                self.maximum_short_risk
            )

            projected_direction_risk = (
                projected_short_risk
            )

        return {
            "approved": approved,
            "status": (
                "APPROVED"
                if approved
                else "BLOCKED"
            ),
            "decision": (
                "ALLOW_PORTFOLIO_RISK"
                if approved
                else "BLOCK_PORTFOLIO_RISK"
            ),
            "candidate_symbol": (
                normalized_symbol
            ),
            "candidate_direction": (
                normalized_direction
            ),
            "candidate_contracts": (
                normalized_contracts
            ),
            "candidate_entry_price": (
                normalized_entry_price
            ),
            "candidate_current_price": (
                normalized_current_price
            ),
            "candidate_stop_loss": (
                normalized_stop_loss
            ),
            "candidate_point_value": (
                normalized_point_value
            ),
            "candidate_risk": candidate_risk,
            "current_total_open_risk": (
                current_total_open_risk
            ),
            "current_long_risk": (
                current_long_risk
            ),
            "current_short_risk": (
                current_short_risk
            ),
            "current_symbol_risk": (
                current_symbol_risk
            ),
            "current_floating_pnl": (
                current_floating_pnl
            ),
            "current_floating_loss": (
                current_floating_loss
            ),
            "projected_total_open_risk": (
                projected_total_open_risk
            ),
            "projected_long_risk": (
                projected_long_risk
            ),
            "projected_short_risk": (
                projected_short_risk
            ),
            "projected_symbol_risk": (
                projected_symbol_risk
            ),
            "remaining_total_open_risk_capacity": max(
                0.0,
                round(
                    self.maximum_total_open_risk
                    - projected_total_open_risk,
                    10,
                ),
            ),
            "remaining_direction_risk_capacity": max(
                0.0,
                round(
                    direction_limit
                    - projected_direction_risk,
                    10,
                ),
            ),
            "remaining_symbol_risk_capacity": max(
                0.0,
                round(
                    self.maximum_symbol_risk
                    - projected_symbol_risk,
                    10,
                ),
            ),
            "maximum_total_open_risk": (
                self.maximum_total_open_risk
            ),
            "maximum_floating_loss": (
                self.maximum_floating_loss
            ),
            "maximum_long_risk": (
                self.maximum_long_risk
            ),
            "maximum_short_risk": (
                self.maximum_short_risk
            ),
            "maximum_symbol_risk": (
                self.maximum_symbol_risk
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
        }
