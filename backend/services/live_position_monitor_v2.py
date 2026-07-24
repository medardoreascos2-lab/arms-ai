from __future__ import annotations

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


class LivePositionMonitorV2:
    """
    Actualiza posiciones abiertas con cada
    nuevo precio y aplica protección Break Even.
    """

    def __init__(
        self,
        *,
        trade_lifecycle_service:
        TradeLifecycleServiceV2,
        break_even_engine:
        BreakEvenEngineV2
        | None = None,
    ) -> None:
        if not isinstance(
            trade_lifecycle_service,
            TradeLifecycleServiceV2,
        ):
            raise TypeError(
                "trade_lifecycle_service debe ser "
                "TradeLifecycleServiceV2."
            )

        if (
            break_even_engine
            is not None
            and not isinstance(
                break_even_engine,
                BreakEvenEngineV2,
            )
        ):
            raise TypeError(
                "break_even_engine debe ser "
                "BreakEvenEngineV2."
            )

        self.trade_lifecycle_service = (
            trade_lifecycle_service
        )

        self.break_even_engine = (
            break_even_engine
        )

    def process_price(
        self,
        *,
        symbol: str,
        current_price: float,
    ) -> dict[str, object]:
        normalized_symbol = (
            str(
                symbol
            )
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol es obligatorio."
            )

        normalized_current_price = float(
            current_price
        )

        if normalized_current_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
            )

        active_positions = (
            self.trade_lifecycle_service
            .get_active_positions()
        )

        updated_positions: list[
            dict[str, object]
        ] = []

        break_even_results: list[
            dict[str, object]
        ] = []

        closed_positions = 0
        performance_metrics = None

        for position in active_positions:
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

            if (
                position_symbol
                != normalized_symbol
            ):
                continue

            position_for_update = dict(
                position
            )

            if (
                self.break_even_engine
                is not None
            ):
                break_even_result = (
                    self.break_even_engine.apply(
                        position=(
                            position_for_update
                        ),
                        current_price=(
                            normalized_current_price
                        ),
                    )
                )

                break_even_results.append(
                    break_even_result
                )

                protected_position = (
                    break_even_result.get(
                        "position"
                    )
                )

                if isinstance(
                    protected_position,
                    dict,
                ):
                    position_for_update = dict(
                        protected_position
                    )

                    self.trade_lifecycle_service\
                        .replace_active_position(
                            position=(
                                position_for_update
                            ),
                        )

            result = (
                self.trade_lifecycle_service
                .update_position(
                    position_id=str(
                        position_for_update[
                            "position_id"
                        ]
                    ),
                    current_price=(
                        normalized_current_price
                    ),
                )
            )

            updated_positions.append(
                result
            )

            result_position = result[
                "position"
            ]

            if (
                str(
                    result_position.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
                == "CLOSED"
            ):
                closed_positions += 1

                performance_metrics = (
                    result.get(
                        "performance_metrics"
                    )
                )

        return {
            "processed": True,
            "symbol": normalized_symbol,
            "current_price": (
                normalized_current_price
            ),
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
            "break_even_results": (
                break_even_results
            ),
        }
