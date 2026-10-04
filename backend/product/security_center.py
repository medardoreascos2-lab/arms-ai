"""Read-only Product Security Center projection."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class SecurityProjectionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INTEGRATION_PENDING = "INTEGRATION_PENDING"
    UNKNOWN = "UNKNOWN"


class SecurityEventSeverity(str, Enum):
    INFORMATION = "INFORMATION"
    WATCH = "WATCH"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"


class LocalSessionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_reference: str = Field(pattern=_SAFE_ID)
    device_label: str = Field(min_length=1, max_length=128)
    issued_at: datetime
    expires_at: datetime
    is_current: bool
    status: str = Field(min_length=1, max_length=32)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("session timestamps must be UTC")
        return value


class SecurityEventProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_reference: str = Field(pattern=_SAFE_ID)
    event_type: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=512)
    severity: SecurityEventSeverity

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("security event time must be UTC")
        return value


class SensitivePermissionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    permission: str = Field(min_length=1, max_length=64)
    status: Literal["ALLOWED", "DENIED", "UNKNOWN"]


class ProductSecurityProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    local_sessions: tuple[LocalSessionProjection, ...] = ()
    recent_events: tuple[SecurityEventProjection, ...] = ()
    mfa_status: SecurityProjectionStatus
    passkey_status: SecurityProjectionStatus
    sensitive_permissions: tuple[SensitivePermissionProjection, ...] = ()
    auth_provider_provisioning_authorized: Literal[False] = False
    credential_mutation_authorized: Literal[False] = False
