"""PH1-REQ-004: canonical risk state dominates caller permission."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.tests.test_account_runtime_transition_v2 import hosted, target, trade, switch
from backend.tests.test_account_switch_safety_containment_v2 import signal
from backend.tests.test_dashboard_read_execution_safety_v2 import capture


def submit(h, **override):
    r = h.c.published.runtime
    from backend.tests.runtime_market_fixture_v81 import publish_test_market
    publish_test_market(r.trade_lifecycle_service, directory=h.config.parent)
    state = r.account_state_manager_v2.get_state()
    return r.trade_lifecycle_service.submit_signal(
        signal={**signal(), "submission_id": "risk-v5-new"}, order_type="MARKET",
        risk_context={**target(h, h.c.identity.profile_name),
            "account_balance": r.portfolio_manager_v2.get_available_balance(),
            "risk_percent": r.account_switch_safety_v2._profile["risk_percent"],
            "point_value": 2., "daily_pnl": state["daily_pnl"],
            "total_drawdown": state["drawdown"], **override},
    )


def test_caller_drawdown_cannot_override_projected_account_loss(hosted, monkeypatch):
    # Real prior PAPER fill/close yields drawdown below the hard limit but with
    # insufficient capacity for the next risk budget. A new day clears only daily loss.
    trade(hosted, 8000.)
    app = hosted.c.published.application
    account = app.state.account_state_manager_v2
    monkeypatch.setattr(account, "_clock", lambda: datetime.now(timezone.utc) + timedelta(days=7))
    account.ensure_trading_day()
    state = account.get_state()
    assert 0 < state["drawdown"] < account.maximum_total_drawdown
    assert state["trading_blocked"] is False
    before = capture(app)
    prepare = Mock(side_effect=AssertionError("Caller drawdown bypass reached order preparation"))
    monkeypatch.setattr(app.state.trade_lifecycle_service_v2.execution_manager, "prepare_order", prepare)
    result = submit(hosted, total_drawdown=0.)
    assert result["accepted"] is False
    assert result["reason"] == "risk_blocked", result
    assert result["prepared_order"] is None
    prepare.assert_not_called()
    after = capture(app)
    # Risk rejection may publish a risk diagnostic, never execution activity.
    before.pop("events"); after.pop("events")
    assert after == before


def account():
    return AccountStateManagerV2(starting_balance=50000, maximum_daily_loss=1000,
                                 maximum_total_drawdown=2000)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_invalid_daily_pnl_cannot_clear_or_corrupt_an_owned_block(invalid):
    owner = account()
    owner.record_daily_pnl(daily_pnl=-1000)
    before = owner.capture_state()
    with pytest.raises(ValueError):
        owner.record_daily_pnl(daily_pnl=invalid)
    assert owner.capture_state() == before


@pytest.mark.parametrize("field", ["total_realized_pnl", "total_unrealized_pnl", "total_pnl", "account_equity"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_invalid_portfolio_update_cannot_clear_or_corrupt_blocks(field, invalid):
    owner = account()
    owner.record_daily_pnl(daily_pnl=-1000)
    before = owner.capture_state()
    summary = {"open_positions": 0, "closed_positions": 0, "total_realized_pnl": 0.,
               "total_unrealized_pnl": 0., "total_pnl": 0., "account_equity": 50000.}
    summary[field] = invalid
    with pytest.raises(ValueError):
        owner.update_from_portfolio(portfolio_summary=summary)
    assert owner.capture_state() == before


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_invalid_open_risk_cannot_mutate_account(invalid):
    owner = account()
    before = owner.capture_state()
    with pytest.raises(ValueError):
        owner.update_open_risk(open_risk=invalid)
    assert owner.capture_state() == before


def test_final_risk_rejection_precedes_executable_order_preparation(monkeypatch):
    from backend.tests.test_trade_lifecycle_execution_risk_gate_v1 import (
        build_service, build_signal, risk_context, FakeBlockedValidator,
    )
    service, broker, gate = build_service(validator=FakeBlockedValidator())
    prepare = Mock(wraps=service.execution_manager.prepare_order)
    monkeypatch.setattr(service.execution_manager, "prepare_order", prepare)
    result = service.submit_signal(signal=build_signal(), order_type="MARKET", risk_context=risk_context())
    assert result["accepted"] is False
    assert result["prepared_order"] is None
    prepare.assert_not_called()
    assert broker.get_orders() == broker.get_fills() == service.get_active_positions() == []


@pytest.mark.parametrize("condition", ["daily", "drawdown", "foreign", "unclassified"])
@pytest.mark.parametrize("recommendation", ["strategy", "signal", "execution"])
def test_account_blocks_dominate_all_downstream_permissions(hosted, monkeypatch, condition, recommendation):
    from backend.backtesting.strategy_decision_engine_v2 import StrategyDecisionEngineV2
    app = hosted.c.published.application
    owner = app.state.account_state_manager_v2
    if condition == "daily":
        owner.record_daily_pnl(daily_pnl=-owner.maximum_daily_loss)
    elif condition == "drawdown":
        trade(hosted, 7500.)
        monkeypatch.setattr(owner, "_clock", lambda: datetime.now(timezone.utc) + timedelta(days=7))
        owner.ensure_trading_day()
    else:
        # Explicit structural-block fixture; ordinary account writers must preserve it.
        owner._state["trading_blocked"] = True
        owner._state["blocking_reasons"] = ["structural_safety_block"] if condition == "foreign" else []
        owner.record_daily_pnl(daily_pnl=0)
    assert owner.get_state()["trading_blocked"]
    downstream = StrategyDecisionEngineV2().decide(strategy={"confidence": 100},
        market_context={"risk_allowed": True, "trend": "BULLISH", "structure": "BOS_CONFIRMED"})
    assert downstream["decision"] == "EXECUTE"
    before = capture(app)
    lifecycle = app.state.trade_lifecycle_service_v2
    guards = [Mock(side_effect=AssertionError("Account block bypass")) for _ in range(3)]
    monkeypatch.setattr(lifecycle.risk_manager_v2, "evaluate", guards[0])
    monkeypatch.setattr(lifecycle.execution_manager, "prepare_order", guards[1])
    monkeypatch.setattr(lifecycle.broker_connector_v2, "submit_order", guards[2])
    result = submit(hosted, daily_pnl=0, total_drawdown=0,
                    **{recommendation + "_approved": True, "risk_allowed": True})
    assert result["accepted"] is False
    assert result["reason"] == "account_trading_blocked"
    assert result["prepared_order"] is result["execution"] is None
    assert capture(app) == before
    for guard in guards:guard.assert_not_called()


@pytest.mark.parametrize("condition", ["failed", "stopped", "switching", "retired", "unpublished"])
def test_runtime_blocks_precede_permissive_risk_evaluation(hosted, monkeypatch, condition):
    app = hosted.c.published.application
    runtime = hosted.c.published.runtime
    durability = runtime.execution_state_store._durability
    field = {"switching": "account_switch_in_progress"}.get(condition, condition)
    before = capture(app)
    context = {**target(hosted, hosted.c.identity.profile_name),
        "account_balance": runtime.portfolio_manager_v2.get_available_balance(),
        "risk_percent": runtime.account_switch_safety_v2._profile["risk_percent"],
        "point_value": 2., "daily_pnl": 0., "total_drawdown": 0.}
    with monkeypatch.context() as patch:
        if condition == "unpublished":patch.setattr(hosted.c, "failed", True)
        else:patch.setattr(durability, field, True)
        guard = Mock(side_effect=AssertionError("Runtime block reached risk/prepare"))
        patch.setattr(runtime.risk_manager_v2, "evaluate", guard)
        patch.setattr(runtime.execution_manager, "prepare_order", guard)
        try:
            result = runtime.trade_lifecycle_service.submit_signal(
                signal=signal(), order_type="MARKET", risk_context=context)
        except RuntimeError as exc:
            assert "closed" in str(exc) or "runtime" in str(exc)
        else:
            assert result["accepted"] is False
            assert result["prepared_order"] is None
        guard.assert_not_called()
    assert capture(app) == before


def test_daily_reset_and_valid_pnl_cannot_clear_foreign_or_drawdown_blocks(monkeypatch):
    owner = account()
    owner.update_from_portfolio(portfolio_summary={"total_realized_pnl": -2500.,
        "total_unrealized_pnl": 0., "total_pnl": -2500., "account_equity": 47500.})
    owner._state["blocking_reasons"].append("durability_consistency_unproven")
    owner.record_daily_pnl(daily_pnl=0)
    assert set(owner.get_state()["blocking_reasons"]) == {
        "maximum_total_drawdown_reached", "durability_consistency_unproven"}
    before = owner.get_state()
    assert owner.reset_daily_state()["reset"] is False
    monkeypatch.setattr(owner, "_clock", lambda: datetime.now(timezone.utc) + timedelta(days=7))
    assert owner.reset_daily_state()["reset"] is True
    after = owner.get_state()
    assert after["blocking_reasons"] == before["blocking_reasons"]
    assert after["drawdown"] == before["drawdown"]
    assert after["trading_blocked"] is True
    # Valid financial improvement clears only the drawdown condition it owns.
    owner.update_from_portfolio(portfolio_summary={"total_realized_pnl": 0.,
        "total_unrealized_pnl": 0., "total_pnl": 0., "account_equity": 50000.})
    assert owner.get_state()["blocking_reasons"] == ["durability_consistency_unproven"]
    assert owner.get_state()["trading_blocked"] is True


@pytest.mark.parametrize("field", ["account_balance", "risk_percent", "stop_points", "point_value"])
@pytest.mark.parametrize("invalid", [0., -1., float("nan"), float("inf")])
def test_sizing_invalid_inputs_never_grant_permission(field, invalid):
    from backend.execution.position_sizing_engine_v2 import PositionSizingEngineV2
    from backend.execution.risk_manager_v2 import RiskManagerV2
    sizing = PositionSizingEngineV2()
    owner = RiskManagerV2(position_sizing_engine=sizing, maximum_daily_loss=1000,
        maximum_total_drawdown=2000, maximum_contracts=5, maximum_open_positions=1)
    inputs = {"account_balance": 50000., "risk_percent": .1, "stop_points": 10., "point_value": 2.}
    inputs[field] = invalid
    with pytest.raises(ValueError):
        owner.evaluate(**inputs, daily_pnl=0, total_drawdown=0, open_positions=0)


def test_sizing_approval_is_not_permission_when_loss_capacity_is_exhausted():
    from backend.execution.position_sizing_engine_v2 import PositionSizingEngineV2
    from backend.execution.risk_manager_v2 import RiskManagerV2
    owner = RiskManagerV2(position_sizing_engine=PositionSizingEngineV2(),
        maximum_daily_loss=1000, maximum_total_drawdown=2000,
        maximum_contracts=5, maximum_open_positions=1)
    result = owner.evaluate(account_balance=50000, risk_percent=.1, stop_points=10,
        point_value=2, daily_pnl=-1000, total_drawdown=2000, open_positions=0)
    assert result["position_sizing"]["approved"] is True
    assert result["approved"] is False
    assert result["blocking_reasons"] == ["daily_loss_limit_reached", "total_drawdown_limit_reached"]


def test_a_b_a_preserves_loss_blocks_without_cross_account_contamination(hosted):
    app_a = hosted.c.published.application
    owner_a = app_a.state.account_state_manager_v2
    owner_a.record_daily_pnl(daily_pnl=-owner_a.maximum_daily_loss)
    assert submit(hosted)["reason"] == "account_trading_blocked"
    assert switch(hosted, "B").status_code == 200
    app_b = hosted.c.published.application
    assert app_b.state.account_state_manager_v2.get_state()["trading_blocked"] is False
    assert app_b.state.account_state_manager_v2.get_state()["daily_pnl"] == 0
    assert switch(hosted, "A").status_code == 200
    restored = hosted.c.published.application.state.account_state_manager_v2.get_state()
    assert restored["trading_blocked"] is True
    assert restored["daily_pnl"] == -owner_a.maximum_daily_loss
    assert submit(hosted)["reason"] == "account_trading_blocked"


@pytest.mark.parametrize("market_state", [False, None])
def test_order_guard_failure_cannot_prepare_an_executable_order(monkeypatch, market_state):
    from backend.tests.test_trade_lifecycle_order_validation_integration_v2 import (
        build_service, build_order_validator, build_signal, build_risk_context,
    )
    service = build_service(order_validation_engine_v2=build_order_validator())
    prepare = Mock(wraps=service.execution_manager.prepare_order)
    monkeypatch.setattr(service.execution_manager, "prepare_order", prepare)
    try:
        result = service.submit_signal(signal=build_signal(), order_type="MARKET",
            risk_context=build_risk_context(), order_context=None if market_state is None else {"market_is_open": market_state})
    except ValueError:
        assert market_state is None
    else:
        assert result["accepted"] is False
        assert result["prepared_order"] is None
    prepare.assert_not_called()
    assert service.broker_connector_v2.get_orders() == []
    assert service.broker_connector_v2.get_fills() == []


@pytest.mark.parametrize("order_type", ["MARKET", "LIMIT"])
@pytest.mark.parametrize("market_open", [False, True])
def test_candidate_validation_preserves_existing_order_guard_rules(order_type, market_open, monkeypatch):
    from backend.tests.test_trade_lifecycle_order_validation_integration_v2 import build_order_validator, build_signal
    from backend.execution.execution_manager_v2 import ExecutionManagerV2
    validator = build_order_validator()
    signal_value = build_signal()
    prepared = ExecutionManagerV2(execution_mode="PAPER", maximum_contracts=20).prepare_order(
        signal=signal_value, order_type=order_type)
    expected = validator.validate(prepared_order=prepared, market_is_open=market_open, open_symbols=set())
    validate_fields = Mock(wraps=validator._validate_fields)
    monkeypatch.setattr(validator, "_validate_fields", validate_fields)
    assert validator.validate_candidate(signal=signal_value, order_type=order_type,
        market_is_open=market_open, open_symbols=set()) == expected
    candidate = validate_fields.call_args.kwargs["prepared_order"]
    assert not {"approved", "status", "decision", "execution_mode"} & candidate.keys()
    # The pre-existing prepared-order entry point still requires permission fields.
    rejected = validator.validate(prepared_order=candidate, market_is_open=True, open_symbols=set())
    assert rejected["approved"] is False
    assert "prepared_order_not_approved" in rejected["blocking_reasons"]



def test_risk_inventory_covers_current_decision_and_writer_evidence():
    import json
    from pathlib import Path
    from backend.tests.phase1_risk_authority_inventory_v5 import discover
    manifest = json.loads(Path(__file__).with_name("phase1_risk_authority_inventory_v5.json").read_text())
    actual = discover()
    rows = {row["id"]: row for row in manifest["points"]}
    assert set(actual) == set(rows), "New or missing risk authority requires review"
    categories = {"CANONICAL_RISK_AUTHORITY", "ACCOUNT_SAFETY_AUTHORITY", "RUNTIME_SAFETY_AUTHORITY",
                  "STRATEGY_POLICY", "EXECUTION_GUARD", "POSITION_SIZING", "OBSERVATIONAL_ONLY",
                  "LEGACY_OR_DUPLICATE", "OTHER_JUSTIFIED"}
    for ident, evidence in actual.items():
        row = rows[ident]
        assert all(row[k] == v for k, v in evidence.items()), ident
        assert row["classification"] in categories
        assert row["owner"] and row["inputs"] and row["output"] and row["downstream_effect"]
        for flag in ("can_block", "can_unblock", "can_size", "account_scoped", "runtime_scoped", "strategy_scoped", "execution_scoped"):
            assert type(row[flag]) is bool
    cert = manifest["certificate"]
    assert cert["TOTAL_RISK_DECISION_POINTS"] == cert["CLASSIFIED_RISK_DECISION_POINTS"] == len(rows)
    assert cert["UNCLASSIFIED_RISK_DECISION_POINTS"] == 0
    assert cert["BLOCK_WRITERS"] == sum(r["persistent_block_writer"] for r in rows.values())
    assert cert["BLOCK_CLEARERS"] == sum(r["persistent_block_clearer"] for r in rows.values())


def test_published_risk_owners_and_profile_limits_are_consistent(hosted):
    r = hosted.c.published.runtime
    app = hosted.c.published.application
    lifecycle = r.trade_lifecycle_service
    account_owner = r.account_state_manager_v2
    profile = r.account_switch_safety_v2._managers[0].get_active_account()
    assert app.state.trade_lifecycle_service_v2 is lifecycle
    assert lifecycle.risk_manager_v2 is r.risk_manager_v2
    assert lifecycle.portfolio_manager_v2.account_state_manager_v2 is account_owner
    assert lifecycle.execution_risk_gate_v1 is app.state.execution_risk_gate_v1
    assert r.risk_manager_v2.maximum_daily_loss == account_owner.maximum_daily_loss
    assert r.risk_manager_v2.maximum_total_drawdown == account_owner.maximum_total_drawdown == profile.max_drawdown
    for symbol, contract_class in [("NQ", "MINI"), ("MNQ", "MICRO"), ("ES", "MINI"), ("MES", "MICRO")]:
        assert r.risk_manager_v2.get_contract_limit(symbol) == lifecycle.execution_manager.get_contract_limit(symbol)
        assert r.risk_manager_v2.get_contract_limit(symbol) <= profile.get_contract_limit(contract_class)
