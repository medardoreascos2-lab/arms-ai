from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WalkForwardOptimizationResultV2:
    """
    Consolida los resultados de múltiples ventanas
    de optimización walk-forward.
    """

    window_results: list[
        dict[str, Any]
    ] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:

        if isinstance(
            self.window_results,
            (
                str,
                bytes,
                dict,
            ),
        ):
            raise TypeError(
                "window_results debe ser una colección."
            )

        try:
            normalized_results = list(
                self.window_results
            )
        except TypeError as exc:
            raise TypeError(
                "window_results debe ser una colección."
            ) from exc

        validated_results: list[
            dict[str, Any]
        ] = []

        for window_result in normalized_results:
            if not isinstance(
                window_result,
                dict,
            ):
                raise TypeError(
                    "Cada window debe ser un dict."
                )

            validated_results.append(
                deepcopy(
                    window_result
                )
            )

        self.window_results = (
            validated_results
        )

    @property
    def total_windows(
        self,
    ) -> int:

        return len(
            self.window_results
        )

    @property
    def successful_window_results(
        self,
    ) -> list[dict[str, Any]]:

        return [
            deepcopy(
                window_result
            )
            for window_result
            in self.window_results
            if window_result.get(
                "success",
                True,
            )
            is True
        ]

    @property
    def failed_window_results(
        self,
    ) -> list[dict[str, Any]]:

        return [
            deepcopy(
                window_result
            )
            for window_result
            in self.window_results
            if window_result.get(
                "success",
                True,
            )
            is False
        ]

    @property
    def successful_windows(
        self,
    ) -> int:

        return len(
            self.successful_window_results
        )

    @property
    def failed_windows(
        self,
    ) -> int:

        return len(
            self.failed_window_results
        )

    def _average_metric(
        self,
        metric_name: str,
    ) -> float:

        successful_results = (
            self.successful_window_results
        )

        if not successful_results:
            return 0.0

        values: list[float] = []

        for result in successful_results:
            value = result.get(
                metric_name
            )

            if value is None:
                continue

            try:
                values.append(
                    float(
                        value
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    f"{metric_name} debe ser numérico."
                ) from exc

        if not values:
            return 0.0

        return sum(
            values
        ) / len(
            values
        )

    @property
    def average_training_score(
        self,
    ) -> float:

        return self._average_metric(
            "training_score"
        )

    @property
    def average_testing_score(
        self,
    ) -> float:

        return self._average_metric(
            "testing_score"
        )

    @property
    def average_testing_net_pnl(
        self,
    ) -> float:

        return self._average_metric(
            "testing_net_pnl"
        )

    @property
    def average_testing_win_rate(
        self,
    ) -> float:

        return self._average_metric(
            "testing_win_rate"
        )

    @property
    def average_testing_maximum_drawdown(
        self,
    ) -> float:

        return self._average_metric(
            "testing_maximum_drawdown"
        )

    def best_window(
        self,
    ) -> dict[str, Any]:

        successful_results = (
            self.successful_window_results
        )

        if not successful_results:
            raise ValueError(
                "No hay ventanas exitosas."
            )

        return deepcopy(
            max(
                successful_results,
                key=lambda result: float(
                    result.get(
                        "testing_score",
                        0.0,
                    )
                ),
            )
        )

    def worst_window(
        self,
    ) -> dict[str, Any]:

        successful_results = (
            self.successful_window_results
        )

        if not successful_results:
            raise ValueError(
                "No hay ventanas exitosas."
            )

        return deepcopy(
            min(
                successful_results,
                key=lambda result: float(
                    result.get(
                        "testing_score",
                        0.0,
                    )
                ),
            )
        )

    def most_frequent_parameters(
        self,
    ) -> dict[str, Any]:

        successful_results = (
            self.successful_window_results
        )

        parameter_sets: list[
            dict[str, Any]
        ] = []

        for result in successful_results:
            parameters = result.get(
                "best_parameters"
            )

            if not isinstance(
                parameters,
                dict,
            ):
                continue

            parameter_sets.append(
                deepcopy(
                    parameters
                )
            )

        if not parameter_sets:
            return {}

        signatures = [
            tuple(
                sorted(
                    parameters.items(),
                    key=lambda item: str(
                        item[0]
                    ),
                )
            )
            for parameters
            in parameter_sets
        ]

        most_common_signature, _ = Counter(
            signatures
        ).most_common(
            1
        )[0]

        return {
            key: value
            for key, value
            in most_common_signature
        }

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "total_windows": (
                self.total_windows
            ),
            "successful_windows": (
                self.successful_windows
            ),
            "failed_windows": (
                self.failed_windows
            ),
            "average_training_score": (
                self.average_training_score
            ),
            "average_testing_score": (
                self.average_testing_score
            ),
            "average_testing_net_pnl": (
                self.average_testing_net_pnl
            ),
            "average_testing_win_rate": (
                self.average_testing_win_rate
            ),
            "average_testing_maximum_drawdown": (
                self.average_testing_maximum_drawdown
            ),
            "most_frequent_parameters": (
                self.most_frequent_parameters()
            ),
            "best_window": (
                self.best_window()
                if self.successful_windows
                else None
            ),
            "worst_window": (
                self.worst_window()
                if self.successful_windows
                else None
            ),
            "window_results": deepcopy(
                self.window_results
            ),
        }
