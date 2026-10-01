"""D3A certified native CLOSED-bar -> LOCAL PAPER bridge tests.

No NinjaTrader process, native account, external broker or LIVE execution.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.backtesting.certified_native_paper_bridge_v1 import (
    CertifiedNativePaperBridgeV1,
)
from backend.backtesting.current_paper_runtime_v1 import (
    CurrentPaperServiceV1,
)
from backend.market_data.certified_bootstrap_v1 import (
    BootstrapBar,
    CertifiedBootstrap,
    HELLO,
)
from backend.market_data.current_candle_authority_v1 import (
    CurrentCandleAuthorityV1,
    CurrentFeedContractV1,
)
from backend.market_data.fresh_native_adapter_v1 import (
    FreshNativeAdapterV1,
)
from backend.services.certified_market_calendar_v2 import (
    CertifiedCalendarSnapshotV2,
)
from backend.services.certified_market_hours_runtime_provider_v2 import (
    CertifiedMarketHoursRuntimeProviderV2,
)
from backend.tests.test_fresh_native_adapter_sprint15y import (
    Files,
    EXPORTER,
)
from backend.tests.test_paper_research_sprint07r import (
    config,
)
from backend.tests.test_production_certified_outcome_v17 import (
    api_settings,
)


UTC = timezone.utc

START = datetime(
    2026,
    9,
    21,
    14,
    0,
    tzinfo=UTC,
)

SESSION = (
    "512fbd5e-d193-48db-"
    "9fdf-25b8dd2c43b9"
)


def _bootstrap():
    return CertifiedBootstrap(
        "0" * 64,
        (
            BootstrapBar(
                "2026-09-21T14:00:00.0000000Z",
                10000.0,
                10000.0,
                10000.0,
                10000.0,
                10,
            ),
        ),
        ("fixture",),
        0,
    )


def _warm_bootstrap(
    count=120,
):
    bars = []

    first_label = (
        START
        - timedelta(
            minutes=count - 1
        )
    )

    for index in range(count):
        label = (
            first_label
            + timedelta(
                minutes=index
            )
        )

        value = (
            label.isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )

        bars.append(
            BootstrapBar(
                value,
                10000.0,
                10000.0,
                10000.0,
                10000.0,
                10,
            )
        )

    return CertifiedBootstrap(
        "1" * 64,
        tuple(bars),
        ("warm-fixture",),
        0,
    )


def _hello():
    return json.dumps(
        {
            "schema":
                "arms.nt.market.v1",
            "session":
                SESSION,
            "sequence":
                0,
            "event_time":
                "2026-09-21T14:00:00.0000000Z",
            "kind":
                "HELLO",
            "payload":
                dict(HELLO),
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _native(
    tmp_path,
    monkeypatch,
    *,
    handoff="COMPLETE",
    bootstrap=None,
):
    root = (
        tmp_path
        / (
            "native-"
            + str(uuid4())
        )
    )

    root.mkdir()

    now = [1000]

    bootstrap = (
        _bootstrap()
        if bootstrap is None
        else bootstrap
    )

    adapter = FreshNativeAdapterV1(
        directory=root,
        installed_exporter=EXPORTER,
        qpc_clock=lambda: (
            "bridge-test",
            1000,
            now[0],
        ),
        health_gated=False,
        bootstrap=bootstrap,
        live_handoff=True,
    )

    adapter.status = "LIVE_TAIL"
    adapter.reason = None
    adapter.session = SESSION
    adapter.hello = _hello()

    adapter.profile.session = SESSION
    adapter.profile.handoff = handoff

    native_state = {
        "market_stream":
            "LIVE",
        "transport_status":
            "TRANSPORT_LIVE",
        "live_handoff_status":
            handoff,
        "timing_pair_status":
            "EXACT_PREFIX",
        "fault":
            None,
    }

    monkeypatch.setattr(
        adapter,
        "snapshot",
        lambda: dict(
            native_state
        ),
    )

    return (
        adapter,
        native_state,
    )


def _paper(
    tmp_path,
    api_settings,
):
    clock = [
        START
        + timedelta(
            minutes=1,
            seconds=1,
        )
    ]

    days = frozenset(
        START.date()
        + timedelta(days=value)
        for value
        in range(-3, 10)
    )

    hours = (
        CertifiedMarketHoursRuntimeProviderV2(
            calendar_snapshot=(
                CertifiedCalendarSnapshotV2(
                    days,
                    frozenset(),
                )
            )
        )
    )

    contract = CurrentFeedContractV1(
        "NINJATRADER:Provider31",
        "NQ DEC26",
        "UTC",
        "CLOSE",
        "CME US Index Futures ETH",
        START - timedelta(days=3),
        START + timedelta(days=10),
        fixture=False,
    )

    gate = CurrentCandleAuthorityV1(
        contract=contract,
        market_hours=hours,
        maximum_age_seconds=(
            api_settings
            .maximum_quote_age_seconds
        ),
        clock=lambda: clock[0],
    )

    service = CurrentPaperServiceV1(
        gate=gate,
        config=config(),
        settings=api_settings,
        state_path=(
            tmp_path
            / (
                "paper-"
                + str(uuid4())
                + ".sqlite"
            )
        ),
        initialization_policy=(
            "NEW_ISOLATED_PAPER_ACCOUNT"
        ),
    )

    return (
        service,
        clock,
    )


def _record(
    *,
    sequence=20,
    event_time=(
        "2026-09-21T14:01:00.0000000Z"
    ),
):
    return {
        "schema":
            "arms.certified-native-live-closed.v1",
        "session":
            SESSION,
        "canonical_sequence":
            sequence,
        "event_time":
            event_time,
        "bar_time":
            "2026-09-21T14:01:00.0000000Z",
        "source_open":
            "2026-09-21T14:00:00+00:00",
        "open":
            10000.0,
        "high":
            10000.0,
        "low":
            10000.0,
        "close":
            10000.0,
        "volume":
            10,
        "handoff":
            "COMPLETE",
    }


def test_bridge_delivers_only_certified_closed_without_auto_enable(
    tmp_path,
    monkeypatch,
    api_settings,
):
    adapter, _ = _native(
        tmp_path,
        monkeypatch,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    adapter.live_handoff_records.append(
        _record()
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    result = bridge.poll()

    assert result["status"] == "LIVE"
    assert result["delivered_closed"] == 1
    assert result["paper_auto_enable"] is False
    assert result["live_execution_allowed"] is False
    assert result["native_order_authority"] is False
    assert result["order_submit_reachable"] is False

    paper = service.get_snapshot()

    assert (
        paper["market_data"]["closed_candles"]
        == 1
    )

    assert (
        paper["paper_execution_enabled"]
        is False
    )

    runtime = (
        service
        ._runtime
        ._paper
        .runtime
    )

    assert (
        runtime
        .lifecycle
        .broker_connector_v2
        .get_fills()
        == []
    )

    assert runtime.completed == []
    assert runtime.journal.trades == []

    again = bridge.poll()

    assert (
        again["delivered_closed"]
        == 1
    )

    assert (
        service
        .get_snapshot()[
            "market_data"
        ][
            "closed_candles"
        ]
        == 1
    )


def test_bridge_waits_for_complete_bootstrap_live_handoff(
    tmp_path,
    monkeypatch,
    api_settings,
):
    adapter, native = _native(
        tmp_path,
        monkeypatch,
        handoff="VERIFYING_OVERLAP",
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    adapter.live_handoff_records.append(
        _record()
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    result = bridge.poll()

    assert result["status"] == "WAITING"
    assert service._runtime is None
    assert (
        len(
            adapter.live_handoff_records
        )
        == 1
    )

    native[
        "live_handoff_status"
    ] = "COMPLETE"

    adapter.profile.handoff = "COMPLETE"

    result = bridge.poll()

    assert result["status"] == "LIVE"
    assert result["delivered_closed"] == 1
    assert service._runtime is not None


def test_stale_absolute_time_revokes_paper_before_financial_runtime(
    tmp_path,
    monkeypatch,
    api_settings,
):
    adapter, _ = _native(
        tmp_path,
        monkeypatch,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    clock[0] = (
        START
        + timedelta(
            minutes=3,
        )
    )

    adapter.live_handoff_records.append(
        _record()
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    with pytest.raises(
        ValueError,
        match=(
            "CERTIFIED_NATIVE_"
            "PAPER_BRIDGE_FAILED"
        ),
    ):
        bridge.poll()

    assert bridge.status == "REVOKED"

    assert (
        service.gate.fault
        == (
            "CERTIFIED_NATIVE_PAPER_"
            "BRIDGE_RECOVERY_REQUIRED"
        )
    )

    assert service._runtime is None


def test_native_revocation_never_delivers_queued_paper_event(
    tmp_path,
    monkeypatch,
    api_settings,
):
    adapter, native = _native(
        tmp_path,
        monkeypatch,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    adapter.live_handoff_records.append(
        _record()
    )

    adapter.status = "REVOKED"
    adapter.reason = "fixture"

    native["market_stream"] = "NOT_LIVE"
    native["transport_status"] = "NOT_LIVE"

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    with pytest.raises(ValueError):
        bridge.poll()

    assert service._runtime is None
    assert bridge.delivered_closed == 0


def test_fresh_adapter_handoff_queue_contains_only_finalized_live_closed(
    tmp_path,
):
    files = Files(
        tmp_path
        / "actual-native",
    )

    files.stream.qpc += 1

    adapter = FreshNativeAdapterV1(
        health_gated=False,
        directory=files.root,
        installed_exporter=EXPORTER,
        qpc_clock=lambda: (
            files.stream.epoch,
            1000,
            files.stream.qpc,
        ),
        live_handoff=True,
    )

    files.adapter = adapter

    adapter.poll()

    for _ in range(5):
        files.boundary()

    records = (
        adapter
        .drain_live_closed_records()
    )

    assert records

    assert all(
        record["schema"]
        == (
            "arms.certified-native-"
            "live-closed.v1"
        )
        for record in records
    )

    assert all(
        record["session"]
        == adapter.session
        for record in records
    )

    assert all(
        record["canonical_sequence"]
        >= 0
        for record in records
    )

    assert (
        adapter
        .drain_live_closed_records()
        == ()
    )

    adapter.close()


def test_bridge_source_has_no_native_order_or_account_surface():
    source = Path(
        "backend/backtesting/"
        "certified_native_paper_bridge_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "AtmStrategy",
        "EnterLong",
        "EnterShort",
    ):
        assert token not in source


def test_bootstrap_installation_creates_no_runtime_account_or_execution(
    tmp_path,
    monkeypatch,
    api_settings,
):
    bootstrap = _warm_bootstrap()

    adapter, _ = _native(
        tmp_path,
        monkeypatch,
        bootstrap=bootstrap,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    assert service._runtime is None
    assert service.gate.connected is False

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    assert bridge.status == "WAITING"
    assert service._runtime is None
    assert service.gate.connected is False

    snapshot = service.get_snapshot()

    assert snapshot["account_overview"] is None
    assert snapshot["strategy_bootstrap_mode"] == (
        "NONEXECUTING_CONTEXT_ONLY"
    )
    assert snapshot["strategy_bootstrap_sha256"] == bootstrap.sha256
    assert snapshot["strategy_bootstrap_bar_count"] == 120
    assert snapshot["strategy_bootstrap_execution_authority"] is False


def test_first_live_close_uses_bootstrap_context_without_bootstrap_execution(
    tmp_path,
    monkeypatch,
    api_settings,
):
    bootstrap = _warm_bootstrap()

    adapter, _ = _native(
        tmp_path,
        monkeypatch,
        bootstrap=bootstrap,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    adapter.live_handoff_records.append(
        _record()
    )

    result = bridge.poll()

    assert result["status"] == "LIVE"
    assert result["delivered_closed"] == 1

    runtime = service._runtime
    assert runtime is not None

    r = runtime._paper.runtime
    s = r.session

    # Only the one LIVE candle advances authoritative current accounting.
    assert r.index == 1
    assert runtime._cursor == 1

    # 120 bootstrap candles are analysis context only; the first LIVE
    # close is the only possible strategy evaluation.
    assert runtime.strategy_bootstrap_bar_count == 120
    assert runtime.strategy_bootstrap is bootstrap
    assert s.strategy_runner_v2.calls == 1

    # 1m strategy context remains bounded.
    assert len(s.candle_history) == s.analysis_window

    # Bootstrap has initialized complete HTF context before first LIVE decision.
    assert len(runtime._htf.history("15m")) == 8
    assert len(runtime._htf.history("1h")) == 2

    account = r.account.get_state()

    assert account["realized_pnl"] == 0
    assert account["daily_pnl"] == 0
    assert account["drawdown"] == 0
    assert account["open_positions"] == 0

    assert r.entries == {}
    assert r.completed == []
    assert r.journal.trades == []
    assert r.lifecycle.get_active_positions() == []
    assert (
        r.lifecycle
        .broker_connector_v2
        .get_fills()
        == []
    )

    snapshot = service.get_snapshot()

    assert snapshot["source_observations_processed"] == 1
    assert snapshot["strategy_bootstrap_mode"] == (
        "NONEXECUTING_CONTEXT_ONLY"
    )
    assert snapshot["strategy_bootstrap_sha256"] == bootstrap.sha256
    assert snapshot["strategy_bootstrap_bar_count"] == 120
    assert snapshot["strategy_bootstrap_execution_authority"] is False

    # PAPER stays disabled until a separate explicit control command.
    assert snapshot["paper_execution_enabled"] is False
    assert "PAPER_DISABLED" in snapshot["readiness_reasons"]


def test_bootstrap_overlap_with_first_live_open_fails_closed(
    tmp_path,
    monkeypatch,
    api_settings,
):
    bootstrap = _warm_bootstrap()

    bad_bar = BootstrapBar(
        "2026-09-21T14:01:00.0000000Z",
        10000.0,
        10000.0,
        10000.0,
        10000.0,
        10,
    )

    bad_bootstrap = CertifiedBootstrap(
        "2" * 64,
        bootstrap.bars
        + (bad_bar,),
        bootstrap.sessions,
        bootstrap.gap_count,
    )

    adapter, _ = _native(
        tmp_path,
        monkeypatch,
        bootstrap=bad_bootstrap,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    adapter.live_handoff_records.append(
        _record()
    )

    with pytest.raises(
        ValueError,
        match=(
            "CERTIFIED_NATIVE_"
            "PAPER_BRIDGE_FAILED"
        ),
    ):
        bridge.poll()

    assert bridge.status == "REVOKED"
    assert service._runtime is None

    assert service.gate.fault == (
        "CERTIFIED_NATIVE_PAPER_"
        "BRIDGE_RECOVERY_REQUIRED"
    )


def test_strategy_bootstrap_install_is_single_owner_and_pre_runtime_only(
    tmp_path,
    api_settings,
):
    service, _ = _paper(
        tmp_path,
        api_settings,
    )

    bootstrap = _warm_bootstrap()

    service.install_strategy_bootstrap(
        bootstrap
    )

    assert service._runtime is None

    with pytest.raises(
        RuntimeError,
        match="STRATEGY_BOOTSTRAP_INSTALL_NOT_FRESH",
    ):
        service.install_strategy_bootstrap(
            bootstrap
        )

    with pytest.raises(
        TypeError,
        match="CertifiedBootstrap",
    ):
        other, _ = _paper(
            tmp_path,
            api_settings,
        )

        other.install_strategy_bootstrap(
            object()
        )
