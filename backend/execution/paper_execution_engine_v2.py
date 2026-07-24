from __future__ import annotations

from uuid import uuid4


class PaperExecutionEngineV2:
    """
    Simula la ejecución de órdenes en modo PAPER.
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
        fill_market_orders_immediately: bool,
        slippage_points: float,
    ) -> None:
        normalized_slippage = float(
            slippage_points
        )

        if normalized_slippage < 0:
            raise ValueError(
                "slippage_points no puede ser "
                "negativo."
            )

        self.fill_market_orders_immediately = bool(
            fill_market_orders_immediately
        )

        self.slippage_points = (
            normalized_slippage
        )

    def execute(
        self,
        *,
        prepared_order: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            prepared_order,
            dict,
        ):
            raise TypeError(
                "prepared_order debe ser un dict."
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

        if side not in self.VALID_SIDES:
            raise ValueError(
                "side debe ser BUY o SELL."
            )

        if (
            order_type
            not in self.VALID_ORDER_TYPES
        ):
            raise ValueError(
                "order_type debe ser MARKET "
                "o LIMIT."
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

        quantity = int(
            prepared_order.get(
                "quantity",
                0,
            )
        )

        if entry_price <= 0:
            raise ValueError(
                "entry_price debe ser mayor "
                "que cero."
            )

        if stop_loss <= 0:
            raise ValueError(
                "stop_loss debe ser mayor "
                "que cero."
            )

        if take_profit <= 0:
            raise ValueError(
                "take_profit debe ser mayor "
                "que cero."
            )

        limit_price_value = (
            prepared_order.get(
                "limit_price"
            )
        )

        if order_type == "LIMIT":
            if limit_price_value is None:
                raise ValueError(
                    "limit_price es obligatorio "
                    "para órdenes LIMIT."
                )

            limit_price = float(
                limit_price_value
            )

            if limit_price <= 0:
                raise ValueError(
                    "limit_price debe ser mayor "
                    "que cero."
                )

            requested_price = (
                limit_price
            )
        else:
            limit_price = None
            requested_price = (
                entry_price
            )

        rejection_reasons: list[str] = []

        if not bool(
            prepared_order.get(
                "approved",
                False,
            )
        ):
            rejection_reasons.append(
                "prepared_order_not_approved"
            )

        execution_mode = (
            str(
                prepared_order.get(
                    "execution_mode",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if execution_mode != "PAPER":
            rejection_reasons.append(
                "execution_mode_not_paper"
            )

        decision = (
            str(
                prepared_order.get(
                    "decision",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if decision != "SUBMIT_ORDER":
            rejection_reasons.append(
                "prepared_order_not_submittable"
            )

        if quantity <= 0:
            rejection_reasons.append(
                "invalid_quantity"
            )

        order_id = str(
            uuid4()
        )

        if rejection_reasons:
            return {
                "accepted": False,
                "status": "REJECTED",
                "execution_mode": "PAPER",
                "order_id": order_id,
                "symbol": (
                    str(
                        prepared_order.get(
                            "symbol",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                ),
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "requested_price": (
                    requested_price
                ),
                "filled_price": None,
                "stop_loss": stop_loss,
                "take_profit": (
                    take_profit
                ),
                "rejection_reasons": (
                    rejection_reasons
                ),
            }

        if (
            order_type == "MARKET"
            and self.fill_market_orders_immediately
        ):
            status = "FILLED"

            if side == "BUY":
                filled_price = round(
                    requested_price
                    + self.slippage_points,
                    10,
                )
            else:
                filled_price = round(
                    requested_price
                    - self.slippage_points,
                    10,
                )

        else:
            status = "SUBMITTED"
            filled_price = None

        return {
            "accepted": True,
            "status": status,
            "execution_mode": "PAPER",
            "order_id": order_id,
            "symbol": (
                str(
                    prepared_order.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            ),
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "requested_price": (
                requested_price
            ),
            "filled_price": (
                filled_price
            ),
            "limit_price": (
                limit_price
            ),
            "stop_loss": stop_loss,
            "take_profit": (
                take_profit
            ),
            "slippage_points": (
                self.slippage_points
            ),
            "rejection_reasons": [],
            "probability": (
                prepared_order.get(
                    "probability"
                )
            ),
            "confluence_score": (
                prepared_order.get(
                    "confluence_score"
                )
            ),
            "grade": prepared_order.get(
                "grade"
            ),
            "warnings": list(
                prepared_order.get(
                    "warnings",
                    [],
                )
            ),
        }
