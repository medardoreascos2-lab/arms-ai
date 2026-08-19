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
