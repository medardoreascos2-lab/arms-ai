"""Standalone read-only Phase 3 research API router."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Mapping

from fastapi import APIRouter, HTTPException


ResearchReader = Callable[[], tuple[Mapping[str, object], ...]]


@dataclass(frozen=True)
class ResearchApiSources:
    datasets: ResearchReader
    experiments: ResearchReader
    challengers: ResearchReader
    reports: ResearchReader
    promotion_reviews: ResearchReader

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not callable(value):
                raise ValueError(f"{name} must be callable")


def _read(reader: ResearchReader) -> dict[str, object]:
    try:
        records = reader()
        if not isinstance(records, tuple) or any(not isinstance(item, Mapping) for item in records):
            raise ValueError("research reader returned an invalid collection")
        items = json.loads(json.dumps(records, ensure_ascii=False, allow_nan=False, sort_keys=True))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="RESEARCH_READ_MODEL_UNAVAILABLE") from exc
    return {
        "count": len(items),
        "execution_authorized": False,
        "items": items,
        "production_mutation_authorized": False,
        "read_only": True,
    }


def create_phase3_research_router(sources: ResearchApiSources) -> APIRouter:
    """Create an injectable GET-only router without mounting it into frozen V8."""

    if not isinstance(sources, ResearchApiSources):
        raise ValueError("sources must be ResearchApiSources")
    router = APIRouter(prefix="/api/phase3/research", tags=["phase3-research-read-only"])

    @router.get("/datasets")
    def list_datasets() -> dict[str, object]:
        return _read(sources.datasets)

    @router.get("/experiments")
    def list_experiments() -> dict[str, object]:
        return _read(sources.experiments)

    @router.get("/challengers")
    def list_challengers() -> dict[str, object]:
        return _read(sources.challengers)

    @router.get("/reports")
    def list_reports() -> dict[str, object]:
        return _read(sources.reports)

    @router.get("/promotion-reviews")
    def list_promotion_reviews() -> dict[str, object]:
        return _read(sources.promotion_reviews)

    return router
