import json

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config.api_settings import APISettings


def _write_snapshot(
    tmp_path,
    *,
    covered_dates,
):
    path = tmp_path / "certified-market-hours-refresh.json"

    path.write_text(
        json.dumps(
            {
                "covered_dates": covered_dates,
                "closed_dates": [],
                "special_hours": [],
            }
        ),
        encoding="utf-8",
    )

    return path


def test_create_app_exposes_refresh_endpoint():
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={},
    )

    assert response.status_code == 422


def test_refresh_endpoint_updates_app_runtime_state(
    tmp_path,
):
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    old_provider = (
        app.state.market_hours_runtime_provider_v2
    )
    old_service = (
        app.state.market_hours_service_v2
    )

    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    client = TestClient(app)

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={
            "file_path": str(path),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["runtime_published"] is True

    assert (
        app.state.market_hours_runtime_provider_v2
        is not old_provider
    )
    assert (
        app.state.market_hours_service_v2
        is not old_service
    )

    assert (
        app.state
        .market_hours_data_lifecycle_v2
        .get_active_provider()
        is app.state.market_hours_runtime_provider_v2
    )

    assert (
        app.state
        .market_hours_data_lifecycle_v2
        .get_active_path()
        == path
    )


def test_refresh_endpoint_missing_file_preserves_runtime(
    tmp_path,
):
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    old_provider = (
        app.state.market_hours_runtime_provider_v2
    )
    old_service = (
        app.state.market_hours_service_v2
    )

    missing = tmp_path / "missing-certified-hours.json"

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={
            "file_path": str(missing),
        },
    )

    assert response.status_code == 500

    assert (
        app.state.market_hours_runtime_provider_v2
        is old_provider
    )
    assert (
        app.state.market_hours_service_v2
        is old_service
    )


def test_create_app_exposes_market_hours_status():
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    client = TestClient(app)

    response = client.get(
        "/api/v2/market-hours/status"
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "EMPTY",
        "active": False,
        "active_path": None,
        "last_activation_report": None,
    }


def test_market_hours_status_reflects_successful_refresh(
    tmp_path,
):
    app = create_app(
        settings=APISettings(
            certified_market_hours_path=None,
        )
    )

    path = _write_snapshot(
        tmp_path,
        covered_dates=["2026-08-18"],
    )

    client = TestClient(app)

    refresh_response = client.post(
        "/api/v2/market-hours/refresh",
        json={
            "file_path": str(path),
        },
    )

    assert refresh_response.status_code == 200

    status_response = client.get(
        "/api/v2/market-hours/status"
    )

    assert status_response.status_code == 200

    payload = status_response.json()

    assert payload["status"] == "READY"
    assert payload["active"] is True
    assert payload["active_path"] == str(path)

    report = payload["last_activation_report"]

    assert report is not None
    assert report["success"] is True
    assert report["status"] == "READY"
    assert report["source"] == str(path)
    assert report["covered_dates"] == 1
    assert report["closed_dates"] == 0
    assert report["special_hours"] == 0
    assert report["error"] is None
