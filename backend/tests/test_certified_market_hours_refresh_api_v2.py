from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers.certified_market_hours_refresh_api_v2 import (
    create_certified_market_hours_refresh_router_v2,
)


class FakeRefreshService:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def refresh_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        path = Path(file_path)
        self.calls.append(path)

        return {
            "runtime_published": True,
            "file_path": path.as_posix(),
        }


def build_client():
    service = FakeRefreshService()

    app = FastAPI()

    app.include_router(
        create_certified_market_hours_refresh_router_v2(
            refresh_service=service,
        )
    )

    return TestClient(app), service


def test_refresh_endpoint_calls_service():
    client, service = build_client()

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={
            "file_path": (
                "backend/config/market_hours/"
                "certified_market_hours_fixture_v2.json"
            ),
        },
    )

    assert response.status_code == 200

    assert len(service.calls) == 1

    assert service.calls[0] == Path(
        "backend/config/market_hours/"
        "certified_market_hours_fixture_v2.json"
    )

    assert response.json() == {
        "runtime_published": True,
        "file_path": (
            "backend/config/market_hours/"
            "certified_market_hours_fixture_v2.json"
        ),
    }


def test_refresh_endpoint_rejects_missing_file_path():
    client, service = build_client()

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={},
    )

    assert response.status_code == 422
    assert service.calls == []


def test_refresh_endpoint_rejects_blank_file_path():
    client, service = build_client()

    response = client.post(
        "/api/v2/market-hours/refresh",
        json={
            "file_path": "   ",
        },
    )

    assert response.status_code == 400
    assert service.calls == []


def test_router_rejects_missing_service():
    with pytest.raises(
        ValueError,
        match="refresh_service es obligatorio",
    ):
        create_certified_market_hours_refresh_router_v2(
            refresh_service=None,
        )


def test_router_rejects_invalid_service():
    with pytest.raises(
        TypeError,
        match="refresh_from_file",
    ):
        create_certified_market_hours_refresh_router_v2(
            refresh_service=object(),
        )


class FakeLifecycle:
    def __init__(
        self,
        *,
        status="EMPTY",
        active_path=None,
        last_activation_report=None,
    ) -> None:
        self.status = status
        self.active_path = active_path
        self.last_activation_report = (
            last_activation_report
        )

    def get_status(self) -> str:
        return self.status

    def get_active_path(self):
        return self.active_path

    def get_last_activation_report(self):
        if self.last_activation_report is None:
            return None

        return dict(
            self.last_activation_report
        )


def build_client_with_lifecycle(
    lifecycle,
):
    service = FakeRefreshService()

    app = FastAPI()

    app.include_router(
        create_certified_market_hours_refresh_router_v2(
            refresh_service=service,
            lifecycle=lifecycle,
        )
    )

    return TestClient(app), service


def test_status_endpoint_reports_empty_runtime():
    lifecycle = FakeLifecycle()

    client, service = build_client_with_lifecycle(
        lifecycle
    )

    response = client.get(
        "/api/v2/market-hours/status"
    )

    assert response.status_code == 200
    assert service.calls == []

    assert response.json() == {
        "status": "EMPTY",
        "active": False,
        "active_path": None,
        "last_activation_report": None,
    }


def test_status_endpoint_reports_ready_runtime():
    active_path = Path(
        "backend/config/market_hours/"
        "certified_market_hours_fixture_v2.json"
    )

    lifecycle = FakeLifecycle(
        status="READY",
        active_path=active_path,
        last_activation_report={
            "success": True,
            "status": "READY",
            "source": str(active_path),
            "covered_dates": 3,
            "closed_dates": 0,
            "special_hours": 0,
            "error": None,
        },
    )

    client, service = build_client_with_lifecycle(
        lifecycle
    )

    response = client.get(
        "/api/v2/market-hours/status"
    )

    assert response.status_code == 200
    assert service.calls == []

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["active"] is True
    assert payload["active_path"] == str(
        active_path
    )

    assert (
        payload["last_activation_report"]
        == lifecycle.last_activation_report
    )


def test_status_endpoint_preserves_failed_attempt_metadata():
    active_path = Path(
        "backend/config/market_hours/"
        "certified_market_hours_fixture_v2.json"
    )

    lifecycle = FakeLifecycle(
        status="READY",
        active_path=active_path,
        last_activation_report={
            "success": False,
            "status": "FAILED",
            "source": "missing.json",
            "covered_dates": None,
            "closed_dates": None,
            "special_hours": None,
            "error": {
                "type": "FileNotFoundError",
                "message": "missing.json",
            },
        },
    )

    client, _ = build_client_with_lifecycle(
        lifecycle
    )

    response = client.get(
        "/api/v2/market-hours/status"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["active"] is True

    assert (
        payload["last_activation_report"]["success"]
        is False
    )
    assert (
        payload["last_activation_report"]["status"]
        == "FAILED"
    )


def test_router_rejects_invalid_lifecycle():
    with pytest.raises(
        TypeError,
        match="lifecycle debe implementar",
    ):
        create_certified_market_hours_refresh_router_v2(
            refresh_service=FakeRefreshService(),
            lifecycle=object(),
        )
