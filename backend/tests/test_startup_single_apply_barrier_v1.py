"""Single-Apply startup barrier contract.

Offline only.

Desired workflow:

runtime.prepare(empty inbox)
-> prepare catch-up request
-> print LIVE + CATCHUP configuration together
-> operator performs one NinjaTrader Apply
-> pin one live quarantine session
-> reuse the already-prepared catch-up request
-> certify
-> post-catch-up health
-> activation

No execution authority.
"""

from pathlib import Path
import inspect

import pytest

import tools.analysis_native_startup_v1 as startup
import tools.startup_chart_catchup_v1 as helper


SESSION = (
    "00000000-0000-0000-"
    "0000-000000000013"
)


class Adapter:
    def __init__(
        self,
        directory,
    ):
        self.directory = directory
        self.status = "WAITING"
        self.activation_start = None
        self.session = None
        self.preactivation_session = SESSION
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
    ):
        self.phase = "VERIFYING_WAITING"

        self.adapter = Adapter(
            directory
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

        self.observations = []


def test_perform_reuses_prepared_request_without_second_prepare(
    tmp_path,
    monkeypatch,
):
    inbox = (
        tmp_path
        / "inbox"
    )

    inbox.mkdir()

    capture = (
        tmp_path
        / "chart-catchup"
    )

    capture.mkdir()

    runtime = Runtime(
        inbox
    )

    request = {
        "schema":
            "arms.startup-chart-catchup-request.v1",
        "indicator":
            "ArmsChartCatchupBridgeV1",
        "capture_enabled":
            True,
        "output_directory":
            str(capture),
        "live_output_directory":
            str(inbox),
        "expected_provider_enum":
            "Provider31",
        "from_close_utc":
            "2026-09-29T21:00:00Z",
        "through_close_utc":
            "LATEST_CLOSED",
        "through_selection":
            "CHART_LATEST_CLOSED",
        "absolute_time_authority":
            "NONE",
        "observation_only":
            True,
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }

    composite = object()

    monkeypatch.setattr(
        helper,
        "prepare_request",
        lambda *args, **kwargs:
            pytest.fail(
                "prepared request must be reused; "
                "prepare_request must not run twice"
            ),
    )

    guard_calls = []

    def fake_wait(
        directory,
        *,
        timeout_seconds,
        guard,
        **_,
    ):
        assert (
            Path(directory)
            == capture
        )

        guard()

        guard_calls.append(
            "wait"
        )

        return "READY"

    monkeypatch.setattr(
        helper,
        "await_capture",
        fake_wait,
    )

    def fake_certify(
        **kwargs,
    ):
        assert (
            kwargs[
                "request"
            ]
            is request
        )

        return {
            "bootstrap":
                composite,
            "sha256":
                "a" * 64,
            "bars":
                9000,
            "cutoff":
                "2026-09-30T21:15:00.0000000Z",
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
            prepared_request=request,
        )
    )

    assert returned_request is request

    assert (
        result[
            "bootstrap"
        ]
        is composite
    )

    assert runtime.installed == [
        composite
    ]

    assert (
        runtime.adapter.session
        is None
    )

    assert (
        runtime.adapter.activation_start
        is None
    )

    assert (
        runtime.adapter.preactivation_session
        == SESSION
    )

    assert (
        runtime.adapter.validation_calls
    )

    assert runtime.observations == []


def test_run_prepares_catchup_before_live_quarantine_is_pinned():
    source = inspect.getsource(
        startup.run
    )

    required = (
        "prepare_request(",
        "STARTUP_OPERATOR_SETUP_REQUIRED=TRUE",
        "STARTUP_LIVE_QUARANTINE_READY=TRUE",
        "perform_startup_chart_catchup(",
    )

    for token in required:
        assert token in source

    assert (
        source.index(
            "prepare_request("
        )
        <
        source.index(
            "STARTUP_OPERATOR_SETUP_REQUIRED=TRUE"
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


def test_single_operator_action_prints_both_indicator_configs():
    source = inspect.getsource(
        startup.run
    )

    assert (
        "ADD_FRESH_ArmsReadOnlyMarketV1_"
        "AND_ArmsChartCatchupBridgeV1_"
        "IN_ONE_APPLY"
        in source
    )

    required = (
        "LIVE_OUTPUT_DIRECTORY=",
        "CATCHUP_OUTPUT_DIRECTORY=",
        "CATCHUP_EXPECTED_PROVIDER_ENUM=",
        "CATCHUP_FROM_CLOSE_UTC=",
        "CATCHUP_THROUGH_CLOSE_UTC=",
    )

    setup = source[
        source.index(
            "STARTUP_OPERATOR_SETUP_REQUIRED=TRUE"
        ):
        source.index(
            "STARTUP_LIVE_QUARANTINE_READY=TRUE"
        )
    ]

    for token in required:
        assert token in setup


def test_no_second_operator_indicator_action_after_live_ready():
    run_source = inspect.getsource(
        startup.run
    )

    catchup_source = inspect.getsource(
        startup.perform_startup_chart_catchup
    )

    ready = run_source.index(
        "STARTUP_LIVE_QUARANTINE_READY=TRUE"
    )

    after_ready = run_source[
        ready:
    ]

    assert (
        "NINJATRADER_ACTION="
        not in after_ready
    )

    assert (
        "NINJATRADER_ACTION="
        not in catchup_source
    )



def test_single_apply_contract_preserves_fail_closed_guards():
    startup_source = Path(
        "tools/"
        "analysis_native_startup_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    adapter_source = Path(
        "backend/market_data/"
        "fresh_native_adapter_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    profile_source = Path(
        "backend/market_data/"
        "analysis_time_profile_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "validate_preactivation_buffer",
        "STARTUP_CATCHUP_WAITING_LOST",
    ):
        assert token in startup_source

    for token in (
        "PREACTIVATION_BUFFER_IDENTITY",
        "SESSION_ROTATION",
        "processing_seconds <= 90",
        "stale_quarantined_pair",
    ):
        assert token in adapter_source

    for token in (
        "BOOTSTRAP_LIVE_GAP",
        "BOOTSTRAP_LIVE_OVERLAP_CONFLICT",
        "TRANSPORT_PROCESSING_DELAY",
    ):
        assert token in profile_source

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
        assert forbidden not in startup_source
