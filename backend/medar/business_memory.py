"""Source-linked, session-only business decision and KPI memory."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


@dataclass(frozen=True)
class BusinessMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    company_reference: str
    source_reference: str
    dataset_reference: str
    goal: str = field(repr=False)
    kpi_name: str = field(repr=False)
    kpi_value: Decimal
    kpi_unit: str
    strategy: str = field(repr=False)
    decision: str = field(repr=False)
    result: str = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.BUSINESS
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    analysis_only: bool = True
    business_action_authority: bool = False
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "company_reference", "source_reference", "dataset_reference", "kpi_unit"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in ("goal", "kpi_name", "strategy", "decision", "result"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like business content is not retained")
        if not isinstance(self.kpi_value, Decimal) or not self.kpi_value.is_finite():
            raise ValueError("KPI value must be a finite Decimal")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.BUSINESS or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("business domain and sensitivity cannot be weakened")
        if not self.session_only or not self.analysis_only or self.business_action_authority or self.trading_authority:
            raise ValueError("business memory cannot authorize actions")
