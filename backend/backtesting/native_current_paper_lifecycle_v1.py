"""Owned worker for certified native -> Current-Market LOCAL PAPER.

This lifecycle owns only the coordinator worker thread.  Analysis startup and
adapter polling remain separately owned by AnalysisStartupV1 / analysis API.
PAPER control remains explicitly owned by the authorized PAPER API.

No NinjaTrader account, broker or order interface is reachable here.
"""

from math import isfinite
from threading import (
    Event,
    RLock,
    Thread,
)

from backend.backtesting.current_paper_runtime_v1 import (
    CurrentPaperServiceV1,
)
from backend.backtesting.native_current_paper_coordinator_v1 import (
    NativeCurrentPaperCoordinatorV1,
)
from backend.market_data.analysis_startup_v1 import (
    AnalysisStartupV1,
)


SCHEMA = (
    "arms.native-current-paper-"
    "lifecycle.v1"
)


class NativeCurrentPaperLifecycleV1:
    """Own one background caller of coordinator.poll()."""

    def __init__(
        self,
        *,
        analysis_runtime,
        service,
        wall_clock,
        poll_interval_seconds=0.25,
    ):
        if type(analysis_runtime) is not AnalysisStartupV1:
            raise TypeError(
                "exact AnalysisStartupV1 required"
            )

        if type(service) is not CurrentPaperServiceV1:
            raise TypeError(
                "exact CurrentPaperServiceV1 required"
            )

        if not callable(wall_clock):
            raise TypeError(
                "explicit wall clock required"
            )

        if (
            type(poll_interval_seconds)
            not in (
                int,
                float,
            )
            or isinstance(
                poll_interval_seconds,
                bool,
            )
            or not isfinite(
                poll_interval_seconds
            )
            or not (
                0.01
                <= poll_interval_seconds
                <= 5.0
            )
        ):
            raise ValueError(
                "BOUNDED_LIFECYCLE_POLL_INTERVAL_REQUIRED"
            )

        self.lock = RLock()

        self.analysis_runtime = (
            analysis_runtime
        )

        self.service = service
        self.wall_clock = wall_clock

        self.poll_interval_seconds = (
            float(
                poll_interval_seconds
            )
        )

        # Constructor is the certified attach action.
        # NativeCurrentPaperCoordinatorV1 arms the one-shot
        # handoff and installs context-only bootstrap.
        self.coordinator = (
            NativeCurrentPaperCoordinatorV1(
                analysis_runtime=
                    analysis_runtime,
                service=service,
                wall_clock=wall_clock,
            )
        )

        self.stop_event = Event()
        self.worker = None

        self.started = False
        self.stopped = False

        self.status = "ATTACHED"
        self.reason = None

        self.worker_error = None
        self.worker_poll_count = 0
        self.last_coordinator_snapshot = None

    def _worker_main(self):
        """The worker has one authority only: coordinator.poll()."""
        while not self.stop_event.is_set():
            try:
                snapshot = (
                    self.coordinator.poll()
                )
            except BaseException as error:
                with self.lock:
                    self.worker_error = error
                    self.reason = (
                        "NATIVE_CURRENT_PAPER_"
                        "LIFECYCLE_WORKER_FAILED"
                    )
                    self.status = "FAILED"

                self.stop_event.set()
                return

            with self.lock:
                self.worker_poll_count += 1
                self.last_coordinator_snapshot = (
                    snapshot
                )

                if (
                    snapshot.get("status")
                    == "LIVE"
                ):
                    self.status = "LIVE"
                else:
                    self.status = "RUNNING"

            if self.stop_event.wait(
                self.poll_interval_seconds
            ):
                return

    def start(self):
        """Start exactly one worker; never arm PAPER execution."""
        with self.lock:
            if (
                self.started
                or self.stopped
                or self.worker is not None
                or self.worker_error
                is not None
            ):
                raise RuntimeError(
                    "LIFECYCLE_START_REENTRY"
                )

            if (
                self.coordinator.stopped
                or self.coordinator.reason
                is not None
            ):
                raise RuntimeError(
                    "COORDINATOR_UNAVAILABLE"
                )

            self.started = True
            self.status = "STARTING"

            worker = Thread(
                target=self._worker_main,
                name=(
                    "arms-current-paper-"
                    + self.analysis_runtime.run_id
                ),
                daemon=True,
            )

            self.worker = worker

            worker.start()

            self.status = "RUNNING"

        return self.get_snapshot()

    def check(self):
        """Fail the owner if its separately owned worker is unavailable."""
        with self.lock:
            if self.stopped:
                raise RuntimeError(
                    "LIFECYCLE_STOPPED"
                )

            if not self.started:
                raise RuntimeError(
                    "LIFECYCLE_NOT_STARTED"
                )

            error = self.worker_error
            worker = self.worker

            if error is not None:
                raise RuntimeError(
                    "NATIVE_CURRENT_PAPER_"
                    "LIFECYCLE_WORKER_FAILED"
                ) from error

            if (
                worker is None
                or not worker.is_alive()
            ):
                self.reason = (
                    "NATIVE_CURRENT_PAPER_"
                    "LIFECYCLE_WORKER_STOPPED"
                )

                self.status = "FAILED"

                raise RuntimeError(
                    self.reason
                )

        return self.get_snapshot()

    def get_snapshot(self):
        with self.lock:
            worker = self.worker

            coordinator_snapshot = (
                self.coordinator
                .get_snapshot()
            )

            return {
                "schema":
                    SCHEMA,
                "status":
                    self.status,
                "reason":
                    self.reason,
                "started":
                    self.started,
                "stopped":
                    self.stopped,
                "worker_alive":
                    (
                        worker is not None
                        and worker.is_alive()
                    ),
                "worker_poll_count":
                    self.worker_poll_count,
                "worker_error_type":
                    (
                        None
                        if self.worker_error
                        is None
                        else type(
                            self.worker_error
                        ).__name__
                    ),
                "analysis_run_id":
                    self.analysis_runtime.run_id,
                "analysis_runtime_owned":
                    False,
                "analysis_poll_authority":
                    False,
                "coordinator":
                    coordinator_snapshot,
                "paper_auto_enable":
                    False,
                "paper_control_authority":
                    False,
                "broker_authority":
                    False,
                "ninjatrader_account_access":
                    False,
                "live_execution_allowed":
                    False,
                "native_order_authority":
                    False,
                "order_submit_reachable":
                    False,
            }

    def close(self):
        """Stop worker first, then close coordinator; never close analysis."""
        with self.lock:
            if self.stopped:
                return

            self.stopped = True
            self.status = "STOPPING"

            self.stop_event.set()

            worker = self.worker

        worker_timeout = False

        if worker is not None:
            worker.join(
                timeout=5.0
            )

            worker_timeout = (
                worker.is_alive()
            )

        coordinator_error = None

        try:
            self.coordinator.close()
        except BaseException as error:
            coordinator_error = error

        with self.lock:
            self.status = "STOPPED"

        if worker_timeout:
            raise RuntimeError(
                "LIFECYCLE_WORKER_STOP_TIMEOUT"
            )

        if coordinator_error is not None:
            raise coordinator_error
