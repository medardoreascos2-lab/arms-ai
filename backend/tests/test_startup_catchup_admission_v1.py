"""Startup catch-up admission gate only; never starts NinjaTrader or orders."""
from pathlib import Path
from uuid import uuid4

import pytest

from backend.market_data.analysis_startup_v1 import (
    AnalysisStartupV1,
)
from backend.market_data.certified_bootstrap_v1 import (
    BootstrapBar,
    CertifiedBootstrap,
)
from backend.tests.test_analysis_time_sprint15x import (
    forbid_account_and_execution_construction,
)


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsReadOnlyMarketV1.cs"
).resolve()

MERGED_SOURCE = (
    "NATIVE_HISTORICAL_REPOSITORY"
    "+NINJATRADER_LOADED_CHART_BARS"
)


def certified_bootstrap():
    return CertifiedBootstrap(
        "a" * 64,
        (
            BootstrapBar(
                "2026-09-30T04:06:00.0000000Z",
                20000.0,
                20001.0,
                19999.0,
                20000.25,
                10,
            ),
        ),
        ("history",),
        0,
        source=MERGED_SOURCE,
    )


class Harness:
    def __init__(
        self,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "backend.market_data.analysis_startup_v1."
            "live_process_start",
            lambda pid: 42 if pid else None,
        )

        self.now = 1000

        self.runtime = AnalysisStartupV1(
            run_id=str(uuid4()),
            installed_exporter=SOURCE,
            qpc_clock=lambda: (
                "offline",
                1000,
                self.now,
            ),
        )

        self.folder = (
            tmp_path / "inbox"
        )

    def prepare(self):
        runtime = self.runtime

        runtime.poll()

        runtime.verify_backend(
            runtime.health(),
            runtime.pid,
        )

        runtime.verify_frontend(
            expected_pid=99,
            expected_start=42,
            actual_pid=99,
            http_status=200,
            build_id="fresh-build",
            html=(
                "ANALYSIS ONLY "
                "ADAPTER_STATUS "
                "fresh-build"
            ),
        )

        runtime.prepare(
            self.folder
        )

    def waiting_tick(self):
        self.now += 1000

        self.runtime.poll()

        self.runtime.observe_waiting(
            self.runtime.health(),
            self.runtime.pid,
        )

    def healthy_waiting(self):
        self.prepare()

        for _ in range(3):
            self.waiting_tick()

    def finish(self):
        self.runtime.finish_health(
            backend_pid=
                self.runtime.pid,
            frontend_pid=99,
            dashboard_status=200,
            allow_activation=True,
        )


def test_certified_catchup_replaces_bootstrap_once_before_activation(
    tmp_path,
    monkeypatch,
    forbid_account_and_execution_construction,
):
    harness = Harness(
        tmp_path,
        monkeypatch,
    )

    harness.healthy_waiting()

    runtime = harness.runtime
    adapter = runtime.adapter
    prior_profile = adapter.profile

    assert len(
        runtime.observations
    ) == 3

    data = certified_bootstrap()

    runtime.install_waiting_bootstrap(
        data
    )

    assert (
        runtime.phase
        == "VERIFYING_WAITING"
    )

    assert (
        runtime.observations
        == []
    )

    assert (
        runtime.bootstrap
        is data
    )

    assert (
        adapter.bootstrap
        is data
    )

    assert (
        adapter.profile
        is not prior_profile
    )

    assert (
        adapter.bootstrap_replacement_count
        == 1
    )

    assert (
        runtime.bootstrap_replacement_count
        == 1
    )

    snapshot = runtime.snapshot()

    assert (
        snapshot[
            "bootstrap_source"
        ]
        == MERGED_SOURCE
    )

    assert (
        snapshot[
            "bootstrap_cutoff"
        ]
        == "2026-09-30T04:06:00.0000000Z"
    )

    assert (
        snapshot[
            "bootstrap_provider_attribution"
        ]
        == "UNATTESTED"
    )

    assert (
        snapshot[
            "order_submit_reachable"
        ]
        is False
    )

    # The old health observations were invalidated.
    # Three fresh observations are required again.
    for _ in range(3):
        harness.waiting_tick()

    harness.finish()

    assert (
        runtime.phase
        == "AWAITING_OPERATOR_ACTIVATION"
    )

    assert (
        adapter.activation_start
        is not None
    )


@pytest.mark.parametrize(
    "fault",
    (
        "invalid_object",
        "nonempty_input",
        "reentry",
        "after_activation",
    ),
)
def test_bootstrap_install_faults_fail_closed(
    tmp_path,
    monkeypatch,
    forbid_account_and_execution_construction,
    fault,
):
    harness = Harness(
        tmp_path,
        monkeypatch,
    )

    harness.healthy_waiting()

    runtime = harness.runtime
    data = certified_bootstrap()

    if fault == "invalid_object":
        value = object()

    elif fault == "nonempty_input":
        (
            harness.folder
            / "unexpected"
        ).write_text(
            "",
            encoding="utf-8",
        )

        value = data

    elif fault == "reentry":
        runtime.install_waiting_bootstrap(
            data
        )

        value = data

    else:
        harness.finish()
        value = data

    with pytest.raises(
        ValueError,
    ):
        runtime.install_waiting_bootstrap(
            value
        )

    assert (
        runtime.phase
        == "FAILED"
    )

    assert (
        runtime.adapter.status
        == "REVOKED"
    )

    assert (
        runtime.snapshot()[
            "order_submit_reachable"
        ]
        is False
    )


def test_bootstrap_install_before_adapter_fails_closed(
    tmp_path,
    monkeypatch,
    forbid_account_and_execution_construction,
):
    harness = Harness(
        tmp_path,
        monkeypatch,
    )

    runtime = harness.runtime

    with pytest.raises(
        ValueError,
    ):
        runtime.install_waiting_bootstrap(
            certified_bootstrap()
        )

    assert (
        runtime.phase
        == "FAILED"
    )

    assert (
        runtime.adapter
        is None
    )

    assert (
        runtime.health()[
            "activation_allowance_started"
        ]
        is False
    )
