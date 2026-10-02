"""Current-PAPER diagnostic accounting; synthetic feed, no LIVE authority."""
from copy import deepcopy
import json
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.current_paper_app_v1 import create_current_paper_app_v1
from backend.backtesting.current_paper_runtime_v1 import _empty_decision_summary
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.test_certified_native_paper_bridge_v1 import _paper, _warm_bootstrap
from backend.tests.test_current_paper_sprint10 import deliver, event, service
from backend.tests.test_paper_runtime_sprint08 import fill_count, witness
from backend.tests.test_production_certified_outcome_v17 import api_settings


def _checkpoint(path):
    with sqlite3.connect(path) as db:
        payload = db.execute("SELECT payload FROM checkpoint WHERE id=1").fetchone()[0]
        phases = db.execute("SELECT phase FROM events ORDER BY id").fetchall()
    return json.loads(payload), [row[0] for row in phases]


def _before_first_injected_decision(s, clock):
    deliver(s, clock, event(0))
    runtime = s._runtime
    first = max(1, runtime._paper.runtime.engine.minimum_candles - 1)
    for index in range(1, first):
        deliver(s, clock, event(index))
    return runtime, first


def test_decisions_maxima_duplicates_controls_reads_and_recovery(api_settings, tmp_path):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    paper = runtime._paper.runtime
    before = deepcopy(s.get_snapshot()["session_decision_summary"])
    financial = paper.account.get_state()
    decisions = iter((
        TradingDecisionV2(TradingActionV2.HOLD, .37, "diagnostic hold", {"confluence_score": .71}),
        TradingDecisionV2(TradingActionV2.BUY, .93, "diagnostic buy", {"confluence_score": .84}),
        TradingDecisionV2(TradingActionV2.SELL, .81, "diagnostic sell"),
        TradingDecisionV2(TradingActionV2.HOLD, .52, "invalid score", {"confluence_score": float("nan")}),
    ))
    paper.session.strategy_runner_v2.run = lambda context: next(decisions)
    for index, action in enumerate(("HOLD", "BUY", "SELL", "HOLD"), first):
        row = event(index)
        snapshot = deliver(s, clock, row)
        assert snapshot["latest_decision"]["action"] == action
        assert s.ingest(row)["session_decision_summary"] == snapshot["session_decision_summary"]
        assert paper.account.get_state() == financial
        assert not paper.lifecycle.get_active_positions()
        assert not paper.journal.trades and not paper.completed
        assert not paper.risk_evaluations
        assert snapshot["plan"] is snapshot["submission"] is None
    summary = snapshot["session_decision_summary"]
    assert summary["total_hold_decisions"] == before["total_hold_decisions"] + 2
    assert summary["total_buy_decisions"] == before["total_buy_decisions"] + 1
    assert summary["total_sell_decisions"] == before["total_sell_decisions"] + 1
    assert summary["max_confidence_observed"] == max(before["max_confidence_observed"] or 0, .93)
    assert summary["max_confluence_observed"] == max(before["max_confluence_observed"] or 0, .84)
    assert summary["plan_count"] == summary["submission_count"] == 0
    assert "confluence_score" not in snapshot["latest_decision"]["metadata"]
    assert paper.session.strategy_runner_v2.run is not None

    app = create_current_paper_app_v1(service=s, admin_token="summary-test-token")
    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/api/v2/backtesting/dashboard").json()["paper_research"]["session_decision_summary"] == summary
            assert client.get("/api/v2/paper/readiness").status_code == 200
    # TestClient lifespan shuts down the service, itself a non-counting control.
    assert s.get_snapshot()["session_decision_summary"] == summary
    saved, phases = _checkpoint(tmp_path / "current.sqlite")
    assert saved["session_decision_summary"] == summary
    assert all(phase == "COMPLETED" for phase in phases)
    recovered, _ = service(tmp_path)
    evidence = recovered.get_snapshot()
    assert evidence["session_decision_summary"] == summary
    assert evidence["operational_state_restored"] is False
    assert evidence["recovery_required"] is True
    assert recovered.get_snapshot()["session_decision_summary"] == summary


def test_plan_and_submission_count_only_when_canonical_results_exist(api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s, clock, event(0))
    runtime = s._runtime
    witness(runtime, entries=(5,))
    assert s.get_snapshot()["session_decision_summary"] == _empty_decision_summary()
    s.control("enable")
    assert s.get_snapshot()["session_decision_summary"] == _empty_decision_summary()
    prior_plan = prior_submission = 0
    trade_snapshot = None
    for index in range(1, 6):
        snap = deliver(s, clock, event(index))
        if snap["plan"] is not None:
            trade_snapshot = snap
        prior_plan += int(snap["plan"] is not None)
        prior_submission += int(snap["submission"] is not None)
        assert snap["session_decision_summary"]["plan_count"] == prior_plan
        assert snap["session_decision_summary"]["submission_count"] == prior_submission
    assert trade_snapshot is not None
    assert trade_snapshot["latest_decision"]["action"] == "BUY"
    assert trade_snapshot["submission"]["accepted"] is True
    assert snap["session_decision_summary"]["total_buy_decisions"] == 1
    assert snap["session_decision_summary"]["plan_count"] == 1
    assert snap["session_decision_summary"]["submission_count"] == 1
    assert fill_count(runtime) == 1
    assert len(runtime._paper.runtime.lifecycle.get_active_positions()) == 1
    assert len(runtime._paper.runtime.journal.trades) == 1
    assert not runtime._paper.runtime.completed
    saved, _ = _checkpoint(tmp_path / "current.sqlite")
    assert trade_snapshot["plan"] is not None
    assert trade_snapshot["submission"] is not None
    assert saved["plan"] == snap["plan"]
    assert saved["submission"] == snap["submission"]
    assert saved["account_overview"] == snap["account_overview"]
    s.control("disable")
    s.control("emergency_block")
    assert s.get_snapshot()["session_decision_summary"] == snap["session_decision_summary"]
    s.shutdown()


def test_failed_completion_preserves_last_committed_summary(api_settings, tmp_path, monkeypatch):
    s, clock = service(tmp_path)
    runtime, first = _before_first_injected_decision(s, clock)
    runtime._paper.runtime.session.strategy_runner_v2.run = lambda context: TradingDecisionV2(
        TradingActionV2.HOLD, .65, "committed hold", {"confluence_score": .6})
    deliver(s, clock, event(first))
    committed = deepcopy(s.get_snapshot()["session_decision_summary"])
    saved, phases = _checkpoint(tmp_path / "current.sqlite")
    assert saved["session_decision_summary"] == committed
    monkeypatch.setattr(runtime, "_save", Mock(side_effect=OSError("synthetic checkpoint failure")))
    with pytest.raises(OSError, match="synthetic checkpoint failure"):
        deliver(s, clock, event(first + 1))
    assert runtime._fault == "RECOVERY_REQUIRED"
    assert s.get_snapshot()["session_decision_summary"] == committed
    saved_after, phases_after = _checkpoint(tmp_path / "current.sqlite")
    assert saved_after["session_decision_summary"] == committed
    assert phases_after == phases + ["INFLIGHT"]
    runtime._db.close()
    recovered, _ = service(tmp_path)
    assert recovered.get_snapshot()["session_decision_summary"] == committed
    assert recovered.get_snapshot()["pending_events"] == 1
    assert recovered.get_snapshot()["operational_state_restored"] is False


def test_rejected_submission_result_counts_without_fill(api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s, clock, event(0))
    runtime = s._runtime
    witness(runtime, entries=(5,))
    s.control("enable")
    life = runtime._paper.runtime.lifecycle
    life.execution_risk_gate_v1.evaluate_trade = Mock(return_value={"execution": "BLOCKED"})
    for index in range(1, 5):
        snap = deliver(s, clock, event(index))
    assert snap["latest_decision"]["action"] == "BUY"
    assert snap["plan"] is not None
    assert snap["submission"] is not None
    assert snap["submission"]["accepted"] is False
    assert snap["session_decision_summary"]["plan_count"] == 1
    assert snap["session_decision_summary"]["submission_count"] == 1
    assert fill_count(runtime) == 0
    assert not life.get_active_positions()
    assert not runtime._paper.runtime.journal.trades
    assert not runtime._paper.runtime.completed
    s.shutdown()


def test_bootstrap_and_pre_runtime_reads_do_not_count(api_settings, tmp_path):
    s, _ = _paper(tmp_path, api_settings)
    assert s.get_snapshot()["session_decision_summary"] == _empty_decision_summary()
    assert s._runtime is None
    s.install_strategy_bootstrap(_warm_bootstrap())
    for _ in range(3):
        assert s.get_snapshot()["session_decision_summary"] == _empty_decision_summary()
    assert s._runtime is None
    s.shutdown()
