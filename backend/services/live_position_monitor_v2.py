from __future__ import annotations

from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class LivePositionMonitorV2:

    def __init__(
        self,
        *,
        trade_lifecycle_service: TradeLifecycleServiceV2,
    ) -> None:

        if not isinstance(
            trade_lifecycle_service,
            TradeLifecycleServiceV2,
        ):
            raise TypeError(
                "trade_lifecycle_service debe ser "
                "TradeLifecycleServiceV2."
            )

        self.trade_lifecycle_service = (
            trade_lifecycle_service
        )

    def process_price(
        self,
        *,
        symbol: str,
        current_price: float,
    ) -> dict[str, object]:

        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol es obligatorio."
            )

        current_price = float(
            current_price
        )

        if current_price <= 0:
            raise ValueError(
                "current_price debe ser mayor que cero."
            )

        active_positions = (
            self.trade_lifecycle_service
            .get_active_positions()
        )

        updated_positions = []
        closed_positions = 0
        performance_metrics = None

        for position in active_positions:

            if (
                position["symbol"]
                != normalized_symbol
            ):
                continue

            result = (
                self.trade_lifecycle_service
                .update_position(
                    position_id=position[
                        "position_id"
                    ],
                    current_price=current_price,
                )
            )

            updated_positions.append(
                result
            )

            if (
                result["position"]["status"]
                == "CLOSED"
            ):
                closed_positions += 1
                performance_metrics = (
                    result[
                        "performance_metrics"
                    ]
                )

        return {
            "processed": True,
            "symbol": normalized_symbol,
            "current_price": current_price,
            "matched_positions": len(
                updated_positions
            ),
            "updated_positions": (
                updated_positions
            ),
            "closed_positions": (
                closed_positions
            ),
            "performance_metrics": (
                performance_metrics
            ),
        }
