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

        from backend.models.trade_plan import TradePlan

        if not isinstance(
            trade_plan,
            (
                dict,
                TradePlan,
            ),
        ):
            raise TypeError(
                "trade_plan inválido."
            )

        def get_trade_plan_value(
            key,
            default=None,
        ):
            if isinstance(
                trade_plan,
                dict,
            ):
                return trade_plan.get(
                    key,
                    default,
                )

            return getattr(
                trade_plan,
                key,
                default,
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
                get_trade_plan_value(
                    "direction",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if not direction:
            decision = (
                str(
                    get_trade_plan_value(
                        "decision",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if decision == "EXECUTE_LONG":
                direction = "LONG"

            elif decision == "EXECUTE_SHORT":
                direction = "SHORT"

        if (
            direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction inválido."
            )

        probability = float(
            get_trade_plan_value(
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
            get_trade_plan_value(
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
                get_trade_plan_value(
                    "grade",
                    "",
                )
            )
            .strip()
            .upper()
        )

        blocking = []

        trade_plan_approved = (
            get_trade_plan_value(
                "approved",
                get_trade_plan_value(
                    "authorized",
                    False,
                ),
            )
        )

        if not trade_plan_approved:
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
            "entry_price": get_trade_plan_value(
                "entry_price"
            ),
            "stop_loss": get_trade_plan_value(
                "stop_loss"
            ),
            "take_profit": get_trade_plan_value(
                "take_profit"
            ),
            "contracts": get_trade_plan_value(
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
                f"ENTRY {get_trade_plan_value('entry_price')} "
                f"SL {get_trade_plan_value('stop_loss')} "
                f"TP {get_trade_plan_value('take_profit')}"
            ),
        }
