"""Strategy intelligence GET must preserve strategic and operational state."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.routers import strategy_intelligence_service_api_v2 as endpoint
from backend.intelligence.strategy_intelligence_service_v1 import StrategyIntelligenceServiceV1
from backend.tests.test_dashboard_read_execution_safety_v2 import (
    capture,
    forbid_mutations,
    seed_existing_activity,
)


URL = "/api/v2/strategy/intelligence"
STRATEGY = "ATR 2.0 RR 1:3"


def strategic_stores(service):
    pipeline = service.pipeline
    return {
        "learning_engine.history": pipeline.learning_engine.history,
        "adaptive_engine.decisions": pipeline.adaptive_engine.decisions,
        "market_engine.analysis": pipeline.market_engine.analysis,
        "autonomous_engine.decisions": pipeline.autonomous_engine.decisions,
        "memory_engine.memory": pipeline.memory_engine.memory,
    }


def seed_legacy_analysis(service):
    """Reproduce old contamination exclusively in test setup, before reads."""
    for result, pnl in [("WIN", 300), ("WIN", 250), ("LOSS", -100)]:
        service.pipeline.learning_engine.record_result(STRATEGY, result, pnl)
    service.analyze_strategy(STRATEGY, 47.4, "TRENDING", "NORMAL")


def forbid_strategic_writes(service, monkeypatch):
    pipeline = service.pipeline
    targets = [
        (service, "analyze_strategy"),
        (pipeline, "analyze"),
        (pipeline.learning_engine, "record_result"),
        (pipeline.adaptive_engine, "evaluate"),
        (pipeline.market_engine, "evaluate"),
        (pipeline.autonomous_engine, "decide"),
        (pipeline.memory_engine, "record_decision"),
        (pipeline.memory_engine, "update_result"),
    ]
    guards = []
    for target, method in targets:
        guard = Mock(side_effect=AssertionError(f"GET invoked {method}"))
        monkeypatch.setattr(target, method, guard)
        guards.append(guard)
    return guards


def assert_unavailable(payload, reason):
    assert payload["status"] == "UNAVAILABLE"
    assert payload["data_status"] == reason
    assert payload["source"] is None
    assert payload["strategy"] is None
    assert payload["final_decision"] == "UNAVAILABLE"
    assert payload["confidence"] is None
    assert payload["reason"] == [reason]
    assert payload["scores"] == {"backtest": None, "learning": None, "final": None}
    assert payload["market"] == {"regime": None, "volatility": None, "compatibility": None}
    assert payload["history"] == {"trades": None, "win_rate": None}


@pytest.mark.parametrize("activity", [False, True], ids=["empty-operational", "existing-operational"])
@pytest.mark.parametrize("strategic_state", ["empty", "legacy", "partial"])
def test_repeated_and_concurrent_gets_preserve_all_state(
    tmp_path, monkeypatch, activity, strategic_state,
):
    service = StrategyIntelligenceServiceV1()
    monkeypatch.setattr(endpoint, "service", service)
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    if activity:
        seed_existing_activity(app)
    if strategic_state == "legacy":
        seed_legacy_analysis(service)
    elif strategic_state == "partial":
        service.pipeline.memory_engine.memory.append({"strategy": "untraceable"})

    stores = strategic_stores(service)
    before = deepcopy(stores)
    operational_before = capture(app)
    learning_before = service.pipeline.learning_engine.analyze_strategy(STRATEGY)
    guards = forbid_mutations(app, monkeypatch)
    guards += forbid_strategic_writes(service, monkeypatch)
    client = TestClient(app)  # No startup workers or external broker connection.
    try:
        def read():
            response = client.get(URL)
            assert response.status_code == 200
            return response.json()

        first = read()
        assert_unavailable(first, "NO_DATA" if strategic_state == "empty" else "UNVERIFIABLE_PROVENANCE")
        for _ in range(10):
            assert read() == first
            assert strategic_stores(service) == before
        barrier = Barrier(8)

        def concurrent_read(_):
            barrier.wait(timeout=10)
            return read()

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(concurrent_read, range(24)))
        assert all(response == first for response in responses)
    finally:
        client.close()

    after = strategic_stores(service)
    assert after == before  # Includes nested values in each of the five stores.
    assert all(after[name] is original for name, original in stores.items())
    learning_after = service.pipeline.learning_engine.analyze_strategy(STRATEGY)
    assert learning_after["trades"] - learning_before["trades"] == 0
    assert learning_after["total_pnl"] - learning_before["total_pnl"] == 0
    assert learning_after["learning_score"] == learning_before["learning_score"]
    assert after["adaptive_engine.decisions"] == before["adaptive_engine.decisions"]
    assert after["autonomous_engine.decisions"] == before["autonomous_engine.decisions"]
    assert capture(app) == operational_before
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize("store_name", list(strategic_stores(StrategyIntelligenceServiceV1())))
def test_each_untraceable_store_is_rejected_without_cleanup(monkeypatch, store_name):
    service = StrategyIntelligenceServiceV1()
    monkeypatch.setattr(endpoint, "service", service)
    stores = strategic_stores(service)
    stores[store_name].append({"strategy": "unknown", "source": "unverified-claim"})
    before = deepcopy(stores)
    guards = forbid_strategic_writes(service, monkeypatch)
    payload = endpoint.get_strategy_intelligence()
    assert_unavailable(payload, "UNVERIFIABLE_PROVENANCE")
    payload["scores"]["learning"] = 999
    payload["reason"].append("caller mutation")
    assert_unavailable(endpoint.get_strategy_intelligence(), "UNVERIFIABLE_PROVENANCE")
    assert strategic_stores(service) == before
    for guard in guards:
        guard.assert_not_called()
