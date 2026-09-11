"""Blocked selections stop the wired chain before risk or simulated execution."""
from copy import deepcopy
from unittest.mock import Mock

import pytest

from backend.api.app import create_app
from backend.backtesting.strategy_decision_engine_v2 import StrategyDecisionEngineV2
from backend.tests.test_dashboard_read_execution_safety_v2 import (
    capture, forbid_mutations, seed_existing_activity,
)


CONTEXT = {"trend": "BULLISH", "structure": "BOS_CONFIRMED", "risk_allowed": True,
           "price": 5100.0}
MARKET_DATA = {"entry": 5100.0}
RISK_CONFIG = {"stop_points": 10, "risk_reward": 2, "risk_amount": 50}
ACCOUNT_STATE = {"daily_loss": 0, "max_daily_loss": 1000}


def register_strategy(registry, strategy_id, status):
    registry.register({
        "strategy_id": strategy_id, "name": "Explicit regression fixture", "version": "1.0",
        "status": status, "grade": "A", "validation_score": 95, "performance_score": 90,
    })


def assert_blocked(result):
    assert result["status"] == "BLOCKED"
    assert result.get("decision") != "EXECUTE"
    assert result.get("approved") is not True
    assert result.get("risk_allowed") is not True
    assert not {"entry", "stop_loss", "take_profit"}.intersection(result)


@pytest.mark.parametrize("argument", ["strategy", "selected_strategy"])
@pytest.mark.parametrize("trend", ["BULLISH", "BEARISH"])
@pytest.mark.parametrize("structure", ["BOS_CONFIRMED", "BREAKOUT"])
@pytest.mark.parametrize("selection", [
    {"status": "BLOCKED", "reason": "NO_STRATEGIES"},
    {"status": "BLOCKED", "reason": "CERTIFICATION_REJECTED",
     "strategy_id": "blocked-with-id", "confidence": 100},
    {"status": "BLOCKED", "strategy_id": "blocked-without-reason", "confidence": 100},
    {"reason": "NO_STRATEGIES"},
])
def test_blocked_selection_cannot_become_execute(argument, trend, structure, selection):
    before = deepcopy(selection)
    result = StrategyDecisionEngineV2().decide(
        **{argument: selection},
        market_context={**CONTEXT, "trend": trend, "structure": structure},
    )
    assert_blocked(result)
    assert result["decision"] == "BLOCK"
    assert result["reason"] == selection.get("reason", "SELECTION_BLOCKED")
    assert result["confidence"] == 0
    assert selection == before


@pytest.mark.parametrize("activity", [False, True], ids=["empty-state", "existing-state"])
@pytest.mark.parametrize("scenario", ["empty-registry", "uncertified", "all-blocked",
                                     "blocked-selection"])
def test_blocked_selection_has_zero_execution_effects(tmp_path, monkeypatch, activity, scenario):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    state = app.state
    registry = state.strategy_registry_v2
    assert registry.list() == []
    if scenario == "uncertified":
        for status in ("DRAFT", "REJECTED"):
            register_strategy(registry, status, status)
    elif scenario == "all-blocked":
        for index in range(2):
            register_strategy(registry, f"blocked-{index}", "BLOCKED")
    elif scenario == "blocked-selection":
        register_strategy(registry, "certified", "CERTIFIED")
        monkeypatch.setattr(state.strategy_selection_service_v2.selection_engine, "select",
                            Mock(return_value={"status": "BLOCKED", "reason": "NO_STRATEGIES"}))
    if activity:
        seed_existing_activity(app)
    before = capture(app)
    registry_before = registry.list()
    guards = forbid_mutations(app, monkeypatch)
    selection = state.strategy_selection_service_v2.select(market_context=CONTEXT)
    assert selection == {"status": "BLOCKED", "reason": "NO_STRATEGIES"}
    decision = state.strategy_decision_service_v2.get_decision(market_context=CONTEXT)
    assert_blocked(decision)
    assert decision["decision"] == "BLOCK"
    assert decision["reason"] == "NO_STRATEGIES"
    plan_args = dict(market_context=CONTEXT, market_data=MARKET_DATA, risk_config=RISK_CONFIG)
    for plan in (state.trade_plan_service_v2.generate(**plan_args),
                 state.trade_plan_service_v2.create_trade_plan(market_context=CONTEXT)):
        assert_blocked(plan)
    # The independent risk entry point must also reject this blocked plan.
    assert_blocked(state.risk_validation_service_v2.validate(
        **plan_args, account_state=ACCOUNT_STATE,
    ))
    risk = Mock(side_effect=AssertionError("Blocked selection reached risk validation"))
    simulation = Mock(side_effect=AssertionError("Blocked selection reached execution simulation"))
    monkeypatch.setattr(state.risk_validation_service_v2, "validate", risk)
    monkeypatch.setattr(state.execution_service_v2.execution_engine, "execute", simulation)
    for _ in range(3):
        assert_blocked(state.execution_service_v2.execute(**plan_args, account_state=ACCOUNT_STATE))
    risk.assert_not_called()
    simulation.assert_not_called()
    for guard in guards:
        guard.assert_not_called()
    assert registry.list() == registry_before
    assert capture(app) == before
    if not activity:
        for field in ("orders", "fills", "broker_positions", "positions", "protections", "oco",
                      "portfolio_open", "portfolio_closed", "journal", "events"):
            assert not before[field], field


@pytest.mark.parametrize("trend,direction", [("BULLISH", "BUY"), ("BEARISH", "SELL")])
def test_certified_selection_preserves_simulated_execution(tmp_path, monkeypatch, trend, direction):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    state = app.state
    register_strategy(state.strategy_registry_v2, "valid", "CERTIFIED")
    register_strategy(state.strategy_registry_v2, "blocked", "BLOCKED")
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    context = {**CONTEXT, "trend": trend}
    selection = state.strategy_selection_service_v2.select(market_context=context)
    assert selection["strategy_id"] == "valid"
    decision = state.strategy_decision_service_v2.get_decision(market_context=context)
    assert decision["decision"] == "EXECUTE"
    assert decision["strategy_id"] == "valid"
    assert decision["direction"] == direction
    args = dict(market_context=context, market_data=MARKET_DATA, risk_config=RISK_CONFIG)
    plan = state.trade_plan_service_v2.generate(**args)
    assert plan["status"] == "READY"
    assert state.trade_plan_service_v2.create_trade_plan(market_context=context)["status"] == "READY"
    validation = state.risk_validation_service_v2.validate(**args, account_state=ACCOUNT_STATE)
    assert validation["status"] == "APPROVED"
    assert validation["risk_allowed"] is True
    risk_spy = Mock(wraps=state.risk_validation_service_v2.validate)
    simulation_spy = Mock(wraps=state.execution_service_v2.execution_engine.execute)
    monkeypatch.setattr(state.risk_validation_service_v2, "validate", risk_spy)
    monkeypatch.setattr(state.execution_service_v2.execution_engine, "execute", simulation_spy)
    result = state.execution_service_v2.execute(**args, account_state=ACCOUNT_STATE)
    assert result == {"status": "EXECUTED", "direction": direction, "entry": plan["entry"],
                      "stop_loss": plan["stop_loss"], "take_profit": plan["take_profit"]}
    risk_spy.assert_called_once()
    simulation_spy.assert_called_once()
    assert capture(app) == before  # This control is explicitly simulated, never PAPER/LIVE.
    for guard in guards:
        guard.assert_not_called()
