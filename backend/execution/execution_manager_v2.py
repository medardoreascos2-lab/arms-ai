from __future__ import annotations


class ExecutionManagerV2:
    """
    Convierte una señal aprobada en una orden
    preparada para ejecución PAPER o LIVE.
    """

    VALID_EXECUTION_MODES = {
        "PAPER",
        "LIVE",
    }

    VALID_ORDER_TYPES = {
        "MARKET",
        "LIMIT",
    }

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        execution_mode: str,
        maximum_contracts: int,
    ) -> None:
        normalized_execution_mode = (
            str(execution_mode)
            .strip()
            .upper()
        )

        normalized_maximum_contracts = int(
            maximum_contracts
        )

        if (
            normalized_execution_mode
            not in self.VALID_EXECUTION_MODES
        ):
            raise ValueError(
                "execution_mode debe ser "
                "PAPER o LIVE."
            )

        if normalized_maximum_contracts <= 0:
            raise ValueError(
                "maximum_contracts debe ser "
                "mayor que cero."
            )

        self.execution_mode = (
            normalized_execution_mode
        )

        self.maximum_contracts = (
            normalized_maximum_contracts
        )

    def prepare_order(
        self,
        *,
        signal: dict[str, object],
        order_type: str,
    ) -> dict[str, object]:
        if not isinstance(
            signal,
            dict,
        ):
            raise TypeError(
                "signal debe ser un dict."
            )

        normalized_order_type = (
            str(order_type)
            .strip()
            .upper()
        )

        if (
            normalized_order_type
            not in self.VALID_ORDER_TYPES
        ):
            raise ValueError(
                "order_type debe ser "
                "MARKET o LIMIT."
            )

        symbol = (
            str(
                signal.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        direction = (
            str(
                signal.get(
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
                "direction debe ser "
                "LONG o SHORT."
            )

        entry_price = float(
            signal.get(
                "entry_price",
                0.0,
            )
        )

        stop_loss = float(
            signal.get(
                "stop_loss",
                0.0,
            )
        )

        take_profit = float(
            signal.get(
                "take_profit",
                0.0,
            )
        )

        quantity = int(
            signal.get(
                "contracts",
                0,
            )
        )

        if entry_price <= 0:
            raise ValueError(
                "entry_price debe ser "
                "mayor que cero."
            )

        if stop_loss <= 0:
            raise ValueError(
                "stop_loss debe ser "
                "mayor que cero."
            )

        if take_profit <= 0:
            raise ValueError(
                "take_profit debe ser "
                "mayor que cero."
            )

        if direction == "LONG":
            if stop_loss >= entry_price:
                raise ValueError(
                    "stop_loss debe estar por "
                    "debajo de entry_price "
                    "para LONG."
                )

            if take_profit <= entry_price:
                raise ValueError(
                    "take_profit debe estar por "
                    "encima de entry_price "
                    "para LONG."
                )

            side = "BUY"

        else:
            if stop_loss <= entry_price:
                raise ValueError(
                    "stop_loss debe estar por "
                    "encima de entry_price "
                    "para SHORT."
                )

            if take_profit >= entry_price:
                raise ValueError(
                    "take_profit debe estar por "
                    "debajo de entry_price "
                    "para SHORT."
                )

            side = "SELL"

        blocking_reasons: list[str] = []

        if not bool(
            signal.get(
                "approved",
                False,
            )
        ):
            blocking_reasons.append(
                "signal_not_approved"
            )

        signal_decision = (
            str(
                signal.get(
                    "decision",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if signal_decision != "SEND_SIGNAL":
            blocking_reasons.append(
                "signal_decision_not_sendable"
            )

        if quantity <= 0:
            blocking_reasons.append(
                "invalid_contract_quantity"
            )

        if quantity > self.maximum_contracts:
            blocking_reasons.append(
                "maximum_contracts_exceeded"
            )

        approved = not blocking_reasons

        return {
            "approved": approved,
            "status": (
                "READY_TO_SUBMIT"
                if approved
                else "BLOCKED"
            ),
            "decision": (
                "SUBMIT_ORDER"
                if approved
                else "DO_NOT_SUBMIT"
            ),
            "execution_mode": (
                self.execution_mode
            ),
            "symbol": symbol,
            "side": side,
            "order_type": (
                normalized_order_type
            ),
            "quantity": quantity,
            "entry_price": entry_price,
            "limit_price": (
                entry_price
                if normalized_order_type
                == "LIMIT"
                else None
            ),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "blocking_reasons": (
                blocking_reasons
            ),
            "source_signal_status": (
                signal.get(
                    "status"
                )
            ),
            "source_signal_decision": (
                signal_decision
            ),
            "probability": signal.get(
                "probability"
            ),
            "confluence_score": signal.get(
                "confluence_score"
            ),
            "grade": signal.get(
                "grade"
            ),
            "warnings": list(
                signal.get(
                    "warnings",
                    [],
                )
            ),
        }
