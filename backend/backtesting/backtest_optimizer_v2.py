from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchItemV2,
)


@dataclass(slots=True)
class BacktestOptimizationCandidateV2:
    """
    Define una configuración candidata para optimización.
    """

    name: str
    pipeline: Any
    json_filename: str = "backtest.json"
    html_filename: str = "backtest.html"
    parameters: dict[str, Any] = field(
        default_factory=dict
    )

    candles: list[Any] | None = None

    def __post_init__(self) -> None:

        normalized_name = str(
            self.name
        ).strip()

        if not normalized_name:
            raise ValueError(
                "name no puede estar vacío."
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

        if not isinstance(
            self.parameters,
            dict,
        ):
            raise TypeError(
                "parameters debe ser un dict."
            )

        self.name = normalized_name
        self.json_filename = (
            normalized_json_filename
        )
        self.html_filename = (
            normalized_html_filename
        )
        self.parameters = deepcopy(
            self.parameters
        )

    def to_batch_item(
        self,
    ) -> BacktestBatchItemV2:

        return BacktestBatchItemV2(
            name=self.name,
            pipeline=self.pipeline,
            candles=self.candles,
            json_filename=self.json_filename,
            html_filename=self.html_filename,
        )


@dataclass(slots=True)
class BacktestOptimizationResultV2:
    """
    Resultado consolidado de una optimización.
    """

    ranking: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )

    batch_result: Any = None

    def __post_init__(self) -> None:

        normalized_ranking: list[
            dict[str, Any]
        ] = []

        for row in self.ranking:
            if not isinstance(
                row,
                dict,
            ):
                raise TypeError(
                    "Cada fila del ranking debe ser un dict."
                )

            normalized_ranking.append(
                deepcopy(row)
            )

        self.ranking = normalized_ranking

    def best_strategy(
        self,
    ) -> dict[str, Any]:

        if not self.ranking:
            raise ValueError(
                "No hay estrategias en el ranking."
            )

        return deepcopy(
            self.ranking[0]
        )

    def top(
        self,
        limit: int,
    ) -> list[dict[str, Any]]:

        if not isinstance(
            limit,
            int,
        ):
            raise TypeError(
                "limit debe ser int."
            )

        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        return deepcopy(
            self.ranking[:limit]
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "total_candidates": len(
                self.ranking
            ),
            "ranking": deepcopy(
                self.ranking
            ),
            "best_strategy": (
                self.best_strategy()
                if self.ranking
                else None
            ),
        }


class BacktestOptimizerV2:
    """
    Ejecuta candidatos mediante batch y los ordena
    con un reporte comparativo y un scorer compuesto.
    """

    def __init__(
        self,
        *,
        batch_runner,
        comparison_report_factory: Callable,
        scorer,
    ) -> None:

        if not callable(
            getattr(
                batch_runner,
                "run",
                None,
            )
        ):
            raise TypeError(
                "batch_runner debe implementar run()."
            )

        if not callable(
            comparison_report_factory
        ):
            raise TypeError(
                "comparison_report_factory debe ser callable."
            )

        self.batch_runner = batch_runner
        self.comparison_report_factory = (
            comparison_report_factory
        )
        self.scorer = scorer

    def optimize(
        self,
        *,
        candidates,
        output_directory,
        candles=None,
    ) -> BacktestOptimizationResultV2:

        normalized_candidates = list(
            candidates
        )

        if not normalized_candidates:
            raise ValueError(
                "candidates no puede estar vacío."
            )

        for candidate in normalized_candidates:
            if not isinstance(
                candidate,
                BacktestOptimizationCandidateV2,
            ):
                raise TypeError(
                    "Cada candidate debe ser "
                    "BacktestOptimizationCandidateV2."
                )

        batch_items = [
            candidate.to_batch_item()
            for candidate in normalized_candidates
        ]

        if candles is not None:
            for item in batch_items:
                item.candles = candles

        batch_result = self.batch_runner.run(
            items=batch_items,
            output_directory=Path(
                output_directory
            ),
        )

        comparison_report = (
            self.comparison_report_factory(
                batch_result
            )
        )

        rank_by_score = getattr(
            comparison_report,
            "rank_by_score",
            None,
        )

        if not callable(
            rank_by_score
        ):
            raise TypeError(
                "comparison_report debe implementar "
                "rank_by_score()."
            )

        ranking = rank_by_score(
            self.scorer
        )

        if not isinstance(
            ranking,
            list,
        ):
            raise TypeError(
                "rank_by_score() debe devolver una lista."
            )

        parameters_by_name = {
            candidate.name: deepcopy(
                candidate.parameters
            )
            for candidate in normalized_candidates
        }

        enriched_ranking: list[
            dict[str, Any]
        ] = []

        for row in ranking:
            if not isinstance(
                row,
                dict,
            ):
                raise TypeError(
                    "Cada fila del ranking debe ser un dict."
                )

            enriched_row = deepcopy(
                row
            )

            name = str(
                enriched_row.get(
                    "name",
                    "",
                )
            ).strip()

            enriched_row["parameters"] = (
                deepcopy(
                    parameters_by_name.get(
                        name,
                        {},
                    )
                )
            )

            enriched_ranking.append(
                enriched_row
            )

        return BacktestOptimizationResultV2(
            ranking=enriched_ranking,
            batch_result=batch_result,
        )
