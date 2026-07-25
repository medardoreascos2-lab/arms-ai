from __future__ import annotations

from backend.execution.break_even_engine_v2 import (
    BreakEvenEngineV2,
)
from backend.execution.partial_take_profit_engine_v2 import (
    PartialTakeProfitEngineV2,
)
from backend.execution.realized_pnl_engine_v2 import (
    RealizedPnLEngineV2,
)
from backend.execution.trailing_stop_engine_v2 import (
    TrailingStopEngineV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


class LivePositionMonitorV2:
    """
    Actualiza posiciones activas con cada precio.

    Orden de gestión:

    1. Partial Take Profit.
    2. Realized PnL.
    3. Break Even.
    4. Trailing Stop.
    5. Actualización y cierre por SL o TP.
    """

    def __init__(
        self,
        *,
        trade_lifecycle_service:
        TradeLifecycleServiceV2,
        partial_take_profit_engine:
        PartialTakeProfitEngineV2
        | None = None,
        realized_pnl_engine:
        RealizedPnLEngineV2
        | None = None,
        break_even_engine:
        BreakEvenEngineV2
        | None = None,
        trailing_stop_engine:
        TrailingStopEngineV2
        | None = None,
        portfolio_manager_v2:
        PortfolioManagerV2
        | None = None,
    ) -> None:
        required_methods = (
            "get_active_positions",
            "update_position",
        )

        for method_name in required_methods:
            if not callable(
                getattr(
                    trade_lifecycle_service,
                    method_name,
                    None,
                )
            ):
                raise TypeError(
                    "trade_lifecycle_service debe implementar "
                    f"{method_name}()."
                )

        if (
            partial_take_profit_engine
            is not None
            and not isinstance(
                partial_take_profit_engine,
                PartialTakeProfitEngineV2,
            )
        ):
            raise TypeError(
                "partial_take_profit_engine debe ser "
                "PartialTakeProfitEngineV2."
            )

        if (
            realized_pnl_engine
            is not None
            and not isinstance(
                realized_pnl_engine,
                RealizedPnLEngineV2,
            )
        ):
            raise TypeError(
                "realized_pnl_engine debe ser "
                "RealizedPnLEngineV2."
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

        if (
            trailing_stop_engine
            is not None
            and not isinstance(
                trailing_stop_engine,
                TrailingStopEngineV2,
            )
        ):
            raise TypeError(
                "trailing_stop_engine debe ser "
                "TrailingStopEngineV2."
            )

        self.trade_lifecycle_service = (
            trade_lifecycle_service
        )

        self.partial_take_profit_engine = (
            partial_take_profit_engine
        )

        self.realized_pnl_engine = (
            realized_pnl_engine
        )

        self.break_even_engine = (
            break_even_engine
        )

        self.trailing_stop_engine = (
            trailing_stop_engine
        )

        if (
            portfolio_manager_v2
            is not None
            and not isinstance(
                portfolio_manager_v2,
                PortfolioManagerV2,
            )
        ):
            raise TypeError(
                "portfolio_manager_v2 debe ser "
                "PortfolioManagerV2."
            )

        self.portfolio_manager_v2 = (
            portfolio_manager_v2
        )

    def _persist_position(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        return (
            self.trade_lifecycle_service
            .replace_active_position(
                position=position,
            )
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

        partial_take_profit_results: list[
            dict[str, object]
        ] = []

        realized_pnl_results: list[
            dict[str, object]
        ] = []

        break_even_results: list[
            dict[str, object]
        ] = []

        trailing_stop_results: list[
            dict[str, object]
        ] = []

        closed_positions = 0
        performance_metrics = None
        portfolio_summary = None

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

            position_for_update[
                "current_price"
            ] = normalized_current_price

            # ======================================
            # 1. PARTIAL TAKE PROFIT
            # ======================================

            if (
                self.partial_take_profit_engine
                is not None
            ):
                partial_result = (
                    self.partial_take_profit_engine.apply(
                        position=(
                            position_for_update
                        ),
                        current_price=(
                            normalized_current_price
                        ),
                    )
                )

                partial_take_profit_results.append(
                    partial_result
                )

                partial_position = (
                    partial_result.get(
                        "position"
                    )
                )

                if isinstance(
                    partial_position,
                    dict,
                ):
                    position_for_update = dict(
                        partial_position
                    )

                    position_for_update[
                        "current_price"
                    ] = normalized_current_price

                    self._persist_position(
                        position=(
                            position_for_update
                        ),
                    )

            # ======================================
            # 2. REALIZED PNL
            # ======================================

            if (
                self.realized_pnl_engine
                is not None
            ):
                realized_result = (
                    self.realized_pnl_engine.calculate(
                        position=(
                            position_for_update
                        ),
                    )
                )

                realized_pnl_results.append(
                    realized_result
                )

                pnl_position = (
                    realized_result.get(
                        "position"
                    )
                )

                if isinstance(
                    pnl_position,
                    dict,
                ):
                    position_for_update = dict(
                        pnl_position
                    )

                    self._persist_position(
                        position=(
                            position_for_update
                        ),
                    )

            # ======================================
            # 3. BREAK EVEN
            # ======================================

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

                    self._persist_position(
                        position=(
                            position_for_update
                        ),
                    )

            # ======================================
            # 4. TRAILING STOP
            # ======================================

            if (
                self.trailing_stop_engine
                is not None
            ):
                trailing_result = (
                    self.trailing_stop_engine.apply(
                        position=(
                            position_for_update
                        ),
                        current_price=(
                            normalized_current_price
                        ),
                    )
                )

                trailing_stop_results.append(
                    trailing_result
                )

                trailed_position = (
                    trailing_result.get(
                        "position"
                    )
                )

                if isinstance(
                    trailed_position,
                    dict,
                ):
                    position_for_update = dict(
                        trailed_position
                    )

                    self._persist_position(
                        position=(
                            position_for_update
                        ),
                    )

            # ======================================
            # 5. ACTUALIZACIÓN DE LA POSICIÓN
            # ======================================

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
                self.portfolio_manager_v2
                is not None
                and str(
                    result_position.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
                != "CLOSED"
            ):
                self.portfolio_manager_v2.update_position(
                    position_id=str(
                        result_position[
                            "position_id"
                        ]
                    ),
                    updates={
                        "current_price": (
                            normalized_current_price
                        ),
                    },
                )

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

                if (
                    self.portfolio_manager_v2
                    is not None
                ):
                    self.portfolio_manager_v2.close_position(
                        position_id=str(
                            result_position[
                                "position_id"
                            ]
                        ),
                        exit_price=(
                            normalized_current_price
                        ),
                    )

                performance_metrics = (
                    result.get(
                        "performance_metrics"
                    )
                )

        if (
            self.portfolio_manager_v2
            is not None
        ):
            portfolio_summary = (
                self.portfolio_manager_v2
                .get_summary()
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
            "portfolio_summary": (
                portfolio_summary
            ),
            "partial_take_profit_results": (
                partial_take_profit_results
            ),
            "realized_pnl_results": (
                realized_pnl_results
            ),
            "break_even_results": (
                break_even_results
            ),
            "trailing_stop_results": (
                trailing_stop_results
            ),
        }
