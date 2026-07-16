from typing import Any


class WalkForwardParameterSelector:
    """
    Selecciona el mejor candidato según una métrica.

    Por defecto maximiza la métrica. Para métricas como
    max_drawdown puede configurarse maximize=False.
    """

    def __init__(
        self,
        metric: str,
        maximize: bool = True,
    ) -> None:
        if not metric.strip():
            raise ValueError(
                "metric no puede estar vacío."
            )

        self.metric = metric
        self.maximize = maximize

    def select(
        self,
        candidates: list[Any],
    ) -> Any:
        if not candidates:
            raise ValueError(
                "candidates no puede estar vacío."
            )

        for candidate in candidates:
            if not hasattr(candidate, self.metric):
                raise ValueError(
                    f"El candidato no contiene "
                    f"la métrica '{self.metric}'."
                )

        selected = candidates[0]
        selected_value = getattr(
            selected,
            self.metric,
        )

        for candidate in candidates[1:]:
            candidate_value = getattr(
                candidate,
                self.metric,
            )

            is_better = (
                candidate_value > selected_value
                if self.maximize
                else candidate_value < selected_value
            )

            if is_better:
                selected = candidate
                selected_value = candidate_value

        return selected
