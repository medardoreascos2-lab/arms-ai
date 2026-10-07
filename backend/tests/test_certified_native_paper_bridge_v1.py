"""D3A certified native CLOSED-bar -> LOCAL PAPER bridge tests.

No NinjaTrader process, native account, external broker or LIVE execution.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.backtesting.certified_native_paper_bridge_v1 import (
    CertifiedNativePaperBridgeV1,
    PENDING_CLOSED_LIMIT,
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
    CurrentMarketEventV1,
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
    *,
    start=START,
):
    bars = []

    first_label = (
        start
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
    *,
    start=START,
):
    clock = [
        start
        + timedelta(
            minutes=1,
            seconds=1,
        )
    ]

    days = frozenset(
        start.date()
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
        start - timedelta(days=3),
        start + timedelta(days=10),
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


def test_native_handoff_attaches_closure_proof_without_changing_event_time(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _ = _native(tmp_path, monkeypatch)
    service, clock = _paper(tmp_path, api_settings)
    source = "2026-09-21T14:00:59.9997804Z"
    adapter.live_handoff_records.append(_record(event_time=source))
    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter, service=service, wall_clock=lambda: clock[0])
    delivered = []
    original = service.ingest

    def capture(event):
        delivered.append(event)
        return original(event)

    monkeypatch.setattr(service, "ingest", capture)
    result = bridge.poll()
    assert result["delivered_closed"] == 1
    assert len(delivered) == 1
    assert delivered[0].closed_boundary_proof is not None
    assert delivered[0].event_time.isoformat() == "2026-09-21T14:00:59.999780+00:00"
    assert service.gate.closed_count == 1
    assert service.get_snapshot()["paper_execution_enabled"] is False
    runtime = service._runtime._paper.runtime
    assert runtime.journal.trades == []
    assert runtime.lifecycle.broker_connector_v2.get_fills() == []


@pytest.mark.parametrize("bad_record", [
    {"handoff": "VERIFYING_OVERLAP"},
    {"schema": "arms.nt.market.v1"},
    {"kind": "FORMING"},
    {"kind": "RAW_EVENT"},
])
def test_bridge_never_certifies_nonhandoff_or_nonclosed_record(
    tmp_path, monkeypatch, api_settings, bad_record,
):
    adapter, _ = _native(tmp_path, monkeypatch)
    service, clock = _paper(tmp_path, api_settings)
    adapter.live_handoff_records.append(dict(_record(), **bad_record))
    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter, service=service, wall_clock=lambda: clock[0])
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert bridge.delivered_closed == 0
    assert service._runtime is None
    assert "PAPER_DISABLED" in service.get_snapshot()["readiness_reasons"]


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


@pytest.mark.parametrize("event_time, clock_offset", [
    ("2026-09-21T14:01:00.0000000Z", timedelta(minutes=3)),
    ("2026-09-21T14:01:02.0000000Z", timedelta(minutes=1, seconds=1)),
    ("not-an-instant", timedelta(minutes=1, seconds=1)),
])
def test_unproven_recency_blocks_without_terminating_and_fresh_recovers(
    tmp_path,
    monkeypatch,
    api_settings,
    event_time,
    clock_offset,
):
    adapter, _ = _native(
        tmp_path,
        monkeypatch,
    )

    service, clock = _paper(
        tmp_path,
        api_settings,
    )

    clock[0] = START + clock_offset

    adapter.live_handoff_records.append(
        _record(event_time=event_time)
    )

    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter,
        service=service,
        wall_clock=lambda: clock[0],
    )

    blocked = bridge.poll()
    assert blocked["status"] == "RECENCY_BLOCKED"
    assert blocked["recency_status"] == "UNPROVEN"
    assert blocked["recency_rejection_reason"] == "ABSOLUTE_RECENCY_UNPROVEN"
    assert blocked["rejected_recency_events"] == 1
    assert bridge.reason is None
    assert service.gate.fault is None
    assert service._runtime is None
    assert "PAPER_DISABLED" in service.get_snapshot()["readiness_reasons"]
    assert service.get_snapshot()["live_execution_allowed"] is False

    label = START + timedelta(minutes=2)
    clock[0] = label + timedelta(seconds=1)
    adapter.live_handoff_records.append(_record_for(
        label, 34, event_time="2026-09-21T14:02:00.0000000Z"))
    recovered = bridge.poll()
    assert recovered["status"] == "LIVE"
    assert recovered["recency_status"] == "PROVEN"
    assert recovered["delivered_closed"] == 1
    paper = service.get_snapshot()
    assert paper["source_observations_processed"] == 1
    assert paper["paper_execution_enabled"] is False
    runtime = service._runtime._paper.runtime
    assert runtime.lifecycle.broker_connector_v2.get_orders() == []
    assert runtime.lifecycle.broker_connector_v2.get_fills() == []
    assert runtime.completed == []
    counts = service._runtime._db.execute(
        "SELECT count(*), count(distinct canonical_observation_id) "
        "FROM decision_trace"
    ).fetchone()
    assert counts[0] == counts[1]


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


def _record_for(label, sequence, *, event_time=None):
    value = _record(sequence=sequence)
    value["bar_time"] = label.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
    value["source_open"] = (label - timedelta(minutes=1)).isoformat()
    value["event_time"] = event_time or value["bar_time"]
    return value


def _pending_bridge(tmp_path, monkeypatch, api_settings, *, start=START):
    adapter, native = _native(
        tmp_path, monkeypatch, bootstrap=_warm_bootstrap(start=start))
    service, clock = _paper(tmp_path, api_settings, start=start)
    bridge = CertifiedNativePaperBridgeV1(
        adapter=adapter, service=service, wall_clock=lambda: clock[0])
    return adapter, native, service, clock, bridge


def _assert_disabled_and_empty(service):
    snapshot = service.get_snapshot()
    assert snapshot["live_execution_allowed"] is False
    if service._runtime is None:
        assert "PAPER_DISABLED" in snapshot["readiness_reasons"]
        assert snapshot["account_overview"] is None
    else:
        assert snapshot["paper_execution_enabled"] is False
        runtime = service._runtime._paper.runtime
        assert runtime.journal.trades == []
        assert runtime.lifecycle.broker_connector_v2.get_fills() == []
        assert runtime.lifecycle.get_active_positions() == []


def test_real_third_run_early_close_is_retained_until_exact_boundary(
    tmp_path, monkeypatch, api_settings,
):
    start = datetime(2026, 10, 1, 14, 22, tzinfo=UTC)
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings, start=start)
    delivered = []
    original_ingest = service.ingest

    def capture(event):
        delivered.append(event)
        return original_ingest(event)

    monkeypatch.setattr(service, "ingest", capture)
    source = (
        (48, 23, "2026-10-01T14:22:59.9156229Z"),
        (62, 24, "2026-10-01T14:23:59.9840900Z"),
        (76, 25, "2026-10-01T14:24:59.9062058Z"),
    )
    for sequence, minute, emitted in source[:2]:
        label = start.replace(minute=minute)
        adapter.live_handoff_records.append(
            _record_for(label, sequence, event_time=emitted))
        clock[0] = label + timedelta(milliseconds=50)
        bridge.poll()

    assert bridge.delivered_closed == 2
    assert service.get_snapshot()["source_observations_processed"] == 2
    assert service.get_snapshot()["canonical_time"] == (
        "2026-10-01T14:24:00+00:00")

    label = start.replace(minute=25)
    adapter.live_handoff_records.append(
        _record_for(label, 76, event_time=source[2][2]))
    clock[0] = label - timedelta(milliseconds=50)
    snapshot = bridge.poll()
    assert snapshot["status"] == "LIVE"
    assert bridge.delivered_closed == 2
    assert len(bridge.pending_closed_records) == 1
    assert adapter.drain_live_closed_records() == ()
    assert service.get_snapshot()["source_observations_processed"] == 2
    assert delivered[-1].sequence == 1
    _assert_disabled_and_empty(service)

    clock[0] = label
    snapshot = bridge.poll()
    assert snapshot["status"] == "LIVE"
    assert bridge.delivered_closed == 3
    assert len(bridge.pending_closed_records) == 0
    assert service.get_snapshot()["source_observations_processed"] == 3
    assert service.get_snapshot()["canonical_time"] == (
        "2026-10-01T14:25:00+00:00")
    assert delivered[-1].event_time == datetime(
        2026, 10, 1, 14, 24, 59, 906205, tzinfo=UTC)
    assert delivered[-1].received_at == label
    assert delivered[-1].closed_boundary_proof is not None
    assert delivered[-1].event_id == SESSION + ":76"
    assert [event.sequence for event in delivered] == [0, 1, 2]
    assert snapshot["paper_auto_enable"] is False
    assert snapshot["native_order_authority"] is False
    assert snapshot["ninjatrader_account_access"] is False
    _assert_disabled_and_empty(service)


@pytest.mark.parametrize("delay", [timedelta(0), timedelta(microseconds=1),
                                   timedelta(milliseconds=50)])
def test_pending_early_close_admits_at_or_after_exact_boundary(
    tmp_path, monkeypatch, api_settings, delay,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    source = "2026-09-21T14:00:59.9062058Z"
    record = _record_for(label, 20, event_time=source)
    adapter.live_handoff_records.append(record)
    clock[0] = label - timedelta(microseconds=1)
    bridge.poll()
    assert bridge.status == "LIVE" and bridge.reason is None
    assert bridge.delivered_closed == 0
    assert service._runtime is None
    assert len(bridge.pending_closed_records) == 1
    assert bridge.pending_closed_records[0] == record

    clock[0] = label + delay
    bridge.poll()
    assert bridge.delivered_closed == 1
    assert not bridge.pending_closed_records
    assert service.gate.last_event_time == datetime(
        2026, 9, 21, 14, 0, 59, 906205, tzinfo=UTC)
    assert service.gate.last_received == clock[0]
    _assert_disabled_and_empty(service)


def test_ordinary_closed_does_not_defer(tmp_path, monkeypatch, api_settings):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    adapter.live_handoff_records.append(_record_for(label, 20))
    clock[0] = label + timedelta(microseconds=1)
    bridge.poll()
    assert bridge.delivered_closed == 1
    assert not bridge.pending_closed_records
    assert service.gate.last_event_time == label
    _assert_disabled_and_empty(service)


@pytest.mark.parametrize("change", [
    "DISCONNECTED", "REVOKED", "SESSION", "METADATA", "METADATA_BYTES",
    "HANDOFF", "TIMING",
])
def test_pending_source_change_fails_closed(
    tmp_path, monkeypatch, api_settings, change,
):
    adapter, native, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    adapter.live_handoff_records.append(_record_for(
        label, 20, event_time="2026-09-21T14:00:59.9000000Z"))
    clock[0] = label - timedelta(milliseconds=50)
    bridge.poll()
    if change in ("DISCONNECTED", "REVOKED"):
        adapter.status = change
        adapter.reason = "fixture"
    elif change == "SESSION":
        adapter.session = "changed-session"
        adapter.profile.session = "changed-session"
    elif change == "METADATA":
        adapter.hello = b"invalid-metadata"
    elif change == "METADATA_BYTES":
        adapter.hello += b" "  # Same parsed fields, changed source identity.
        assert bridge._metadata()["provider"] == "Provider31"
    elif change == "HANDOFF":
        native["live_handoff_status"] = "VERIFYING_OVERLAP"
    else:
        native["timing_pair_status"] = "WAITING"
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert bridge.status == "REVOKED"
    assert not bridge.pending_closed_records
    assert bridge.delivered_closed == 0
    assert service._runtime is None
    _assert_disabled_and_empty(service)


def test_pending_staleness_fails_closed(tmp_path, monkeypatch, api_settings):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    adapter.live_handoff_records.append(_record_for(
        label, 20, event_time="2026-09-21T14:00:59.9000000Z"))
    clock[0] = label - timedelta(milliseconds=50)
    bridge.poll()
    clock[0] = label + timedelta(
        seconds=service.gate.maximum_age + 1)
    blocked = bridge.poll()
    assert blocked["status"] == "RECENCY_BLOCKED"
    assert blocked["recency_rejection_reason"] == "ABSOLUTE_RECENCY_UNPROVEN"
    assert not bridge.pending_closed_records
    assert service._runtime is None


@pytest.mark.parametrize("bad_field", [
    {"schema": "arms.nt.market.v1"},
    {"session": "foreign-session"},
    {"handoff": "VERIFYING_OVERLAP"},
    {"source_open": "2026-09-21T13:59:00+00:00"},
    {"canonical_sequence": True},
])
def test_malformed_early_delivery_fails_before_deferral(
    tmp_path, monkeypatch, api_settings, bad_field,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    clock[0] = label - timedelta(milliseconds=50)
    record = _record_for(
        label, 20, event_time="2026-09-21T14:00:59.9000000Z")
    adapter.live_handoff_records.append(dict(record, **bad_field))
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert bridge.status == "REVOKED"
    assert not bridge.pending_closed_records
    assert bridge.delivered_closed == 0
    assert service._runtime is None


def test_pending_queue_bound_and_sequence_conflict_fail_closed(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    assert PENDING_CLOSED_LIMIT == 1024
    label = START + timedelta(minutes=1)
    record = _record_for(
        label, 20, event_time="2026-09-21T14:00:59.9000000Z")
    clock[0] = label - timedelta(milliseconds=50)
    adapter.live_handoff_records.append(record)
    bridge.poll()
    adapter.live_handoff_records.append(dict(record))
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert service._runtime is None

    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    clock[0] = label - timedelta(milliseconds=50)
    bridge.pending_closed_records.extend(
        dict(record) for _ in range(PENDING_CLOSED_LIMIT))
    adapter.live_handoff_records.append(record)
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert bridge.status == "REVOKED"
    assert not bridge.pending_closed_records
    assert service._runtime is None


def test_consecutive_early_closes_retry_without_overtake(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    delivered = []
    original_ingest = service.ingest

    def capture(event):
        delivered.append(event.event_id)
        return original_ingest(event)

    monkeypatch.setattr(service, "ingest", capture)
    for sequence, minute in ((20, 1), (34, 2), (48, 3)):
        label = START + timedelta(minutes=minute)
        adapter.live_handoff_records.append(_record_for(
            label, sequence,
            event_time=(label - timedelta(milliseconds=100)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ")))
        clock[0] = label - timedelta(milliseconds=50)
        bridge.poll()
        assert len(bridge.pending_closed_records) == 1
        assert bridge.delivered_closed == len(delivered) == minute - 1
        clock[0] = label
        bridge.poll()
        assert not bridge.pending_closed_records
        assert bridge.delivered_closed == len(delivered) == minute
    assert delivered == [SESSION + ":20", SESSION + ":34", SESSION + ":48"]
    _assert_disabled_and_empty(service)


def test_multiple_drained_records_keep_fifo_order(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    # Isolate bridge ordering; no PAPER runtime or financial operation is made.
    seen = []
    monkeypatch.setattr(service, "ingest", lambda event: seen.append(event.event_id))
    first = START + timedelta(minutes=1)
    second = first + timedelta(minutes=1)
    adapter.live_handoff_records.extend((
        _record_for(first, 20, event_time="2026-09-21T14:01:59.9000000Z"),
        _record_for(second, 34, event_time="2026-09-21T14:01:59.9500000Z"),
    ))
    clock[0] = second + timedelta(milliseconds=50)
    bridge.poll()
    assert seen == [SESSION + ":20", SESSION + ":34"]
    assert bridge.delivered_closed == 2
    assert bridge.last_source_sequence == 34
    assert not bridge.pending_closed_records
    assert service._runtime is None
    _assert_disabled_and_empty(service)


def test_later_record_cannot_overtake_future_head(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    seen = []
    monkeypatch.setattr(service, "ingest", lambda event: seen.append(event.event_id))
    first = START + timedelta(minutes=2)
    second = first + timedelta(minutes=1)
    clock[0] = first - timedelta(milliseconds=50)
    adapter.live_handoff_records.append(_record_for(
        first, 20, event_time="2026-09-21T14:01:59.9000000Z"))
    bridge.poll()
    adapter.live_handoff_records.append(_record_for(
        second, 34, event_time="2026-09-21T14:01:59.9000000Z"))
    bridge.poll()
    assert seen == []
    assert [r["canonical_sequence"] for r in bridge.pending_closed_records] == [20, 34]

    clock[0] = first
    bridge.poll()
    assert seen == [SESSION + ":20"]
    assert [r["canonical_sequence"] for r in bridge.pending_closed_records] == [34]
    clock[0] = second
    blocked = bridge.poll()  # The second record is stale; it must not overtake or ingest.
    assert blocked["status"] == "RECENCY_BLOCKED"
    assert seen == [SESSION + ":20"]
    assert bridge.status == "RECENCY_BLOCKED"
    assert not bridge.pending_closed_records
    assert service._runtime is None
    _assert_disabled_and_empty(service)


def test_pending_sequence_integrity_is_revalidated(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    clock[0] = label - timedelta(milliseconds=50)
    adapter.live_handoff_records.append(_record_for(
        label, 20, event_time="2026-09-21T14:00:59.9000000Z"))
    bridge.poll()
    bridge.pending_closed_records[0]["canonical_sequence"] = -1
    clock[0] = label
    with pytest.raises(ValueError, match="CERTIFIED_NATIVE_PAPER_BRIDGE_FAILED"):
        bridge.poll()
    assert bridge.status == "REVOKED"
    assert not bridge.pending_closed_records
    assert service._runtime is None


def test_forged_proof_cannot_use_deferred_path(
    tmp_path, monkeypatch, api_settings,
):
    adapter, _, service, clock, bridge = _pending_bridge(
        tmp_path, monkeypatch, api_settings)
    label = START + timedelta(minutes=1)
    record = _record_for(label, 20, event_time="2026-09-21T14:00:59.9000000Z")
    clock[0] = label
    event, _ = bridge._validated_events((record,), now=clock[0])[0]
    assert type(event) is CurrentMarketEventV1
    service.gate.connection(True)
    with pytest.raises(ValueError, match="INVALID_CLOSED_PROVENANCE"):
        service.gate.admit(replace(
            event, closed_boundary_proof="CERTIFIED_NATIVE_SAME_CALLBACK_CLOSED"))
    assert service._runtime is None
