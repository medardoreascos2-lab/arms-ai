from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BacktestReportV2:
    """
    Resultado consolidado de una sesión de backtesting.
    """

    candles_processed: int

    decisions: list[Any] = field(
        default_factory=list
    )

    trade_plans: list[Any] = field(
        default_factory=list
    )

    signals: list[Any] = field(
        default_factory=list
    )

    submission_results: list[Any] = field(
        default_factory=list
    )

    position_updates: list[Any] = field(
        default_factory=list
    )

    trade_history: list[Any] = field(
        default_factory=list
    )

    performance_metrics: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    active_positions: list[Any] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:

        normalized_candles_processed = int(
            self.candles_processed
        )

        if normalized_candles_processed < 0:
            raise ValueError(
                "candles_processed no puede ser negativo."
            )

        self.candles_processed = (
            normalized_candles_processed
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Devuelve una representación completa y segura
        del reporte para APIs, JSON y dashboards.
        """

        return {
            "summary": self.summary(),
            "candles_processed": (
                self.candles_processed
            ),
            "decisions": deepcopy(
                self.decisions
            ),
            "trade_plans": deepcopy(
                self.trade_plans
            ),
            "signals": deepcopy(
                self.signals
            ),
            "submission_results": deepcopy(
                self.submission_results
            ),
            "position_updates": deepcopy(
                self.position_updates
            ),
            "trade_history": deepcopy(
                self.trade_history
            ),
            "performance_metrics": deepcopy(
                self.performance_metrics
            ),
            "active_positions": deepcopy(
                self.active_positions
            ),
        }

    def summary(
        self,
    ) -> dict[str, int]:
        """
        Devuelve un resumen numérico del backtest.
        """

        return {
            "candles_processed": self.candles_processed,
            "decisions": len(
                self.decisions
            ),
            "trade_plans": len(
                self.trade_plans
            ),
            "signals": len(
                self.signals
            ),
            "submissions": len(
                self.submission_results
            ),
            "position_updates": len(
                self.position_updates
            ),
            "closed_trades": len(
                self.trade_history
            ),
            "active_positions": len(
                self.active_positions
            ),
        }
