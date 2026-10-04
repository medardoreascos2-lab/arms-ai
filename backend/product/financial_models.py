"""Product-facing, read-only financial projection contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FinancialProjectionStatus(str, Enum):
    READY = "READY"
    UNKNOWN = "UNKNOWN"


class FinancialSourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class ProductFinancialProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=128)
    source_label: str = Field(min_length=1, max_length=128)
    classification: Literal["SYNTHETIC", "LOCAL_TEST_ONLY", "NOT_REAL_ACCOUNT_DATA", "UNKNOWN"]
    observed_at: datetime | None
    freshness_seconds: int | None = Field(ge=0)
    source_status: FinancialSourceStatus

    @model_validator(mode="after")
    def freshness_matches_source(self) -> ProductFinancialProvenance:
        if self.source_status == FinancialSourceStatus.UNKNOWN:
            if self.observed_at is not None or self.freshness_seconds is not None:
                raise ValueError("unknown source cannot claim observation freshness")
        elif self.observed_at is None or self.freshness_seconds is None:
            raise ValueError("available source requires observation freshness")
        return self


class ReadOnlyFinancialProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    status: FinancialProjectionStatus
    provenance: ProductFinancialProvenance
    warnings: tuple[str, ...] = ()
    investment_advice: Literal[False] = False
    execution_authorized: Literal[False] = False
    portfolio_mutation_authorized: Literal[False] = False


class FinancialAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    alert_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    detail: str = Field(min_length=1, max_length=1024)
    severity: Literal["INFORMATION", "WATCH", "IMPORTANT", "UNKNOWN"]


class TradingSummaryProjection(ReadOnlyFinancialProjection):
    instrument: Literal["NQ", "MNQ", "UNKNOWN"]
    account_ref: str | None = None
    market_state: str = "UNKNOWN"
    risk_state: str = "UNKNOWN"
    session_state: str = "UNKNOWN"
    coach_summary: str | None = None
    alerts: tuple[FinancialAlert, ...] = ()
    data_freshness: str = "UNKNOWN"
    source_status: FinancialSourceStatus


class PortfolioAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=128)
    percentage: Decimal | None = Field(default=None, ge=0, le=100)


class PortfolioSummaryProjection(ReadOnlyFinancialProjection):
    portfolio_ref: str | None = None
    currency: str = Field(default="UNKNOWN", min_length=3, max_length=8)
    total_value: Decimal | None = Field(default=None, ge=0)
    cash: Decimal | None = Field(default=None, ge=0)
    allocation: tuple[PortfolioAllocation, ...] = ()
    concentration: str = "UNKNOWN"
    risk: str = "UNKNOWN"
    drawdown: Decimal | None = Field(default=None, ge=0)
    alerts: tuple[FinancialAlert, ...] = ()
    source_status: FinancialSourceStatus


class PortfolioRiskProjection(ReadOnlyFinancialProjection):
    portfolio_ref: str | None = None
    risk_state: str = "UNKNOWN"
    concentration_state: str = "UNKNOWN"
    drawdown: Decimal | None = Field(default=None, ge=0)
    source_status: FinancialSourceStatus


class TradingCoachProjection(ReadOnlyFinancialProjection):
    summary: str | None = None
    strengths: tuple[str, ...] = ()
    review_items: tuple[str, ...] = ()
    source_status: FinancialSourceStatus


class ShadowMedarProjection(ReadOnlyFinancialProjection):
    summary: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    evidence: tuple[str, ...] = ()
    source_status: FinancialSourceStatus


class FinancialAlertCollection(ReadOnlyFinancialProjection):
    alerts: tuple[FinancialAlert, ...] = ()
    source_status: FinancialSourceStatus


class DailyFinancialSnapshot(ReadOnlyFinancialProjection):
    headline: str | None = None
    trading: TradingSummaryProjection | None = None
    portfolio: PortfolioSummaryProjection | None = None
    coach: TradingCoachProjection | None = None
    shadow_medar: ShadowMedarProjection | None = None
    alerts: tuple[FinancialAlert, ...] = ()
    source_status: FinancialSourceStatus
