from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class RuntimeRefreshServiceProtocol(Protocol):
    def refresh_from_file(
        self,
        *,
        file_path: str | Path,
    ) -> dict[str, object]:
        ...


class MarketHoursLifecycleProtocol(Protocol):
    def get_status(self) -> str:
        ...

    def get_active_path(self) -> Path | None:
        ...

    def get_last_activation_report(
        self,
    ) -> dict[str, object] | None:
        ...


class CertifiedMarketHoursRefreshRequestV2(BaseModel):
    file_path: str


def create_certified_market_hours_refresh_router_v2(
    *,
    refresh_service: RuntimeRefreshServiceProtocol,
    lifecycle: MarketHoursLifecycleProtocol | None = None,
) -> APIRouter:
    if refresh_service is None:
        raise ValueError(
            "refresh_service es obligatorio."
        )

    refresh_method = getattr(
        refresh_service,
        "refresh_from_file",
        None,
    )

    if not callable(refresh_method):
        raise TypeError(
            "refresh_service debe implementar "
            "refresh_from_file()."
        )

    if lifecycle is not None:
        for method_name in (
            "get_status",
            "get_active_path",
            "get_last_activation_report",
        ):
            method = getattr(
                lifecycle,
                method_name,
                None,
            )

            if not callable(method):
                raise TypeError(
                    "lifecycle debe implementar "
                    f"{method_name}()."
                )

    router = APIRouter(
        prefix="/api/v2/market-hours",
        tags=["market-hours"],
    )

    @router.post("/refresh")
    def refresh_certified_market_hours(
        request: CertifiedMarketHoursRefreshRequestV2,
    ) -> dict[str, object]:
        file_path = request.file_path.strip()

        if not file_path:
            raise HTTPException(
                status_code=400,
                detail="file_path no puede estar vacío.",
            )

        return refresh_service.refresh_from_file(
            file_path=file_path,
        )

    if lifecycle is not None:

        @router.get("/status")
        def get_certified_market_hours_status(
        ) -> dict[str, object]:
            active_path = lifecycle.get_active_path()
            last_activation_report = (
                lifecycle.get_last_activation_report()
            )

            return {
                "status": lifecycle.get_status(),
                "active": active_path is not None,
                "active_path": (
                    None
                    if active_path is None
                    else str(active_path)
                ),
                "last_activation_report": (
                    last_activation_report
                ),
            }

    return router
