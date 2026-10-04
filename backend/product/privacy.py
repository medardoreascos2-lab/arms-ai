"""Read-only Product privacy-center projection and request seams."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class PrivacySeamStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INTEGRATION_PENDING = "INTEGRATION_PENDING"
    UNAVAILABLE = "UNAVAILABLE"


class RetentionChoice(str, Enum):
    SESSION_ONLY = "SESSION_ONLY"
    THIRTY_DAYS = "THIRTY_DAYS"
    NINETY_DAYS = "NINETY_DAYS"
    UNTIL_REMOVAL = "UNTIL_REMOVAL"


class MemoryCategoryProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str = Field(min_length=1, max_length=64)
    visible: bool
    provenance: str = Field(min_length=1, max_length=128)


class ConnectedServiceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    service_reference: str = Field(pattern=_SAFE_ID)
    label: str = Field(min_length=1, max_length=128)
    status: PrivacySeamStatus


class ProductPrivacyProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    memory_categories: tuple[MemoryCategoryProjection, ...] = ()
    retention_choice: RetentionChoice | None = None
    data_export_status: PrivacySeamStatus
    removal_request_status: PrivacySeamStatus
    connected_services: tuple[ConnectedServiceProjection, ...] = ()
    activity_history_visible: bool | None = None
    direct_deletion_authorized: Literal[False] = False
    production_identity_authorized: Literal[False] = False


class PrivacyRequestKind(str, Enum):
    DATA_EXPORT = "DATA_EXPORT"
    REMOVAL_REVIEW = "REMOVAL_REVIEW"


class PrivacyRequestSeam(Protocol):
    def request_review(
        self, *, tenant_id: str, user_id: str, kind: PrivacyRequestKind,
        idempotency_key: str,
    ) -> str: ...
