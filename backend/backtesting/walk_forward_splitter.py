from dataclasses import dataclass


@dataclass(frozen=True)
class WalkForwardWindow:
    training_start: int
    training_end: int
    testing_start: int
    testing_end: int


class WalkForwardSplitter:
    """
    Construye ventanas rolling de entrenamiento y prueba.

    Los índices finales siguen la convención de slicing de Python:
    el valor de *_end no se incluye.
    """

    def __init__(
        self,
        training_size: int,
        testing_size: int,
        step_size: int,
    ) -> None:
        if training_size <= 0:
            raise ValueError(
                "training_size debe ser mayor que cero."
            )

        if testing_size <= 0:
            raise ValueError(
                "testing_size debe ser mayor que cero."
            )

        if step_size <= 0:
            raise ValueError(
                "step_size debe ser mayor que cero."
            )

        self.training_size = training_size
        self.testing_size = testing_size
        self.step_size = step_size

    def split(
        self,
        total_items: int,
    ) -> list[WalkForwardWindow]:
        if total_items < 0:
            raise ValueError(
                "total_items no puede ser negativo."
            )

        minimum_required = (
            self.training_size
            + self.testing_size
        )

        if total_items < minimum_required:
            return []

        windows: list[WalkForwardWindow] = []
        training_start = 0

        while True:
            training_end = (
                training_start
                + self.training_size
            )
            testing_start = training_end
            testing_end = (
                testing_start
                + self.testing_size
            )

            if testing_end > total_items:
                break

            windows.append(
                WalkForwardWindow(
                    training_start=training_start,
                    training_end=training_end,
                    testing_start=testing_start,
                    testing_end=testing_end,
                )
            )

            training_start += self.step_size

        return windows
