from __future__ import annotations

from threading import (
    Event,
    RLock,
    Thread,
)


class BacktestingBackgroundWorkerV2:
    """
    Procesa continuamente tareas de backtesting
    mediante un hilo dedicado y controlado.
    """

    def __init__(
        self,
        *,
        worker,
        poll_interval: float = 0.25,
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

        normalized_poll_interval = float(
            poll_interval
        )

        if normalized_poll_interval <= 0.0:
            raise ValueError(
                "poll_interval debe ser mayor que cero."
            )

        self.worker = worker
        self.poll_interval = (
            normalized_poll_interval
        )

        self._iterations = 0
        self._last_result = None
        self._last_error = None

        self._stop_event = Event()
        self._thread: Thread | None = None

        self._lock = RLock()

    def run_once(
        self,
    ):

        try:
            result = self.worker.process_next()

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

    def _run_loop(
        self,
    ) -> None:

        while not self._stop_event.is_set():

            try:
                result = self.run_once()

            except Exception:
                result = None

            if (
                result is None
                and not self._stop_event.is_set()
            ):
                self._stop_event.wait(
                    self.poll_interval
                )

    def start(
        self,
    ) -> Thread:

        with self._lock:

            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return self._thread

            self._stop_event.clear()

            self._thread = Thread(
                target=self._run_loop,
                name=(
                    "backtesting-background-worker-v2"
                ),
                daemon=True,
            )

            self._thread.start()

            return self._thread

    def stop(
        self,
        *,
        timeout: float | None = None,
    ) -> None:

        with self._lock:
            thread = self._thread

        if thread is None:
            return

        self._stop_event.set()

        if (
            thread.is_alive()
            and thread is not __import__(
                "threading"
            ).current_thread()
        ):
            thread.join(
                timeout=timeout
            )

        with self._lock:

            if not thread.is_alive():
                self._thread = None

    def join(
        self,
        *,
        timeout: float | None = None,
    ) -> None:

        with self._lock:
            thread = self._thread

        if thread is None:
            return

        thread.join(
            timeout=timeout
        )

    @property
    def is_running(
        self,
    ) -> bool:

        with self._lock:
            return (
                self._thread is not None
                and self._thread.is_alive()
                and not self._stop_event.is_set()
            )

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

    def __enter__(
        self,
    ) -> "BacktestingBackgroundWorkerV2":

        self.start()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> bool:

        self.stop(
            timeout=5.0,
        )

        return False
