"""Default-deny Product support projection containing metadata only."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.billing import BillingStatus
from backend.product.customer_session import CustomerSessionStatus


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class SupportViewAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request_id: str = Field(pattern=_SAFE_ID)
    operator_id: str = Field(pattern=_SAFE_ID)
    authorized: Literal[True]
    scope: Literal["READ_ONLY_METADATA"] = "READ_ONLY_METADATA"


class SupportAccountMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_reference: str = Field(pattern=_SAFE_ID)
    tenant_reference: str = Field(pattern=_SAFE_ID)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("created_at must be UTC")
        return value


class ProductSupportProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_metadata: SupportAccountMetadata
    membership_state: BillingStatus
    error_reference: str | None = Field(default=None, pattern=_SAFE_ID)
    session_status: CustomerSessionStatus
    read_only: Literal[True] = True
    sensitive_content_included: Literal[False] = False
    financial_details_included: Literal[False] = False


def create_support_projection(
    *,
    authorization: SupportViewAuthorization | None,
    account_metadata: SupportAccountMetadata,
    membership_state: BillingStatus,
    error_reference: str | None,
    session_status: CustomerSessionStatus,
) -> ProductSupportProjection:
    if authorization is None or authorization.authorized is not True:
        raise PermissionError("explicit read-only support authorization required")
    return ProductSupportProjection(
        account_metadata=account_metadata,
        membership_state=membership_state,
        error_reference=error_reference,
        session_status=session_status,
    )