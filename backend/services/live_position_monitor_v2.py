from __future__ import annotations

from datetime import datetime
from datetime import timezone

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

from backend.intelligence.trade_learning_service_v2 import (
    TradeLearningServiceV2,
)

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
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

        trade_learning_service_v2:
        TradeLearningServiceV2
        | None = None,
        instrument_profile_engine:
        InstrumentProfileEngine
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

        self.instrument_profile_engine = (
            instrument_profile_engine
            if instrument_profile_engine is not None
            else InstrumentProfileEngine()
        )


        self.trade_learning_service_v2 = (
            trade_learning_service_v2
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

    def _resolve_point_value(
        self,
        *,
        symbol: str,
    ) -> float:
        profile = self.instrument_profile_engine.get_profile(
            symbol=symbol,
        )
        return float(profile["point_value"])

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
                point_value = (
                    self._resolve_point_value(
                        symbol=str(
                            position_for_update.get(
                                "symbol",
                                normalized_symbol,
                            )
                        ),
                    )
                )

                realized_engine = (
                    self.realized_pnl_engine
                    if float(
                        self.realized_pnl_engine.point_value
                    ) == point_value
                    else RealizedPnLEngineV2(
                        point_value=point_value,
                    )
                )

                realized_result = (
                    realized_engine.calculate(
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
            # 5. RESOLUCIÓN DE POINT VALUE
            # ======================================

            if position_for_update.get(
                "point_value"
            ) is None:

                position_for_update[
                    "point_value"
                ] = self._resolve_point_value(
                    symbol=str(
                        position_for_update.get(
                            "symbol",
                            normalized_symbol,
                        )
                    )
                    .strip()
                    .upper()
                )

            # ======================================
            # 6. ACTUALIZACIÓN DE LA POSICIÓN
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

            # V40: propagate the resolved point value into
            # the lifecycle result before downstream Journal
            # synchronization.

            if (
                result_position.get(
                    "point_value"
                ) is None
                and position_for_update.get(
                    "point_value"
                ) is not None
            ):
                result_position[
                    "point_value"
                ] = position_for_update[
                    "point_value"
                ]

            # V40: defensive Journal synchronization.
            #
            # TradeLifecycleServiceV2 normally owns the Journal
            # close. If the lifecycle implementation already
            # closed the Journal, there is no open trade here and
            # nothing is done. This fallback only closes a Journal
            # trade that remains open after a CLOSED lifecycle result.

            journal = getattr(
                self.trade_lifecycle_service,
                "trade_journal_v2",
                None,
            )

            if journal is not None:
                get_open_trades = getattr(
                    journal,
                    "get_open_trades",
                    None,
                )

                close_trade = getattr(
                    journal,
                    "close_trade",
                    None,
                )

                if (
                    callable(get_open_trades)
                    and callable(close_trade)
                ):
                    open_trades = (
                        get_open_trades()
                    )

                    matching_journal_trade = None

                    for journal_trade in (
                        open_trades or []
                    ):
                        if (
                            str(
                                getattr(
                                    journal_trade,
                                    "trade_id",
                                    "",
                                )
                            )
                            == (
                                "journal-"
                                + str(
                                    result_position[
                                        "position_id"
                                    ]
                                )
                            )
                            or str(
                                getattr(
                                    journal_trade,
                                    "trade_id",
                                    "",
                                )
                            )
                        ):
                            matching_journal_trade = (
                                journal_trade
                            )
                            break

                    if matching_journal_trade is not None:
                        fallback_point_value = (
                            result_position.get(
                                "point_value"
                            )
                            or position_for_update.get(
                                "point_value"
                            )
                            or self._resolve_point_value(
                                symbol=normalized_symbol
                            )
                        )

                        fallback_pnl = float(
                            result_position.get(
                                "realized_pnl",
                                result_position.get(
                                    "total_pnl",
                                    0.0,
                                ),
                            )
                            or 0.0
                        )

                        fallback_exit_price = float(
                            result_position.get(
                                "exit_price",
                                normalized_current_price,
                            )
                            or normalized_current_price
                        )

                        fallback_reason = str(
                            result_position.get(
                                "close_reason",
                                "CLOSED",
                            )
                        )

                        close_trade(
                            trade_id=str(
                                getattr(
                                    matching_journal_trade,
                                    "trade_id",
                                )
                            ),
                            result=fallback_reason,
                            pnl=fallback_pnl,
                            exit_price=fallback_exit_price,
                            exit_reason=fallback_reason,
                            point_value=float(
                                fallback_point_value
                            ),
                        )

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

                # V40: TradeLifecycleServiceV2 normally owns
                # Portfolio close synchronization. Keep this
                # defensive fallback for monitor configurations
                # whose lifecycle does not own the shared
                # Portfolio. Only close when the position is
                # still present in the Portfolio open set.
                if self.portfolio_manager_v2 is not None:
                    normalized_position_id = str(
                        result_position["position_id"]
                    )

                    portfolio_position_is_open = any(
                        str(
                            portfolio_position.get(
                                "position_id",
                                "",
                            )
                        )
                        == normalized_position_id
                        for portfolio_position in (
                            self.portfolio_manager_v2
                            .get_open_positions()
                        )
                    )

                    if portfolio_position_is_open:
                        self.portfolio_manager_v2.close_position(
                            position_id=normalized_position_id,
                            exit_price=float(
                                result_position.get(
                                    "exit_price",
                                    normalized_current_price,
                                )
                                or normalized_current_price
                            ),
                            realized_pnl=float(
                                result_position.get(
                                    "realized_pnl",
                                    result_position.get(
                                        "total_pnl",
                                        0.0,
                                    ),
                                )
                                or 0.0
                            ),
                        )

                # Continue with downstream learning/telemetry.
                if (
                    self.trade_learning_service_v2
                    is not None
                ):

                    self.trade_learning_service_v2.process_closed_trade(

                        trade_id=str(
                            getattr(
                                matching_journal_trade,
                                "trade_id",
                                "",
                            )
                        ),

                        symbol=str(
                            getattr(
                                matching_journal_trade,
                                "symbol",
                                normalized_symbol,
                            )
                        ),

                        direction=str(
                            getattr(
                                matching_journal_trade,
                                "direction",
                                result_position.get(
                                    "direction",
                                    "UNKNOWN",
                                ),
                            )
                        ),

                        strategy=(
                            "ARMS AI Decision Engine"
                        ),

                        entry=float(
                            getattr(
                                matching_journal_trade,
                                "entry",
                                result_position.get(
                                    "entry_price",
                                    0.0,
                                ),
                            )
                        ),

                        exit_price=float(
                            result_position.get(
                                "exit_price",
                                normalized_current_price,
                            )
                            or normalized_current_price
                        ),

                        contracts=int(
                            getattr(
                                matching_journal_trade,
                                "contracts",
                                result_position.get(
                                    "quantity",
                                    0,
                                ),
                            )
                        ),

                        real_pnl=float(
                            getattr(
                                matching_journal_trade,
                                "pnl",
                                result_position.get(
                                    "realized_pnl",
                                    0.0,
                                ),
                            )
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
