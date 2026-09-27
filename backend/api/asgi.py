"""ASGI entry point: recover and publish the committed PAPER account at startup.

Production requests resolve one complete account application per generation.
Explicitly injected standalone contexts retain containment-only switching.
"""

from __future__ import annotations

import os
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from anyio import CancelScope

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
    account_config_path=None,
    account_registry=None,
    sim_native_service_factory=None,
) -> FastAPI:
    """Construye la aplicación ASGI con un runtime compartido."""

    if runtime_context is None:
        from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
        from backend.api.account_runtime_application_v2 import AccountRuntimeApplicationV2
        from backend.services.account_runtime_coordinator_v2 import AccountRuntimeCoordinatorV2
        legacy_path = Path(state_path) if state_path is not None else resolve_runtime_state_path()
        from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
        from backend.api.sim_native_financial_api_v3 import create_sim_native_financial_router_v3
        holder = {}

        def read_native_financial():
            service = holder.get("service")
            return service.get_snapshot() if service is not None else SimNativeFinancialRuntimeServiceV3.unavailable()

        def child_application(runtime, manager, directory):
            child = AccountRuntimeCoordinatorV2._application(runtime, manager, directory)
            def read_native_preflight():
                from backend.services.first_controlled_trade_preflight_v3 import FirstControlledTradePreflightV3
                service = holder.get("service")
                return service.get_first_trade_preflight() if service is not None else FirstControlledTradePreflightV3.unavailable()
            child.include_router(create_sim_native_financial_router_v3(read_native_financial, read_native_preflight))
            return child

        coordinator = AccountRuntimeCoordinatorV2(
            config_path=account_config_path or AccountConfigManagerV2.DEFAULT_CONFIG_PATH,
            namespace_root=legacy_path.parent / (legacy_path.stem + "-accounts"),
            legacy_state_path=legacy_path, registry=account_registry, application_factory=child_application)
        application = AccountRuntimeApplicationV2(coordinator)
        paper_lifespan = application.router.lifespan_context

        @asynccontextmanager
        async def process_lifespan(app):
            # Construct/start only here, never at import or during PAPER switches.
            service = (sim_native_service_factory or SimNativeFinancialRuntimeServiceV3)()
            holder["service"] = service
            stopped = asyncio.Event()

            async def observe():
                while not stopped.is_set():
                    try:
                        await asyncio.wait_for(stopped.wait(), timeout=service.cadence_seconds)
                    except asyncio.TimeoutError:
                        await asyncio.to_thread(service.observe)

            worker = None
            try:
                await asyncio.to_thread(service.start)
                if service.cadence_seconds is not None:
                    worker = asyncio.create_task(observe())
                async with paper_lifespan(app):
                    yield
            finally:
                with CancelScope(shield=True):
                    stopped.set()
                    try:
                        if worker is not None:
                            await worker
                    finally:
                        await asyncio.to_thread(service.stop)
                        holder.clear()

        application.router.lifespan_context = process_lifespan
        return application

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


# Startup resolves the committed account; no module-global runtime captures A.
app = create_asgi_app()
