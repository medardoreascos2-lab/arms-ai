"""Immutable strategy experiment identity and research-only lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re

from .backtest_runner import ResearchParameterSet


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


class ExperimentTransitionError(RuntimeError):
    """The requested research lifecycle transition is not authorized."""


class StrategyExperimentStatus(str, Enum):
    RESEARCH = "RESEARCH"
    BACKTESTED = "BACKTESTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    PAPER_CHALLENGER = "PAPER_CHALLENGER"
    REJECTED = "REJECTED"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"


_TRANSITIONS: dict[StrategyExperimentStatus, frozenset[StrategyExperimentStatus]] = {
    StrategyExperimentStatus.RESEARCH: frozenset({
        StrategyExperimentStatus.BACKTESTED,
        StrategyExperimentStatus.REJECTED,
    }),
    StrategyExperimentStatus.BACKTESTED: frozenset({
        StrategyExperimentStatus.VALIDATION_FAILED,
        StrategyExperimentStatus.VALIDATION_PASSED,
        StrategyExperimentStatus.REJECTED,
    }),
    StrategyExperimentStatus.VALIDATION_FAILED: frozenset(),
    StrategyExperimentStatus.VALIDATION_PASSED: frozenset({
        StrategyExperimentStatus.PAPER_CHALLENGER,
        StrategyExperimentStatus.PROMOTION_CANDIDATE,
        StrategyExperimentStatus.REJECTED,
    }),
    StrategyExperimentStatus.PAPER_CHALLENGER: frozenset({
        StrategyExperimentStatus.PROMOTION_CANDIDATE,
        StrategyExperimentStatus.REJECTED,
    }),
    StrategyExperimentStatus.PROMOTION_CANDIDATE: frozenset({
        StrategyExperimentStatus.REJECTED,
    }),
    StrategyExperimentStatus.REJECTED: frozenset(),
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


def _hash(document: dict[str, object]) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ExperimentWindow:
    starts_at: datetime
    ends_at: datetime

    def __post_init__(self) -> None:
        start = _utc(self.starts_at, "starts_at")
        end = _utc(self.ends_at, "ends_at")
        if start >= end:
            raise ValueError("experiment window start must precede end")
        object.__setattr__(self, "starts_at", start)
        object.__setattr__(self, "ends_at", end)

    def document(self) -> dict[str, str]:
        return {
            "ends_at": _utc_text(self.ends_at),
            "starts_at": _utc_text(self.starts_at),
        }


@dataclass(frozen=True)
class StrategyExperiment:
    experiment_id: str
    parent_production_version: str
    candidate_parameters: ResearchParameterSet
    dataset_ids: tuple[str, ...]
    train_window: ExperimentWindow
    validation_window: ExperimentWindow
    test_window: ExperimentWindow
    creation_reason: str
    created_at: datetime
    status: StrategyExperimentStatus
    status_reason: str
    status_updated_at: datetime
    revision: int
    previous_hash: str | None
    hash: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    paper_execution_authorized: bool = field(default=False, init=False)
    live_execution_authorized: bool = field(default=False, init=False)
    production_assignment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "experiment_id", _text(self.experiment_id, "experiment_id", identifier=True)
        )
        object.__setattr__(
            self,
            "parent_production_version",
            _text(
                self.parent_production_version,
                "parent_production_version",
                identifier=True,
            ),
        )
        if not isinstance(self.candidate_parameters, ResearchParameterSet):
            raise ValueError("candidate_parameters must be ResearchParameterSet")
        if not isinstance(self.dataset_ids, tuple) or not self.dataset_ids:
            raise ValueError("dataset_ids must be a nonempty tuple")
        normalized_ids = tuple(
            sorted(_text(value, "dataset_id", identifier=True) for value in self.dataset_ids)
        )
        if len(set(normalized_ids)) != len(normalized_ids):
            raise ValueError("dataset_ids must be unique")
        object.__setattr__(self, "dataset_ids", normalized_ids)
        for name in ("train_window", "validation_window", "test_window"):
            if not isinstance(getattr(self, name), ExperimentWindow):
                raise ValueError(f"{name} must be ExperimentWindow")
        if self.train_window.ends_at > self.validation_window.starts_at:
            raise ValueError("train and validation windows must not overlap")
        if self.validation_window.ends_at > self.test_window.starts_at:
            raise ValueError("validation and test windows must not overlap")
        object.__setattr__(
            self, "creation_reason", _text(self.creation_reason, "creation_reason")
        )
        created = _utc(self.created_at, "created_at")
        updated = _utc(self.status_updated_at, "status_updated_at")
        if updated < created:
            raise ValueError("status_updated_at cannot precede created_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "status_updated_at", updated)
        if not isinstance(self.status, StrategyExperimentStatus):
            raise ValueError("status must be a research StrategyExperimentStatus")
        object.__setattr__(self, "status_reason", _text(self.status_reason, "status_reason"))
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a nonnegative integer")
        if self.revision == 0:
            if self.status is not StrategyExperimentStatus.RESEARCH:
                raise ValueError("a new experiment must begin in RESEARCH")
            if self.previous_hash is not None:
                raise ValueError("a new experiment cannot have previous_hash")
        elif not isinstance(self.previous_hash, str) or _HASH.fullmatch(self.previous_hash) is None:
            raise ValueError("transitioned experiments require previous_hash")
        object.__setattr__(self, "hash", _hash(self.document(include_hash=False)))

    @classmethod
    def create(
        cls,
        *,
        experiment_id: str,
        parent_production_version: str,
        candidate_parameters: ResearchParameterSet,
        dataset_ids: tuple[str, ...],
        train_window: ExperimentWindow,
        validation_window: ExperimentWindow,
        test_window: ExperimentWindow,
        creation_reason: str,
        created_at: datetime,
    ) -> "StrategyExperiment":
        return cls(
            experiment_id=experiment_id,
            parent_production_version=parent_production_version,
            candidate_parameters=candidate_parameters,
            dataset_ids=dataset_ids,
            train_window=train_window,
            validation_window=validation_window,
            test_window=test_window,
            creation_reason=creation_reason,
            created_at=created_at,
            status=StrategyExperimentStatus.RESEARCH,
            status_reason="EXPERIMENT_CREATED",
            status_updated_at=created_at,
            revision=0,
            previous_hash=None,
        )

    def transition(
        self,
        status: StrategyExperimentStatus,
        *,
        reason: str,
        transitioned_at: datetime,
    ) -> "StrategyExperiment":
        if not isinstance(status, StrategyExperimentStatus):
            raise ExperimentTransitionError(
                "research lifecycle accepts only StrategyExperimentStatus values"
            )
        if status not in _TRANSITIONS[self.status]:
            raise ExperimentTransitionError(
                f"transition {self.status.value}->{status.value} is not allowed"
            )
        changed_at = _utc(transitioned_at, "transitioned_at")
        if changed_at < self.status_updated_at:
            raise ExperimentTransitionError("transition timestamp cannot move backward")
        return StrategyExperiment(
            experiment_id=self.experiment_id,
            parent_production_version=self.parent_production_version,
            candidate_parameters=self.candidate_parameters,
            dataset_ids=self.dataset_ids,
            train_window=self.train_window,
            validation_window=self.validation_window,
            test_window=self.test_window,
            creation_reason=self.creation_reason,
            created_at=self.created_at,
            status=status,
            status_reason=_text(reason, "reason"),
            status_updated_at=changed_at,
            revision=self.revision + 1,
            previous_hash=self.hash,
        )

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        document: dict[str, object] = {
            "candidate_parameter_set": self.candidate_parameters.canonical_json,
            "candidate_parameter_set_sha256": self.candidate_parameters.sha256,
            "created_at": _utc_text(self.created_at),
            "creation_reason": self.creation_reason,
            "dataset_ids": list(self.dataset_ids),
            "experiment_id": self.experiment_id,
            "parent_production_version": self.parent_production_version,
            "previous_hash": self.previous_hash,
            "revision": self.revision,
            "status": self.status.value,
            "status_reason": self.status_reason,
            "status_updated_at": _utc_text(self.status_updated_at),
            "test_window": self.test_window.document(),
            "train_window": self.train_window.document(),
            "validation_window": self.validation_window.document(),
        }
        if include_hash:
            document["hash"] = self.hash
        return document
