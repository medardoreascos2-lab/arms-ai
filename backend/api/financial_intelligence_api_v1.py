"""Admin-gated GET-only financial intelligence API over an immutable read model."""

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from fastapi import APIRouter, Depends, Response

from backend.api.admin_authorization_dependency_v2 import require_admin_authorization_v2


SECTIONS = (
    "portfolio", "company-intelligence", "crypto-scanner", "arbitrage-radar",
    "trading-coach", "shadow-medar", "daily-snapshot",
)


@dataclass(frozen=True)
class FinancialReadModel:
    sections: Mapping[str, Mapping[str, object]]
    _serialized: Mapping[str, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if set(self.sections) != set(SECTIONS):
            raise ValueError("financial read model must provide all sections")
        frozen = {}
        serialized = {}
        for key, payload in self.sections.items():
            if not isinstance(payload, Mapping) or not isinstance(payload.get("status"), str):
                raise ValueError("financial section requires explicit status")
            encoded = json.dumps(dict(payload), allow_nan=False)
            frozen[key] = MappingProxyType(json.loads(encoded))
            serialized[key] = encoded
        object.__setattr__(self, "sections", MappingProxyType(frozen))
        object.__setattr__(self, "_serialized", MappingProxyType(serialized))

    @classmethod
    def unavailable(cls) -> "FinancialReadModel":
        return cls({name: {"status": "UNKNOWN", "reason": "NO_SOURCE_CONNECTED"} for name in SECTIONS})

    def get(self, section: str) -> dict[str, object]:
        return json.loads(self._serialized[section])


def create_financial_intelligence_router_v1(read_model: FinancialReadModel) -> APIRouter:
    if not isinstance(read_model, FinancialReadModel):
        raise TypeError("immutable financial read model is required")
    router = APIRouter(
        prefix="/api/v1/financial",
        tags=["financial intelligence"],
        dependencies=[Depends(require_admin_authorization_v2)],
    )
    def make_reader(section_name: str):
        def read_section(response: Response):
            response.headers["Cache-Control"] = "no-store"
            return read_model.get(section_name)
        read_section.__name__ = f"read_financial_{section_name.replace('-', '_')}"
        return read_section

    for section in SECTIONS:
        router.add_api_route(f"/{section}", make_reader(section), methods=["GET"])
    return router
