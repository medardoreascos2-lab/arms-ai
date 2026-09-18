"""Economic reconciliation at the canonical PAPER lifecycle boundary."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.tests.test_phase1_fill_atomicity_v2 import build_service, build_durable_service, build_signal
from backend.services.execution_state_store_v2 import ExecutionStateStoreV2
from backend.services.state_recovery_service_v2 import StateRecoveryServiceV2
from backend.services.startup_coordinator_v2 import StartupCoordinatorV2
from backend.services.live_position_monitor_v2 import LivePositionMonitorV2
from backend.services.price_feed_service_v2 import PriceFeedServiceV2
from backend.execution.partial_take_profit_engine_v2 import PartialTakeProfitEngineV2
from backend.execution.realized_pnl_engine_v2 import RealizedPnLEngineV2


@pytest.fixture
def financial(tmp_path):
    service, store = build_durable_service(tmp_path)
    try:
        yield SimpleNamespace(service=service, store=store)
    finally:
        store._durability.release()


def submit(service, direction="LONG", submission_id="financial-v6"):
    value = build_signal()
    value.update(direction=direction, submission_id=submission_id)
    if direction == "SHORT":
        value.update(stop_loss=105., take_profit=90.)
    return service.submit_signal(signal=value, order_type="MARKET",
        risk_context={"account_balance":service.portfolio_manager_v2.get_available_balance(),
            "risk_percent":.5, "point_value":2., "daily_pnl":0., "total_drawdown":0.})


def state(store):
    result = deepcopy(store.capture_state())
    result.pop("captured_at", None)
    return result


def reconcile(service, *, realized, unrealized, remaining):
    portfolio = service.portfolio_manager_v2
    account = portfolio.account_state_manager_v2.get_state()
    summary = portfolio.get_summary()
    journal = service.trade_journal_v2.trades
    assert summary["total_realized_pnl"] == account["realized_pnl"] == pytest.approx(realized)
    assert summary["total_unrealized_pnl"] == account["unrealized_pnl"] == pytest.approx(unrealized)
    assert account["daily_pnl"] == pytest.approx(realized)
    assert account["equity"] == summary["account_equity"] == pytest.approx(17000 + realized + unrealized)
    assert account["balance"] == portfolio.get_available_balance() == pytest.approx(17000 + realized)
    assert len(journal) == 1
    assert journal[0].pnl == pytest.approx(realized)
    active = service.get_active_positions()
    assert sum(p["quantity"] for p in active) == remaining
    assert sum(p["quantity"] for p in portfolio.get_open_positions()) == remaining
    if remaining:
        assert active[0]["unrealized_pnl"] == pytest.approx(unrealized)
        assert len(service.get_trade_history()) == 0
    else:
        assert len(service.get_trade_history()) == len(portfolio.get_closed_positions()) == 1
        assert service.get_trade_history()[0]["realized_pnl"] == pytest.approx(realized)
        assert portfolio.get_closed_positions()[0]["unrealized_pnl"] == 0
        assert journal[0].remaining_quantity == 0
        assert journal[0].status == "CLOSED"


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
@pytest.mark.parametrize("with_partial", [False, True])
@pytest.mark.parametrize("outcome", ["profit", "loss"])
def test_fill_partial_close_and_restart_reconcile_once(financial, direction, with_partial, outcome):
    service, store = financial.service, financial.store
    result = submit(service, direction)
    assert result["accepted"] is True
    position = result["position"]
    entry, quantity, point_value = position["entry_price"], position["quantity"], position["point_value"]
    sign = 1 if direction == "LONG" else -1
    reconcile(service, realized=0., unrealized=0., remaining=quantity)
    monitor = LivePositionMonitorV2(trade_lifecycle_service=service,
        portfolio_manager_v2=service.portfolio_manager_v2,
        partial_take_profit_engine=PartialTakeProfitEngineV2(trigger_profit_points=2., close_fraction=.5) if with_partial else None,
        realized_pnl_engine=RealizedPnLEngineV2(point_value=point_value) if with_partial else None)
    mark = entry + sign * 3
    monitor.process_price(symbol="MNQ", current_price=mark)
    remaining = quantity / 2 if with_partial else quantity
    realized = 3 * (quantity - remaining) * point_value
    reconcile(service, realized=realized, unrealized=3 * remaining * point_value, remaining=remaining)
    replay = service.get_active_positions()[0]
    before = state(store)
    service.replace_active_position(position=deepcopy(replay))
    assert state(store) == before
    # Recovery uses the last automatic COMMITTED checkpoint, without manual export.
    path = store._durability.path
    store._durability.release()
    restored = build_service()
    target = ExecutionStateStoreV2(trade_lifecycle_service=restored,
        protective_order_registry=restored.protective_order_registry_v2, oco_manager=restored.oco_manager_v2)
    startup = StartupCoordinatorV2(state_recovery_service=StateRecoveryServiceV2(execution_state_store=target))
    try:
        startup.startup_from(file_path=path)
        assert state(target) == before
        restored.replace_active_position(position=deepcopy(replay))
        assert state(target) == before
        close = position["take_profit"] if outcome == "profit" else position["stop_loss"]
        expected = realized + sign * (close - entry) * remaining * point_value
        closed = restored.update_position(position_id=position["position_id"], current_price=close)
        assert closed["active_position_removed"] is True
        reconcile(restored, realized=expected, unrealized=0., remaining=0)
        after = state(target)
        with pytest.raises(ValueError, match="position_id"):
            restored.update_position(position_id=position["position_id"], current_price=close)
        assert state(target) == after
        assert len(restored.broker_connector_v2.get_fills()) == 1 + int(with_partial)
        assert all(row["status"] != "ACTIVE" for row in restored.protective_order_registry_v2.list_protections())
    finally:
        target._durability.release()


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_closed_events_have_zero_unrealized_pnl(financial, monkeypatch, direction):
    service = financial.service
    seen = []
    publisher = service.dashboard_event_publisher_v2
    monkeypatch.setattr(publisher, "publish_trade_closed", lambda **kw: seen.append(deepcopy(kw["trade"])))
    monkeypatch.setattr(publisher, "publish_position_updated", lambda **kw: seen.append(deepcopy(kw["position"])))
    result = submit(service, direction)
    p = result["position"]
    service.update_position(position_id=p["position_id"], current_price=p["take_profit"])
    assert len(seen) == 2
    assert all(row["status"] == "CLOSED" and row["unrealized_pnl"] == 0 for row in seen)


def test_open_mark_event_observes_synchronized_portfolio_and_account(financial, monkeypatch):
    service = financial.service
    p = submit(service)["position"]
    observations = []
    def observe(*, position):
        observations.append((deepcopy(position), deepcopy(service.portfolio_manager_v2.get_summary())))
    monkeypatch.setattr(service.dashboard_event_publisher_v2, "publish_position_updated", observe)
    service.update_position(position_id=p["position_id"], current_price=p["entry_price"]+1)
    position, portfolio = observations[0]
    assert position["unrealized_pnl"] == portfolio["total_unrealized_pnl"] == portfolio["account_state"]["unrealized_pnl"]


@pytest.mark.parametrize("invalid", [0., -1., float("nan"), float("inf")])
def test_invalid_market_mark_does_not_mutate_financial_state(financial, invalid):
    service, store = financial.service, financial.store
    submit(service)
    monitor = LivePositionMonitorV2(trade_lifecycle_service=service)
    feed = PriceFeedServiceV2(live_position_monitor_v2=monitor, maximum_age_seconds=30.)
    before = state(store)
    with pytest.raises(ValueError):
        feed.process_price(symbol="MNQ", current_price=invalid, source="MARKET_WEBHOOK", timestamp=datetime.now(timezone.utc))
    assert state(store) == before


@pytest.mark.parametrize("age", [-5, 120])
def test_unavailable_market_evidence_cannot_book_pnl(financial, age):
    service, store = financial.service, financial.store
    submit(service)
    feed = PriceFeedServiceV2(live_position_monitor_v2=LivePositionMonitorV2(trade_lifecycle_service=service), maximum_age_seconds=30.)
    now = datetime.now(timezone.utc)
    before = state(store)
    with pytest.raises(ValueError):
        feed.process_price(symbol="MNQ", current_price=110., source="MARKET_WEBHOOK", timestamp=now-timedelta(seconds=age), current_timestamp=now)
    assert state(store) == before


@pytest.mark.parametrize("after_restart", [False, True])
@pytest.mark.parametrize("identity", ["order", "broker_position", "both"])
def test_replayed_entry_execution_cannot_create_a_second_financial_application(financial, monkeypatch, after_restart, identity):
    service, store = financial.service, financial.store
    first = submit(service)
    position = first["position"]
    service.update_position(position_id=position["position_id"], current_price=position["take_profit"])
    before = state(store)
    if after_restart:
        path = store._durability.path
        store._durability.release()
        service = build_service()
        store = ExecutionStateStoreV2(trade_lifecycle_service=service,
            protective_order_registry=service.protective_order_registry_v2, oco_manager=service.oco_manager_v2)
        StartupCoordinatorV2(state_recovery_service=StateRecoveryServiceV2(execution_state_store=store)).startup_from(file_path=path)
    replay = deepcopy(first["execution"])
    replay["idempotent_replay"] = False  # Identity, not a permissive adapter flag, controls application.
    if identity == "order": replay["position_id"] = "unrecognized-broker-position"
    if identity == "broker_position": replay["order_id"] = "unrecognized-order"
    monkeypatch.setattr(service.broker_connector_v2, "submit_order", lambda **kw: deepcopy(replay))
    try:
        result = submit(service, submission_id="different-request-same-fill")
        assert result["accepted"] is False
        assert result["reason"] == "duplicate_execution"
        assert state(store) == before
        assert store._durability.failed is False
    finally:
        if after_restart:
            store._durability.release()


def test_scale_in_is_rejected_before_order_preparation(financial, monkeypatch):
    service, store = financial.service, financial.store
    submit(service)
    before = state(store)
    prepare = Mock(side_effect=AssertionError("Unsupported scale-in reached preparation"))
    monkeypatch.setattr(service.execution_manager, "prepare_order", prepare)
    result = submit(service, submission_id="second-entry")
    assert result["accepted"] is False
    prepare.assert_not_called()
    assert state(store) == before


def test_duplicate_close_history_record_is_idempotent(financial):
    service, store = financial.service, financial.store
    p = submit(service)["position"]
    closed = service.update_position(position_id=p["position_id"], current_price=p["take_profit"])["position"]
    before = state(store)
    assert service.trade_history_manager.record(position=closed)["reason"] == "duplicate_position"
    assert state(store) == before


from backend.tests.test_account_runtime_transition_v2 import hosted, switch, trade


def test_financial_settlement_and_journal_are_isolated_across_accounts(hosted):
    original = hosted.c.published.runtime
    result = trade(hosted)
    p = result["position"]
    original.trade_lifecycle_service.update_position(position_id=p["position_id"], current_price=p["take_profit"])
    original_state = state(original.execution_state_store)
    expected = (p["take_profit"]-p["entry_price"]) * p["quantity"] * p["point_value"]
    assert original.account_state_manager_v2.get_state()["realized_pnl"] == expected
    assert switch(hosted, "B").status_code == 200
    target = hosted.c.published.runtime
    before = state(target.execution_state_store)
    assert target.account_state_manager_v2.get_state()["realized_pnl"] == 0
    assert target.trade_lifecycle_service.get_trade_history() == []
    assert target.trade_lifecycle_service.trade_journal_v2.trades == []
    with pytest.raises(RuntimeError, match="retired"):
        original.trade_lifecycle_service.update_position(position_id=p["position_id"], current_price=p["stop_loss"])
    assert state(target.execution_state_store) == before
    assert switch(hosted, "A").status_code == 200
    restored = state(hosted.c.published.runtime.execution_state_store)
    for field in ("account_portfolio", "execution_records", "active_positions"):
        assert restored[field] == original_state[field]


def test_open_fill_call_order_and_identity_are_canonical(financial, monkeypatch):
    service = financial.service
    calls = []
    targets = [
        (service.broker_connector_v2, "submit_order", "fill"),
        (service.position_manager, "open_position", "position"),
        (service.protective_order_registry_v2, "create_protection", "protection"),
        (service.oco_manager_v2, "create_group", "oco"),
        (service.portfolio_manager_v2, "add_position", "portfolio"),
        (service.portfolio_manager_v2.account_state_manager_v2, "update_from_portfolio", "account"),
        (service.trade_journal_v2, "record_open_trade", "journal"),
        (service.dashboard_event_publisher_v2, "publish_trade_opened", "event"),
    ]
    for owner, name, label in targets:
        original = getattr(owner, name)
        def record(*args, _original=original, _label=label, **kwargs):
            calls.append(_label)
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, name, record)
    p = submit(service)["position"]
    assert calls == [row[2] for row in targets]
    broker = service.broker_connector_v2
    fills = broker.get_fills()
    assert len(fills) == 1 and fills[0]["order_id"] == p["order_id"]
    assert service.trade_journal_v2.trades[0].position_id == p["position_id"]
    assert service.trade_journal_v2.trades[0].trade_id == "journal-" + p["position_id"]


def test_financial_inventory_matches_reviewed_source_and_ownership():
    import json
    from pathlib import Path
    from backend.tests.phase1_financial_inventory_v6 import discover, EXPLICIT
    from backend.tests.phase1_risk_authority_inventory_v5 import functions
    manifest = json.loads(Path(__file__).with_name("phase1_financial_inventory_v6.json").read_text())
    points = {r["id"]:r for r in manifest["points"]}
    actual = discover()
    assert set(points) == set(actual), "Financial mutation boundary requires review"
    categories = {"CANONICAL_FILL_OWNER", "CANONICAL_POSITION_OWNER", "CANONICAL_PORTFOLIO_OWNER",
        "CANONICAL_PNL_OWNER", "CANONICAL_JOURNAL_OWNER", "EXECUTION_ADAPTER", "OBSERVATIONAL_PROJECTION",
        "RECOVERY_REHYDRATION", "LEGACY_OR_DUPLICATE", "OTHER_JUSTIFIED"}
    available = {(path,node.name) for path,name,node in functions()}
    assert all((path,name) in available for path,names in EXPLICIT.items() for name in names)
    for ident,evidence in actual.items():
        row = points[ident]
        assert all(row[k] == v for k,v in evidence.items()), ident
        assert row["classification"] in categories
        assert row["owner"] and row["input"] and row["output"] and row["downstream_consumers"]
        for field in ("mutates_fill_state", "mutates_position_state", "mutates_portfolio",
                      "mutates_account_pnl", "mutates_journal", "mutates_history",
                      "account_scoped", "persisted", "recovery_relevant"):
            assert type(row[field]) is bool
    cert = manifest["certificate"]
    assert cert["TOTAL_FINANCIAL_MUTATION_POINTS"] == cert["CLASSIFIED_FINANCIAL_MUTATION_POINTS"] == len(points)
    assert cert["UNCLASSIFIED_FINANCIAL_MUTATION_POINTS"] == 0
