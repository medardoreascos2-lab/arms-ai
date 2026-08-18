from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
)


@dataclass(slots=True)
class BacktestBatchItemV2:
    """
    Define un pipeline individual dentro de un batch.
    """

    name: str
    pipeline: Any
    candles: list[Any] | None = None
    json_filename: str = "backtest.json"
    html_filename: str = "backtest.html"

    def __post_init__(self) -> None:

        normalized_name = str(
            self.name
        ).strip()

        if not normalized_name:
            raise ValueError(
                "name no puede estar vacío."
            )

        if not callable(
            getattr(
                self.pipeline,
                "run",
                None,
            )
        ):
            raise TypeError(
                "pipeline debe implementar run()."
            )

        normalized_json_filename = str(
            self.json_filename
        ).strip()

        normalized_html_filename = str(
            self.html_filename
        ).strip()

        if not normalized_json_filename:
            raise ValueError(
                "json_filename no puede estar vacío."
            )

        if not normalized_html_filename:
            raise ValueError(
                "html_filename no puede estar vacío."
            )

        self.name = normalized_name
        self.json_filename = (
            normalized_json_filename
        )
        self.html_filename = (
            normalized_html_filename
        )


@dataclass(slots=True)
class BacktestBatchResultV2:
    """
    Resultado consolidado de ejecutar múltiples pipelines.
    """

    total_runs: int
    successful_runs: int
    failed_runs: int

    results: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )

    errors: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )

    total_candles_processed: int = 0
    total_trades: int = 0
    total_net_pnl: float = 0.0

    def __post_init__(self) -> None:

        self.total_runs = int(
            self.total_runs
        )

        self.successful_runs = int(
            self.successful_runs
        )

        self.failed_runs = int(
            self.failed_runs
        )

        self.total_candles_processed = int(
            self.total_candles_processed
        )

        self.total_trades = int(
            self.total_trades
        )

        self.total_net_pnl = float(
            self.total_net_pnl
        )

        numeric_values = (
            self.total_runs,
            self.successful_runs,
            self.failed_runs,
            self.total_candles_processed,
            self.total_trades,
        )

        if any(
            value < 0
            for value in numeric_values
        ):
            raise ValueError(
                "Los totales no pueden ser negativos."
            )

        if (
            self.successful_runs
            + self.failed_runs
            != self.total_runs
        ):
            raise ValueError(
                "successful_runs y failed_runs "
                "deben coincidir con total_runs."
            )


class BacktestBatchRunnerV2:
    """
    Ejecuta varios BacktestPipelineV2 de forma secuencial.
    """

    def __init__(
        self,
        *,
        continue_on_error: bool = True,
    ) -> None:

        if not isinstance(
            continue_on_error,
            bool,
        ):
            raise TypeError(
                "continue_on_error debe ser bool."
            )

        self.continue_on_error = (
            continue_on_error
        )

    def run(
        self,
        *,
        items,
        output_directory,
    ) -> BacktestBatchResultV2:

        normalized_items = list(
            items
        )

        if not normalized_items:
            raise ValueError(
                "items no puede estar vacío."
            )

        for item in normalized_items:
            if not isinstance(
                item,
                BacktestBatchItemV2,
            ):
                raise TypeError(
                    "Cada elemento de items debe ser "
                    "BacktestBatchItemV2."
                )

        normalized_output_directory = Path(
            output_directory
        )

        results: list[
            dict[str, Any]
        ] = []

        errors: list[
            dict[str, Any]
        ] = []

        total_candles_processed = 0
        total_trades = 0
        total_net_pnl = 0.0

        for item in normalized_items:

            item_output_directory = (
                normalized_output_directory
                / item.name
            )

            try:
                pipeline_kwargs = {
                    "output_directory": (
                        item_output_directory
                    ),
                    "json_filename": (
                        item.json_filename
                    ),
                    "html_filename": (
                        item.html_filename
                    ),
                }

                if item.candles is not None:
                    pipeline_kwargs[
                        "candles"
                    ] = item.candles


                pipeline_result = (
                    item.pipeline.run(
                        **pipeline_kwargs
                    )
                )

                if not isinstance(
                    pipeline_result,
                    BacktestPipelineResultV2,
                ):
                    raise TypeError(
                        "pipeline.run() debe devolver "
                        "BacktestPipelineResultV2."
                    )

                results.append(
                    {
                        "name": item.name,
                        "success": True,
                        "pipeline_result": (
                            pipeline_result
                        ),
                    }
                )

                total_candles_processed += (
                    pipeline_result
                    .candles_processed
                )

                performance_metrics = (
                    pipeline_result
                    .report
                    .performance_metrics
                )

                total_trades += int(
                    performance_metrics.get(
                        "total_trades",
                        len(
                            pipeline_result
                            .report
                            .trade_history
                        ),
                    )
                )

                total_net_pnl += float(
                    performance_metrics.get(
                        "net_pnl",
                        0.0,
                    )
                )

            except Exception as exc:

                if not self.continue_on_error:
                    raise

                errors.append(
                    {
                        "name": item.name,
                        "success": False,
                        "error_type": (
                            type(exc).__name__
                        ),
                        "message": str(exc),
                    }
                )

        return BacktestBatchResultV2(
            total_runs=len(
                normalized_items
            ),
            successful_runs=len(
                results
            ),
            failed_runs=len(
                errors
            ),
            results=results,
            errors=errors,
            total_candles_processed=(
                total_candles_processed
            ),
            total_trades=total_trades,
            total_net_pnl=total_net_pnl,
        )
