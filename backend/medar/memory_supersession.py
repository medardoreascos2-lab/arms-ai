"""Evidence gate for atomic durable memory supersession with history."""

import math
from dataclasses import dataclass
from typing import Protocol

from backend.medar.durable_memory_record import (
    DurableMemoryRecord, DurableMemoryType, MemoryLifecycle, ProvenanceClass,
)
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.sqlite_memory_store import MemoryScope


@dataclass(frozen=True)
class VerifiedFactEvidence:
    evidence_references: tuple[str, ...]
    verification_score: float
    independently_verified: bool
    mutation_authority: bool = False

    def __post_init__(self) -> None:
        if not self.evidence_references or len(self.evidence_references) > 20:
            raise ValueError("verified fact requires bounded evidence references")
        if any(
            not isinstance(reference, str) or not reference.startswith("synthetic-test:")
            or len(reference) > 240
            for reference in self.evidence_references
        ):
            raise ValueError("verified fact evidence must be synthetic scoped references")
        if any(has_secret_like_content(reference) for reference in self.evidence_references):
            raise PermissionError("secret-like verification evidence is not retained")
        if (
            isinstance(self.verification_score, bool)
            or not isinstance(self.verification_score, (int, float))
            or not math.isfinite(self.verification_score)
            or not 0 <= self.verification_score <= 1
        ):
            raise ValueError("verification score must be finite and between zero and one")
        if not isinstance(self.independently_verified, bool):
            raise TypeError("independent verification flag must be boolean")
        if self.mutation_authority:
            raise ValueError("evidence cannot grant mutation authority")


@dataclass(frozen=True)
class MemorySupersessionReceipt:
    superseded_memory_id: str
    superseded_version: int
    replacement_memory_id: str
    replacement_version: int
    history_preserved: bool = True
    deletion_performed: bool = False

    def __post_init__(self) -> None:
        if not self.history_preserved or self.deletion_performed:
            raise ValueError("supersession must preserve history without deletion")


class AtomicSupersessionStore(Protocol):
    def supersede_with(
        self, scope: MemoryScope, memory_id: str,
        replacement: DurableMemoryRecord,
    ) -> tuple[DurableMemoryRecord, DurableMemoryRecord]: ...


def supersede_with_verified_fact(
    store: AtomicSupersessionStore,
    scope: MemoryScope,
    current_memory_id: str,
    replacement: DurableMemoryRecord,
    evidence: VerifiedFactEvidence,
) -> MemorySupersessionReceipt:
    if not isinstance(scope, MemoryScope) or not isinstance(replacement, DurableMemoryRecord):
        raise TypeError("scope and replacement memory are required")
    if replacement.tenant_id != scope.tenant_id or replacement.owner_id != scope.owner_id:
        raise PermissionError("replacement fact scope mismatch")
    if not isinstance(current_memory_id, str) or not current_memory_id.strip():
        raise ValueError("current memory ID is required")
    if not isinstance(evidence, VerifiedFactEvidence):
        raise TypeError("verified fact evidence is required")
    if not evidence.independently_verified or evidence.verification_score < 0.8:
        raise PermissionError("fact supersession requires strong independent verification")
    if replacement.memory_type is not DurableMemoryType.FACT or replacement.status is not MemoryLifecycle.ACTIVE:
        raise PermissionError("only an active verified fact may replace durable fact memory")
    if replacement.provenance_class not in (
        ProvenanceClass.DIRECT_OBSERVATION,
        ProvenanceClass.TOOL_RESULT,
        ProvenanceClass.SOURCE_DOCUMENT,
    ):
        raise PermissionError("replacement fact provenance is not independently verifiable")
    if replacement.source_reference not in evidence.evidence_references:
        raise PermissionError("replacement source is not cited by verification evidence")
    if replacement.confidence < evidence.verification_score:
        raise PermissionError("replacement confidence is below verification evidence")
    superseded, stored = store.supersede_with(scope, current_memory_id, replacement)
    if superseded.status is not MemoryLifecycle.SUPERSEDED or stored.status is not MemoryLifecycle.ACTIVE:
        raise RuntimeError("memory store returned invalid supersession state")
    return MemorySupersessionReceipt(
        superseded.memory_id, superseded.version,
        stored.memory_id, stored.version,
    )
