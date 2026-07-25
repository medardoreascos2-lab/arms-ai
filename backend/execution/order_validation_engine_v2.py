from __future__ import annotations


class OrderValidationEngineV2:
    """
    Realiza la validación final de una orden
    antes de permitir su ejecución.
    """

    VALID_SIDES = {
        "BUY",
        "SELL",
    }

    VALID_ORDER_TYPES = {
        "MARKET",
        "LIMIT",
    }

    def __init__(
        self,
        *,
        minimum_reward_risk_ratio: float,
        minimum_stop_points: float,
        maximum_stop_points: float,
        allowed_symbols: set[str],
    ) -> None:
        normalized_minimum_rr = float(
            minimum_reward_risk_ratio
        )

        normalized_minimum_stop = float(
            minimum_stop_points
        )

        normalized_maximum_stop = float(
            maximum_stop_points
        )

        if normalized_minimum_rr <= 0:
            raise ValueError(
                "minimum_reward_risk_ratio debe ser "
                "mayor que cero."
            )

        if normalized_minimum_stop <= 0:
            raise ValueError(
                "minimum_stop_points debe ser "
                "mayor que cero."
            )

        if normalized_maximum_stop <= 0:
            raise ValueError(
                "maximum_stop_points debe ser "
                "mayor que cero."
            )

        if (
            normalized_maximum_stop
            < normalized_minimum_stop
        ):
            raise ValueError(
                "maximum_stop_points no puede ser "
                "menor que minimum_stop_points."
            )

        if not isinstance(
            allowed_symbols,
            set,
        ):
            raise TypeError(
                "allowed_symbols debe ser un set."
            )

        normalized_symbols = {
            str(symbol)
            .strip()
            .upper()
            for symbol in allowed_symbols
            if str(symbol).strip()
        }

        if not normalized_symbols:
            raise ValueError(
                "allowed_symbols no puede estar vacío."
            )

        self.minimum_reward_risk_ratio = (
            normalized_minimum_rr
        )

        self.minimum_stop_points = (
            normalized_minimum_stop
        )

        self.maximum_stop_points = (
            normalized_maximum_stop
        )

        self.allowed_symbols = (
            normalized_symbols
        )

    def validate(
        self,
        *,
        prepared_order: dict[str, object],
        market_is_open: bool,
        open_symbols: set[str],
    ) -> dict[str, object]:
        if not isinstance(
            prepared_order,
            dict,
        ):
            raise TypeError(
                "prepared_order debe ser un dict."
            )

        if not isinstance(
            open_symbols,
            set,
        ):
            raise TypeError(
                "open_symbols debe ser un set."
            )

        normalized_open_symbols = {
            str(symbol)
            .strip()
            .upper()
            for symbol in open_symbols
            if str(symbol).strip()
        }

        symbol = (
            str(
                prepared_order.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        side = (
            str(
                prepared_order.get(
                    "side",
                    "",
                )
            )
            .strip()
            .upper()
        )

        order_type = (
            str(
                prepared_order.get(
                    "order_type",
                    "",
                )
            )
            .strip()
            .upper()
        )

        quantity = int(
            prepared_order.get(
                "quantity",
                0,
            )
        )

        entry_price = float(
            prepared_order.get(
                "entry_price",
                0.0,
            )
        )

        stop_loss = float(
            prepared_order.get(
                "stop_loss",
                0.0,
            )
        )

        take_profit = float(
            prepared_order.get(
                "take_profit",
                0.0,
            )
        )

        limit_price_value = (
            prepared_order.get(
                "limit_price"
            )
        )

        blocking_reasons: list[str] = []

        if not bool(
            prepared_order.get(
                "approved",
                False,
            )
        ):
            blocking_reasons.append(
                "prepared_order_not_approved"
            )

        prepared_status = (
            str(
                prepared_order.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            prepared_status
            != "READY_TO_SUBMIT"
        ):
            blocking_reasons.append(
                "prepared_order_not_ready"
            )

        prepared_decision = (
            str(
                prepared_order.get(
                    "decision",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            prepared_decision
            != "SUBMIT_ORDER"
        ):
            blocking_reasons.append(
                "prepared_order_not_submittable"
            )

        if not bool(
            market_is_open
        ):
            blocking_reasons.append(
                "market_closed"
            )

        if symbol not in self.allowed_symbols:
            blocking_reasons.append(
                "symbol_not_allowed"
            )

        if symbol in normalized_open_symbols:
            blocking_reasons.append(
                "symbol_position_already_open"
            )

        if quantity <= 0:
            blocking_reasons.append(
                "invalid_quantity"
            )

        if side not in self.VALID_SIDES:
            blocking_reasons.append(
                "invalid_side"
            )

        if (
            order_type
            not in self.VALID_ORDER_TYPES
        ):
            blocking_reasons.append(
                "invalid_order_type"
            )

        if entry_price <= 0:
            blocking_reasons.append(
                "invalid_entry_price"
            )

        if stop_loss <= 0:
            blocking_reasons.append(
                "invalid_stop_loss"
            )

        if take_profit <= 0:
            blocking_reasons.append(
                "invalid_take_profit"
            )

        if (
            order_type == "LIMIT"
            and limit_price_value is None
        ):
            blocking_reasons.append(
                "limit_price_required"
            )

        stop_distance = 0.0
        reward_distance = 0.0
        reward_risk_ratio = 0.0

        levels_are_valid = (
            entry_price > 0
            and stop_loss > 0
            and take_profit > 0
            and side in self.VALID_SIDES
        )

        if levels_are_valid:
            if side == "BUY":
                if not (
                    stop_loss
                    < entry_price
                    < take_profit
                ):
                    blocking_reasons.append(
                        "invalid_buy_levels"
                    )

                stop_distance = round(
                    entry_price
                    - stop_loss,
                    10,
                )

                reward_distance = round(
                    take_profit
                    - entry_price,
                    10,
                )

            else:
                if not (
                    take_profit
                    < entry_price
                    < stop_loss
                ):
                    blocking_reasons.append(
                        "invalid_sell_levels"
                    )

                stop_distance = round(
                    stop_loss
                    - entry_price,
                    10,
                )

                reward_distance = round(
                    entry_price
                    - take_profit,
                    10,
                )

            if stop_distance > 0:
                reward_risk_ratio = round(
                    reward_distance
                    / stop_distance,
                    10,
                )

            if (
                stop_distance
                < self.minimum_stop_points
            ):
                blocking_reasons.append(
                    "stop_distance_below_minimum"
                )

            if (
                stop_distance
                > self.maximum_stop_points
            ):
                blocking_reasons.append(
                    "stop_distance_above_maximum"
                )

            if (
                reward_risk_ratio
                < self.minimum_reward_risk_ratio
            ):
                blocking_reasons.append(
                    "reward_risk_below_minimum"
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
                "ALLOW_ORDER"
                if approved
                else "BLOCK_ORDER"
            ),
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "entry_price": entry_price,
            "limit_price": (
                None
                if limit_price_value is None
                else float(
                    limit_price_value
                )
            ),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "stop_distance": (
                stop_distance
            ),
            "reward_distance": (
                reward_distance
            ),
            "reward_risk_ratio": (
                reward_risk_ratio
            ),
            "minimum_reward_risk_ratio": (
                self.minimum_reward_risk_ratio
            ),
            "minimum_stop_points": (
                self.minimum_stop_points
            ),
            "maximum_stop_points": (
                self.maximum_stop_points
            ),
            "market_is_open": bool(
                market_is_open
            ),
            "open_symbols": sorted(
                normalized_open_symbols
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
        }
