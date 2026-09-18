"""Canonical composition and execution ownership across production entry points."""
from unittest.mock import Mock

import pytest

from backend.tests.test_account_runtime_transition_v2 import hosted, switch
from backend.tests.test_account_switch_safety_containment_v2 import submit


def assert_runtime_graph(runtime):
    lifecycle = runtime.trade_lifecycle_service
    store = runtime.execution_state_store
    assert lifecycle.execution_manager is runtime.execution_manager
    assert lifecycle.paper_execution_engine is runtime.paper_execution_engine
    assert lifecycle.broker_connector_v2.execution_engine is runtime.paper_execution_engine
    assert lifecycle.position_manager is runtime.position_manager
    assert lifecycle.trade_history_manager is runtime.trade_history_manager
    assert lifecycle.risk_manager_v2 is runtime.risk_manager_v2
    assert lifecycle.portfolio_manager_v2 is runtime.portfolio_manager_v2
    assert runtime.portfolio_manager_v2.account_state_manager_v2 is runtime.account_state_manager_v2
    assert lifecycle.protective_order_registry_v2 is runtime.protective_order_registry is store.protective_order_registry
    assert lifecycle.oco_manager_v2 is runtime.oco_manager is store.oco_manager
    assert store.trade_lifecycle_service is lifecycle
    assert runtime.state_recovery_service.execution_state_store is store
    assert runtime.startup_coordinator.state_recovery_service is runtime.state_recovery_service
    assert runtime.graceful_shutdown_service.execution_state_store is store
    assert runtime.runtime_lifecycle_manager.startup_coordinator is runtime.startup_coordinator
    assert runtime.runtime_lifecycle_manager.graceful_shutdown_service is runtime.graceful_shutdown_service
    for owner in (lifecycle, runtime.execution_manager, runtime.paper_execution_engine,
                  lifecycle.broker_connector_v2, runtime.portfolio_manager_v2,
                  runtime.account_state_manager_v2, lifecycle.trade_journal_v2):
        assert owner._durability is store._durability


def assert_application_graph(app, runtime):
    assert_runtime_graph(runtime)
    state = app.state
    lifecycle = runtime.trade_lifecycle_service
    assert state.trade_lifecycle_service_v2 is lifecycle
    assert state.account_state_manager_v2 is runtime.account_state_manager_v2
    assert state.portfolio_manager_v2 is runtime.portfolio_manager_v2
    assert state.trade_journal_v2 is lifecycle.trade_journal_v2
    assert state.execution_risk_gate_v1 is lifecycle.execution_risk_gate_v1
    assert state.live_position_monitor_v2.trade_lifecycle_service is lifecycle
    assert state.live_position_monitor_v2.portfolio_manager_v2 is runtime.portfolio_manager_v2
    assert state.price_feed_service_v2.live_position_monitor_v2 is state.live_position_monitor_v2
    assert state.broker_connector_v2 is lifecycle.broker_connector_v2
    assert state.execution_manager_v2 is runtime.execution_manager
    assert state.paper_execution_engine_v2 is runtime.paper_execution_engine


def test_standalone_api_delegates_core_composition(runtime, monkeypatch):
    from backend.api.app import create_app
    from backend.services import runtime_context_v2 as factory
    builder = Mock(wraps=factory.build_runtime_context)
    monkeypatch.setattr(factory, "build_runtime_context", builder)
    app = create_app(account_config_manager_v2=runtime.safety._managers[0])
    builder.assert_called_once()
    context = app.state.runtime_context_v2
    assert_application_graph(app, context)
    assert app.state.account_switch_safety_v2 is context.account_switch_safety_v2
    assert context.trade_lifecycle_service.exposure_manager_v2 is not None
    assert context.trade_lifecycle_service.portfolio_risk_engine_v2 is not None
    assert context.trade_lifecycle_service.order_validation_engine_v2 is not None


def test_injected_api_preserves_core_instances(runtime):
    from backend.api.app import create_app
    app = create_app(runtime_context=runtime.context, account_config_manager_v2=runtime.safety._managers[0])
    assert_application_graph(app, runtime.context)


def test_coordinated_account_publications_share_one_core_graph(hosted):
    source = hosted.c.published
    assert_application_graph(source.application, source.runtime)
    assert switch(hosted, "B").status_code == 200
    target = hosted.c.published
    assert_application_graph(target.application, target.runtime)
    assert source.runtime.trade_lifecycle_service is not target.runtime.trade_lifecycle_service
    assert source.runtime.execution_state_store._durability.retired
    assert target.generation > source.generation


@pytest.mark.parametrize("condition", ["daily", "foreign", "failed", "switching", "retired"])
def test_safety_authority_precedes_broker_and_simulator(runtime, monkeypatch, condition):
    context = runtime.context
    account = context.account_state_manager_v2
    durability = context.execution_state_store._durability
    if condition == "daily": account.record_daily_pnl(daily_pnl=-account.maximum_daily_loss)
    elif condition == "foreign":
        account._state["trading_blocked"] = True
        account._state["blocking_reasons"] = ["ownership-safety-block"]
    else:
        monkeypatch.setattr(durability, "account_switch_in_progress" if condition == "switching" else condition, True)
    guards = [Mock(side_effect=AssertionError("Safety bypass")) for _ in range(3)]
    monkeypatch.setattr(context.execution_manager, "prepare_order", guards[0])
    monkeypatch.setattr(context.trade_lifecycle_service.broker_connector_v2, "submit_order", guards[1])
    monkeypatch.setattr(context.paper_execution_engine, "execute", guards[2])
    try: result = submit(runtime)
    except RuntimeError: assert condition == "failed"
    else: assert result["accepted"] is False
    for guard in guards: guard.assert_not_called()


def test_api_custom_paper_settings_reach_canonical_owners(runtime):
    from backend.api.app import APISettings, create_app
    settings = APISettings(maximum_open_positions=3,
        paper_execution_fill_market_orders_immediately=False,
        paper_execution_slippage_points=.75)
    app = create_app(settings=settings, account_config_manager_v2=runtime.safety._managers[0])
    context = app.state.runtime_context_v2
    assert_application_graph(app, context)
    assert context.risk_manager_v2.maximum_open_positions == 3
    assert context.paper_execution_engine.fill_market_orders_immediately is False
    assert context.paper_execution_engine.slippage_points == .75
    assert context.account_state_manager_v2.get_state()["balance"] == 150000
    assert context.execution_manager.get_contract_limit("MNQ") == 150
    assert context.execution_manager.get_contract_limit("NQ") == 15


def test_standalone_api_reports_the_same_daily_limit_as_its_runtime(runtime):
    from backend.api.app import create_app
    manager = runtime.safety._managers[0]
    limit = manager.get_active_account().daily_loss_limit
    app = create_app(account_config_manager_v2=manager)
    context = app.state.runtime_context_v2
    assert context.account_state_manager_v2.maximum_daily_loss == limit
    assert context.risk_manager_v2.maximum_daily_loss == limit
    assert app.state.active_maximum_daily_loss == limit
    assert app.state.account_risk_guard.daily_loss_limit == limit


def test_accepted_fill_trace_crosses_risk_then_execution_then_financial_owners(runtime, monkeypatch):
    context = runtime.context
    lifecycle = context.trade_lifecycle_service
    events = []
    boundaries = [
        (context.risk_manager_v2, "evaluate", "risk"),
        (lifecycle.execution_risk_gate_v1, "evaluate_trade", "execution_guard"),
        (context.execution_manager, "prepare_order", "prepare"),
        (lifecycle.broker_connector_v2, "submit_order", "broker"),
        (context.paper_execution_engine, "execute", "paper"),
        (context.position_manager, "open_position", "position"),
        (context.protective_order_registry, "create_protection", "protection"),
        (context.oco_manager, "create_group", "oco"),
        (context.portfolio_manager_v2, "add_position", "portfolio"),
        (context.account_state_manager_v2, "update_from_portfolio", "account"),
        (lifecycle.trade_journal_v2, "record_open_trade", "journal"),
    ]
    for owner, method, label in boundaries:
        original = getattr(owner, method)
        def traced(*args, _original=original, _label=label, **kwargs):
            events.append(_label)
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, method, traced)
    result = submit(runtime)
    assert result["accepted"] is True, result
    assert events == [row[2] for row in boundaries]
    assert len(lifecycle.broker_connector_v2.get_fills()) == 1
    assert len(lifecycle.get_active_positions()) == 1
    assert len(context.portfolio_manager_v2.get_open_positions()) == 1
    assert len(lifecycle.trade_journal_v2.trades) == 1


def test_asgi_clean_and_recovered_runtime_keep_the_same_ownership(runtime, tmp_path):
    from fastapi.testclient import TestClient
    from backend.api.asgi import create_asgi_app
    from backend.services.runtime_context_v2 import build_runtime_context
    path = tmp_path / "asgi-ownership.json"
    contexts = []
    for expected_mode in ("CLEAN", "RECOVERY"):
        context = build_runtime_context(account_manager=runtime.safety._managers[0])
        contexts.append(context)
        app = create_asgi_app(runtime_context=context, state_path=path)
        with TestClient(app):
            assert_application_graph(app, context)
            assert context.runtime_lifecycle_manager.get_status() == "RUNNING"
            assert context.startup_coordinator.get_startup_report()["mode"] == expected_mode
            assert context.execution_state_store._durability.enabled
            assert context.trade_lifecycle_service.broker_connector_v2.get_fills() == []
        assert context.execution_state_store._durability._lease is None
    assert contexts[0].trade_lifecycle_service is not contexts[1].trade_lifecycle_service


def test_cli_actual_factory_preserves_graph_across_restart(runtime, tmp_path, monkeypatch):
    import backend.main as main
    from backend.config_settings import ArmsSettings
    from backend.services.runtime_context_v2 import build_runtime_context
    from backend.tests.test_main_runtime_integration import configure_fakes, FakeLifecycleManager, FakePipeline
    configure_fakes(monkeypatch, FakeLifecycleManager())
    settings = ArmsSettings(runtime_snapshot_path=str(tmp_path / "cli-ownership.json"))
    monkeypatch.setattr(main, "ArmsSettings", lambda: settings)
    contexts = []
    def factory(**kwargs):
        context = build_runtime_context(**kwargs)
        contexts.append(context)
        return context
    monkeypatch.setattr(main, "build_runtime_context", factory)
    def pipeline(self, *, initial_context):
        context = contexts[-1]
        assert_runtime_graph(context)
        assert context.runtime_lifecycle_manager.get_status() == "RUNNING"
        assert context.execution_state_store._durability.enabled
        assert context.startup_coordinator.get_startup_report()["mode"] == (
            "CLEAN" if len(contexts) == 1 else "RECOVERY")
    monkeypatch.setattr(FakePipeline, "run", pipeline)
    for _ in range(2):
        main.main()
        assert contexts[-1].execution_state_store._durability._lease is None
    assert contexts[0] is not contexts[1]


def test_inventory_matches_all_reviewed_production_boundaries():
    import json
    from pathlib import Path
    from backend.tests.phase1_runtime_execution_inventory_v7 import discover, source_nodes, EXPLICIT
    manifest = json.loads(Path(__file__).with_name("phase1_runtime_execution_inventory_v7.json").read_text(encoding="utf-8"))
    builders, execution = discover()
    for actual, key in ((builders, "builders"), (execution, "execution_points")):
        reviewed = {row["id"]: row for row in manifest[key]}
        assert set(actual) == set(reviewed), "New construction/execution boundary requires ownership review"
        for ident, evidence in actual.items():
            assert all(reviewed[ident][key] == value for key, value in evidence.items()), ident
            assert reviewed[ident]["classification"] and reviewed[ident]["owner"]
    for row in manifest["builders"]:
        for field in ("caller", "account_scope", "runtime_generation", "services_created",
                      "execution_owner", "risk_owner", "financial_owner", "market_owner",
                      "startup_or_runtime", "test_or_production", "canonical_or_legacy", "downstream_effect"):
            assert row[field], row["id"]
        assert row["unsafe_duplicate"] is False
    for row in manifest["execution_points"]:
        assert row["callers"] and row["downstream_effects"]
        assert row["direct_broker_bypass"] is False
        assert row["unauthorized_execution_entry"] is False
    available = {(path, name.rsplit(".", 1)[-1]) for path, name, _ in source_nodes()}
    assert all((path, name) in available for path, names in EXPLICIT.items() for name in names)
    cert = manifest["certificate"]
    assert cert["TOTAL_RUNTIME_BUILDERS"] == cert["CLASSIFIED_RUNTIME_BUILDERS"] == len(builders)
    assert cert["TOTAL_EXECUTION_DECISION_POINTS"] == cert["CLASSIFIED_EXECUTION_DECISION_POINTS"] == len(execution)
    assert cert["UNCLASSIFIED_RUNTIME_BUILDERS"] == cert["UNCLASSIFIED_EXECUTION_DECISION_POINTS"] == 0


def test_only_canonical_lifecycle_submits_to_broker_and_facades_do_not_book_fills():
    from backend.tests.phase1_runtime_execution_inventory_v7 import discover
    _, points = discover()
    submitters = {ident for ident, row in points.items()
                  if any(call.endswith(".submit_order") for call in row["calls"])}
    assert submitters == {
        "backend/services/trade_lifecycle_service_v2.py:TradeLifecycleServiceV2.submit_signal"}
    forbidden = {"submit_order", "open_position", "record_open_trade", "close_trade", "prepare_order"}
    for ident, row in points.items():
        if row["path"].startswith(("backend/api/", "backend/intelligence/", "backend/strategies/")):
            assert not forbidden.intersection(row["execution_calls"]), ident


def test_isolated_backtest_lifecycle_cannot_share_operational_ledgers(runtime):
    from backend.backtesting.strategy_backtest_factory_v2 import build_lifecycle
    from backend.api.app import APISettings
    replay = build_lifecycle(settings=APISettings())
    operational = runtime.context.trade_lifecycle_service
    assert type(replay) is type(operational)
    assert replay.paper_execution_engine is not operational.paper_execution_engine
    assert replay.position_manager is not operational.position_manager
    assert replay.trade_history_manager is not operational.trade_history_manager
    assert replay.broker_connector_v2.execution_mode == "PAPER"
    assert replay.portfolio_manager_v2 is None
    assert replay.trade_journal_v2 is None


def crash_canonical_runtime(path, config, profiles_path, window):
    """Child-process failure injection; real canonical factory and PAPER state."""
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace
    from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
    from backend.accounts.account_registry_v1 import AccountRegistryV1
    from backend.accounts.funding_firm_profile_v1 import FundingFirmProfile
    from backend.services.runtime_context_v2 import build_runtime_context
    from backend.services import durable_execution_state_v2 as durable
    registry = AccountRegistryV1()
    registry.accounts = {name: FundingFirmProfile(**row) for name, row in
        json.loads(Path(profiles_path).read_text(encoding="utf-8")).items()}
    manager = AccountConfigManagerV2(config_path=config, registry=registry)
    context = build_runtime_context(account_manager=manager)
    context.runtime_lifecycle_manager.start_from(file_path=path)
    write = durable.atomic_write
    def crash_at_boundary(target, state):
        phase = state.get("durability", {}).get("phase")
        if window == "completed" and phase == "COMMITTED":
            os._exit(23)
        write(target, state)
        if window == "prepared" and phase == "PENDING":
            os._exit(23)
    durable.atomic_write = crash_at_boundary
    submit(SimpleNamespace(context=context, safety=context.account_switch_safety_v2))
    raise AssertionError("Crash boundary was not reached")


@pytest.mark.parametrize("window,positions", [("prepared", 0), ("completed", 1)])
def test_pending_reconciliation_restores_canonical_graph_without_reexecution(runtime, tmp_path, monkeypatch, window, positions):
    import json
    import subprocess
    import sys
    from dataclasses import asdict
    from backend.services.runtime_context_v2 import build_runtime_context
    manager = runtime.safety._managers[0]
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({name: asdict(row) for name, row in manager.registry.accounts.items()}), encoding="utf-8")
    path = tmp_path / "pending-ownership.json"
    code = ("import sys; from backend.tests.test_phase1_runtime_execution_ownership_v7 "
            "import crash_canonical_runtime; crash_canonical_runtime(*sys.argv[1:])")
    result = subprocess.run([sys.executable, "-c", code, str(path), str(runtime.config), str(profiles), window],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 23, result.stdout + result.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["durability"]["phase"] == "PENDING"
    recovered = build_runtime_context(account_manager=manager)
    guard = Mock(side_effect=AssertionError("Recovery resubmitted an order"))
    monkeypatch.setattr(recovered.trade_lifecycle_service.broker_connector_v2, "submit_order", guard)
    try:
        recovered.runtime_lifecycle_manager.start_from(file_path=path)
        assert_runtime_graph(recovered)
        assert recovered.startup_coordinator.get_startup_report()["mode"] == "RECOVERY"
        lifecycle = recovered.trade_lifecycle_service
        assert len(lifecycle.get_active_positions()) == positions
        assert len(lifecycle.broker_connector_v2.get_fills()) == positions
        assert len(lifecycle.trade_journal_v2.trades) == positions
        assert len(recovered.portfolio_manager_v2.get_open_positions()) == positions
        assert recovered.account_state_manager_v2.get_state()["realized_pnl"] == 0
        guard.assert_not_called()
    finally:
        recovered.execution_state_store._durability.release()
