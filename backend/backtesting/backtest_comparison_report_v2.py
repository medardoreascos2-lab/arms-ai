from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchResultV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)


@dataclass(slots=True)
class BacktestComparisonReportV2:
    """
    Reporte comparativo construido a partir de un batch
    de backtests ejecutados correctamente.
    """

    strategies: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )

    ALLOWED_METRICS = {
        "net_pnl",
        "win_rate",
        "profit_factor",
        "maximum_drawdown",
        "expectancy",
        "total_trades",
    }

    LOWER_IS_BETTER = {
        "maximum_drawdown",
    }

    def __post_init__(self) -> None:

        normalized_strategies: list[
            dict[str, Any]
        ] = []

        for strategy in self.strategies:
            if not isinstance(
                strategy,
                dict,
            ):
                raise TypeError(
                    "Cada estrategia debe ser un dict."
                )

            normalized_strategies.append(
                deepcopy(strategy)
            )

        self.strategies = (
            normalized_strategies
        )

    @property
    def total_strategies(
        self,
    ) -> int:

        return len(
            self.strategies
        )

    @classmethod
    def from_batch_result(
        cls,
        batch_result: BacktestBatchResultV2,
    ) -> BacktestComparisonReportV2:

        if not isinstance(
            batch_result,
            BacktestBatchResultV2,
        ):
            raise TypeError(
                "batch_result debe ser "
                "BacktestBatchResultV2."
            )

        strategies: list[
            dict[str, Any]
        ] = []

        for item in batch_result.results:

            if not isinstance(
                item,
                dict,
            ):
                raise TypeError(
                    "Cada resultado del batch debe ser un dict."
                )

            pipeline_result = item.get(
                "pipeline_result"
            )

            if not isinstance(
                pipeline_result,
                BacktestPipelineResultV2,
            ):
                raise TypeError(
                    "pipeline_result debe ser "
                    "BacktestPipelineResultV2."
                )

            metrics = (
                pipeline_result
                .report
                .performance_metrics
            )

            strategies.append(
                {
                    "name": str(
                        item.get(
                            "name",
                            "",
                        )
                    ).strip(),
                    "candles_processed": (
                        pipeline_result
                        .candles_processed
                    ),
                    "total_trades": int(
                        metrics.get(
                            "total_trades",
                            len(
                                pipeline_result
                                .report
                                .trade_history
                            ),
                        )
                    ),
                    "net_pnl": float(
                        metrics.get(
                            "net_pnl",
                            0.0,
                        )
                    ),
                    "win_rate": float(
                        metrics.get(
                            "win_rate",
                            0.0,
                        )
                    ),
                    "profit_factor": (
                        cls._normalize_optional_float(
                            metrics.get(
                                "profit_factor"
                            )
                        )
                    ),
                    "maximum_drawdown": float(
                        metrics.get(
                            "maximum_drawdown",
                            0.0,
                        )
                    ),
                    "expectancy": float(
                        metrics.get(
                            "expectancy",
                            0.0,
                        )
                    ),
                    "json_path": str(
                        pipeline_result
                        .json_path
                    ),
                    "html_path": str(
                        pipeline_result
                        .html_path
                    ),
                }
            )

        return cls(
            strategies=strategies
        )

    @staticmethod
    def _normalize_optional_float(
        value,
    ) -> float | None:

        if value is None:
            return None

        return float(
            value
        )

    @classmethod
    def _validate_metric(
        cls,
        metric: str,
    ) -> str:

        normalized_metric = str(
            metric
        ).strip()

        if (
            normalized_metric
            not in cls.ALLOWED_METRICS
        ):
            raise ValueError(
                "Métrica de comparación inválida."
            )

        return normalized_metric

    def rank_by(
        self,
        metric: str,
    ) -> list[dict[str, Any]]:

        normalized_metric = (
            self._validate_metric(
                metric
            )
        )

        reverse = (
            normalized_metric
            not in self.LOWER_IS_BETTER
        )

        def metric_value(
            strategy: dict[str, Any],
        ) -> float:

            value = strategy.get(
                normalized_metric
            )

            if value is None:
                return (
                    float("-inf")
                    if reverse
                    else float("inf")
                )

            return float(
                value
            )

        return deepcopy(
            sorted(
                self.strategies,
                key=metric_value,
                reverse=reverse,
            )
        )

    def best_by(
        self,
        metric: str,
    ) -> dict[str, Any]:

        ranking = self.rank_by(
            metric
        )

        if not ranking:
            raise ValueError(
                "No hay estrategias para comparar."
            )

        return ranking[0]

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "total_strategies": (
                self.total_strategies
            ),
            "strategies": deepcopy(
                self.strategies
            ),
        }
