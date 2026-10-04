"""Analysis-only, session-local portfolio memory proposals."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


class PortfolioEvidenceMode(str, Enum):
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    HISTORICAL = "HISTORICAL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class PortfolioMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    portfolio_reference: str
    source_reference: str
    dataset_reference: str
    evidence_mode: PortfolioEvidenceMode
    thesis: str = field(repr=False)
    risk_observation: str = field(repr=False)
    allocation_decision: str = field(repr=False)
    rebalance_proposal: str = field(repr=False)
    outcome: str = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.PORTFOLIO
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    analysis_only: bool = True
    portfolio_mutation_authority: bool = False
    trading_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "portfolio_reference", "source_reference", "dataset_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be bounded explicit reference")
        for name in ("thesis", "risk_observation", "allocation_decision", "rebalance_proposal", "outcome"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like portfolio content is not retained")
        if not isinstance(self.evidence_mode, PortfolioEvidenceMode):
            raise TypeError("portfolio evidence mode must be explicit")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("portfolio observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.PORTFOLIO or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("portfolio domain and sensitivity cannot be weakened")
        if not self.session_only or not self.analysis_only or self.portfolio_mutation_authority or self.trading_authority:
            raise ValueError("portfolio memory cannot authorize execution or mutation")
