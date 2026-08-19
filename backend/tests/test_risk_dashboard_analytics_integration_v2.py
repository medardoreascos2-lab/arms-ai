from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_client(
    tmp_path: Path,
) -> TestClient:

    app = create_app(
        risk_event_store_path_v2=(
            tmp_path / "risk_events.json"
        ),
    )

    return TestClient(app)


def test_risk_dashboard_preserves_existing_contract(
    tmp_path: Path,
):

    client = build_client(tmp_path)

    response = client.get(
        "/api/v2/dashboard/risk"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["account"] == "TOPSTEP_50K"
    assert payload["balance"] == 50000
    assert payload["risk_percent"] == 0.5
    assert payload["risk_per_trade"] == 250.0
    assert payload["daily_loss_limit"] == 1000
    assert payload["max_drawdown"] == 2000
    assert payload["status"] == "TRADING ENABLED"


def test_risk_dashboard_exposes_event_analytics(
    tmp_path: Path,
):

    client = build_client(tmp_path)

    response = client.get(
        "/api/v2/dashboard/risk"
    )

    assert response.status_code == 200

    payload = response.json()

    assert "event_analytics" in payload

    analytics = payload["event_analytics"]

    assert analytics["total_events"] == 0

    assert analytics[
        "decision_summary"
    ]["decision_total"] == 0

    assert analytics["by_event_type"] == {}
    assert analytics["by_symbol"] == {}
    assert analytics["by_reason"] == {}


def test_dashboard_and_summary_share_analytics_contract(
    tmp_path: Path,
):

    client = build_client(tmp_path)

    dashboard_response = client.get(
        "/api/v2/dashboard/risk"
    )

    summary_response = client.get(
        "/api/v2/execution/risk-events/summary"
    )

    assert dashboard_response.status_code == 200
    assert summary_response.status_code == 200

    dashboard = dashboard_response.json()
    summary = summary_response.json()

    assert (
        dashboard["event_analytics"]
        == summary["summary"]
    )
