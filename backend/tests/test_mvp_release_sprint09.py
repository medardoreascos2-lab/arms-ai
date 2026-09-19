"""Release boundary tests. All synthetic inputs are explicit unit witnesses."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api.paper_rc_app_v1 import create_paper_rc_app_v1
from backend.tests.research_release_sprint09 import durable
from backend.tests.test_historical_accounting_sprint07r import observations
from backend.tests.test_historical_eligibility_v31 import policy
from backend.tests.test_paper_runtime_sprint08 import make, witness, fill_count
from backend.tests.test_production_certified_outcome_v17 import api_settings


@pytest.mark.parametrize("boundary", ["flat", "open", "completed"])
def test_shutdown_is_durable_idempotent_and_never_finalizes_again(policy, api_settings, tmp_path, boundary):
    prices = [(10000,10000,10000,10000)] * 8
    prices[5] = (10000,10060,10000,10000)
    rows = observations(policy, prices)
    service = make(policy, tmp_path, rows)
    witness(service)
    service.control("enable")
    for _ in range({"flat": 1, "open": 5, "completed": 6}[boundary]):
        service.step()
    before = service.get_snapshot()
    fills = fill_count(service)
    app = create_paper_rc_app_v1(mode="PAPER_RESEARCH", configuration_id="synthetic-release-test",
                                runtime=service, admin_token="synthetic-test-token")
    with TestClient(app) as client:
        headers = {"X-ARMS-ADMIN-TOKEN": "synthetic-test-token"}
        assert client.post("/api/v2/paper/shutdown", headers=headers).status_code == 200
        stopped = service.get_snapshot()
        assert not stopped["paper_ready"] and "STOPPED" in stopped["readiness_reasons"]
        assert stopped["account_overview"] == before["account_overview"]
        assert stopped["active_simulated_positions"] == before["active_simulated_positions"]
        disk = durable(tmp_path / "paper.sqlite")
        for command in ("enable", "step", "disable", "emergency_block"):
            assert client.post("/api/v2/paper/" + command, headers=headers).status_code == 409
        assert client.post("/api/v2/paper/shutdown", headers=headers).status_code == 200
        assert service.get_snapshot() == stopped
        assert durable(tmp_path / "paper.sqlite") == disk
        assert fill_count(service) == fills
    recovered = make(policy, tmp_path, rows)
    snap = recovered.get_snapshot()
    assert recovered._paper is None and not snap["paper_ready"]
    assert snap["dashboard_status"] == "RECOVERY_REQUIRED"
    assert snap["account_overview"] == before["account_overview"]
    assert snap["journal_completed"] == int(boundary == "completed")
    assert len(snap["active_simulated_positions"]) == int(boundary == "open")
    with pytest.raises(RuntimeError): recovered.control("enable")
    with pytest.raises(RuntimeError): recovered.step()


def test_risk_block_preserves_exit_of_already_authorized_position(policy, api_settings, tmp_path):
    prices = [(10000,10000,10000,10000)] * 8
    prices[5] = (10000,10060,10000,10000)
    service = make(policy, tmp_path, observations(policy, prices))
    witness(service, entries=(5,6,7))
    service.control("enable")
    for _ in range(5): service.step()
    runtime = service._paper.runtime
    blocked = runtime.account.capture_state()
    blocked["state"].update(trading_blocked=True, blocking_reasons=["explicit_test_risk_block"])
    runtime.account.restore_state(snapshot=blocked)
    for _ in range(3): service.step()
    assert fill_count(service) == 1
    assert service.get_snapshot()["completed_trades"] == service.get_snapshot()["journal_completed"] == 1
    assert runtime.account.get_state()["realized_pnl"] == 1170
    assert not runtime.lifecycle.get_active_positions()
    service.shutdown()


def test_pending_event_requires_reconciliation_without_reset(policy, api_settings, tmp_path):
    service = make(policy, tmp_path)
    service.step()
    service.shutdown()
    state = tmp_path / "paper.sqlite"
    # Explicit ambiguity fixture; cannot represent a certified completed input.
    with closing(sqlite3.connect(state)) as db:
        db.execute("INSERT INTO events VALUES(1,'ambiguous-test-event','INFLIGHT')")
        db.commit()
    before = durable(state)
    recovered = make(policy, tmp_path)
    assert recovered._paper is None
    assert recovered.get_snapshot()["pending_events"] == 1
    assert not recovered.get_snapshot()["paper_ready"]
    with pytest.raises(RuntimeError): recovered.control("enable")
    with pytest.raises(RuntimeError): recovered.step()
    assert durable(state) == before


def test_release_identity_is_separate_from_strategy_configuration():
    page = Path("frontend/src/app/paper-rc/page.tsx").read_text(encoding="utf-8")
    assert "ARMS AI MVP 1.0" in page
    assert "No live trading certification" in page
    from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
    config = PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json")
    assert config.boundary == 80.5 and config.quality == 85
