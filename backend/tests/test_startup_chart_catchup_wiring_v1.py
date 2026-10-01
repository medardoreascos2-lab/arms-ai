"""Startup chart catch-up wiring tests; never starts NinjaTrader or orders."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.startup_chart_catchup_v1 as helper
from backend.market_data.chart_catchup_bridge_v1 import MERGED_SOURCE
from backend.tests.test_chart_catchup_bridge_v1 import october_composite
from tools.analysis_native_startup_v1 import (
    perform_startup_chart_catchup,
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

        # Deterministic quarantined live-session identity for
        # this offline wiring harness.
        self.preactivation_session = (
            "00000000-0000-0000-0000-000000000001"
        )

        self.validation_calls = []

    def validate_preactivation_buffer(
        self,
        reason,
    ):
        self.validation_calls.append(
            reason
        )

        # Existing arbitrary-input negative test stays fail-closed.
        if any(
            self.directory.iterdir()
        ):
            raise ValueError(
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
        _, self.bootstrap = october_composite()
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

        # Contract established by C3C1.
        self.observations = []


def test_catchup_wiring_orders_prepare_wait_certify_install(
    tmp_path,
    monkeypatch,
):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    runtime = Runtime(
        inbox
    )

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
            "2026-09-29T21:00:00Z",
        "through_close_utc":
            "2026-09-30T04:06:00Z",
    }

    (
        tmp_path
        / "chart-catchup"
    ).mkdir()

    composite = SimpleNamespace(
        source=MERGED_SOURCE,
    )

    def fake_prepare(folder, bootstrap, **kwargs):
        assert bootstrap.source == MERGED_SOURCE
        calls.append(("prepare", folder, bootstrap))
        return request

    monkeypatch.setattr(
        helper,
        "prepare_request",
        fake_prepare,
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

    def fake_certify(**kwargs):
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
                10,
            "cutoff":
                "2026-09-30T04:06:00.0000000Z",
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

    guard_calls = []

    returned_request, result = (
        perform_startup_chart_catchup(
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
        result["bootstrap"]
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

    assert len(
        guard_calls
    ) == 3

    assert runtime.installed == [
        composite
    ]

    assert len(runtime.installed) == 1

    assert runtime.bootstrap is composite

    assert runtime.observations == []

    assert (
        runtime.adapter.activation_start
        is None
    )

    assert (
        runtime.adapter.status
        == "WAITING"
    )


@pytest.mark.parametrize(
    "fault",
    (
        "phase",
        "activation",
        "session",
        "observations",
        "input",
    ),
)
def test_catchup_wiring_preconditions_fail_closed(
    tmp_path,
    monkeypatch,
    fault,
):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    runtime = Runtime(
        inbox
    )

    if fault == "phase":
        runtime.phase = "FAILED"

    elif fault == "activation":
        runtime.adapter.activation_start = 123

    elif fault == "session":
        runtime.adapter.session = "existing"

    elif fault == "observations":
        runtime.observations = [
            1,
            2,
        ]

    else:
        (
            inbox
            / "unexpected.jsonl"
        ).write_text(
            "{}",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        helper,
        "prepare_request",
        lambda *_: pytest.fail(
            "prepare_request must not run"
        ),
    )

    with pytest.raises(
        ValueError,
        match="STARTUP_CATCHUP_GATE_ORDER",
    ):
        perform_startup_chart_catchup(
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
        if fault != "activation"
        else runtime.adapter.activation_start
        == 123
    )


def test_installed_catchup_source_hash_uses_real_crlf_normalization():
    from pathlib import Path

    from backend.market_data.chart_catchup_source_identity_v1 import (
        EXPORTER_SHA256,
        verify_chart_catchup_source,
    )

    source = Path(
        "integrations/ninjatrader/"
        "ArmsChartCatchupBridgeV1.cs"
    ).resolve().read_bytes()

    lf_source = source.replace(
        b"\r\n",
        b"\n",
    )

    crlf_source = lf_source.replace(
        b"\n",
        b"\r\n",
    )

    result = verify_chart_catchup_source(
        crlf_source,
        mismatch_reason=(
            "STARTUP_CATCHUP_INSTALLED_SOURCE"
        ),
    )

    assert (
        result["authored_sha256"]
        == EXPORTER_SHA256
    )




def test_catchup_wiring_contains_no_execution_surface():
    text = Path(
        "tools/"
        "analysis_native_startup_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in text
