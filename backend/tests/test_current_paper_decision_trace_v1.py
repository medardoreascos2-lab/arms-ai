"""Current-PAPER trace durability and evaluation truth on synthetic inputs."""
from copy import deepcopy
import json
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.current_paper_app_v1 import create_current_paper_app_v1
from backend.backtesting.current_paper_runtime_v1 import MAX_DECISION_TRACE_RECORDS
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1, _plain
from backend.backtesting import current_paper_entry_authority_v1 as entry_module
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.test_certified_native_paper_bridge_v1 import _warm_bootstrap
from backend.tests.test_current_paper_decision_summary_v1 import _before_first_injected_decision
from backend.tests.test_current_paper_entry_authority_v1 import setup as entry_setup
from backend.tests.test_current_paper_sprint10 import START, deliver, event, service
from backend.tests.test_current_paper_auto_admission_e2e_v1 import (
    deltas, feed, setup, warm,
)
from backend.tests.test_production_certified_outcome_v17 import api_settings


def _database(path):
    with sqlite3.connect(path) as db:
        traces = [json.loads(row[0]) for row in db.execute(
            "SELECT payload FROM decision_trace ORDER BY sequence")]
        phases = [row[0] for row in db.execute("SELECT phase FROM events ORDER BY id")]
    return traces, phases


def test_hold_buy_sell_are_once_and_recovery_reads_only(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    paper = runtime._paper.runtime
    account_before = deepcopy(paper.account.get_state())
    run = Mock(side_effect=(
        TradingDecisionV2(TradingActionV2.HOLD, .37, "hold", {"confluence_score": .71}),
        TradingDecisionV2(TradingActionV2.BUY, .93, "buy", {"confluence_score": .84}),
        TradingDecisionV2(TradingActionV2.SELL, .81, "sell", {"confluence_score": .82}),
    ))
    paper.session.strategy_runner_v2.run = run
    for offset, action in enumerate(("HOLD", "BUY", "SELL")):
        row = event(first + offset)
        deliver(s, clock, row)
        trace = s.get_decision_trace()
        assert trace["total"] == offset + 1
        assert trace["records"][0]["action"] == action
        assert trace["records"][0]["sequence"] == offset + 1
        assert trace["records"][0]["observation"]["event_id"] == row.event_id
        assert trace["records"][0]["observation"]["source_sha256"]
        assert trace["records"][0]["observation"]["trading_date"]
        assert trace["records"][0]["observation"]["instrument"] == "NQ"
        assert trace["records"][0]["plan_present"] is False
        assert trace["records"][0]["submission_present"] is False
        assert trace["records"][0]["risk_status"] == "NOT_EVALUATED"
        assert trace["records"][0]["news_l1_spread_status"] == "NOT_EVALUATED"
        assert trace["records"][0]["entry_gate_evaluations"] == []
        assert trace["records"][0]["entry_gate_status"].startswith("NOT_EVALUATED_")
        # The canonical duplicate path must neither call strategy nor recount.
        assert s.ingest(row)["session_decision_summary"] == s.get_snapshot()["session_decision_summary"]
        assert s.get_decision_trace()["total"] == offset + 1
    assert run.call_count == 3
    assert paper.account.get_state() == account_before
    assert not paper.lifecycle.broker_connector_v2.get_orders()
    assert not paper.lifecycle.broker_connector_v2.get_fills()
    assert not paper.lifecycle.get_active_positions()
    assert not paper.journal.trades
    saved, phases = _database(tmp_path / "current.sqlite")
    assert len(saved) == 3 and all(x == "COMPLETED" for x in phases)
    assert [record["sequence"] for record in saved] == [1, 2, 3]
    assert [record["observation"]["event_id"] for record in saved] == [
        event(first + offset).event_id for offset in range(3)]
    summary = s.get_snapshot()["session_decision_summary"]
    assert [summary[f"total_{action}_decisions"] for action in ("hold", "buy", "sell")] == [1, 1, 1]
    with sqlite3.connect(tmp_path / "current.sqlite") as db:
        maxima = db.execute("SELECT max(confidence),max(confluence),"
            "sum(plan_present),sum(submission_present) FROM decision_trace").fetchone()
    assert maxima == (summary["max_confidence_observed"],
        summary["max_confluence_observed"], summary["plan_count"],
        summary["submission_count"])
    runtime._db.close()
    recovered, _ = service(tmp_path)
    evidence = recovered.get_decision_trace(limit=2)
    assert evidence["status"] == "COMMITTED_EVIDENCE"
    assert evidence["total"] == 3 and len(evidence["records"]) == 2
    assert evidence["operational_state_restored"] is False
    assert recovered.get_snapshot()["recovery_required"] is True
    assert len(_database(tmp_path / "current.sqlite")[0]) == 3


def test_actual_strategy_evidence_and_read_controls_do_not_recount(api_settings, tmp_path):
    s, clock = service(tmp_path)
    assert s.get_decision_trace()["status"] == "AWAITING_MARKET_DATA"
    runtime, first = _before_first_injected_decision(s, clock)
    assert s.get_decision_trace()["total"] == 0
    s.control("enable")
    s.control("disable")
    assert s.get_decision_trace()["total"] == 0
    runner = runtime._paper.runtime.session.strategy_runner_v2
    before_calls = runner.calls
    for index in range(first, first + 12):
        deliver(s, clock, event(index))
    trace = s.get_decision_trace()["records"][0]
    assert runner.calls == before_calls + 12
    assert s.get_decision_trace()["total"] == 12
    assert trace["strategy_evidence"] == runtime._snapshot["strategy_evidence"]
    assert set(trace["strategy_evidence"]) == {
        "trend", "structure", "liquidity", "fvg", "regime", "confluence", "quality"}
    assert trace["trade_quality_score"] == trace["strategy_evidence"]["quality"]["score"]
    assert trace["confluence_grade"] == trace["strategy_evidence"]["confluence"]["grade"]
    assert trace["confluence_engine_score"] == trace["strategy_evidence"]["confluence"]["score"]
    assert trace["confluence_approved"] == trace["strategy_evidence"]["confluence"]["approved"]
    app = create_current_paper_app_v1(service=s, admin_token="trace-test-token")
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/api/v2/backtesting/dashboard").status_code == 200
            assert client.get("/api/v2/paper/readiness").status_code == 200
            assert s.get_decision_trace(limit=1)["total"] == 12
    assert s.get_decision_trace(limit=1)["total"] == 12  # After shutdown.
    assert len(_database(tmp_path / "current.sqlite")[0]) == 12


def test_emergency_control_does_not_create_trace(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    deliver(s, clock, event(first))
    total = s.get_decision_trace()["total"]
    s.control("emergency_block")
    assert s.get_decision_trace()["total"] == total
    assert runtime._paper.runtime.lifecycle.broker_connector_v2.get_orders() == []


def test_bootstrap_has_no_trace_until_a_live_decision(api_settings, tmp_path):
    s, clock = service(tmp_path)
    s.connection(False)
    s.install_strategy_bootstrap(_warm_bootstrap(start=START))
    assert s.get_decision_trace()["total"] == 0
    assert s._runtime is None
    s.connection(True)
    deliver(s, clock, event(0))
    assert s._runtime.strategy_bootstrap_bar_count == 120
    assert s.get_decision_trace()["total"] == 1
    assert s.get_snapshot()["session_decision_summary"]["total_hold_decisions"] == 1


def test_failed_completion_has_no_committed_trace(api_settings, tmp_path, monkeypatch):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    paper = runtime._paper.runtime
    paper.session.strategy_runner_v2.run = lambda _: TradingDecisionV2(
        TradingActionV2.HOLD, .5, "hold")
    deliver(s, clock, event(first))
    committed = deepcopy(s.get_snapshot()["session_decision_summary"])
    account_before = deepcopy(paper.account.get_state())
    monkeypatch.setattr(runtime, "_save", Mock(side_effect=OSError("synthetic trace/checkpoint failure")))
    with pytest.raises(OSError, match="synthetic trace/checkpoint failure"):
        deliver(s, clock, event(first + 1))
    traces, phases = _database(tmp_path / "current.sqlite")
    assert len(traces) == 1 and phases[-1] == "INFLIGHT"
    assert s.get_snapshot()["session_decision_summary"] == committed
    assert paper.account.get_state() == account_before
    assert runtime._fault == "RECOVERY_REQUIRED"
    runtime._db.close()
    recovered, _ = service(tmp_path)
    assert recovered.get_decision_trace()["total"] == 1
    assert recovered.get_snapshot()["pending_events"] == 1


def test_checkpoint_failure_after_trace_insert_rolls_trace_back(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    runtime._paper.runtime.session.strategy_runner_v2.run = lambda _: TradingDecisionV2(
        TradingActionV2.HOLD, .5, "hold")
    deliver(s, clock, event(first))
    observed_inserts = []

    def deny_checkpoint(action, table, _column, _database, _trigger):
        if action == sqlite3.SQLITE_INSERT and table == "decision_trace":
            observed_inserts.append(table)
        if action == sqlite3.SQLITE_INSERT and table == "checkpoint":
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    runtime._db.set_authorizer(deny_checkpoint)
    with pytest.raises(sqlite3.DatabaseError):
        deliver(s, clock, event(first + 1))
    runtime._db.set_authorizer(None)
    traces, phases = _database(tmp_path / "current.sqlite")
    assert observed_inserts
    assert len(traces) == 1 and phases[-1] == "INFLIGHT"
    assert runtime._fault == "RECOVERY_REQUIRED"


def test_legacy_namespace_trace_read_is_evidence_only(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    deliver(s, clock, event(first))
    s.shutdown()
    with sqlite3.connect(tmp_path / "current.sqlite") as db:
        db.execute("DROP TABLE decision_trace")  # Synthetic pre-trace namespace.
    recovered, _ = service(tmp_path)
    assert recovered.get_decision_trace()["status"] == "UNAVAILABLE_LEGACY"
    assert recovered.get_decision_trace()["records"] == []
    assert recovered.get_snapshot()["recovery_required"] is True
    assert recovered._runtime._paper is None


def test_corrupt_trace_payload_is_not_reported_as_committed_evidence(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    deliver(s, clock, event(first))
    s.shutdown()
    with sqlite3.connect(tmp_path / "current.sqlite") as db:
        db.execute("UPDATE decision_trace SET payload='{}' WHERE sequence=1")
    recovered, _ = service(tmp_path)
    evidence = recovered.get_decision_trace()
    assert evidence["status"] == "UNREADABLE_RECONCILIATION_REQUIRED"
    assert evidence["records"] == []
    assert evidence["operational_state_restored"] is False


def test_trace_capacity_fails_before_strategy_or_financial_work(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    assert MAX_DECISION_TRACE_RECORDS == 4096
    runtime._trace_limit = 1  # Inject a small limit; same preflight path as production.
    run = Mock(side_effect=(
        TradingDecisionV2(TradingActionV2.HOLD, .5, "hold"),
        TradingDecisionV2(TradingActionV2.BUY, .95, "would buy",
            {"confluence_score": .95, "grade": "A+", "stop_loss": 9970,
             "take_profit": 10060}),
    ))
    paper = runtime._paper.runtime
    paper.session.strategy_runner_v2.run = run
    deliver(s, clock, event(first))
    before = (paper.index, deepcopy(paper.account.get_state()),
        len(paper.lifecycle.broker_connector_v2.get_orders()),
        len(paper.lifecycle.broker_connector_v2.get_fills()),
        len(paper.journal.trades))
    with pytest.raises(RuntimeError, match="DECISION_TRACE_CAPACITY_REACHED"):
        deliver(s, clock, event(first + 1))
    assert run.call_count == 1
    assert (paper.index, paper.account.get_state(),
        len(paper.lifecycle.broker_connector_v2.get_orders()),
        len(paper.lifecycle.broker_connector_v2.get_fills()),
        len(paper.journal.trades)) == before
    traces, phases = _database(tmp_path / "current.sqlite")
    assert len(traces) == 1 and phases[-1] == "INFLIGHT"
    assert runtime._fault == "RECOVERY_REQUIRED"


def test_entry_diagnostics_preserve_early_returns_and_gate_call_counts(monkeypatch):
    owner, gate, news, l1, _, decision = entry_setup()
    gate.reasons = Mock(wraps=gate.reasons)
    news.inspect = Mock(wraps=news.inspect)
    l1.inspect = Mock(wraps=l1.inspect)
    owner.clock = Mock(wraps=owner.clock)
    original_atr_calculate = entry_module.ATREngine.calculate
    atr_calls = []

    def count_atr(instance, candles):
        atr_calls.append(candles)
        return original_atr_calculate(instance, candles)

    monkeypatch.setattr(entry_module.ATREngine, "calculate", count_atr)

    invalid_diagnostic = {}
    assert owner.inspect(row=None, decision=decision, open_positions=0,
        diagnostic=invalid_diagnostic) == ["CURRENT_CLOSED_OBSERVATION_REQUIRED"]
    assert gate.reasons.call_count == 0
    assert owner.clock.call_count == news.inspect.call_count == l1.inspect.call_count == 0
    assert len(atr_calls) == 0
    assert all(value["status"] == "NOT_EVALUATED"
        for value in invalid_diagnostic.values())

    hold_diagnostic = {}
    hold = TradingDecisionV2(TradingActionV2.HOLD, .5, "hold")
    assert owner.inspect(row=owner.rows[-1], decision=hold, open_positions=0,
        diagnostic=hold_diagnostic) == ["SIGNAL_INVALID"]
    assert gate.reasons.call_count == 1
    assert owner.clock.call_count == news.inspect.call_count == l1.inspect.call_count == 0
    assert len(atr_calls) == 0
    assert hold_diagnostic["market_session"]["status"] == "PASS"
    assert hold_diagnostic["max_position"]["status"] == "PASS"
    assert all(hold_diagnostic[name]["status"] == "NOT_EVALUATED" for name in
        ("probability", "confluence", "atr", "signal_age", "news", "l1",
         "quote_freshness", "spread", "stop", "target", "plan_direction", "rr"))

    actionable_diagnostic = {}
    assert owner.inspect(row=owner.rows[-1], decision=decision, open_positions=0,
        diagnostic=actionable_diagnostic) == []
    assert gate.reasons.call_count == 2
    assert owner.clock.call_count == news.inspect.call_count == l1.inspect.call_count == 1
    assert len(atr_calls) == 1
    assert all(value["status"] == "PASS" for value in actionable_diagnostic.values())


@pytest.mark.parametrize("action", (TradingActionV2.BUY, TradingActionV2.SELL))
def test_actionable_accepted_trace_preserves_plan_risk_and_fill(
        api_settings, tmp_path, monkeypatch, action):
    s, clock, _, _ = setup(tmp_path, monkeypatch, api_settings)
    warm(s, clock)
    if action is TradingActionV2.SELL:
        def sell(context):
            price = context["candle"]["close"]
            return TradingDecisionV2(action, .95, "synthetic sell",
                {"confluence_score": .95, "grade": "A+",
                 "stop_loss": price + 30, "take_profit": price - 60})
        s._runtime._paper.runtime.session.strategy_runner_v2.run = sell
    inspected = Mock(wraps=s.entry_authority.inspect)
    s.entry_authority.inspect = inspected
    before = deltas(s)
    snapshot = feed(s, clock, 15)
    record = s.get_decision_trace(limit=1)["records"][0]
    assert record["action"] == action.value
    assert record["entry_gate_status"] == "EVALUATED"
    assert record["entry_gate_evaluations"]
    assert inspected.call_count == len(record["entry_gate_evaluations"]) == 2
    assert all(not x["blocking_reasons"] for x in record["entry_gate_evaluations"])
    assert record["news_l1_spread_status"] == "EVALUATED_SEE_ENTRY_GATE_EVALUATIONS"
    for evaluation in record["entry_gate_evaluations"]:
        assert all(item["status"] == "PASS" for item in
            evaluation["infrastructure_gates"].values())
    assert record["plan_present"] and record["plan"] == snapshot["plan"]
    assert record["submission_present"] and record["submission"] == snapshot["submission"]
    assert record["submission_outcome"]["accepted"] is True
    assert record["prepared_order_present"] is True
    assert record["execution_present"] is True
    assert record["risk_status"] == "EVALUATED"
    assert record["risk_evaluation"] == snapshot["risk_evaluation"]
    assert tuple(b-a for a,b in zip(before,deltas(s))) == (1,1,1,1)
    assert snapshot["execution_state"] == "OPEN"
    assert snapshot["session_decision_summary"]["plan_count"] == 1
    assert snapshot["session_decision_summary"]["submission_count"] == 1
    with sqlite3.connect(tmp_path / "paper.sqlite") as db:
        aggregates = db.execute("SELECT max(confidence),max(confluence),"
            "sum(plan_present),sum(submission_present) FROM decision_trace").fetchone()
    summary = snapshot["session_decision_summary"]
    assert aggregates == (summary["max_confidence_observed"],
        summary["max_confluence_observed"], summary["plan_count"],
        summary["submission_count"])


@pytest.mark.parametrize("action", (TradingActionV2.BUY, TradingActionV2.SELL))
def test_actionable_gate_veto_is_recorded_without_execution(
        api_settings, tmp_path, monkeypatch, action):
    s, clock, _, _ = setup(tmp_path, monkeypatch, api_settings)
    warm(s, clock)
    if action is TradingActionV2.SELL:
        def sell(context):
            price = context["candle"]["close"]
            return TradingDecisionV2(action, .95, "synthetic sell",
                {"confluence_score": .95, "grade": "A+",
                 "stop_loss": price + 30, "take_profit": price - 60})
        s._runtime._paper.runtime.session.strategy_runner_v2.run = sell
    s.entry_authority.news.inspect = lambda **_: dict(
        status="PACKAGE_MISSING", reason="PACKAGE_MISSING", blocked=True)
    before = deltas(s)
    snapshot = feed(s, clock, 15)
    record = s.get_decision_trace(limit=1)["records"][0]
    assert record["action"] == action.value
    assert record["entry_gate_status"] == "EVALUATED"
    assert any("NEWS_MISSING" in x["blocking_reasons"] for x in record["entry_gate_evaluations"])
    assert any(x["infrastructure_gates"]["news"]["reasons"] == ["NEWS_MISSING"]
        for x in record["entry_gate_evaluations"])
    assert all(x["infrastructure_gates"]["news"]["source"]["status"] == "PACKAGE_MISSING"
        for x in record["entry_gate_evaluations"])
    assert record["submission_present"]
    assert record["submission_outcome"]["accepted"] is False
    assert record["submission_outcome"]["reason"] == "NEWS_MISSING"
    assert "NEWS_MISSING" in record["submission_outcome"]["blocking_reasons"]
    assert record["prepared_order_present"] is False
    assert record["execution_present"] is False
    # The existing risk pipeline runs before the current-only entry guard.
    assert record["risk_status"] == "EVALUATED"
    assert record["risk_evaluation"] == snapshot["risk_evaluation"]
    assert record["plan_present"] == (snapshot["plan"] is not None)
    assert deltas(s) == before


def test_unreached_quote_and_spread_gates_remain_not_evaluated(
        api_settings, tmp_path, monkeypatch):
    s, clock, view, _ = setup(tmp_path, monkeypatch, api_settings)
    warm(s, clock)
    s.l1_reader.inspect = lambda: (dict(view, status="WAITING"), None)
    before = deltas(s)
    feed(s, clock, 15)
    record = s.get_decision_trace(limit=1)["records"][0]
    assert record["entry_gate_status"] == "EVALUATED"
    for evaluation in record["entry_gate_evaluations"]:
        gates = evaluation["infrastructure_gates"]
        assert gates["l1"]["reasons"] == ["QUOTE_MISSING"]
        assert gates["quote_freshness"]["status"] == "NOT_EVALUATED"
        assert gates["spread"]["status"] == "NOT_EVALUATED"
        assert gates["news"]["status"] == "PASS"
    assert deltas(s) == before


def test_health_block_never_labels_news_or_l1_pass(api_settings, tmp_path, monkeypatch):
    s, clock, _, _ = setup(tmp_path, monkeypatch, api_settings)
    warm(s, clock)
    s._runtime.health_eligible = lambda: False
    before = deltas(s)
    feed(s, clock, 15)
    record = s.get_decision_trace(limit=1)["records"][0]
    assert record["entry_gate_status"] == "NOT_EVALUATED_READINESS_BLOCKED"
    assert record["entry_gate_evaluations"] == []
    assert record["news_l1_spread_status"] == "NOT_EVALUATED"
    assert record["risk_status"] == "NOT_EVALUATED"
    assert deltas(s) == before


def test_entry_authority_skipped_after_health_change_is_not_labeled_evaluated(
        api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, _ = _before_first_injected_decision(s, clock)
    runtime.health_eligible = lambda: False
    runtime._trace_in_process = True
    try:
        assert runtime._entry_reasons() == ["CURRENT_PAPER_HEALTH_UNAVAILABLE"]
    finally:
        runtime._trace_in_process = False
    decision = TradingDecisionV2(TradingActionV2.BUY, .95, "synthetic",
        {"confluence_score": .95})
    trace = runtime._decision_trace(runtime._paper.runtime.current, decision)
    assert trace["entry_gate_status"] == "NOT_EVALUATED_ENTRY_AUTHORITY_SKIPPED"
    assert trace["entry_gate_evaluations"][0]["entry_authority_inspected"] is False
    assert trace["entry_gate_evaluations"][0]["infrastructure_gates"]["health"] == {
        "status": "BLOCKED", "reasons": ["CURRENT_PAPER_HEALTH_UNAVAILABLE"]}


def test_gate_diagnostic_collection_has_identical_financial_behavior(
        api_settings, tmp_path, monkeypatch):
    instrumented, instrumented_clock, _, _ = setup(
        tmp_path / "instrumented", monkeypatch, api_settings)
    baseline, baseline_clock, _, _ = setup(
        tmp_path / "baseline", monkeypatch, api_settings)
    original_inspect = baseline.entry_authority.inspect

    def without_gate_diagnostics(*, row, decision, open_positions, diagnostic=None):
        return original_inspect(row=row, decision=decision,
            open_positions=open_positions)

    baseline.entry_authority.inspect = without_gate_diagnostics
    warm(instrumented, instrumented_clock)
    warm(baseline, baseline_clock)
    baseline_runtime = baseline._runtime
    # Test-only reference path: the existing generic processing and checkpoint
    # methods run with the same Current-PAPER submission guard, without trace.
    baseline_runtime._process = lambda observation: PaperRuntimeV1._process(
        baseline_runtime, observation)
    baseline_runtime._save = lambda: PaperRuntimeV1._save(baseline_runtime)
    baseline_trace_total = baseline.get_decision_trace()["total"]

    def financial(service):
        runtime = service._runtime._paper.runtime
        life = runtime.lifecycle
        snapshot = service.get_snapshot()
        return dict(decision=snapshot["latest_decision"], plan=snapshot["plan"],
            submission=snapshot["submission"], risk=snapshot["risk_evaluation"],
            orders=life.broker_connector_v2.get_orders(),
            fills=life.broker_connector_v2.get_fills(),
            positions=life.get_active_positions(),
            journal=runtime.journal.trades,
            account=snapshot["account_overview"])

    def comparable(value):
        value = _plain(value)
        if isinstance(value, dict):
            return {key: comparable(item) for key, item in value.items()
                if not (key.endswith("_id") or key in
                    ("submitted_at", "updated_at", "filled_at", "timestamp"))}
        if isinstance(value, list):
            return [comparable(item) for item in value]
        return value

    for index, conditions in ((15, {}), (16, {"low": 9960})):
        feed(instrumented, instrumented_clock, index, **conditions)
        feed(baseline, baseline_clock, index, **conditions)
        assert comparable(financial(instrumented)) == comparable(financial(baseline))
    assert instrumented.get_decision_trace()["total"] > 0
    assert baseline.get_decision_trace()["total"] == baseline_trace_total
