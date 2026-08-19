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


def test_execution_risk_events_filters_by_symbol(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    gate.logger.log_event(
        {
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "status": "BLOCKED",
        }
    )

    gate.logger.log_event(
        {
            "symbol": "NQ",
            "event_type": "RISK_APPROVED",
            "status": "APPROVED",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "symbol": "mnq",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["count"] == 1
    assert payload["events"][0]["symbol"] == "MNQ"


def test_execution_risk_events_filters_by_event_type(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    gate.logger.log_event(
        {
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "status": "BLOCKED",
        }
    )

    gate.logger.log_event(
        {
            "symbol": "MNQ",
            "event_type": "RISK_APPROVED",
            "status": "APPROVED",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "event_type": "risk_blocked",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1
    assert (
        payload["events"][0]["event_type"]
        == "RISK_BLOCKED"
    )


def test_execution_risk_events_supports_limit(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    for index in range(5):
        gate.logger.log_event(
            {
                "symbol": "MNQ",
                "event_type": "RISK_EVENT",
                "sequence": index,
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "limit": 2,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 2
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [3, 4]


def test_execution_risk_events_supports_offset(tmp_path):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    for index in range(5):
        gate.logger.log_event(
            {
                "symbol": "MNQ",
                "event_type": "RISK_EVENT",
                "sequence": index,
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "offset": 2,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 3
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [2, 3, 4]


def test_execution_risk_events_supports_limit_and_offset(
    tmp_path,
):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    for index in range(5):
        gate.logger.log_event(
            {
                "symbol": "MNQ",
                "event_type": "RISK_EVENT",
                "sequence": index,
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 2
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [1, 2]


def test_execution_risk_events_rejects_invalid_limit(tmp_path):
    _, client = _client(tmp_path)

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_execution_risk_events_rejects_negative_offset(tmp_path):
    _, client = _client(tmp_path)

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "offset": -1,
        },
    )

    assert response.status_code == 422


def test_execution_risk_events_filters_start_timestamp(
    tmp_path,
):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    store = gate.logger.store

    store.append(
        {
            "timestamp": "2026-08-19T10:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_EVENT",
            "sequence": 1,
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T11:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_EVENT",
            "sequence": 2,
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T12:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_EVENT",
            "sequence": 3,
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "start_timestamp":
                "2026-08-19T11:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 2
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [2, 3]


def test_execution_risk_events_filters_end_timestamp(
    tmp_path,
):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    store = gate.logger.store

    for timestamp, sequence in (
        ("2026-08-19T10:00:00+00:00", 1),
        ("2026-08-19T11:00:00+00:00", 2),
        ("2026-08-19T12:00:00+00:00", 3),
    ):
        store.append(
            {
                "timestamp": timestamp,
                "symbol": "MNQ",
                "event_type": "RISK_EVENT",
                "sequence": sequence,
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "end_timestamp":
                "2026-08-19T11:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 2
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [1, 2]


def test_execution_risk_events_filters_timestamp_range(
    tmp_path,
):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    store = gate.logger.store

    for timestamp, sequence in (
        ("2026-08-19T09:00:00+00:00", 1),
        ("2026-08-19T10:00:00+00:00", 2),
        ("2026-08-19T11:00:00+00:00", 3),
        ("2026-08-19T12:00:00+00:00", 4),
    ):
        store.append(
            {
                "timestamp": timestamp,
                "symbol": "NQ",
                "event_type": "RISK_EVENT",
                "sequence": sequence,
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "start_timestamp":
                "2026-08-19T10:00:00+00:00",
            "end_timestamp":
                "2026-08-19T11:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 2
    assert [
        event["sequence"]
        for event in payload["events"]
    ] == [2, 3]


def test_execution_risk_events_combines_all_filters(
    tmp_path,
):
    app, client = _client(tmp_path)

    gate = (
        app.state
        .trade_lifecycle_service_v2
        .execution_risk_gate_v1
    )

    store = gate.logger.store

    events = (
        {
            "timestamp": "2026-08-19T10:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "sequence": 1,
        },
        {
            "timestamp": "2026-08-19T11:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "sequence": 2,
        },
        {
            "timestamp": "2026-08-19T12:00:00+00:00",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "sequence": 3,
        },
        {
            "timestamp": "2026-08-19T11:00:00+00:00",
            "symbol": "NQ",
            "event_type": "RISK_BLOCKED",
            "sequence": 4,
        },
    )

    for event in events:
        store.append(event)

    response = client.get(
        "/api/v2/execution/risk-events",
        params={
            "symbol": "mnq",
            "event_type": "risk_blocked",
            "start_timestamp":
                "2026-08-19T10:00:00+00:00",
            "end_timestamp":
                "2026-08-19T12:00:00+00:00",
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["count"] == 1
    assert payload["events"][0]["sequence"] == 2
