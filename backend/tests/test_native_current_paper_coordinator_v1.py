"""D4C native-current PAPER coordinator core tests.

No NinjaTrader process, broker, account discovery or LIVE execution.
"""

from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.backtesting.native_current_paper_coordinator_v1 import (
    NativeCurrentPaperCoordinatorV1,
)
from backend.market_data.analysis_startup_v1 import (
    AnalysisStartupV1,
)
from backend.tests.test_certified_native_paper_bridge_v1 import (
    SESSION,
    _hello,
    _paper,
    _record,
    _warm_bootstrap,
)
from backend.tests.test_fresh_native_adapter_sprint15y import (
    EXPORTER,
)
from backend.tests.test_preactivation_live_buffer_v1 import (
    write_valid_buffer,
)
from backend.tests.test_production_certified_outcome_v17 import (
    api_settings,
)


def _analysis_runtime(
    tmp_path,
    monkeypatch,
    *,
    sample_count=3,
    with_buffer=False,
):
    monkeypatch.setattr(
        "backend.market_data."
        "analysis_startup_v1."
        "live_process_start",
        lambda pid: 42 if pid else None,
    )

    now = [1000]

    bootstrap = _warm_bootstrap()

    runtime = AnalysisStartupV1(
        run_id=str(uuid4()),
        installed_exporter=EXPORTER,
        qpc_clock=lambda: (
            "coordinator-test",
            1000,
            now[0],
        ),
        bootstrap=bootstrap,
    )

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

    inbox = (
        tmp_path
        / (
            "analysis-"
            + str(uuid4())
        )
    )

    runtime.prepare(
        inbox
    )

    if with_buffer:
        write_valid_buffer(
            inbox
        )

    for _ in range(sample_count):
        now[0] += 1000

        runtime.poll()

        runtime.observe_waiting(
            runtime.health(),
            runtime.pid,
        )

    return (
        runtime,
        now,
        bootstrap,
    )


def _coordinator(
    tmp_path,
    monkeypatch,
    api_settings,
    *,
    sample_count=3,
    with_buffer=False,
):
    runtime, now, bootstrap = (
        _analysis_runtime(
            tmp_path,
            monkeypatch,
            sample_count=sample_count,
            with_buffer=with_buffer,
        )
    )

    service, wall = _paper(
        tmp_path,
        api_settings,
    )

    coordinator = (
        NativeCurrentPaperCoordinatorV1(
            analysis_runtime=runtime,
            service=service,
            wall_clock=lambda: wall[0],
        )
    )

    return (
        coordinator,
        runtime,
        service,
        wall,
        now,
        bootstrap,
    )


def _make_live(
    runtime,
    monkeypatch,
):
    adapter = runtime.adapter

    adapter.status = "LIVE_TAIL"
    adapter.reason = None
    adapter.session = SESSION
    adapter.hello = _hello()

    adapter.profile.session = SESSION
    adapter.profile.handoff = "COMPLETE"

    native_state = {
        "market_stream":
            "LIVE",
        "transport_status":
            "TRANSPORT_LIVE",
        "live_handoff_status":
            "COMPLETE",
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

    return adapter


class _L1:
    def __init__(self):
        self.terminated = False
        self.status = 'FRESH'
        self.closed = False
    def poll(self):
        return None
    def get_snapshot(self):
        if self.terminated:
            return {'status':'REVOKED','reason':'L1_STREAM_TERMINATED:FILE_IO_ERROR'}
        if self.status=='REVOKED':
            return {'status':'REVOKED','reason':'STREAM_OR_CONTEXT_INVALID',
                'first_failed_check':'SEQUENCE_GAP_OR_ROLLBACK'}
        return {'status':self.status,'reason':None,
            'ready':self.status=='FRESH','authority':self.status=='FRESH'}
    def close(self):
        self.closed = True


def test_preactivation_arm_success_and_analysis_remains_disabled(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, service, _, _, bootstrap = (
        _coordinator(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    adapter = runtime.adapter

    assert adapter.live_handoff_enabled is True

    assert adapter.activation_start is None
    assert adapter.status == "WAITING"
    assert adapter.session is None

    assert service._runtime is None

    assert (
        service._strategy_bootstrap
        is bootstrap
    )

    analysis = runtime.snapshot()

    assert analysis[
        "paper_entry_authority"
    ] == "DISABLED"

    assert analysis[
        "sim_execution_authority"
    ] == "DISABLED"

    assert analysis[
        "live_authority"
    ] is False

    assert analysis[
        "order_submit_reachable"
    ] is False

    snapshot = coordinator.get_snapshot()

    assert snapshot[
        "paper_auto_enable"
    ] is False

    assert snapshot[
        "paper_control_authority"
    ] is False

    assert snapshot[
        "native_order_authority"
    ] is False

    assert snapshot[
        "order_submit_reachable"
    ] is False


def test_valid_quarantined_preactivation_session_can_be_armed(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, service, _, _, _ = (
        _coordinator(
            tmp_path,
            monkeypatch,
            api_settings,
            with_buffer=True,
        )
    )

    adapter = runtime.adapter

    assert adapter.preactivation_session is not None
    assert adapter.session is None
    assert adapter.market is None
    assert adapter.timing is None
    assert adapter.sequence == -1

    assert adapter.live_handoff_enabled is True
    assert coordinator.status == "WAITING_FOR_ACTIVATION"
    assert service._runtime is None


def test_arm_after_activation_fails(
    tmp_path,
    monkeypatch,
):
    runtime, _, _ = _analysis_runtime(
        tmp_path,
        monkeypatch,
    )

    runtime.finish_health(
        backend_pid=runtime.pid,
        frontend_pid=99,
        dashboard_status=200,
        allow_activation=True,
    )

    assert runtime.adapter.activation_start is not None

    with pytest.raises(
        ValueError,
        match=(
            "LIVE_HANDOFF_ARM_REENTRY_"
            "OR_INVALID_STATE"
        ),
    ):
        runtime.adapter.arm_live_handoff()

    assert runtime.adapter.live_handoff_enabled is False


@pytest.mark.parametrize(
    "mutation",
    (
        "session",
        "queue",
    ),
)
def test_arm_with_bound_or_consumed_input_fails(
    tmp_path,
    monkeypatch,
    mutation,
):
    runtime, _, _ = _analysis_runtime(
        tmp_path,
        monkeypatch,
    )

    adapter = runtime.adapter

    if mutation == "session":
        adapter.session = str(
            uuid4()
        )
    else:
        adapter.queue.append(
            (
                b"fixture",
                0,
                0,
            )
        )

    with pytest.raises(
        ValueError,
        match=(
            "LIVE_HANDOFF_ARM_REENTRY_"
            "OR_INVALID_STATE"
        ),
    ):
        adapter.arm_live_handoff()

    assert adapter.live_handoff_enabled is False


def test_live_handoff_arm_is_one_shot(
    tmp_path,
    monkeypatch,
):
    runtime, _, _ = _analysis_runtime(
        tmp_path,
        monkeypatch,
    )

    adapter = runtime.adapter

    adapter.arm_live_handoff()

    assert adapter.live_handoff_enabled is True

    with pytest.raises(
        ValueError,
        match=(
            "LIVE_HANDOFF_ARM_REENTRY_"
            "OR_INVALID_STATE"
        ),
    ):
        adapter.arm_live_handoff()


def test_coordinator_requires_three_post_bootstrap_waiting_samples(
    tmp_path,
    monkeypatch,
    api_settings,
):
    runtime, _, _ = _analysis_runtime(
        tmp_path,
        monkeypatch,
        sample_count=2,
    )

    service, wall = _paper(
        tmp_path,
        api_settings,
    )

    with pytest.raises(
        ValueError,
        match="COORDINATOR_ATTACH_GATE",
    ):
        NativeCurrentPaperCoordinatorV1(
            analysis_runtime=runtime,
            service=service,
            wall_clock=lambda: wall[0],
        )

    assert runtime.adapter.live_handoff_enabled is False
    assert service._runtime is None


def test_coordinator_never_calls_analysis_runtime_poll(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, _, _, _, _ = (
        _coordinator(
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

    snapshot = coordinator.poll()

    assert snapshot["status"] == "WAITING_FOR_LIVE_TAIL"
    assert forbidden.call_count == 0


def test_coordinator_delivers_live_closed_without_auto_enable(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, service, _, _, _ = (
        _coordinator(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

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

    snapshot = coordinator.poll()

    assert snapshot["status"] == "LIVE"

    assert snapshot[
        "bridge"
    ][
        "delivered_closed"
    ] == 1

    paper = service.get_snapshot()

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


def test_l1_terminal_immediately_disables_and_journals_exact_reason(
    tmp_path,monkeypatch,api_settings,
):
    runtime, _, _ = _analysis_runtime(tmp_path,monkeypatch)
    service, wall = _paper(tmp_path,api_settings)
    l1 = _L1()
    coordinator = NativeCurrentPaperCoordinatorV1(
        analysis_runtime=runtime,service=service,
        wall_clock=lambda:wall[0],l1_reader=l1)
    runtime.finish_health(backend_pid=runtime.pid,frontend_pid=99,
        dashboard_status=200,allow_activation=True)
    adapter=_make_live(runtime,monkeypatch)
    adapter.live_handoff_records.append(_record())
    snapshot=coordinator.poll()
    assert service.publish_health(coordinator=snapshot,worker_alive=True)
    service._runtime.control('enable',request_id='request-id',
        request_nonce='nonce',initiating_path='OFFLINE_TEST',
        readiness_snapshot=service.get_snapshot())
    paper_runtime=service._runtime._paper.runtime
    assert service._runtime._enabled is True
    l1.terminated=True
    with pytest.raises(RuntimeError,match='L1_STREAM_TERMINATED:FILE_IO_ERROR'):
        coordinator.poll()
    paper=service.get_snapshot()
    assert paper['paper_execution_enabled'] is False
    assert paper['paper_authority_state']=='DISABLED_L1_TERMINATED'
    assert paper['fresh_authorization_session_required'] is True
    assert paper['latest_paper_authority_transition']['reason']==(
        'L1_STREAM_TERMINATED:FILE_IO_ERROR')
    assert paper['latest_paper_authority_transition']['initiating_path']==(
        'CURRENT_PAPER_L1_READER')
    assert paper['paper_authority_transition_count']==2
    assert paper_runtime.lifecycle.broker_connector_v2.get_fills()==[]
    assert paper_runtime.completed==[]


def test_l1_revocation_preserves_first_failed_check_in_coordinator_reason(
    tmp_path,monkeypatch,api_settings,
):
    runtime, _, _ = _analysis_runtime(tmp_path,monkeypatch)
    service, wall = _paper(tmp_path,api_settings)
    l1 = _L1();l1.status='REVOKED'
    coordinator = NativeCurrentPaperCoordinatorV1(
        analysis_runtime=runtime,service=service,
        wall_clock=lambda:wall[0],l1_reader=l1)
    expected=('L1_STREAM_REVOKED:STREAM_OR_CONTEXT_INVALID:'
        'SEQUENCE_GAP_OR_ROLLBACK')
    with pytest.raises(RuntimeError,match=expected):
        coordinator.poll()
    assert coordinator.reason==expected
    assert service._runtime is None


def test_l1_catching_up_waits_without_execution_authority_or_revocation(
    tmp_path,monkeypatch,api_settings,
):
    runtime, _, _ = _analysis_runtime(tmp_path,monkeypatch)
    service, wall = _paper(tmp_path,api_settings)
    l1 = _L1()
    coordinator = NativeCurrentPaperCoordinatorV1(
        analysis_runtime=runtime,service=service,
        wall_clock=lambda:wall[0],l1_reader=l1)
    runtime.finish_health(backend_pid=runtime.pid,frontend_pid=99,
        dashboard_status=200,allow_activation=True)
    adapter=_make_live(runtime,monkeypatch)
    adapter.live_handoff_records.append(_record())
    first=coordinator.poll()
    assert first['status']=='LIVE'
    assert service.publish_health(coordinator=first,worker_alive=True)
    service._runtime.control('enable',request_id='request-id',
        request_nonce='nonce',initiating_path='OFFLINE_TEST',
        readiness_snapshot=service.get_snapshot())
    paper_runtime=service._runtime._paper.runtime
    before=(paper_runtime.lifecycle.broker_connector_v2.get_orders(),
        paper_runtime.lifecycle.broker_connector_v2.get_fills(),
        list(paper_runtime.completed))
    l1.status='CATCHING_UP'
    waiting=coordinator.poll()
    paper=service.get_snapshot()
    assert waiting['status']=='WAITING_FOR_L1_CATCHUP'
    assert waiting['reason'] is None
    assert waiting['l1']['ready'] is False
    assert waiting['l1']['authority'] is False
    assert coordinator.status!='REVOKED'
    assert paper['paper_execution_enabled'] is False
    assert paper['fresh_authorization_session_required'] is True
    assert paper['latest_paper_authority_transition']['reason']=='L1_CATCHING_UP'
    assert (paper_runtime.lifecycle.broker_connector_v2.get_orders(),
        paper_runtime.lifecycle.broker_connector_v2.get_fills(),
        list(paper_runtime.completed))==before


def test_analysis_failure_fails_closed_without_analysis_poll(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, service, _, _, _ = (
        _coordinator(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    runtime.revoke(
        "fixture-analysis-failure"
    )

    with pytest.raises(
        RuntimeError,
        match="ANALYSIS_RUNTIME_UNAVAILABLE",
    ):
        coordinator.poll()

    assert coordinator.status == "REVOKED"
    assert service._stopped is True

    assert service.gate.fault == (
        "NATIVE_CURRENT_PAPER_"
        "COORDINATOR_RECOVERY_REQUIRED"
    )

    assert service._runtime is None


def test_close_is_idempotent_and_does_not_close_analysis_runtime(
    tmp_path,
    monkeypatch,
    api_settings,
):
    coordinator, runtime, service, _, _, _ = (
        _coordinator(
            tmp_path,
            monkeypatch,
            api_settings,
        )
    )

    coordinator.close()
    coordinator.close()

    assert coordinator.status == "STOPPED"
    assert coordinator.stopped is True

    assert service._stopped is True

    # Analysis runtime is a separate owner.
    assert runtime.phase == "VERIFYING_WAITING"
    assert runtime.reason is None
    assert runtime.adapter.status == "WAITING"


def test_native_order_surface_remains_absent():
    sources = "\n".join(
        Path(name).read_text(
            encoding="utf-8"
        )
        for name in (
            "backend/market_data/"
            "fresh_native_adapter_v1.py",
            "backend/backtesting/"
            "native_current_paper_coordinator_v1.py",
        )
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
        assert token not in sources
