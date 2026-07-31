from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import asgi
from backend.api.asgi import (
    create_asgi_app,
    create_runtime_lifespan,
    resolve_runtime_state_path,
)
from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
    build_runtime_context,
)


def test_asgi_exposes_fastapi_application():
    assert isinstance(
        asgi.app,
        FastAPI,
    )


def test_asgi_exposes_runtime_context():
    assert isinstance(
        asgi.runtime_context,
        RuntimeContextV2,
    )


def test_asgi_app_uses_shared_runtime_context():
    assert (
        asgi.app.state.runtime_context_v2
        is asgi.runtime_context
    )


def test_asgi_app_uses_shared_trade_lifecycle():
    assert (
        asgi.app.state.trade_lifecycle_service_v2
        is asgi.runtime_context.trade_lifecycle_service
    )


def test_asgi_app_uses_shared_execution_manager():
    assert (
        asgi.app.state.execution_manager_v2
        is asgi.runtime_context.execution_manager
    )


def test_asgi_app_uses_shared_paper_execution_engine():
    assert (
        asgi.app.state.paper_execution_engine_v2
        is asgi.runtime_context.paper_execution_engine
    )


def test_asgi_app_uses_shared_position_manager():
    assert (
        asgi.app.state
        .trade_lifecycle_service_v2
        .position_manager
        is asgi.runtime_context.position_manager
    )


def test_create_asgi_app_uses_supplied_context(
    tmp_path: Path,
):
    context = build_runtime_context()
    state_path = tmp_path / "runtime-state.json"

    application = create_asgi_app(
        runtime_context=context,
        state_path=state_path,
    )

    assert application.state.runtime_context_v2 is context
    assert (
        application.state.runtime_state_path_v2
        == state_path
    )


def test_lifespan_starts_and_stops_runtime(
    tmp_path: Path,
):
    context = build_runtime_context()
    state_path = tmp_path / "runtime-state.json"

    application = create_asgi_app(
        runtime_context=context,
        state_path=state_path,
    )

    manager = context.runtime_lifecycle_manager

    assert manager.get_status() == "IDLE"

    with TestClient(application) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert manager.get_status() == "RUNNING"

        startup_report = (
            application.state
            .runtime_startup_report_v2
        )

        assert startup_report is not None
        assert startup_report["success"] is True

    assert manager.get_status() == "STOPPED"
    assert state_path.exists()

    shutdown_report = (
        application.state
        .runtime_shutdown_report_v2
    )

    assert shutdown_report is not None
    assert shutdown_report["success"] is True


def test_lifespan_recovers_existing_snapshot(
    tmp_path: Path,
):
    state_path = tmp_path / "runtime-state.json"

    first_context = build_runtime_context()

    first_context.runtime_lifecycle_manager.start_clean()

    first_context.runtime_lifecycle_manager.shutdown_to(
        file_path=state_path,
    )

    second_context = build_runtime_context()

    application = create_asgi_app(
        runtime_context=second_context,
        state_path=state_path,
    )

    with TestClient(application):
        startup_report = (
            application.state
            .runtime_startup_report_v2
        )

        assert startup_report is not None
        assert startup_report["success"] is True
        assert startup_report["snapshot_found"] is True
        assert startup_report["recovery_attempted"] is True

    assert state_path.exists()


def test_resolve_runtime_state_path_uses_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(
        "ARMS_RUNTIME_STATE_PATH",
        raising=False,
    )

    assert resolve_runtime_state_path() == (
        asgi.DEFAULT_RUNTIME_STATE_PATH
    )


def test_resolve_runtime_state_path_uses_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    configured_path = (
        tmp_path / "configured-state.json"
    )

    monkeypatch.setenv(
        "ARMS_RUNTIME_STATE_PATH",
        str(configured_path),
    )

    assert resolve_runtime_state_path() == (
        configured_path
    )


def test_resolve_runtime_state_path_rejects_blank_env(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "ARMS_RUNTIME_STATE_PATH",
        "   ",
    )

    assert resolve_runtime_state_path() == (
        asgi.DEFAULT_RUNTIME_STATE_PATH
    )


def test_create_runtime_lifespan_rejects_invalid_context(
    tmp_path: Path,
):
    with pytest.raises(
        TypeError,
        match="RuntimeContextV2",
    ):
        create_runtime_lifespan(
            runtime_context=object(),  # type: ignore[arg-type]
            state_path=tmp_path / "state.json",
        )


def test_create_asgi_app_rejects_invalid_context(
    tmp_path: Path,
):
    with pytest.raises(
        TypeError,
        match="RuntimeContextV2",
    ):
        create_asgi_app(
            runtime_context=object(),  # type: ignore[arg-type]
            state_path=tmp_path / "state.json",
        )
