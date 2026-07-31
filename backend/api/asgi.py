"""Punto de entrada ASGI de ARMS AI.

Este módulo construye un único RuntimeContextV2 y lo comparte
con FastAPI durante toda la vida del proceso.

El lifespan de FastAPI:

1. Recupera el estado anterior cuando existe un snapshot.
2. Inicia el runtime.
3. Mantiene disponible el mismo contexto para REST, WebSocket
   y dashboard.
4. Guarda el estado y apaga ordenadamente el runtime.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.api.app import create_app
from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
    build_runtime_context,
)


DEFAULT_RUNTIME_STATE_PATH = Path(
    "data/runtime/runtime-state-v2.json"
)


def resolve_runtime_state_path() -> Path:
    """Resuelve la ubicación del snapshot del runtime."""

    configured_path = os.getenv(
        "ARMS_RUNTIME_STATE_PATH",
    )

    if configured_path is None:
        return DEFAULT_RUNTIME_STATE_PATH

    normalized_path = configured_path.strip()

    if not normalized_path:
        return DEFAULT_RUNTIME_STATE_PATH

    return Path(normalized_path)


def create_runtime_lifespan(
    *,
    runtime_context: RuntimeContextV2,
    state_path: str | Path,
):
    """Construye el lifespan asociado a un runtime concreto."""

    if not isinstance(
        runtime_context,
        RuntimeContextV2,
    ):
        raise TypeError(
            "runtime_context debe ser RuntimeContextV2"
        )

    resolved_state_path = Path(state_path)

    @asynccontextmanager
    async def lifespan(
        app: FastAPI,
    ) -> AsyncIterator[None]:
        lifecycle_manager = (
            runtime_context.runtime_lifecycle_manager
        )

        startup_completed = False

        app.state.runtime_state_path_v2 = (
            resolved_state_path
        )
        app.state.runtime_startup_report_v2 = None
        app.state.runtime_shutdown_report_v2 = None

        try:
            startup_report = (
                lifecycle_manager.start_from(
                    file_path=resolved_state_path,
                    recover_if_available=True,
                )
            )

            startup_completed = True

            app.state.runtime_startup_report_v2 = (
                startup_report
            )

            yield

        finally:
            if startup_completed:
                shutdown_report = (
                    lifecycle_manager.shutdown_to(
                        file_path=resolved_state_path,
                    )
                )

                app.state.runtime_shutdown_report_v2 = (
                    shutdown_report
                )

    return lifespan


def create_asgi_app(
    *,
    runtime_context: RuntimeContextV2 | None = None,
    state_path: str | Path | None = None,
) -> FastAPI:
    """Construye la aplicación ASGI con un runtime compartido."""

    resolved_runtime_context = (
        runtime_context
        if runtime_context is not None
        else build_runtime_context()
    )

    if not isinstance(
        resolved_runtime_context,
        RuntimeContextV2,
    ):
        raise TypeError(
            "runtime_context debe ser RuntimeContextV2"
        )

    resolved_state_path = (
        Path(state_path)
        if state_path is not None
        else resolve_runtime_state_path()
    )

    application = create_app(
        runtime_context=resolved_runtime_context,
    )

    application.router.lifespan_context = (
        create_runtime_lifespan(
            runtime_context=resolved_runtime_context,
            state_path=resolved_state_path,
        )
    )

    application.state.runtime_context_v2 = (
        resolved_runtime_context
    )
    application.state.runtime_state_path_v2 = (
        resolved_state_path
    )

    return application


runtime_context: RuntimeContextV2 = (
    build_runtime_context()
)

runtime_state_path = resolve_runtime_state_path()

app = create_asgi_app(
    runtime_context=runtime_context,
    state_path=runtime_state_path,
)
