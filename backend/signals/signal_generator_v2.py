from __future__ import annotations


class SignalGeneratorV2:

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        minimum_probability: float,
        minimum_confluence_score: float,
        allowed_grades: set[str],
    ) -> None:

        minimum_probability = float(
            minimum_probability
        )

        minimum_confluence_score = float(
            minimum_confluence_score
        )

        if not (
            0.0 <= minimum_probability <= 1.0
        ):
            raise ValueError(
                "minimum_probability inválido."
            )

        if not (
            0.0 <= minimum_confluence_score <= 1.0
        ):
            raise ValueError(
                "minimum_confluence_score inválido."
            )

        if not allowed_grades:
            raise ValueError(
                "allowed_grades vacío."
            )

        self.minimum_probability = (
            minimum_probability
        )

        self.minimum_confluence_score = (
            minimum_confluence_score
        )

        self.allowed_grades = {
            str(g).strip().upper()
            for g in allowed_grades
        }

    def generate(
        self,
        *,
        symbol,
        timeframe,
        trade_plan,
        trade_validation,
    ):

        if not isinstance(
            trade_plan,
            dict,
        ):
            raise TypeError(
                "trade_plan inválido."
            )

        if not isinstance(
            trade_validation,
            dict,
        ):
            raise TypeError(
                "trade_validation inválido."
            )

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        timeframe = (
            str(timeframe)
            .strip()
            .upper()
        )

        if not symbol:
            raise ValueError(
                "symbol inválido."
            )

        if not timeframe:
            raise ValueError(
                "timeframe inválido."
            )

        direction = (
            str(
                trade_plan.get(
                    "direction",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction inválido."
            )

        probability = float(
            trade_plan.get(
                "probability",
                0.0,
            )
        )

        if not (
            0.0 <= probability <= 1.0
        ):
            raise ValueError(
                "probability inválido."
            )

        confluence_score = float(
            trade_plan.get(
                "confluence_score",
                0.0,
            )
        )

        if not (
            0.0
            <= confluence_score
            <= 1.0
        ):
            raise ValueError(
                "confluence_score inválido."
            )

        grade = (
            str(
                trade_plan.get(
                    "grade",
                    "",
                )
            )
            .strip()
            .upper()
        )

        blocking = []

        if not trade_plan.get(
            "approved",
            False,
        ):
            blocking.append(
                "trade_plan_not_approved"
            )

        if not trade_validation.get(
            "approved",
            False,
        ):
            blocking.append(
                "trade_validation_rejected"
            )

            blocking.extend(
                trade_validation.get(
                    "blocking_reasons",
                    [],
                )
            )

        if (
            probability
            < self.minimum_probability
        ):
            blocking.append(
                "probability_below_minimum"
            )

        if (
            confluence_score
            < self.minimum_confluence_score
        ):
            blocking.append(
                "confluence_below_minimum"
            )

        if (
            grade
            not in self.allowed_grades
        ):
            blocking.append(
                "grade_not_allowed"
            )

        approved = not blocking

        return {
            "approved": approved,
            "status": (
                "READY"
                if approved
                else "BLOCKED"
            ),
            "decision": (
                "SEND_SIGNAL"
                if approved
                else "DO_NOT_SEND"
            ),
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "entry_price": trade_plan.get(
                "entry_price"
            ),
            "stop_loss": trade_plan.get(
                "stop_loss"
            ),
            "take_profit": trade_plan.get(
                "take_profit"
            ),
            "contracts": trade_plan.get(
                "contracts"
            ),
            "probability": probability,
            "confluence_score": (
                confluence_score
            ),
            "grade": grade,
            "warnings": (
                trade_validation.get(
                    "warnings",
                    [],
                )
            ),
            "blocking_reasons": blocking,
            "summary": (
                f"{symbol} "
                f"{direction} "
                f"ENTRY {trade_plan.get('entry_price')} "
                f"SL {trade_plan.get('stop_loss')} "
                f"TP {trade_plan.get('take_profit')}"
            ),
        }
