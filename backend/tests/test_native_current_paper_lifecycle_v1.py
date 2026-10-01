"""D4D3 native-current PAPER lifecycle worker tests.

No NinjaTrader process, native account discovery or LIVE execution.
"""

import inspect
from pathlib import Path
import time
from unittest.mock import Mock

import pytest

from backend.backtesting.native_current_paper_lifecycle_v1 import (
    NativeCurrentPaperLifecycleV1,
)
from backend.tests.test_certified_native_paper_bridge_v1 import (
    _paper,
    _record,
)
from backend.tests.test_native_current_paper_coordinator_v1 import (
    _analysis_runtime,
    _make_live,
)
from backend.tests.test_production_certified_outcome_v17 import (
    api_settings,
)


def _lifecycle(
    tmp_path,
    monkeypatch,
    api_settings,
    *,
    poll_interval_seconds=0.01,
):
    runtime, _, _ = (
        _analysis_runtime(
            tmp_path,
            monkeypatch,
        )
    )

    service, wall = _paper(
        tmp_path,
        api_settings,
    )

    lifecycle = (
        NativeCurrentPaperLifecycleV1(
            analysis_runtime=runtime,
            service=service,
            wall_clock=lambda: wall[0],
            poll_interval_seconds=
                poll_interval_seconds,
        )
    )

    return (
        lifecycle,
        runtime,
        service,
        wall,
    )


def _wait_until(
    predicate,
    *,
    seconds=2.0,
):
    deadline = (
        time.monotonic()
        + seconds
    )

    while (
        time.monotonic()
        < deadline
    ):
        if predicate():
            return

        time.sleep(
            0.01
        )

    raise AssertionError(
        "condition did not become true"
    )


def test_constructor_attaches_without_starting_worker_or_enabling_paper(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, service, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    assert lifecycle.started is False
    assert lifecycle.worker is None
    assert lifecycle.status == "ATTACHED"

    assert (
        runtime.adapter
        .live_handoff_enabled
        is True
    )

    assert (
        runtime.adapter
        .activation_start
        is None
    )

    paper = service.get_snapshot()

    assert paper[
        "paper_execution_enabled"
    ] is False if (
        "paper_execution_enabled"
        in paper
    ) else (
        "PAPER_DISABLED"
        in paper[
            "readiness_reasons"
        ]
    )

    snapshot = (
        lifecycle.get_snapshot()
    )

    assert snapshot[
        "analysis_runtime_owned"
    ] is False

    assert snapshot[
        "analysis_poll_authority"
    ] is False

    assert snapshot[
        "paper_auto_enable"
    ] is False

    assert snapshot[
        "paper_control_authority"
    ] is False

    assert snapshot[
        "order_submit_reachable"
    ] is False

    lifecycle.close()

    # Separately owned analysis runtime is untouched.
    assert runtime.phase == "VERIFYING_WAITING"


def test_worker_calls_coordinator_only_and_never_analysis_poll(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, _, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    forbidden = Mock(
        side_effect=AssertionError(
            "analysis poll is separately owned"
        )
    )

    monkeypatch.setattr(
        runtime,
        "poll",
        forbidden,
    )

    lifecycle.start()

    _wait_until(
        lambda:
            lifecycle.worker_poll_count
            >= 2
    )

    snapshot = lifecycle.check()

    assert snapshot[
        "worker_alive"
    ] is True

    assert snapshot[
        "worker_poll_count"
    ] >= 2

    assert forbidden.call_count == 0

    lifecycle.close()

    assert forbidden.call_count == 0


def test_real_attach_order_starts_worker_before_analysis_activation(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, _, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    assert (
        runtime.adapter
        .activation_start
        is None
    )

    lifecycle.start()

    _wait_until(
        lambda:
            lifecycle.worker_poll_count
            >= 1
    )

    assert (
        runtime.adapter
        .activation_start
        is None
    )

    runtime.finish_health(
        backend_pid=runtime.pid,
        frontend_pid=99,
        dashboard_status=200,
        allow_activation=True,
    )

    assert (
        runtime.adapter
        .activation_start
        is not None
    )

    lifecycle.close()


def test_worker_delivers_certified_live_close_without_auto_enable(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, service, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    lifecycle.start()

    runtime.finish_health(
        backend_pid=runtime.pid,
        frontend_pid=99,
        dashboard_status=200,
        allow_activation=True,
    )

    adapter = _make_live(
        runtime,
        monkeypatch,
    )

    adapter.live_handoff_records.append(
        _record()
    )

    _wait_until(
        lambda:
            service.gate.closed_count
            == 1
    )

    lifecycle_snapshot = (
        lifecycle.check()
    )

    paper = service.get_snapshot()

    assert lifecycle_snapshot[
        "status"
    ] in (
        "RUNNING",
        "LIVE",
    )

    assert paper[
        "market_data"
    ][
        "closed_candles"
    ] == 1

    assert paper[
        "paper_execution_enabled"
    ] is False

    assert "PAPER_DISABLED" in paper[
        "readiness_reasons"
    ]

    runtime_paper = (
        service
        ._runtime
        ._paper
        .runtime
    )

    assert (
        runtime_paper
        .lifecycle
        .broker_connector_v2
        .get_fills()
        == []
    )

    assert runtime_paper.completed == []

    lifecycle.close()


def test_worker_failure_is_latched_and_check_fails_closed(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, service, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    monkeypatch.setattr(
        lifecycle.coordinator,
        "poll",
        Mock(
            side_effect=ValueError(
                "fixture worker failure"
            )
        ),
    )

    lifecycle.start()

    _wait_until(
        lambda:
            lifecycle.worker_error
            is not None
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "NATIVE_CURRENT_PAPER_"
            "LIFECYCLE_WORKER_FAILED"
        ),
    ):
        lifecycle.check()

    assert lifecycle.status == "FAILED"
    assert lifecycle.reason == (
        "NATIVE_CURRENT_PAPER_"
        "LIFECYCLE_WORKER_FAILED"
    )

    lifecycle.close()

    assert service._stopped is True

    # Lifecycle never owns analysis shutdown.
    assert runtime.phase == "VERIFYING_WAITING"


def test_start_is_one_shot(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, _, _, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    lifecycle.start()

    with pytest.raises(
        RuntimeError,
        match="LIFECYCLE_START_REENTRY",
    ):
        lifecycle.start()

    lifecycle.close()


def test_check_before_start_fails_closed(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, _, _, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="LIFECYCLE_NOT_STARTED",
    ):
        lifecycle.check()

    lifecycle.close()


def test_close_before_start_is_idempotent_and_preserves_analysis(
    tmp_path,
    monkeypatch,
    api_settings,
):
    lifecycle, runtime, service, _ = (
        _lifecycle(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    lifecycle.close()
    lifecycle.close()

    assert lifecycle.stopped is True
    assert lifecycle.status == "STOPPED"
    assert service._stopped is True

    assert runtime.phase == "VERIFYING_WAITING"
    assert runtime.reason is None


def test_close_source_stops_worker_before_coordinator_close():
    source = inspect.getsource(
        NativeCurrentPaperLifecycleV1.close
    )

    stop = source.index(
        "self.stop_event.set()"
    )

    join = source.index(
        "worker.join("
    )

    coordinator_close = source.index(
        "self.coordinator.close()"
    )

    assert (
        stop
        < join
        < coordinator_close
    )


@pytest.mark.parametrize(
    "interval",
    (
        0,
        -1,
        0.001,
        6,
        float("nan"),
        float("inf"),
        True,
    ),
)
def test_invalid_poll_interval_fails_before_attach(
    tmp_path,
    monkeypatch,
    api_settings,
    interval,
):
    runtime, _, _ = (
        _analysis_runtime(
            tmp_path,
            monkeypatch,
        )
    )

    service, wall = _paper(
        tmp_path,
        api_settings,
    )

    with pytest.raises(
        ValueError,
        match=(
            "BOUNDED_LIFECYCLE_"
            "POLL_INTERVAL_REQUIRED"
        ),
    ):
        NativeCurrentPaperLifecycleV1(
            analysis_runtime=runtime,
            service=service,
            wall_clock=lambda: wall[0],
            poll_interval_seconds=interval,
        )

    assert (
        runtime.adapter
        .live_handoff_enabled
        is False
    )

    assert service._stopped is False


def test_lifecycle_source_has_no_analysis_poll_paper_control_or_order_surface():
    source = Path(
        "backend/backtesting/"
        "native_current_paper_lifecycle_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "analysis_runtime.poll" not in source
    assert "self.analysis_runtime.poll" not in source
    assert "service.control" not in source
    assert ".control(" not in source

    for forbidden in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "AtmStrategy",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in source
