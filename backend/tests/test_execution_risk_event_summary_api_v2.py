from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_client(tmp_path):
    app = create_app(
        risk_event_store_path_v2=(
            tmp_path / "risk-events.json"
        )
    )

    return app, TestClient(app)


def test_summary_route_exists(tmp_path):
    _, client = build_client(tmp_path)

    response = client.get(
        "/api/v2/execution/risk-events/summary"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["summary"]["total_events"] == 0


def test_summary_aggregates_persisted_events(
    tmp_path,
):
    app, client = build_client(tmp_path)

    store = app.state.risk_event_store_v2

    store.append(
        {
            "timestamp": "2026-08-19T10:00:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_APPROVED",
            "reason": "APPROVED",
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T10:01:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "reason": "DAILY_LIMIT",
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T10:02:00Z",
            "symbol": "NQ",
            "event_type": "RISK_BLOCKED",
            "reason": "EXPOSURE_LIMIT",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events/summary"
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["total_events"] == 3

    assert summary["decision_summary"] == {
        "approved": 1,
        "blocked": 2,
        "unknown": 0,
        "decision_total": 3,
        "approval_rate_percent": 33.33,
        "block_rate_percent": 66.67,
    }

    assert summary["by_symbol"] == {
        "MNQ": 2,
        "NQ": 1,
    }

    assert summary["by_event_type"] == {
        "RISK_BLOCKED": 2,
        "RISK_APPROVED": 1,
    }

    assert summary["by_reason"] == {
        "APPROVED": 1,
        "DAILY_LIMIT": 1,
        "EXPOSURE_LIMIT": 1,
    }


def test_summary_filters_by_symbol(
    tmp_path,
):
    app, client = build_client(tmp_path)

    store = app.state.risk_event_store_v2

    store.append(
        {
            "timestamp": "2026-08-19T10:00:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "reason": "DAILY_LIMIT",
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T10:01:00Z",
            "symbol": "NQ",
            "event_type": "RISK_BLOCKED",
            "reason": "EXPOSURE_LIMIT",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events/summary",
        params={
            "symbol": "mnq",
        },
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["total_events"] == 1
    assert summary["by_symbol"] == {
        "MNQ": 1,
    }


def test_summary_filters_by_event_type(
    tmp_path,
):
    app, client = build_client(tmp_path)

    store = app.state.risk_event_store_v2

    store.append(
        {
            "timestamp": "2026-08-19T10:00:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_APPROVED",
            "reason": "APPROVED",
        }
    )

    store.append(
        {
            "timestamp": "2026-08-19T10:01:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "reason": "DAILY_LIMIT",
        }
    )

    response = client.get(
        "/api/v2/execution/risk-events/summary",
        params={
            "event_type": "risk_blocked",
        },
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["total_events"] == 1

    assert summary["by_event_type"] == {
        "RISK_BLOCKED": 1,
    }

    assert (
        summary["decision_summary"]["blocked"]
        == 1
    )


def test_summary_filters_timestamp_range(
    tmp_path,
):
    app, client = build_client(tmp_path)

    store = app.state.risk_event_store_v2

    for timestamp in (
        "2026-08-19T09:00:00Z",
        "2026-08-19T10:00:00Z",
        "2026-08-19T11:00:00Z",
    ):
        store.append(
            {
                "timestamp": timestamp,
                "symbol": "MNQ",
                "event_type": "RISK_BLOCKED",
                "reason": "DAILY_LIMIT",
            }
        )

    response = client.get(
        "/api/v2/execution/risk-events/summary",
        params={
            "start_timestamp":
                "2026-08-19T09:30:00Z",
            "end_timestamp":
                "2026-08-19T10:30:00Z",
        },
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["total_events"] == 1


def test_summary_combines_filters(
    tmp_path,
):
    app, client = build_client(tmp_path)

    store = app.state.risk_event_store_v2

    events = [
        {
            "timestamp": "2026-08-19T09:00:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "reason": "OLD_EVENT",
        },
        {
            "timestamp": "2026-08-19T10:00:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_BLOCKED",
            "reason": "DAILY_LIMIT",
        },
        {
            "timestamp": "2026-08-19T10:10:00Z",
            "symbol": "MNQ",
            "event_type": "RISK_APPROVED",
            "reason": "APPROVED",
        },
        {
            "timestamp": "2026-08-19T10:20:00Z",
            "symbol": "NQ",
            "event_type": "RISK_BLOCKED",
            "reason": "EXPOSURE_LIMIT",
        },
    ]

    for event in events:
        store.append(event)

    response = client.get(
        "/api/v2/execution/risk-events/summary",
        params={
            "symbol": "mnq",
            "event_type": "risk_blocked",
            "start_timestamp":
                "2026-08-19T09:30:00Z",
            "end_timestamp":
                "2026-08-19T10:30:00Z",
        },
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["total_events"] == 1

    assert summary["by_reason"] == {
        "DAILY_LIMIT": 1,
    }


def test_summary_rejects_invalid_timestamp(
    tmp_path,
):
    _, client = build_client(tmp_path)

    response = client.get(
        "/api/v2/execution/risk-events/summary",
        params={
            "start_timestamp": "not-a-timestamp",
        },
    )

    assert response.status_code == 422
