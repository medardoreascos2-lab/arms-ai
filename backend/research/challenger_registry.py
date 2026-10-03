"""Append-only research challenger registry with a read-only production reference."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from threading import RLock

from .backtest_runner import ResearchParameterSet


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class ChallengerRegistryError(RuntimeError):
    """Base challenger registry failure."""


class ChallengerConflictError(ChallengerRegistryError):
    """An immutable registry identity conflicts with existing evidence."""


class ChallengerTransitionError(ChallengerRegistryError):
    """A requested challenger transition is not authorized."""


class ChallengerStatus(str, Enum):
    PRODUCTION_REFERENCE = "PRODUCTION_REFERENCE"
    RESEARCH = "RESEARCH"
    CHALLENGER = "CHALLENGER"
    PAPER_CHALLENGER = "PAPER_CHALLENGER"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"


_TRANSITIONS = {
    ChallengerStatus.PRODUCTION_REFERENCE: frozenset(),
    ChallengerStatus.RESEARCH: frozenset({ChallengerStatus.CHALLENGER}),
    ChallengerStatus.CHALLENGER: frozenset({ChallengerStatus.PAPER_CHALLENGER}),
    ChallengerStatus.PAPER_CHALLENGER: frozenset(),
    ChallengerStatus.PROMOTION_CANDIDATE: frozenset(),
}


def _text(value: object, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    normalized = value.strip()
    if len(normalized) > 512:
        raise ValueError(f"{name} is too long")
    if identifier and _ID.fullmatch(normalized) is None:
        raise ValueError(f"{name} is invalid")
    return normalized


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return _utc(value, "timestamp").isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strategy_hash(value: object) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError("strategy_hash must be a lowercase sha256 digest")
    return value


def _evidence_ids(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not values:
        raise ValueError("evidence_ids must be a nonempty tuple")
    normalized = tuple(sorted(_text(value, "evidence_id", identifier=True) for value in values))
    if len(set(normalized)) != len(normalized):
        raise ValueError("evidence_ids must be unique")
    return normalized


@dataclass(frozen=True)
class ProductionReferenceDefinition:
    strategy_id: str
    strategy_hash: str
    parameters: ResearchParameterSet
    evidence_ids: tuple[str, ...]
    registered_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "strategy_id", _text(self.strategy_id, "strategy_id", identifier=True)
        )
        object.__setattr__(self, "strategy_hash", _strategy_hash(self.strategy_hash))
        if not isinstance(self.parameters, ResearchParameterSet):
            raise ValueError("parameters must be ResearchParameterSet")
        object.__setattr__(self, "evidence_ids", _evidence_ids(self.evidence_ids))
        object.__setattr__(self, "registered_at", _utc(self.registered_at, "registered_at"))


@dataclass(frozen=True)
class PromotionHistoryEntry:
    sequence: int
    from_status: ChallengerStatus | None
    to_status: ChallengerStatus
    occurred_at: datetime
    reason: str
    evidence_ids: tuple[str, ...]
    previous_event_hash: str | None
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")
        if self.sequence == 0:
            if self.from_status is not None or self.previous_event_hash is not None:
                raise ValueError("initial history entry cannot have a predecessor")
        else:
            if not isinstance(self.from_status, ChallengerStatus):
                raise ValueError("transition history requires from_status")
            if not isinstance(self.previous_event_hash, str) or _HASH.fullmatch(
                self.previous_event_hash
            ) is None:
                raise ValueError("transition history requires previous_event_hash")
        if not isinstance(self.to_status, ChallengerStatus):
            raise ValueError("to_status must be ChallengerStatus")
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "evidence_ids", _evidence_ids(self.evidence_ids))
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "evidence_ids": list(self.evidence_ids),
            "from_status": None if self.from_status is None else self.from_status.value,
            "occurred_at": _utc_text(self.occurred_at),
            "previous_event_hash": self.previous_event_hash,
            "reason": self.reason,
            "sequence": self.sequence,
            "to_status": self.to_status.value,
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class StrategyChallengerRecord:
    strategy_id: str
    strategy_hash: str
    parameters: ResearchParameterSet
    evidence_ids: tuple[str, ...]
    status: ChallengerStatus
    promotion_history: tuple[PromotionHistoryEntry, ...]
    revision: int
    previous_record_hash: str | None
    registered_at: datetime
    updated_at: datetime
    hash: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    paper_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "strategy_id", _text(self.strategy_id, "strategy_id", identifier=True)
        )
        object.__setattr__(self, "strategy_hash", _strategy_hash(self.strategy_hash))
        if not isinstance(self.parameters, ResearchParameterSet):
            raise ValueError("parameters must be ResearchParameterSet")
        object.__setattr__(self, "evidence_ids", _evidence_ids(self.evidence_ids))
        if not isinstance(self.status, ChallengerStatus):
            raise ValueError("status must be ChallengerStatus")
        if not isinstance(self.promotion_history, tuple) or not self.promotion_history:
            raise ValueError("promotion_history must be a nonempty tuple")
        if any(not isinstance(item, PromotionHistoryEntry) for item in self.promotion_history):
            raise ValueError("promotion_history contains an invalid entry")
        if [item.sequence for item in self.promotion_history] != list(
            range(len(self.promotion_history))
        ):
            raise ValueError("promotion history sequence is not contiguous")
        initial = self.promotion_history[0]
        if initial.from_status is not None or initial.to_status not in {
            ChallengerStatus.PRODUCTION_REFERENCE,
            ChallengerStatus.RESEARCH,
        }:
            raise ValueError("promotion history has an invalid initial status")
        for previous, current in zip(self.promotion_history, self.promotion_history[1:]):
            if current.previous_event_hash != previous.hash:
                raise ValueError("promotion history hash chain is invalid")
            if current.from_status is not previous.to_status:
                raise ValueError("promotion history status chain is invalid")
            if current.to_status not in _TRANSITIONS[previous.to_status]:
                raise ValueError("promotion history contains an unauthorized transition")
            if current.occurred_at < previous.occurred_at:
                raise ValueError("promotion history timestamps move backward")
        if self.promotion_history[-1].to_status is not self.status:
            raise ValueError("record status differs from promotion history")
        if type(self.revision) is not int or self.revision != len(self.promotion_history) - 1:
            raise ValueError("revision must match promotion history")
        if self.revision == 0:
            if self.previous_record_hash is not None:
                raise ValueError("initial record cannot have previous_record_hash")
        elif not isinstance(self.previous_record_hash, str) or _HASH.fullmatch(
            self.previous_record_hash
        ) is None:
            raise ValueError("revised record requires previous_record_hash")
        registered = _utc(self.registered_at, "registered_at")
        updated = _utc(self.updated_at, "updated_at")
        if updated < registered:
            raise ValueError("updated_at cannot precede registered_at")
        if self.promotion_history[0].occurred_at != registered:
            raise ValueError("initial history timestamp must match registration")
        if self.promotion_history[-1].occurred_at != updated:
            raise ValueError("latest history timestamp must match updated_at")
        history_evidence = tuple(sorted({
            evidence_id
            for event in self.promotion_history
            for evidence_id in event.evidence_ids
        }))
        if history_evidence != self.evidence_ids:
            raise ValueError("record evidence differs from promotion history")
        object.__setattr__(self, "registered_at", registered)
        object.__setattr__(self, "updated_at", updated)
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "evidence_ids": list(self.evidence_ids),
            "parameter_set": self.parameters.canonical_json,
            "parameter_set_sha256": self.parameters.sha256,
            "previous_record_hash": self.previous_record_hash,
            "promotion_history": [item.document() for item in self.promotion_history],
            "registered_at": _utc_text(self.registered_at),
            "revision": self.revision,
            "status": self.status.value,
            "strategy_hash": self.strategy_hash,
            "strategy_id": self.strategy_id,
            "updated_at": _utc_text(self.updated_at),
        }
        if include_hash:
            document["hash"] = self.hash
        return document


@dataclass(frozen=True)
class ChallengerRegistrationResult:
    record: StrategyChallengerRecord
    inserted: bool
    duplicate: bool

    def __post_init__(self) -> None:
        if self.inserted == self.duplicate:
            raise ValueError("registration must be inserted or duplicate")


def _initial_record(
    *,
    strategy_id: str,
    strategy_hash: str,
    parameters: ResearchParameterSet,
    evidence_ids: tuple[str, ...],
    status: ChallengerStatus,
    registered_at: datetime,
    reason: str,
) -> StrategyChallengerRecord:
    event = PromotionHistoryEntry(
        sequence=0,
        from_status=None,
        to_status=status,
        occurred_at=registered_at,
        reason=reason,
        evidence_ids=evidence_ids,
        previous_event_hash=None,
    )
    return StrategyChallengerRecord(
        strategy_id=strategy_id,
        strategy_hash=strategy_hash,
        parameters=parameters,
        evidence_ids=evidence_ids,
        status=status,
        promotion_history=(event,),
        revision=0,
        previous_record_hash=None,
        registered_at=registered_at,
        updated_at=registered_at,
    )


class StrategyChallengerRegistry:
    """Append-only registry whose production reference has no mutation API."""

    execution_authorized = False
    paper_execution_authorized = False
    live_execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, production_reference: ProductionReferenceDefinition):
        if not isinstance(production_reference, ProductionReferenceDefinition):
            raise ValueError("production_reference must be ProductionReferenceDefinition")
        production = _initial_record(
            strategy_id=production_reference.strategy_id,
            strategy_hash=production_reference.strategy_hash,
            parameters=production_reference.parameters,
            evidence_ids=production_reference.evidence_ids,
            status=ChallengerStatus.PRODUCTION_REFERENCE,
            registered_at=production_reference.registered_at,
            reason="PRODUCTION_REFERENCE_IMPORTED_READ_ONLY",
        )
        self._production_id = production.strategy_id
        self._records: dict[str, StrategyChallengerRecord] = {
            production.strategy_id: production
        }
        self._revisions: dict[str, tuple[StrategyChallengerRecord, ...]] = {
            production.strategy_id: (production,)
        }
        self._lock = RLock()

    def production_reference(self) -> StrategyChallengerRecord:
        with self._lock:
            return self._records[self._production_id]

    def register_research(
        self,
        *,
        strategy_id: str,
        strategy_hash: str,
        parameters: ResearchParameterSet,
        evidence_ids: tuple[str, ...],
        registered_at: datetime,
        reason: str,
    ) -> ChallengerRegistrationResult:
        candidate = _initial_record(
            strategy_id=strategy_id,
            strategy_hash=strategy_hash,
            parameters=parameters,
            evidence_ids=evidence_ids,
            status=ChallengerStatus.RESEARCH,
            registered_at=registered_at,
            reason=reason,
        )
        with self._lock:
            existing = self._records.get(candidate.strategy_id)
            if existing is not None:
                if existing.status is ChallengerStatus.PRODUCTION_REFERENCE:
                    raise ChallengerConflictError(
                        "research cannot overwrite the production reference"
                    )
                if existing.hash == candidate.hash:
                    return ChallengerRegistrationResult(existing, False, True)
                raise ChallengerConflictError(
                    "strategy ID already identifies different immutable research evidence"
                )
            self._records[candidate.strategy_id] = candidate
            self._revisions[candidate.strategy_id] = (candidate,)
            return ChallengerRegistrationResult(candidate, True, False)

    def transition(
        self,
        strategy_id: str,
        to_status: ChallengerStatus,
        *,
        evidence_ids: tuple[str, ...],
        reason: str,
        occurred_at: datetime,
    ) -> StrategyChallengerRecord:
        key = _text(strategy_id, "strategy_id", identifier=True)
        if not isinstance(to_status, ChallengerStatus):
            raise ChallengerTransitionError("to_status must be ChallengerStatus")
        added_evidence = _evidence_ids(evidence_ids)
        changed_at = _utc(occurred_at, "occurred_at")
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise KeyError(key)
            if current.status is ChallengerStatus.PRODUCTION_REFERENCE:
                raise ChallengerTransitionError("production reference is read-only")
            if to_status not in _TRANSITIONS[current.status]:
                raise ChallengerTransitionError(
                    f"transition {current.status.value}->{to_status.value} is not allowed"
                )
            if changed_at < current.updated_at:
                raise ChallengerTransitionError("promotion timestamp cannot move backward")
            event = PromotionHistoryEntry(
                sequence=current.revision + 1,
                from_status=current.status,
                to_status=to_status,
                occurred_at=changed_at,
                reason=reason,
                evidence_ids=added_evidence,
                previous_event_hash=current.promotion_history[-1].hash,
            )
            combined_evidence = tuple(sorted(set(current.evidence_ids + added_evidence)))
            updated = StrategyChallengerRecord(
                strategy_id=current.strategy_id,
                strategy_hash=current.strategy_hash,
                parameters=current.parameters,
                evidence_ids=combined_evidence,
                status=to_status,
                promotion_history=current.promotion_history + (event,),
                revision=current.revision + 1,
                previous_record_hash=current.hash,
                registered_at=current.registered_at,
                updated_at=changed_at,
            )
            self._records[key] = updated
            self._revisions[key] = self._revisions[key] + (updated,)
            return updated

    def get(self, strategy_id: str) -> StrategyChallengerRecord | None:
        key = _text(strategy_id, "strategy_id", identifier=True)
        with self._lock:
            return self._records.get(key)

    def history(self, strategy_id: str) -> tuple[StrategyChallengerRecord, ...]:
        key = _text(strategy_id, "strategy_id", identifier=True)
        with self._lock:
            return self._revisions.get(key, ())

    def list(self, *, status: ChallengerStatus | None = None) -> tuple[StrategyChallengerRecord, ...]:
        if status is not None and not isinstance(status, ChallengerStatus):
            raise ValueError("status must be ChallengerStatus or None")
        with self._lock:
            records = tuple(self._records.values())
        return tuple(sorted(
            (record for record in records if status is None or record.status is status),
            key=lambda record: record.strategy_id,
        ))
