"""Synthetic safety witnesses are explicit; real detector parity is a separate soak."""
from dataclasses import replace
from datetime import timedelta
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.paper_rc_app_v1 import create_paper_rc_app_v1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1
from backend.config.api_settings import APISettings
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.test_historical_accounting_sprint07r import observations
from backend.tests.test_historical_eligibility_v31 import policy
from backend.tests.test_paper_research_sprint07r import config
from backend.tests.test_production_certified_outcome_v17 import api_settings


def make(policy, tmp_path, rows=None):
    return PaperRuntimeV1(mode="PAPER_RESEARCH", config=config(), settings=APISettings(),
        policy=policy, observations=rows or observations(policy), contract="JUN25",
        state_path=tmp_path/"paper.sqlite", initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")


def witness(service, entries=(5,)):
    def strategy(context):
        if context["signal_index"] not in entries:
            return TradingDecisionV2(TradingActionV2.HOLD, .5, "synthetic HOLD")
        price = context["candle"]["close"]
        return TradingDecisionV2(TradingActionV2.BUY, .95, "synthetic execution witness",
            {"stop_loss":price-30, "take_profit":price+60, "confluence_score":.95, "grade":"A+", "reasons":[]})
    service._paper.runtime.session.strategy_runner_v2.run = strategy


def fill_count(service):
    return len(service._paper.runtime.lifecycle.broker_connector_v2.get_fills())


def test_complete_path_and_read_safety(policy, api_settings, tmp_path, monkeypatch):
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (10000,10060,10000,10000)
    rows = observations(policy, prices)
    service = make(policy, tmp_path, rows)
    witness(service)
    app = create_paper_rc_app_v1(mode="PAPER_RESEARCH", configuration_id="fixture", runtime=service, admin_token="fixture-token")
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "PROCESS_HEALTHY"
        assert client.get("/api/v2/paper/readiness").json()["paper_ready"] is False
        assert client.post("/api/v2/paper/enable").status_code == 401
        headers = {"X-ARMS-ADMIN-TOKEN":"fixture-token"}
        assert client.post("/api/v2/paper/enable", headers=headers).status_code == 200
        for i, row in enumerate(rows):
            assert client.post("/api/v2/paper/step", headers=headers).status_code == 200
            snapshot = service.get_snapshot()
            assert service.ingest(row, received_at=row.available_at) == snapshot
            if i == 0:
                assert snapshot["paper_ready"] is True
            if i == 4:
                assert snapshot["submission"]["accepted"] is True
                assert snapshot["execution_state"] == "OPEN"
        assert fill_count(service) == 1
        snap = service.get_snapshot()
        assert snap["completed_trades"] == snap["journal_completed"] == 1
        assert snap["account_overview"]["balance"] == 151170
        assert snap["account_overview"]["realized_pnl"] == 1170
        assert snap["latest_canonical_trade"]["net_pnl"] == 1170
        with sqlite3.connect(tmp_path/"paper.sqlite") as db:
            assert db.execute("SELECT count(*) FROM journal").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM events WHERE phase='COMPLETED'").fetchone()[0] == 8
        for owner, name in ((service,"step"),(service,"ingest"),
                (service._paper.runtime.lifecycle,"submit_signal"), (service._paper.runtime.lifecycle,"update_position")):
            monkeypatch.setattr(owner, name, Mock(side_effect=AssertionError("read mutation")))
        for _ in range(3):
            assert client.get("/api/v2/backtesting/dashboard").json()["paper_research"] == snap
            assert client.get("/api/v2/paper/readiness").json()["paper_ready"] is False
        assert service.get_snapshot() == snap
    restored = make(policy, tmp_path, rows)
    assert restored._paper is None
    recovery = restored.get_snapshot()
    assert recovery["account_overview"] == snap["account_overview"]
    assert recovery["dashboard_status"] == "RECOVERY_REQUIRED"
    assert recovery["operational_state_restored"] is False
    with pytest.raises(RuntimeError):
        restored.control("enable")


@pytest.mark.parametrize("control", ["disable", "emergency_block", "hold", "risk", "rejected"])
def test_nonexecution_paths(policy, api_settings, tmp_path, control):
    service = make(policy, tmp_path)
    witness(service, entries=() if control == "hold" else (5,))
    service.control("enable")
    r = service._paper.runtime
    if control in ("disable", "emergency_block"):
        service.control(control)
    if control == "risk":
        saved = r.account.capture_state()
        saved["state"].update(trading_blocked=True, blocking_reasons=["fixture_risk_block"])
        r.account.restore_state(snapshot=saved)
    if control == "rejected":
        r.lifecycle.execution_risk_gate_v1.evaluate_trade = Mock(return_value={"execution":"BLOCKED"})
    for _ in service._rows:
        service.step()
    assert fill_count(service) == 0
    assert not r.journal.trades and not r.completed
    assert r.account.get_state()["realized_pnl"] == 0
    service.shutdown()


@pytest.mark.parametrize("kind", ["stale", "future", "order", "conflict", "authority"])
def test_bad_input_latches_fail_closed(policy, api_settings, tmp_path, kind):
    service = make(policy, tmp_path)
    witness(service)
    service.control("enable")
    row = service._rows[0]
    clock = row.available_at
    if kind == "stale": clock += timedelta(seconds=31)
    if kind == "future": clock -= timedelta(seconds=1)
    if kind == "order": row = service._rows[1]
    if kind == "conflict": row = replace(row, raw_row=row.raw_row+" ")
    if kind == "authority": service._paper.runtime.lifecycle.trade_journal_v2 = None
    with pytest.raises(ValueError):
        service.ingest(row, received_at=clock)
    assert not service.get_snapshot()["paper_ready"]
    with pytest.raises(RuntimeError): service.step()
    assert fill_count(service) == 0
    service.shutdown()


def test_duplicate_threads_are_serialized(policy, api_settings, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    service = make(policy, tmp_path)
    witness(service)
    service.control("enable")
    for row in service._rows[:5]:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: service.ingest(row, received_at=row.available_at), range(8)))
    assert service._paper.runtime.index == 5 and fill_count(service) == 1
    service.shutdown()


def test_readiness_detects_lost_authority_without_execution(policy, api_settings, tmp_path):
    service = make(policy,tmp_path)
    service.control("enable")
    service.step()
    assert service.get_snapshot()["paper_ready"]
    service._paper.runtime.lifecycle.risk_manager_v2 = None
    assert not service.get_snapshot()["paper_ready"]
    assert "AUTHORITY_UNAVAILABLE" in service.get_snapshot()["readiness_reasons"]
    assert fill_count(service) == 0
    service.shutdown()


def test_effective_policy_is_identified_and_cannot_drift(policy, api_settings, tmp_path):
    service = make(policy,tmp_path)
    service.control("enable")
    service.step()
    published = service.get_snapshot()
    assert published["effective_policy"]["maximum_total_drawdown"] == 4500
    assert published["effective_policy"]["minimum_signal_confluence"] == .8
    # Fixture-only corruption of a runtime setting must revoke readiness.
    service._paper.runtime.session.signal_generator_v2.minimum_probability = .99
    assert not service.get_snapshot()["paper_ready"]
    with pytest.raises(ValueError,match="AUTHORITY_UNAVAILABLE"): service.step()
    assert fill_count(service) == 0
    service.shutdown()


def test_failed_durable_completion_cannot_repeat_fill(policy, api_settings, tmp_path, monkeypatch):
    service = make(policy,tmp_path)
    witness(service)
    service.control("enable")
    for _ in range(4): service.step()
    monkeypatch.setattr(service,"_save",Mock(side_effect=OSError("fixture disk full")))
    with pytest.raises(OSError): service.step()
    assert fill_count(service) == 1
    with pytest.raises(RuntimeError): service.step()
    restarted = make(policy,tmp_path)
    assert restarted.get_snapshot()["pending_events"] == 1
    assert not restarted.get_snapshot()["paper_ready"]
    # Last committed state is explicitly stale, not a claim that the fill did not occur.
    assert restarted.get_snapshot()["processed_candles"] == 4
    service._db.close()


def test_storage_loss_before_pending_cannot_execute(policy, api_settings, tmp_path):
    service = make(policy,tmp_path)
    witness(service)
    service.control("enable")
    for _ in range(4): service.step()
    service._db.close()
    with pytest.raises(sqlite3.Error): service.step()
    assert not service.get_snapshot()["paper_ready"]
    assert fill_count(service) == 0
    with pytest.raises(RuntimeError): service.step()


def test_corrupt_checkpoint_cannot_initialize_fresh_account(policy, api_settings, tmp_path):
    service = make(policy,tmp_path)
    service.shutdown()
    with sqlite3.connect(tmp_path/"paper.sqlite") as db:
        db.execute("UPDATE checkpoint SET payload='{}'")
    restarted = make(policy,tmp_path)
    assert restarted._paper is None
    assert restarted.get_snapshot()["account_overview"] is None
    assert restarted.get_snapshot()["evidence_status"] == "UNREADABLE_RECONCILIATION_REQUIRED"


def test_recovery_reader_releases_windows_database_handle(policy, api_settings, tmp_path):
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        service = make(policy,Path(directory))
        service.shutdown()
        restarted = make(policy,Path(directory))
        assert restarted.get_snapshot()["dashboard_status"] == "RECOVERY_REQUIRED"
    # Windows cleanup must succeed while the recovered service is still alive.
    assert not Path(directory).exists()


def test_actual_losses_trigger_existing_projected_drawdown_veto(policy, api_settings, tmp_path):
    prices = [(10000+i,10000+i,10000+i,10000+i) for i in range(25)]
    for i in range(5,23,2): prices[i] = (10000+i,10000+i,10000+i-31,10000+i)
    service = make(policy,tmp_path,observations(policy,prices))
    witness(service,entries=tuple(range(5,24,2)))
    service.control("enable")
    for _ in prices: service.step()
    snap = service.get_snapshot()
    # Existing projected-risk rule stops the next 630-dollar loss BEFORE 4,500.
    assert snap["completed_trades"] == fill_count(service) == 7
    assert snap["account_overview"]["realized_pnl"] == -4410
    assert snap["risk_vetoes"] == 3
    assert snap["journal_completed"] == 7
    service.shutdown()


def test_certified_loader_rejects_hash_changes(tmp_path):
    from hashlib import sha256
    import json
    from backend.api.paper_rc_app_v1 import load_certified_replay
    p = policy.__wrapped__()
    source = tmp_path/"source.txt"
    source.write_text("synthetic input\n")
    stream = tmp_path/"stream.jsonl"
    stream.write_text(json.dumps({"raw_row":"20250619 150100;10000;10000;10000;10000;1","source_row":1})+"\n")
    days = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
    calendar = {"timezone":"Central Standard Time","sha256":p.digest,
        "sessions":[{"BeginDay":days[(i-1)%7],"BeginTime":"1700","EndDay":days[i],"EndTime":"1600","TradingDay":days[i]} for i in range(5)],
        "full":{},"partial":{}}
    manifest = tmp_path/"manifest.json"
    manifest.write_text(json.dumps({"calendar":calendar,"segments":[{"contract":"JUN25",
        "stream":str(stream),"stream_sha256":sha256(stream.read_bytes()).hexdigest(),
        "source_file":str(source),"source_sha256":sha256(source.read_bytes()).hexdigest()}]}))
    _, rows = load_certified_replay(manifest_path=manifest,contract="JUN25")
    assert len(rows) == 1
    stream.write_text("changed fixture")
    with pytest.raises(ValueError,match="hash mismatch"):
        load_certified_replay(manifest_path=manifest,contract="JUN25")


def test_mode_and_identity_are_explicit():
    for mode in ("", "LIVE", None):
        with pytest.raises(ValueError):
            create_paper_rc_app_v1(mode=mode, configuration_id="fixture")
    for mode in ("PRODUCTION_POLICY", "PAPER_RESEARCH", "HISTORICAL_RESEARCH"):
        with TestClient(create_paper_rc_app_v1(mode=mode, configuration_id="fixture")) as client:
            assert client.get("/health").json()["mode"] == mode
            assert not client.get("/api/v2/paper/readiness").json()["paper_ready"]
            assert client.post("/api/v2/paper/enable").status_code == 503
    with pytest.raises(ValueError):
        create_paper_rc_app_v1(mode="PAPER_RESEARCH", configuration_id="")


def test_emergency_block_still_allows_canonical_exit(policy, api_settings, tmp_path):
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (10000,10060,10000,10000)
    service = make(policy, tmp_path, observations(policy, prices))
    witness(service, entries=(5,6,7))
    service.control("enable")
    for _ in range(5): service.step()
    service.control("emergency_block")
    service.control("enable")  # Cannot clear the emergency latch.
    for _ in range(3): service.step()
    assert fill_count(service) == 1
    assert service.get_snapshot()["completed_trades"] == 1
    assert service.get_snapshot()["account_overview"]["realized_pnl"] == 1170
    service.shutdown()


def test_anomaly_never_marks_closes_or_enters(policy, api_settings, tmp_path):
    stamps = [f"20250618 20{i:02d}00" for i in range(55,60)] + ["20250618 210100", "20250618 220100"]
    prices = [(10000,10000,10000,10000)]*7
    prices[5] = (10000,10100,9900,10000)
    rows = observations(policy, prices, stamps)
    service = make(policy, tmp_path, rows)
    witness(service)
    service.control("enable")
    for _ in range(5): service.step()
    r = service._paper.runtime
    before = r.account.capture_state()
    service.step()
    assert r.account.capture_state() == before
    assert r.index == 5 and fill_count(service) == 1 and not r.completed
    assert service.get_snapshot()["anomalies_excluded"] == 1
    service.shutdown()


def test_closed_htf_and_bounded_history_without_future(policy, api_settings, tmp_path):
    from datetime import datetime, timezone
    start = datetime(2025,6,18,15,1,tzinfo=timezone.utc)
    stamps = [(start+timedelta(minutes=i)).strftime("%Y%m%d %H%M%S") for i in range(130)]
    rows = observations(policy, [(10000,10000,10000,10000)]*130, stamps)
    service = make(policy, tmp_path, rows)
    contexts = []
    def strategy(context):
        contexts.append(context)
        return TradingDecisionV2(TradingActionV2.HOLD,.5,"synthetic chronology witness")
    service._paper.runtime.session.strategy_runner_v2.run = strategy
    for _ in rows: service.step()
    assert [c["signal_index"] for c in contexts] == list(range(5,130))
    assert all(len(c["history"]) <= 50 for c in contexts)
    assert len(contexts[54]["history_1h"]) == 0  # index 59
    assert len(contexts[55]["history_1h"]) == 1  # index 60
    assert service.get_snapshot()["htf_emitted"] == {"15m":8,"1h":2}
    r = service._paper.runtime
    assert len(r.session.candle_history) == 50 and not r.states and not r.session.decisions
    service.shutdown()


def crash_worker(path, boundary):
    import os
    p = policy.__wrapped__()
    prices = [(10000,10000,10000,10000)]*8
    prices[5] = (10000,10060,10000,10000)
    service = make(p, path, observations(p,prices))
    witness(service)
    service.control("enable")
    r = service._paper.runtime
    if boundary == "accepted_before_execution":
        r.lifecycle.paper_execution_engine.execute = lambda **kwargs: os._exit(23)
    if boundary == "risk_blocked":
        saved = r.account.capture_state()
        saved["state"].update(trading_blocked=True, blocking_reasons=["fixture_risk_block"])
        r.account.restore_state(snapshot=saved)
    count = {"flat":1,"accepted_before_execution":5,"open":5,"realized":6,"risk_blocked":5}[boundary]
    for _ in range(count): service.step()
    os._exit(23)


@pytest.mark.parametrize("boundary", ["flat","accepted_before_execution","open","realized","risk_blocked"])
def test_abrupt_restart_never_resumes_or_resets_account(policy, api_settings, tmp_path, boundary):
    import subprocess
    import sys
    result = subprocess.run([sys.executable,"-m","backend.tests.test_paper_runtime_sprint08",str(tmp_path),boundary],
                            capture_output=True,text=True,timeout=30)
    assert result.returncode == 23, result.stdout+result.stderr
    service = make(policy,tmp_path)
    snap = service.get_snapshot()
    assert service._paper is None and snap["dashboard_status"] == "RECOVERY_REQUIRED"
    assert not snap["paper_ready"] and not snap["operational_state_restored"]
    assert snap["pending_events"] == int(boundary == "accepted_before_execution")
    assert snap["account_overview"]["balance"] == (151170 if boundary == "realized" else 150000)
    assert len(snap["active_simulated_positions"]) == int(boundary == "open")
    assert snap["journal_completed"] == int(boundary == "realized")
    if boundary == "risk_blocked": assert snap["account_overview"]["trading_blocked"]
    with pytest.raises(RuntimeError): service.step()
    with pytest.raises(RuntimeError): service.control("enable")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    crash_worker(Path(sys.argv[1]),sys.argv[2])
