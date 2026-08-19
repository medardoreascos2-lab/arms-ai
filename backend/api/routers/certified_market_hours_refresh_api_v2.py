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


class CertifiedMarketHoursRefreshRequestV2(BaseModel):
    file_path: str


def create_certified_market_hours_refresh_router_v2(
    *,
    refresh_service: RuntimeRefreshServiceProtocol,
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

    return router
