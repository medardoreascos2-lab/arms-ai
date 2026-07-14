from collections.abc import Iterable
from typing import Any


class ArmsPipeline:
    """
    Orquestador simple de etapas para ARMS AI.

    Cada etapa debe implementar:
        run(context: dict[str, Any]) -> dict[str, Any]
    """

    def __init__(
        self,
        stages: Iterable[Any] | None = None,
    ) -> None:
        self.stages = list(stages or [])

    def add_stage(self, stage: Any) -> None:
        self.stages.append(stage)

    def run(
        self,
        initial_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(initial_context or {})

        for stage in self.stages:
            result = stage.run(context)

            if result is None:
                raise RuntimeError(
                    f"La etapa {stage.__class__.__name__} "
                    "devolvió None."
                )

            if not isinstance(result, dict):
                raise TypeError(
                    f"La etapa {stage.__class__.__name__} "
                    "debe devolver un diccionario."
                )

            context = result

        return context
