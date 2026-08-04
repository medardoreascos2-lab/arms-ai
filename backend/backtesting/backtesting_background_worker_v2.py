from __future__ import annotations

from threading import RLock


class BacktestingBackgroundWorkerV2:
    """
    Servicio base para procesar trabajos de backtesting.

    En esta versión ejecuta iteraciones controladas
    mediante run_once(). La ejecución continua se añadirá
    después con start() y stop().
    """

    def __init__(
        self,
        *,
        worker,
    ) -> None:

        if not callable(
            getattr(
                worker,
                "process_next",
                None,
            )
        ):
            raise TypeError(
                "worker debe implementar process_next()."
            )

        self.worker = worker

        self._iterations = 0
        self._last_result = None
        self._last_error = None

        self._lock = RLock()

    def run_once(
        self,
        *,
        candles,
        output_directory,
    ):

        try:
            result = self.worker.process_next(
                candles=candles,
                output_directory=output_directory,
            )

            with self._lock:
                self._iterations += 1
                self._last_result = result
                self._last_error = None

            return result

        except Exception as exc:

            with self._lock:
                self._iterations += 1
                self._last_result = None
                self._last_error = exc

            raise

    @property
    def iterations(
        self,
    ) -> int:

        with self._lock:
            return self._iterations

    @property
    def last_result(
        self,
    ):

        with self._lock:
            return self._last_result

    @property
    def last_error(
        self,
    ):

        with self._lock:
            return self._last_error
