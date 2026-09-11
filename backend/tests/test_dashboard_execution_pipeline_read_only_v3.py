"""HTTP contract: existing observations only, with no execution capability."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.intelligence_decision_api_v3 import router
from backend.journal.trade_journal_v2 import TradeJournalV2


URL = "/api/v3/dashboard/execution-pipeline"
POSITION = {"position_id": "existing-position", "symbol": "MES",
            "direction": "SHORT", "status": "OPEN"}
TRADE = {"trade_id": "existing-journal", "position_id": "existing-position",
         "symbol": "MES", "direction": "SHORT", "status": "CLOSED"}


def make_client(positions, trades):
    app = FastAPI()
    # Deliberately expose only getters: no execution service, account or broker.
    app.state.trade_lifecycle_service_v2 = SimpleNamespace(
        get_active_positions=lambda: positions)
    app.state.trade_journal_v2 = SimpleNamespace(get_trades=lambda: trades)
    app.include_router(router)
    return TestClient(app)


def read(client):
    response = client.get(URL)
    assert response.status_code == 200
    payload = response.json()
    assert "accepted" not in payload
    assert "execution" not in payload
    assert "prepared_order" not in payload
    return payload


def test_empty_sources_are_idle_without_fabricated_activity():
    payload = read(make_client([], []))
    assert payload["status"] == payload["execution_status"] == "IDLE"
    assert payload["journal_status"] == "NOT_RECORDED"
    for field in ("source", "position_id", "trade_id", "symbol", "direction"):
        assert payload[field] is None


def test_existing_position_and_matching_journal_are_observed_not_inferred():
    positions, trades = [deepcopy(POSITION)], [deepcopy(TRADE)]
    before = deepcopy((positions, trades))
    payload = read(make_client(positions, trades))
    assert payload["status"] == "AVAILABLE"
    assert payload["source"] == "position"
    assert payload["position_id"] == POSITION["position_id"]
    assert payload["trade_id"] == TRADE["trade_id"]
    assert payload["symbol"] == "MES"
    assert payload["direction"] == "SHORT"
    assert payload["execution_status"] == "OPEN"  # Not FILLED or journal CLOSED.
    assert payload["journal_status"] == "RECORDED"
    assert (positions, trades) == before
    payload["symbol"] = "CHANGED"
    assert positions[0]["symbol"] == "MES"


@pytest.mark.parametrize("trades", [[], [{**TRADE, "position_id": "unrelated"}]])
def test_accepted_position_does_not_imply_a_journal_entry(trades):
    payload = read(make_client([{**POSITION, "accepted": True}], trades))
    assert payload["journal_status"] == "NOT_RECORDED"
    assert payload["trade_id"] is None
    assert payload["execution_status"] == "OPEN"


def test_last_existing_journal_record_is_visible_without_an_active_position():
    payload = read(make_client([], [{**TRADE, "trade_id": "older"}, TRADE]))
    assert payload["source"] == "journal"
    assert payload["trade_id"] == "existing-journal"
    assert payload["execution_status"] == "CLOSED"
    assert payload["journal_status"] == "RECORDED"


def test_actual_journal_dataclass_is_read_without_writing():
    journal = TradeJournalV2()
    journal.record_open_trade({**TRADE, "entry_price": 5100, "quantity": 1})
    before = deepcopy(journal.get_trades())
    payload = read(make_client([POSITION], journal.get_trades()))
    assert payload["trade_id"] == TRADE["trade_id"]
    assert payload["journal_status"] == "RECORDED"
    assert journal.get_trades() == before


@pytest.mark.parametrize("field", ["position_id", "symbol", "direction", "status"])
def test_incomplete_position_preserves_known_data_without_inference(field):
    position = {**POSITION, "accepted": True}
    position.pop(field)
    payload = read(make_client([position], [TRADE]))
    assert payload["status"] == "UNAVAILABLE"
    if field == "status":
        assert payload["execution_status"] == "UNAVAILABLE"
    elif field == "position_id":
        assert payload["journal_status"] == "UNAVAILABLE"
        assert payload["trade_id"] is None  # Matching symbol is not identity.
    else:
        assert payload[field] is None


@pytest.mark.parametrize("positions,trades", [
    (None, None), (None, []), ([], None), ({}, []), ([], {}),
    ([None], []), ([], [None]), ([{}], []), ([], [{}]),
])
def test_unavailable_or_malformed_sources_never_report_idle(positions, trades):
    assert read(make_client(positions, trades))["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("source,method", [
    ("trade_lifecycle_service_v2", "get_active_positions"),
    ("trade_journal_v2", "get_trades"),
])
@pytest.mark.parametrize("failure", ["missing", "raising"])
def test_missing_or_failed_reader_has_no_execution_fallback(source, method, failure):
    client = make_client([POSITION], [TRADE])
    command = Mock(side_effect=AssertionError("Read attempted execution"))
    client.app.state.trade_lifecycle_service_v2.submit_signal = command
    if failure == "missing":
        delattr(client.app.state, source)
    else:
        setattr(getattr(client.app.state, source), method,
                Mock(side_effect=RuntimeError("unavailable")))
    payload = read(client)
    assert payload["status"] == "UNAVAILABLE"
    assert "RuntimeError" not in payload["message"]
    command.assert_not_called()


def test_positions_can_remain_visible_when_journal_is_unavailable():
    payload = read(make_client([POSITION], None))
    assert payload["position_id"] == POSITION["position_id"]
    assert payload["execution_status"] == "OPEN"
    assert payload["journal_status"] == "UNAVAILABLE"
    assert payload["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("positions", [[], [POSITION]])
def test_journal_without_identity_cannot_prove_presence_or_absence(positions):
    payload = read(make_client(positions, [{"accepted": True, "symbol": "MES"}]))
    assert payload["status"] == "UNAVAILABLE"
    assert payload["journal_status"] == "UNAVAILABLE"
    assert payload["trade_id"] is None
