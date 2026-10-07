from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import sqlite3
from types import SimpleNamespace

import pytest

from backend.dashboard.beta_dashboard_projection_v1 import BetaDashboardProjectionV1
from backend.dashboard.current_paper_read_model_v1 import CurrentPaperReadOnlySourceV1


NOW = datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc)


class Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class GetOnlyOpener:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, request, *, timeout):
        self.calls.append((request.get_method(), request.full_url, timeout))
        payload = self.payloads[request.full_url]
        return Response(json.dumps(payload).encode("utf-8"))


def create_database(path, *, future_decision=False):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE decision_trace (sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE journal (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        """
    )
    decision_time = NOW + timedelta(minutes=1) if future_decision else NOW - timedelta(minutes=1)
    decision = {
        "canonical_observation_id": "decision-1",
        "action": "HOLD",
        "confidence": 0.0,
        "confluence_score": 0.42,
        "decision_reason": "Risk gate remained closed",
        "plan": None,
        "observation": {
            "canonical_timestamp": decision_time.isoformat(),
            "instrument": "NQ",
            "contract": "NQ DEC26",
        },
    }
    trade = {
        "trade_id": "trade-1",
        "symbol": "NQ",
        "direction": "LONG",
        "entry": 20000.0,
        "stop_loss": 19990.0,
        "take_profit": 20020.0,
        "created_at": (NOW - timedelta(hours=2)).isoformat(),
        "closed_at": (NOW - timedelta(hours=1)).isoformat(),
        "exit_price": 20020.0,
        "result": "TARGET_HIT",
        "pnl": 40.0,
        "status": "CLOSED",
    }
    connection.execute(
        "INSERT INTO decision_trace(sequence, payload) VALUES (?, ?)",
        (1, json.dumps(decision)),
    )
    connection.execute(
        "INSERT INTO journal(id, payload) VALUES (?, ?)",
        ("trade-1", json.dumps(trade)),
    )
    connection.commit()
    connection.close()


def payloads():
    return {
        "http://127.0.0.1:54002/health": {
            "status": "PROCESS_HEALTHY",
            "mode": "CURRENT_MARKET_PAPER",
            "live_execution_allowed": False,
        },
        "http://127.0.0.1:54002/api/v2/backtesting/dashboard": {
            "paper_research": {
                "dashboard_status": "BLOCKED",
                "mode": "CURRENT_MARKET_PAPER",
                "live_execution_allowed": False,
                "config_hash": "config-hash",
                "contract": "NQ DEC26",
                "canonical_time": (NOW - timedelta(minutes=1)).isoformat(),
                "paper_ready": False,
                "paper_execution_enabled": False,
                "paper_authority_state": "DISABLED_RUNTIME_FAILURE",
                "evidence_status": "CURRENT_PROCESS",
                "data_freshness": "STALE_OR_MISSING",
                "session_state": {"state": "OPEN"},
                "latest_decision": {"action": "HOLD", "confidence": 0.0},
                "active_simulated_positions": [],
                "market_data": {
                    "connected": True,
                    "instrument": "NQ",
                    "contract": "NQ DEC26",
                    "last_received_time": (NOW - timedelta(seconds=45)).isoformat(),
                },
                "account_overview": {"realized_pnl": 40.0},
            }
        },
        "http://127.0.0.1:54000/api/v2/market-analysis/health": {
            "phase": "AWAITING_OPERATOR_ACTIVATION",
            "analysis_only": True,
            "order_submit_reachable": False,
        },
    }


def build_source(tmp_path, *, future_decision=False):
    database = tmp_path / "paper.sqlite"
    create_database(database, future_decision=future_decision)
    opener = GetOnlyOpener(payloads())
    source = CurrentPaperReadOnlySourceV1(
        paper_base_url="http://127.0.0.1:54002",
        analysis_base_url="http://127.0.0.1:54000",
        database_path=database,
        maximum_age_seconds=30,
        opener=opener,
        now_provider=lambda: NOW,
    )
    return source, opener, database


def test_reads_only_canonical_get_endpoints_and_query_only_database(tmp_path):
    source, opener, database = build_source(tmp_path)
    before = sha256(database.read_bytes()).hexdigest()

    snapshot = source.get_snapshot()

    assert sha256(database.read_bytes()).hexdigest() == before
    assert {method for method, _url, _timeout in opener.calls} == {"GET"}
    assert {url for _method, url, _timeout in opener.calls} == set(payloads())
    assert not hasattr(source, "control")
    assert snapshot["execution_mode"] == "PAPER"
    assert snapshot["market_data"]["status"] == "STALE"
    assert snapshot["current_signal"]["action"] == "HOLD"
    assert snapshot["current_signal"]["approved"] is False
    assert snapshot["journal_history"][0]["pnl"] == 40.0
    assert snapshot["runtime_observation"]["read_only"] is True
    assert snapshot["runtime_observation"]["live_execution_allowed"] is False
    assert snapshot["runtime_observation"]["order_submit_reachable"] is False


def test_projection_uses_canonical_signal_history_trade_metrics_and_runtime(tmp_path):
    source, _opener, _database = build_source(tmp_path)
    state = SimpleNamespace(
        runtime_context_v2=None,
        live_signal_store=None,
        live_analysis_store=None,
        signal_history_store=None,
    )

    bundle = BetaDashboardProjectionV1(symbol="MNQ", timeframe="5m").build(
        state, source
    )

    assert bundle["live"]["instrument"] == "NQ"
    assert bundle["live"]["contract"] == "NQ DEC26"
    assert bundle["live"]["market_status"] == "STALE"
    assert bundle["live"]["current_signal"] == "NO_TRADE"
    assert bundle["live"]["signal"]["entry_price"] is None
    assert bundle["history"]["status"] == "AVAILABLE"
    assert {row["record_type"] for row in bundle["history"]["records"]} == {
        "PAPER_SIGNAL", "PAPER_TRADE"
    }
    assert bundle["performance"]["cumulative_pnl"] == 40.0
    assert bundle["performance"]["wins"] == 1
    assert bundle["performance"]["losses"] == 0
    assert bundle["performance"]["profit_factor"] is None
    assert bundle["runtime"]["ninjatrader_status"] == "CONNECTED"
    assert bundle["runtime"]["read_only"] is True
    assert bundle["runtime"]["live_execution_allowed"] is False


def test_offline_runtime_keeps_history_but_expires_current_signal(tmp_path):
    database = tmp_path / "paper.sqlite"
    create_database(database)
    offline_payloads = payloads()
    offline_payloads[
        "http://127.0.0.1:54002/api/v2/backtesting/dashboard"
    ] = {}
    source = CurrentPaperReadOnlySourceV1(
        paper_base_url="http://127.0.0.1:54002",
        analysis_base_url="http://127.0.0.1:54000",
        database_path=database,
        maximum_age_seconds=30,
        opener=GetOnlyOpener(offline_payloads),
        now_provider=lambda: NOW,
    )
    state = SimpleNamespace(
        runtime_context_v2=SimpleNamespace(account_identity={"account_id": "local"}),
        live_signal_store=None,
        live_analysis_store=None,
        signal_history_store=None,
    )

    snapshot = source.get_snapshot()
    bundle = BetaDashboardProjectionV1(symbol="MNQ", timeframe="5m").build(
        state, source
    )

    assert snapshot["dashboard_status"] == "UNAVAILABLE"
    assert snapshot["runtime"]["evidence_status"] == "HISTORICAL_QUERY_ONLY"
    assert snapshot["current_signal"]["status"] == "EXPIRED"
    assert snapshot["current_signal"]["approved"] is False
    assert bundle["live"]["market_status"] == "UNAVAILABLE"
    assert bundle["live"]["current_signal"] == "NO_TRADE"
    assert bundle["history"]["status"] == "AVAILABLE"
    assert bundle["performance"]["cumulative_pnl"] == 40.0
    assert bundle["runtime"]["status"] == "UNAVAILABLE"

def test_future_signal_timestamp_is_rejected(tmp_path):
    source, _opener, _database = build_source(tmp_path, future_decision=True)

    snapshot = source.get_snapshot()

    assert snapshot["current_signal"]["generated_at"] is None


def test_maintenance_is_independent_from_freshness_and_runtime_failure(tmp_path):
    database = tmp_path / "paper.sqlite"
    create_database(database)
    maintenance = payloads()
    paper = maintenance[
        "http://127.0.0.1:54002/api/v2/backtesting/dashboard"
    ]["paper_research"]
    paper["session_state"] = {"state": "DAILY_MAINTENANCE"}
    paper["paper_authority_state"] = "DISABLED_RUNTIME_FAILURE"
    source = CurrentPaperReadOnlySourceV1(
        paper_base_url="http://127.0.0.1:54002",
        analysis_base_url="http://127.0.0.1:54000",
        database_path=database,
        maximum_age_seconds=30,
        opener=GetOnlyOpener(maintenance),
        now_provider=lambda: NOW,
    )

    snapshot = source.get_snapshot()
    observation = snapshot["runtime_observation"]
    assert snapshot["market_session_status"] == "MAINTENANCE"
    assert snapshot["feed_freshness"] == "STALE_OR_UNAVAILABLE"
    assert snapshot["paper_runtime_health"] == "FAILED"
    assert snapshot["paper_execution_authority"] == "DISABLED"
    assert snapshot["live_execution_authority"] == "DISABLED"
    assert observation["market_session_status"] == "MAINTENANCE"
    assert observation["feed_freshness"] == "STALE_OR_UNAVAILABLE"
    assert observation["paper_runtime_health"] == "FAILED"
    assert observation["paper_execution_authority"] == "DISABLED"
    assert observation["live_execution_authority"] == "DISABLED"
    assert observation["read_only"] is True


def test_projection_preserves_separate_market_and_authority_dimensions(tmp_path):
    source, _opener, _database = build_source(tmp_path)
    bundle = BetaDashboardProjectionV1(symbol="NQ", timeframe="1m").build(
        SimpleNamespace(runtime_context_v2=None, live_signal_store=None,
            live_analysis_store=None, signal_history_store=None),
        source,
    )
    runtime = bundle["runtime"]
    assert runtime["market_session_status"] == "OPEN"
    assert runtime["feed_freshness"] == "STALE_OR_UNAVAILABLE"
    assert runtime["paper_runtime_health"] == "FAILED"
    assert runtime["paper_execution_authority"] == "DISABLED"
    assert runtime["live_execution_authority"] == "DISABLED"
    assert runtime["read_only"] is True


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:54002",
        "http://example.com:54002",
        "http://user:secret@127.0.0.1:54002",
        "http://127.0.0.1:54002/api/v2/paper/enable",
    ],
)
def test_rejects_non_loopback_or_non_origin_sources(url):
    with pytest.raises(ValueError, match="loopback HTTP origin"):
        CurrentPaperReadOnlySourceV1(paper_base_url=url)
