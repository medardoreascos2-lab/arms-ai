"""Atomic read-only status projection for the Phase 3 runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Mapping

from fastapi import APIRouter, HTTPException


StatusReader = Callable[[], Mapping[str, object]]


@dataclass(frozen=True)
class Phase3StatusSources:
    runtime_health: StatusReader
    snapshot_ingestion: StatusReader
    evaluation_health: StatusReader
    outbox_health: StatusReader
    worker_health: StatusReader
    research_queue_health: StatusReader

    def __post_init__(self) -> None:
        if any(not callable(value) for value in self.__dict__.values()):
            raise ValueError("every status source must be callable")


def _read_all(sources: Phase3StatusSources) -> dict[str, object]:
    try:
        values: dict[str, Mapping[str, object]] = {}
        for name, reader in sources.__dict__.items():
            value = reader()
            if not isinstance(value, Mapping):
                raise ValueError(f"{name} returned invalid status")
            values[name] = value
        snapshot = json.loads(json.dumps(values, ensure_ascii=False, allow_nan=False, sort_keys=True))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="PHASE3_STATUS_UNAVAILABLE") from exc
    return {
        "execution_authorized": False,
        "production_mutation_authorized": False,
        "read_only": True,
        "status": snapshot,
    }


def create_phase3_status_router(sources: Phase3StatusSources) -> APIRouter:
    if not isinstance(sources, Phase3StatusSources):
        raise ValueError("sources must be Phase3StatusSources")
    router = APIRouter(prefix="/api/phase3", tags=["phase3-status-read-only"])

    @router.get("/status")
    def get_phase3_status() -> dict[str, object]:
        return _read_all(sources)

    return router
