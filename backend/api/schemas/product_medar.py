"""Untrusted HTTP shape for the separate Product MEDAR conversation boundary.

Identity and session scope are intentionally absent from the caller's body. A trusted
transport dependency must supply them before any MEDAR invocation.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductMedarPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    conversation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
    message: str = Field(min_length=1, max_length=8192)
    locale: str = Field(default="en", min_length=2, max_length=32,
                        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")
    response_profile: Literal["CONCISE", "STANDARD", "DETAILED"] = "STANDARD"
    client_context: ProductClientContext | None = None


class ProductClientContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    active_view: Literal["HOME", "MEDAR", "MARKETS", "TRADING", "PORTFOLIO"] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class ProductMedarStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    MEDAR_UNAVAILABLE = "MEDAR_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    MEMORY_UNAVAILABLE = "MEMORY_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_REQUEST = "INVALID_REQUEST"
    SESSION_INVALID = "SESSION_INVALID"
    LOCAL_TEST_DISABLED = "LOCAL_TEST_DISABLED"


class ProductSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    title: str
    locator: str


class ProductEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    summary: str
    digest: str


class ProductActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str
    description: str
    requires_confirmation: bool
    state: Literal["PROPOSED_ONLY"] = "PROPOSED_ONLY"
    execution_authorized: Literal[False] = False


class ProductModelProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    model_id: str
    locality: Literal["LOCAL"]


class ProductMedarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    response_id: str | None = None
    request_id: str
    status: ProductMedarStatus
    answer: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    reasoning_summary: str | None = None
    sources: tuple[ProductSourceReference, ...] = ()
    tool_evidence: tuple[ProductEvidenceReference, ...] = ()
    memory_evidence: tuple[ProductEvidenceReference, ...] = ()
    warnings: tuple[str, ...] = ()
    follow_up_needed: bool = False
    follow_up_suggestions: tuple[str, ...] = ()
    action_proposals: tuple[ProductActionProposal, ...] = ()
    model_provenance: ProductModelProvenance | None = None

    @model_validator(mode="after")
    def no_fabricated_degraded_answer(self) -> ProductMedarResponse:
        degraded = {
            ProductMedarStatus.MEDAR_UNAVAILABLE,
            ProductMedarStatus.MODEL_UNAVAILABLE,
            ProductMedarStatus.MEMORY_UNAVAILABLE,
            ProductMedarStatus.PERMISSION_DENIED,
            ProductMedarStatus.ENTITLEMENT_REQUIRED,
            ProductMedarStatus.RATE_LIMITED,
            ProductMedarStatus.INVALID_REQUEST,
            ProductMedarStatus.SESSION_INVALID,
            ProductMedarStatus.LOCAL_TEST_DISABLED,
        }
        if self.status not in degraded and (
            not self.response_id or not self.answer or self.confidence is None
        ):
            raise ValueError("canonical Product MEDAR responses require response identity and answer")
        if self.status in degraded and (
            self.answer is not None or self.confidence is not None
            or self.action_proposals or self.follow_up_suggestions
        ):
            raise ValueError("degraded Product MEDAR responses cannot contain an answer or proposals")
        return self
