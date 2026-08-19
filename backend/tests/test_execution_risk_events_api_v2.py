from fastapi.testclient import TestClient

from backend.api.app import create_app


def _client(tmp_path):
    app = create_app(
        risk_event_store_path_v2=(
            tmp_path / "risk_events.json"
        ),
    )
    return app, TestClient(app)


def test_execution_risk_events_route_exists(tmp_path):
    app, client = _client(tmp_path)

    response = client.get(
        "/api/v2/execution/risk-events"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["count"] == 0
    assert payload["events"] == []

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    assert gate is not None


def test_execution_risk_events_reads_runtime_gate(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    gate.logger.log_event(
        {
            "symbol": "MNQ",
            "side": "BUY",
            "contracts": 1,
            "risk": 25.0,
            "status": "BLOCKED",
            "reason": "TEST_BLOCK",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["count"] == 1

    event = payload["events"][0]

    assert event["symbol"] == "MNQ"
    assert event["side"] == "BUY"
    assert event["contracts"] == 1
    assert event["risk"] == 25.0
    assert event["status"] == "BLOCKED"
    assert event["reason"] == "TEST_BLOCK"
    assert "timestamp" in event


def test_execution_risk_events_returns_copy(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    gate.logger.log_event(
        {
            "symbol": "NQ",
            "side": "SELL",
            "contracts": 1,
            "risk": 50.0,
            "status": "APPROVED",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events"
    )

    payload = response.json()

    assert payload["count"] == 1
    assert payload["events"] is not gate.logger.events
