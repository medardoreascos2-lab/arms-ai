"""Session-only NQ futures research evidence with no trading authority."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


class FuturesInstrument(str, Enum):
    NQ = "NQ"
    MNQ = "MNQ"


class ResearchObservationMode(str, Enum):
    HISTORICAL = "HISTORICAL"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    PAPER_OBSERVED = "PAPER_OBSERVED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class FuturesResearchMemory:
    instrument: FuturesInstrument
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    dataset_reference: str
    observation_mode: ResearchObservationMode
    market_regime: str = field(repr=False)
    setup: str = field(repr=False)
    decision: str = field(repr=False)
    result: str = field(repr=False)
    risk_observation: str = field(repr=False)
    evidence: str = field(repr=False)
    observed_at: datetime
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    session_only: bool = True
    broker_authority: bool = False
    paper_execution_authority: bool = False
    live_execution_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, FuturesInstrument) or not isinstance(self.observation_mode, ResearchObservationMode):
            raise TypeError("instrument and observation mode must be explicit")
        if self.observation_mode is ResearchObservationMode.PAPER_OBSERVED:
            raise PermissionError("paper observation requires independently validated execution evidence")
        for name in ("tenant_id", "owner_id", "session_id", "source_reference", "dataset_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be source-linked bounded text")
        for name in ("market_regime", "setup", "decision", "result", "risk_observation", "evidence"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError(f"{name} must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like research content is not retained")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.sensitivity is not DurableSensitivity.SENSITIVE or not self.session_only:
            raise ValueError("futures research remains sensitive and session-only")
        if self.broker_authority or self.paper_execution_authority or self.live_execution_authority:
            raise ValueError("research memory cannot authorize execution")

    @property
    def domain(self) -> DurableMemoryDomain:
        return DurableMemoryDomain[self.instrument.value]


class FuturesResearchSessionIndex:
    """Separate instrument buckets; never combine NQ and MNQ implicitly."""

    def __init__(self, tenant_id: str, owner_id: str, session_id: str, *, max_per_instrument: int = 100):
        for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id), ("session_id", session_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if type(max_per_instrument) is not int or not 1 <= max_per_instrument <= 1000:
            raise ValueError("max_per_instrument must be 1 to 1000")
        self.tenant_id = tenant_id
        self.owner_id = owner_id
        self.session_id = session_id
        self.max_per_instrument = max_per_instrument
        self._buckets: dict[FuturesInstrument, list[FuturesResearchMemory]] = {instrument: [] for instrument in FuturesInstrument}

    def add(self, record: FuturesResearchMemory) -> None:
        if not isinstance(record, FuturesResearchMemory) or (
            record.tenant_id, record.owner_id, record.session_id
        ) != (self.tenant_id, self.owner_id, self.session_id):
            raise PermissionError("futures research session scope mismatch")
        bucket = self._buckets[record.instrument]
        if len(bucket) >= self.max_per_instrument:
            raise ValueError("instrument research capacity exceeded")
        if any(existing.source_reference == record.source_reference for existing in bucket):
            raise ValueError("instrument source already recorded")
        bucket.append(record)

    def list_for(self, instrument: FuturesInstrument, *, tenant_id: str, owner_id: str, session_id: str) -> tuple[FuturesResearchMemory, ...]:
        if not isinstance(instrument, FuturesInstrument):
            raise TypeError("explicit NQ or MNQ instrument is required")
        if (tenant_id, owner_id, session_id) != (self.tenant_id, self.owner_id, self.session_id):
            raise PermissionError("futures research session scope mismatch")
        return tuple(self._buckets[instrument])
