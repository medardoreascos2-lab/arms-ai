from __future__ import annotations

from copy import deepcopy
from typing import Any


class WalkForwardDatasetSplitterV2:
    """
    Divide una colección usando ventanas walk-forward
    previamente generadas y validadas.
    """

    def __init__(
        self,
        *,
        warmup_size: int = 0,
    ) -> None:

        if warmup_size < 0:
            raise ValueError(
                "warmup_size no puede ser negativo."
            )

        self.warmup_size = int(
            warmup_size
        )

    REQUIRED_WINDOW_KEYS = (
        "window_index",
        "training_start",
        "training_end",
        "testing_start",
        "testing_end",
    )

    def split(
        self,
        *,
        items,
        windows,
    ) -> list[dict[str, Any]]:

        normalized_items = self._normalize_collection(
            value=items,
            field_name="items",
        )

        normalized_windows = self._normalize_collection(
            value=windows,
            field_name="windows",
        )

        if not normalized_windows:
            return []

        total_items = len(
            normalized_items
        )

        datasets: list[
            dict[str, Any]
        ] = []

        for raw_window in normalized_windows:

            if not isinstance(
                raw_window,
                dict,
            ):
                raise TypeError(
                    "Cada window debe ser un dict."
                )

            for key in self.REQUIRED_WINDOW_KEYS:
                if key not in raw_window:
                    raise ValueError(
                        f"Falta la clave requerida: {key}."
                    )

            window = {
                key: self._normalize_integer(
                    raw_window[key],
                    field_name=key,
                )
                for key in self.REQUIRED_WINDOW_KEYS
            }

            self._validate_boundaries(
                window=window,
                total_items=total_items,
            )

            training_items = deepcopy(
                normalized_items[
                    window["training_start"]:
                    window["training_end"]
                ]
            )

            testing_start = max(
                0,
                window["testing_start"]
                - self.warmup_size,
            )

            testing_items = deepcopy(
                normalized_items[
                    testing_start:
                    window["testing_end"]
                ]
            )

            datasets.append(
                {
                    "window_index": (
                        window["window_index"]
                    ),
                    "training_start": (
                        window["training_start"]
                    ),
                    "training_end": (
                        window["training_end"]
                    ),
                    "testing_start": (
                        window["testing_start"]
                    ),
                    "testing_end": (
                        window["testing_end"]
                    ),
                    "training_items": training_items,
                    "testing_items": testing_items,
                }
            )

        return datasets

    @staticmethod
    def _normalize_collection(
        *,
        value,
        field_name: str,
    ) -> list[Any]:

        if isinstance(
            value,
            (
                str,
                bytes,
                dict,
            ),
        ):
            raise TypeError(
                f"{field_name} debe ser una colección."
            )

        try:
            return list(
                value
            )
        except TypeError as exc:
            raise TypeError(
                f"{field_name} debe ser una colección."
            ) from exc

    @staticmethod
    def _normalize_integer(
        value,
        *,
        field_name: str,
    ) -> int:

        if not isinstance(
            value,
            int,
        ):
            raise TypeError(
                f"{field_name} debe ser int."
            )

        return value

    @staticmethod
    def _validate_boundaries(
        *,
        window: dict[str, int],
        total_items: int,
    ) -> None:

        window_index = window[
            "window_index"
        ]

        training_start = window[
            "training_start"
        ]

        training_end = window[
            "training_end"
        ]

        testing_start = window[
            "testing_start"
        ]

        testing_end = window[
            "testing_end"
        ]

        if window_index < 0:
            raise ValueError(
                "window_index no puede ser negativo."
            )

        if (
            training_start < 0
            or training_end < 0
            or testing_start < 0
            or testing_end < 0
        ):
            raise ValueError(
                "Los límites deben ser no negativos."
            )

        if (
            training_start >= training_end
            or testing_start >= testing_end
            or training_end > testing_start
        ):
            raise ValueError(
                "Los límites de la ventana son inválidos."
            )

        if (
            training_end > total_items
            or testing_end > total_items
        ):
            raise ValueError(
                "Los límites están fuera del rango "
                "del dataset."
            )
