from __future__ import annotations

from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobV2,
)


class BacktestingJobTaskV2:
    """
    Contenedor de ejecución para un job de backtesting.

    Mantiene unidos el job, sus candles y el
    directorio de salida correspondiente.
    """

    def __init__(
        self,
        *,
        job: BacktestingJobV2,
        candles,
        output_directory: str,
    ) -> None:

        if not isinstance(
            job,
            BacktestingJobV2,
        ):
            raise TypeError(
                "job debe ser BacktestingJobV2."
            )

        try:
            normalized_candles = list(
                candles
            )
        except TypeError as exc:
            raise TypeError(
                "candles debe ser iterable."
            ) from exc

        if not normalized_candles:
            raise ValueError(
                "candles no puede estar vacío."
            )

        normalized_output_directory = str(
            output_directory
        ).strip()

        if not normalized_output_directory:
            raise ValueError(
                "output_directory no puede estar vacío."
            )

        self.job = job
        self.candles = normalized_candles
        self.output_directory = (
            normalized_output_directory
        )

    @property
    def candle_count(
        self,
    ) -> int:

        return len(
            self.candles
        )

    def to_dict(
        self,
    ) -> dict:

        return {
            "job_id": self.job.job_id,
            "candle_count": self.candle_count,
            "output_directory": (
                self.output_directory
            ),
        }
