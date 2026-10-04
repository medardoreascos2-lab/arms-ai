"""Session-only campaign observations with no ad spend authority."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


@dataclass(frozen=True)
class MarketingMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    campaign_reference: str
    source_reference: str
    dataset_reference: str
    audience: str = field(repr=False)
    creative: str = field(repr=False)
    channel: str
    budget_amount: Decimal
    budget_currency: str
    result: str = field(repr=False)
    lesson: str = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.MARKETING
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    analysis_only: bool = True
    ad_spend_authority: bool = False
    campaign_mutation_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "campaign_reference", "source_reference", "dataset_reference", "channel", "budget_currency"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in ("audience", "creative", "result", "lesson"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like marketing content is not retained")
        if not isinstance(self.budget_amount, Decimal) or not self.budget_amount.is_finite() or self.budget_amount < 0:
            raise ValueError("budget metadata must be finite nonnegative Decimal")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.MARKETING or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("marketing domain and sensitivity cannot be weakened")
        if not self.session_only or not self.analysis_only or self.ad_spend_authority or self.campaign_mutation_authority:
            raise ValueError("marketing memory cannot authorize spending or mutations")
