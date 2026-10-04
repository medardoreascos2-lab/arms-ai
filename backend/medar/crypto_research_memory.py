"""Source-linked, session-only crypto market research without exchange authority."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


class CryptoEvidenceMode(str, Enum):
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    HISTORICAL = "HISTORICAL"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class CryptoResearchMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    asset_symbol: str
    exchange_reference: str
    source_reference: str
    dataset_reference: str
    evidence_mode: CryptoEvidenceMode
    asset_research: str = field(repr=False)
    exchange_observation: str = field(repr=False)
    fee_assumption: str = field(repr=False)
    network_condition: str = field(repr=False)
    arbitrage_opportunity: str = field(repr=False)
    paper_outcome: str = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.CRYPTO
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    analysis_only: bool = True
    exchange_execution_authority: bool = False
    paper_execution_authority: bool = False
    live_execution_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "asset_symbol", "exchange_reference", "source_reference", "dataset_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        for name in ("asset_research", "exchange_observation", "fee_assumption", "network_condition", "arbitrage_opportunity", "paper_outcome"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like crypto research is not retained")
        if not isinstance(self.evidence_mode, CryptoEvidenceMode):
            raise TypeError("crypto evidence mode must be explicit")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.CRYPTO or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("crypto research domain and sensitivity cannot be weakened")
        if not self.session_only or not self.analysis_only or self.exchange_execution_authority or self.paper_execution_authority or self.live_execution_authority:
            raise ValueError("crypto research cannot authorize execution")
