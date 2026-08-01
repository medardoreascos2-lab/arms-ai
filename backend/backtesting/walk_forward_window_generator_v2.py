from __future__ import annotations


class WalkForwardWindowGeneratorV2:
    """
    Genera ventanas rolling de entrenamiento y prueba
    para validación walk-forward.
    """

    def __init__(
        self,
        *,
        training_size: int,
        testing_size: int,
        step_size: int,
    ) -> None:

        for name, value in (
            ("training_size", training_size),
            ("testing_size", testing_size),
            ("step_size", step_size),
        ):
            if not isinstance(
                value,
                int,
            ):
                raise TypeError(
                    f"{name} debe ser int."
                )

            if value <= 0:
                raise ValueError(
                    f"{name} debe ser mayor que cero."
                )

        self.training_size = training_size
        self.testing_size = testing_size
        self.step_size = step_size

    def generate(
        self,
        *,
        total_items: int,
    ) -> list[dict[str, int]]:

        if not isinstance(
            total_items,
            int,
        ):
            raise TypeError(
                "total_items debe ser int."
            )

        if total_items < 0:
            raise ValueError(
                "total_items no puede ser negativo."
            )

        required_items = (
            self.training_size
            + self.testing_size
        )

        if total_items < required_items:
            return []

        windows: list[
            dict[str, int]
        ] = []

        window_index = 0
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
                {
                    "window_index": window_index,
                    "training_start": training_start,
                    "training_end": training_end,
                    "testing_start": testing_start,
                    "testing_end": testing_end,
                }
            )

            window_index += 1

            training_start += (
                self.step_size
            )

        return windows
