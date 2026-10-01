"""R13 live-before-catchup startup ordering contract.

Offline only. Never starts NinjaTrader, broker/account access or orders.
"""

from pathlib import Path
from uuid import uuid4
import inspect

import pytest

import tools.analysis_native_startup_v1 as startup
import tools.startup_chart_catchup_v1 as helper


class Adapter:
    def __init__(
        self,
        directory,
        *,
        live_session=True,
    ):
        self.directory = directory

        self.status = "WAITING"
        self.activation_start = None
        self.session = None

        self.preactivation_session = (
            str(uuid4())
            if live_session
            else None
        )

        self.validation_calls = []

    def validate_preactivation_buffer(
        self,
        reason,
    ):
        self.validation_calls.append(
            reason
        )

        return (
            self.preactivation_session
        )


class Runtime:
    def __init__(
        self,
        directory,
        *,
        live_session=True,
    ):
        self.phase = "VERIFYING_WAITING"

        self.adapter = Adapter(
            directory,
            live_session=live_session,
        )

        self.bootstrap = object()

        self.observations = [
            1,
            2,
            3,
        ]

        self.installed = []

    def install_waiting_bootstrap(
        self,
        bootstrap,
    ):
        self.installed.append(
            bootstrap
        )

        self.bootstrap = bootstrap

        # Existing startup contract:
        # all old waiting observations are invalidated.
        self.observations = []


def _write_live_quarantine(
    inbox,
    session,
):
    (
        inbox
        / (
            session
            + ".jsonl"
        )
    ).write_bytes(
        b'{"kind":"HELLO"}\n'
    )

    (
        inbox
        / (
            session
            + ".connection.jsonl"
        )
    ).write_bytes(
        b""
    )

    timing = (
        inbox
        / "timing"
    )

    timing.mkdir()

    (
        timing
        / (
            session
            + ".production-timing.jsonl"
        )
    ).write_bytes(
        b""
    )


def _patch_success_path(
    monkeypatch,
    tmp_path,
):
    calls = []

    request = {
        "output_directory":
            str(
                tmp_path
                / "chart-catchup"
            ),
        "live_output_directory":
            str(
                tmp_path
                / "inbox"
            ),
        "expected_provider_enum":
            "Provider31",
        "from_close_utc":
            "2026-09-30T14:00:00Z",
        "through_close_utc":
            "LATEST_CLOSED",
    }

    (
        tmp_path
        / "chart-catchup"
    ).mkdir()

    composite = object()

    monkeypatch.setattr(
        helper,
        "prepare_request",
        lambda folder, bootstrap, **_: (
            calls.append(
                (
                    "prepare",
                    folder,
                    bootstrap,
                )
            )
            or request
        ),
    )

    def fake_wait(
        directory,
        *,
        timeout_seconds,
        guard,
        **_,
    ):
        calls.append(
            (
                "wait",
                directory,
                timeout_seconds,
            )
        )

        guard()

        return "READY"

    monkeypatch.setattr(
        helper,
        "await_capture",
        fake_wait,
    )

    def fake_certify(
        **kwargs,
    ):
        calls.append(
            (
                "certify",
                kwargs[
                    "capture_directory"
                ],
            )
        )

        return {
            "bootstrap":
                composite,
            "sha256":
                "a" * 64,
            "bars":
                100,
            "cutoff":
                "2026-09-30T14:10:00.0000000Z",
            "source":
                (
                    "NATIVE_HISTORICAL_REPOSITORY"
                    "+NINJATRADER_LOADED_CHART_BARS"
                ),
            "report":
                {},
            "output":
                str(
                    tmp_path
                    / "certified.bundle.json"
                ),
            "runtime_admission":
                False,
            "execution_authority":
                False,
        }

    monkeypatch.setattr(
        helper,
        "certify_capture",
        fake_certify,
    )

    return (
        calls,
        request,
        composite,
    )


def test_catchup_accepts_valid_quarantined_live_session(
    tmp_path,
    monkeypatch,
):
    inbox = (
        tmp_path
        / "inbox"
    )

    inbox.mkdir()

    runtime = Runtime(
        inbox,
        live_session=True,
    )

    _write_live_quarantine(
        inbox,
        runtime.adapter.preactivation_session,
    )

    (
        calls,
        request,
        composite,
    ) = _patch_success_path(
        monkeypatch,
        tmp_path,
    )

    guard_calls = []

    returned_request, result = (
        startup.perform_startup_chart_catchup(
            runtime=runtime,
            run_directory=tmp_path,
            base_path=
                tmp_path
                / "base.json",
            base_sha256=
                "b" * 64,
            source_path=
                tmp_path
                / "bridge.cs",
            timeout_seconds=30,
            guard=lambda:
                guard_calls.append(
                    "guard"
                ),
        )
    )

    assert returned_request is request

    assert (
        result[
            "bootstrap"
        ]
        is composite
    )

    assert [
        item[0]
        for item in calls
    ] == [
        "prepare",
        "wait",
        "certify",
    ]

    assert runtime.installed == [
        composite
    ]

    assert (
        runtime.adapter.activation_start
        is None
    )

    assert (
        runtime.adapter.session
        is None
    )

    assert (
        runtime.adapter.preactivation_session
        is not None
    )

    assert (
        runtime.adapter.validation_calls
    )

    assert runtime.observations == []


def test_catchup_requires_live_quarantine_before_capture(
    tmp_path,
    monkeypatch,
):
    inbox = (
        tmp_path
        / "inbox"
    )

    inbox.mkdir()

    runtime = Runtime(
        inbox,
        live_session=False,
    )

    monkeypatch.setattr(
        helper,
        "prepare_request",
        lambda *_, **__:
            pytest.fail(
                "catch-up request must not start "
                "before live quarantine is ready"
            ),
    )

    with pytest.raises(
        ValueError,
        match="STARTUP_LIVE_QUARANTINE_REQUIRED",
    ):
        startup.perform_startup_chart_catchup(
            runtime=runtime,
            run_directory=tmp_path,
            base_path=
                tmp_path
                / "base.json",
            base_sha256=
                "b" * 64,
            source_path=
                tmp_path
                / "bridge.cs",
            timeout_seconds=30,
            guard=lambda: None,
        )

    assert runtime.installed == []

    assert (
        runtime.adapter.activation_start
        is None
    )


def test_run_orders_live_quarantine_before_chart_catchup():
    source = inspect.getsource(
        startup.run
    )

    required = (
        "STARTUP_LIVE_QUARANTINE_REQUIRED=TRUE",
        "STARTUP_LIVE_QUARANTINE_READY=TRUE",
        "perform_startup_chart_catchup(",
    )

    for token in required:
        assert token in source

    assert (
        source.index(
            "STARTUP_LIVE_QUARANTINE_REQUIRED=TRUE"
        )
        <
        source.index(
            "STARTUP_LIVE_QUARANTINE_READY=TRUE"
        )
        <
        source.index(
            "perform_startup_chart_catchup("
        )
    )


def test_catchup_guard_allows_quarantined_input_not_empty_only():
    source = inspect.getsource(
        startup.run
    )

    start = source.index(
        "def catchup_guard():"
    )

    end = source.index(
        "request, catchup_result",
        start,
    )

    guard = source[
        start:end
    ]

    assert (
        "validate_preactivation_buffer"
        in guard
    )

    assert (
        "preactivation_session"
        in guard
    )

    assert (
        "not any("
        not in guard
    )


def test_operator_prompt_keeps_live_exporter_running():
    run_source = inspect.getsource(
        startup.run
    )

    catchup_source = inspect.getsource(
        startup.perform_startup_chart_catchup
    )

    assert (
        "ADD_FRESH_ArmsReadOnlyMarketV1_AND_ArmsChartCatchupBridgeV1_IN_ONE_APPLY"
        in run_source
    )

    assert (
        "STARTUP_OPERATOR_APPLY_COUNT=1"
        in run_source
    )

    assert (
        "LIVE_OUTPUT_DIRECTORY="
        in run_source
    )

    assert (
        "CATCHUP_OUTPUT_DIRECTORY="
        in run_source
    )

    assert (
        "NINJATRADER_ACTION="
        not in catchup_source
    )
