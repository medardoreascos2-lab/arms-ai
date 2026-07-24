from __future__ import annotations

from uuid import uuid4


class PaperExecutionEngineV2:
    """
    Simula la ejecución de órdenes PAPER.

    Las órdenes bloqueadas se rechazan sin
    exigir precios válidos.
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

    @staticmethod
    def _optional_float(
        value: object,
    ) -> float | None:
        if value is None:
            return None

        return float(
            value
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

        quantity = int(
            prepared_order.get(
                "quantity",
                0,
            )
            or 0
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

        if execution_mode != "PAPER":
            rejection_reasons.append(
                "execution_mode_not_paper"
            )

        if decision != "SUBMIT_ORDER":
            rejection_reasons.append(
                "prepared_order_not_submittable"
            )

        if quantity <= 0:
            rejection_reasons.append(
                "invalid_quantity"
            )

        entry_price = self._optional_float(
            prepared_order.get(
                "entry_price"
            )
        )

        stop_loss = self._optional_float(
            prepared_order.get(
                "stop_loss"
            )
        )

        take_profit = self._optional_float(
            prepared_order.get(
                "take_profit"
            )
        )

        limit_price = self._optional_float(
            prepared_order.get(
                "limit_price"
            )
        )

        order_id = str(
            uuid4()
        )

        # Una orden bloqueada se rechaza
        # inmediatamente y puede contener
        # precios None.
        if rejection_reasons:
            requested_price = (
                limit_price
                if order_type == "LIMIT"
                else entry_price
            )

            return {
                "accepted": False,
                "status": "REJECTED",
                "execution_mode": "PAPER",
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "quantity": quantity,
                "requested_price": (
                    requested_price
                ),
                "filled_price": None,
                "limit_price": limit_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "slippage_points": (
                    self.slippage_points
                ),
                "rejection_reasons": (
                    rejection_reasons
                ),
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

        if (
            entry_price is None
            or entry_price <= 0
        ):
            raise ValueError(
                "entry_price debe ser mayor "
                "que cero."
            )

        if (
            stop_loss is None
            or stop_loss <= 0
        ):
            raise ValueError(
                "stop_loss debe ser mayor "
                "que cero."
            )

        if (
            take_profit is None
            or take_profit <= 0
        ):
            raise ValueError(
                "take_profit debe ser mayor "
                "que cero."
            )

        if order_type == "LIMIT":
            if (
                limit_price is None
                or limit_price <= 0
            ):
                raise ValueError(
                    "limit_price es obligatorio "
                    "para órdenes LIMIT."
                )

            requested_price = limit_price
        else:
            requested_price = entry_price

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
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "requested_price": (
                requested_price
            ),
            "filled_price": filled_price,
            "limit_price": limit_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
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
