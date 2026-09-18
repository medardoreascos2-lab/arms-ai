"""CLI startup exercises real PAPER recovery owners; external pipeline is inert."""
from types import SimpleNamespace
from unittest.mock import Mock
import json

import pytest

import backend.main as main_module
from backend.config_settings import ArmsSettings
from backend.services.graceful_shutdown_service_v2 import GracefulShutdownServiceV2
from backend.services.runtime_lifecycle_manager_v2 import RuntimeLifecycleManagerV2
from backend.tests.test_durable_crash_recovery_v2 import build_runtime, comparable, run_crash
from backend.tests.test_main_runtime_integration import (
    configure_fakes, FakeLifecycleManager, FakeArmsCore, FakeMarketConnector, FakePipeline,
)


@pytest.mark.parametrize("action,expected_count,expected_pnl,pipeline_failure", [
    (None, 0, 0, False),
    ("open", 1, 0, False),
    ("window_after_pending", 0, 0, False),
    ("window_before_committed", 1, 0, False),
    ("loss", 0, -40, False),
    ("open", 1, 0, True),
])
def test_cli_recovers_before_pipeline_and_shuts_down(
    tmp_path, monkeypatch, action, expected_count, expected_pnl, pipeline_failure,
):
    path = tmp_path / "cli-state.json"
    if action:
        run_crash(path, action)
    lifecycle, account, store, recovery, startup = build_runtime()
    manager = RuntimeLifecycleManagerV2(
        startup_coordinator=startup,
        graceful_shutdown_service=GracefulShutdownServiceV2(execution_state_store=store),
    )
    context = SimpleNamespace(startup_coordinator=startup, runtime_lifecycle_manager=manager)
    configure_fakes(monkeypatch, FakeLifecycleManager())
    settings = ArmsSettings(runtime_snapshot_path=str(path))
    monkeypatch.setattr(main_module, "ArmsSettings", lambda: settings)
    factory = Mock(return_value=context)
    monkeypatch.setattr(main_module, "build_runtime_context", factory)
    events = []

    def trace(owner, name, label):
        original = getattr(owner, name)
        def call(*args, **kwargs):
            events.append(label)
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, name, call)

    trace(recovery, "pending_reconciliation_required", "applicability")
    trace(recovery, "reconcile_pending_from", "reconcile")
    trace(recovery, "recover_from", "recover")
    trace(store._durability, "enable", "enable")
    guards = []
    for owner, names in [
        (lifecycle.broker_connector_v2, ("submit_order", "close_position", "close_partial")),
        (lifecycle.trade_journal_v2, ("record_open_trade", "close_trade")),
        (account, ("update_from_portfolio",)),
    ]:
        for name in names:
            guard = Mock(side_effect=AssertionError("Recovery replayed execution/accounting"))
            monkeypatch.setattr(owner, name, guard)
            guards.append(guard)

    def pipeline(self, *, initial_context):
        events.append("pipeline")
        assert manager.get_status() == "RUNNING"
        assert store._durability.enabled is True
        assert len(lifecycle.get_active_positions()) == expected_count
        assert account.get_state()["realized_pnl"] == expected_pnl
        assert account.get_state()["daily_pnl"] == expected_pnl
        assert account.get_state()["trading_blocked"] is (action == "loss")
        if pipeline_failure:
            raise RuntimeError("pipeline failure")

    monkeypatch.setattr(FakePipeline, "run", pipeline)
    try:
        if pipeline_failure:
            with pytest.raises(RuntimeError, match="pipeline failure"):
                main_module.main()
        else:
            main_module.main()
        factory.assert_called_once_with(settings=settings)
        expected = ["enable", "pipeline"] if action is None else ["applicability"] + (
            ["reconcile"] if action.startswith("window_") else []
        ) + ["recover", "enable", "pipeline"]
        assert events == expected
        assert manager.get_status() == "STOPPED"
        assert store._durability.enabled is False
        assert store._durability._lease is None
        saved = json.loads(path.read_text())
        assert saved["durability"]["phase"] == "COMMITTED"
        assert saved["durability"]["generation"] >= 2
        assert comparable(store.load_from_file(file_path=path)) == comparable(store.capture_state())
        for guard in guards:
            guard.assert_not_called()
    finally:
        store._durability.release()


def test_cli_actual_runtime_factory_clean_start_and_restart(runtime, tmp_path, monkeypatch):
    from backend.services.runtime_context_v2 import build_runtime_context

    configure_fakes(monkeypatch, FakeLifecycleManager())
    settings = ArmsSettings(runtime_snapshot_path=str(tmp_path / "actual-factory.json"))
    monkeypatch.setattr(main_module, "ArmsSettings", lambda: settings)
    contexts = []

    def factory(*, settings):
        context = build_runtime_context(settings=settings)
        contexts.append(context)
        return context

    monkeypatch.setattr(main_module, "build_runtime_context", factory)

    def pipeline(self, *, initial_context):
        context = contexts[-1]
        assert context.runtime_lifecycle_manager.get_status() == "RUNNING"
        assert context.runtime_lifecycle_manager.startup_coordinator is context.startup_coordinator
        assert context.startup_coordinator.state_recovery_service is context.state_recovery_service
        assert context.state_recovery_service.execution_state_store is context.execution_state_store
        assert context.execution_state_store._durability.enabled is True
        assert context.startup_coordinator.get_startup_report()["mode"] == (
            "CLEAN" if len(contexts) == 1 else "RECOVERY"
        )

    monkeypatch.setattr(FakePipeline, "run", pipeline)
    try:
        for _ in range(2):
            main_module.main()
            context = contexts[-1]
            assert context.runtime_lifecycle_manager.get_status() == "STOPPED"
            assert context.execution_state_store._durability._lease is None
            assert context.trade_lifecycle_service.get_active_positions() == []
            assert context.trade_lifecycle_service.broker_connector_v2.get_fills() == []
        assert contexts[0] is not contexts[1]
    finally:
        for context in contexts:
            context.execution_state_store._durability.release()


@pytest.mark.parametrize("action", ["pending", "pending_open", "pending_loss", "corrupt"])
def test_cli_unsafe_recovery_never_enters_pipeline_or_shutdown(tmp_path, monkeypatch, action):
    path = tmp_path / "cli-state.json"
    run_crash(path, "open" if action == "corrupt" else action)
    if action == "corrupt":
        path.write_text('{"checksum":"invalid"}')
    before = path.read_bytes()
    lifecycle, account, store, recovery, startup = build_runtime()
    manager = RuntimeLifecycleManagerV2(
        startup_coordinator=startup,
        graceful_shutdown_service=GracefulShutdownServiceV2(execution_state_store=store),
    )
    configure_fakes(monkeypatch, FakeLifecycleManager())
    monkeypatch.setattr(main_module, "ArmsSettings", lambda: ArmsSettings(runtime_snapshot_path=str(path)))
    monkeypatch.setattr(main_module, "build_runtime_context", lambda **kw: SimpleNamespace(
        startup_coordinator=startup, runtime_lifecycle_manager=manager,
    ))
    shutdown = Mock(wraps=manager.shutdown_to)
    enable = Mock(wraps=store._durability.enable)
    recover = Mock(wraps=recovery.recover_from)
    monkeypatch.setattr(manager, "shutdown_to", shutdown)
    monkeypatch.setattr(store._durability, "enable", enable)
    monkeypatch.setattr(recovery, "recover_from", recover)
    try:
        error, message = (ValueError, "checksum") if action == "corrupt" else (RuntimeError, "did not resolve")
        with pytest.raises(error, match=message):
            main_module.main()
        assert manager.get_status() == startup.get_status() == "FAILED"
        assert account.get_state()["trading_blocked"] is True
        assert store._durability.failed is True
        assert store._durability.enabled is False
        assert store._durability._lease is None
        assert path.read_bytes() == before
        shutdown.assert_not_called()
        enable.assert_not_called()
        recover.assert_not_called()
        assert FakeArmsCore.started is False
        assert FakeMarketConnector.connected is False
        assert FakePipeline.received_context is None
        assert FakePipeline.received_stages is None
    finally:
        store._durability.release()
