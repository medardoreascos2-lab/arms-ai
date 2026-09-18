from datetime import datetime
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class EconomicNewsRefreshServiceProtocol(Protocol):
    def refresh_from_file(self, *, file_path: str | Path) -> dict[str, object]:
        ...


class EconomicNewsLifecycleProtocol(Protocol):
    def get_status(self) -> str:
        ...

    def get_active_path(self) -> Path | None:
        ...

    def get_last_activation_report(self) -> dict[str, object] | None:
        ...

    def get_active_provider(self):
        ...


class EconomicNewsProviderProtocol(Protocol):
    def is_timestamp_covered(self, *, timestamp: datetime) -> bool:
        ...


class CertifiedEconomicNewsRefreshRequestV2(BaseModel):
    file_path: str


def create_certified_economic_news_refresh_router_v2(
    *,
    refresh_service: EconomicNewsRefreshServiceProtocol,
    lifecycle: EconomicNewsLifecycleProtocol,
    runtime_provider: EconomicNewsProviderProtocol,
) -> APIRouter:
    if refresh_service is None or lifecycle is None or runtime_provider is None:
        raise ValueError("refresh_service, lifecycle y runtime_provider son obligatorios.")

    router = APIRouter(
        prefix="/api/v2/economic-news",
        tags=["economic-news"],
    )

    @router.post("/refresh")
    def refresh_certified_economic_news(
        request: CertifiedEconomicNewsRefreshRequestV2,
    ) -> dict[str, object]:
        file_path = request.file_path.strip()
        if not file_path:
            raise HTTPException(status_code=400, detail="file_path no puede estar vacío.")
        return refresh_service.refresh_from_file(file_path=file_path)

    @router.get("/status")
    def get_certified_economic_news_status() -> dict[str, object]:
        active_path = lifecycle.get_active_path()
        return {
            "status": lifecycle.get_status(),
            "active": active_path is not None,
            "active_path": None if active_path is None else str(active_path),
            "last_activation_report": lifecycle.get_last_activation_report(),
        }

    @router.get("/coverage")
    def get_certified_economic_news_coverage(
        timestamp: datetime | None = None,
    ) -> dict[str, object]:
        if timestamp is None:
            timestamp = datetime.now().astimezone()
        provider = lifecycle.get_active_provider()
        return {
            "timestamp": timestamp.isoformat(),
            "covered": provider.is_timestamp_covered(timestamp=timestamp),
        }

    return router
