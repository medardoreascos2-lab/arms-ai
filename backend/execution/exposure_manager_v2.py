from __future__ import annotations


class ExposureManagerV2:
    """
    Controla el riesgo y los contratos abiertos
    antes de permitir una nueva operación.
    """

    def __init__(
        self,
        *,
        maximum_total_open_risk: float,
        maximum_symbol_open_risk: float,
        maximum_total_contracts: int | None,
        maximum_symbol_contracts: int | None,
    ) -> None:
        normalized_total_risk = float(
            maximum_total_open_risk
        )

        normalized_symbol_risk = float(
            maximum_symbol_open_risk
        )

        normalized_total_contracts = (
            None
            if maximum_total_contracts is None
            else int(maximum_total_contracts)
        )

        normalized_symbol_contracts = (
            None
            if maximum_symbol_contracts is None
            else int(maximum_symbol_contracts)
        )

        if normalized_total_risk <= 0:
            raise ValueError(
                "maximum_total_open_risk debe ser "
                "mayor que cero."
            )

        if normalized_symbol_risk <= 0:
            raise ValueError(
                "maximum_symbol_open_risk debe ser "
                "mayor que cero."
            )

        if (
            normalized_total_contracts is not None
            and normalized_total_contracts <= 0
        ):
            raise ValueError(
                "maximum_total_contracts debe ser "
                "mayor que cero cuando está definido."
            )

        if (
            normalized_symbol_contracts is not None
            and normalized_symbol_contracts <= 0
        ):
            raise ValueError(
                "maximum_symbol_contracts debe ser "
                "mayor que cero cuando está definido."
            )

        if (
            normalized_symbol_risk
            > normalized_total_risk
        ):
            raise ValueError(
                "maximum_symbol_open_risk no puede ser "
                "mayor que maximum_total_open_risk."
            )

        if (
            normalized_symbol_contracts is not None
            and normalized_total_contracts is not None
            and normalized_symbol_contracts
            > normalized_total_contracts
        ):
            raise ValueError(
                "maximum_symbol_contracts no puede ser "
                "mayor que maximum_total_contracts."
            )

        self.maximum_total_open_risk = (
            normalized_total_risk
        )

        self.maximum_symbol_open_risk = (
            normalized_symbol_risk
        )

        self.maximum_total_contracts = (
            normalized_total_contracts
        )

        self.maximum_symbol_contracts = (
            normalized_symbol_contracts
        )

    def evaluate(
        self,
        *,
        open_positions: list[
            dict[str, object]
        ],
        candidate_symbol: str,
        candidate_contracts: int,
        candidate_stop_points: float,
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

        normalized_contracts = int(
            candidate_contracts
        )

        normalized_stop_points = float(
            candidate_stop_points
        )

        normalized_point_value = float(
            candidate_point_value
        )

        if normalized_contracts <= 0:
            raise ValueError(
                "candidate_contracts debe ser "
                "mayor que cero."
            )

        if normalized_stop_points <= 0:
            raise ValueError(
                "candidate_stop_points debe ser "
                "mayor que cero."
            )

        if normalized_point_value <= 0:
            raise ValueError(
                "candidate_point_value debe ser "
                "mayor que cero."
            )

        current_total_open_risk = 0.0
        current_symbol_open_risk = 0.0
        current_total_contracts = 0
        current_symbol_contracts = 0

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

            position_symbol = (
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

            stop_points = abs(
                entry_price
                - stop_loss
            )

            position_risk = round(
                stop_points
                * quantity
                * point_value,
                10,
            )

            current_total_open_risk += (
                position_risk
            )

            current_total_contracts += (
                quantity
            )

            if (
                position_symbol
                == normalized_symbol
            ):
                current_symbol_open_risk += (
                    position_risk
                )

                current_symbol_contracts += (
                    quantity
                )

        current_total_open_risk = round(
            current_total_open_risk,
            10,
        )

        current_symbol_open_risk = round(
            current_symbol_open_risk,
            10,
        )

        candidate_risk = round(
            normalized_contracts
            * normalized_stop_points
            * normalized_point_value,
            10,
        )

        projected_total_open_risk = round(
            current_total_open_risk
            + candidate_risk,
            10,
        )

        projected_symbol_open_risk = round(
            current_symbol_open_risk
            + candidate_risk,
            10,
        )

        projected_total_contracts = (
            current_total_contracts
            + normalized_contracts
        )

        projected_symbol_contracts = (
            current_symbol_contracts
            + normalized_contracts
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
            projected_symbol_open_risk
            > self.maximum_symbol_open_risk
        ):
            blocking_reasons.append(
                "maximum_symbol_open_risk_exceeded"
            )

        if (
            self.maximum_total_contracts is not None
            and projected_total_contracts
            > self.maximum_total_contracts
        ):
            blocking_reasons.append(
                "maximum_total_contracts_exceeded"
            )

        if (
            self.maximum_symbol_contracts is not None
            and projected_symbol_contracts
            > self.maximum_symbol_contracts
        ):
            blocking_reasons.append(
                "maximum_symbol_contracts_exceeded"
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
                "ALLOW_EXPOSURE"
                if approved
                else "BLOCK_EXPOSURE"
            ),
            "candidate_symbol": (
                normalized_symbol
            ),
            "candidate_contracts": (
                normalized_contracts
            ),
            "candidate_stop_points": (
                normalized_stop_points
            ),
            "candidate_point_value": (
                normalized_point_value
            ),
            "candidate_risk": candidate_risk,
            "current_total_open_risk": (
                current_total_open_risk
            ),
            "current_symbol_open_risk": (
                current_symbol_open_risk
            ),
            "current_total_contracts": (
                current_total_contracts
            ),
            "current_symbol_contracts": (
                current_symbol_contracts
            ),
            "projected_total_open_risk": (
                projected_total_open_risk
            ),
            "projected_symbol_open_risk": (
                projected_symbol_open_risk
            ),
            "projected_total_contracts": (
                projected_total_contracts
            ),
            "projected_symbol_contracts": (
                projected_symbol_contracts
            ),
            "remaining_total_open_risk_capacity": max(
                0.0,
                round(
                    self.maximum_total_open_risk
                    - projected_total_open_risk,
                    10,
                ),
            ),
            "remaining_symbol_open_risk_capacity": max(
                0.0,
                round(
                    self.maximum_symbol_open_risk
                    - projected_symbol_open_risk,
                    10,
                ),
            ),
            "remaining_total_contract_capacity": (
                None
                if self.maximum_total_contracts is None
                else max(
                    0,
                    self.maximum_total_contracts
                    - projected_total_contracts,
                )
            ),
            "remaining_symbol_contract_capacity": (
                None
                if self.maximum_symbol_contracts is None
                else max(
                    0,
                    self.maximum_symbol_contracts
                    - projected_symbol_contracts,
                )
            ),
            "maximum_total_open_risk": (
                self.maximum_total_open_risk
            ),
            "maximum_symbol_open_risk": (
                self.maximum_symbol_open_risk
            ),
            "maximum_total_contracts": (
                self.maximum_total_contracts
            ),
            "maximum_symbol_contracts": (
                self.maximum_symbol_contracts
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
        }
