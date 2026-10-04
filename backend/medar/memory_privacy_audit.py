"""Content-free Phase 8 privacy audit for durable memory and runtime results."""

from dataclasses import dataclass

from backend.medar.durable_memory_record import DurableMemoryRecord, DurableSensitivity, content_digest
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.model_memory_runtime import ModelMemoryRuntimeResult
from backend.medar.sqlite_memory_store import MemoryScope


@dataclass(frozen=True)
class MemoryPrivacyAuditResult:
    passed: bool
    findings: tuple[str, ...]
    records_examined: int
    runtime_examined: bool

    def __post_init__(self) -> None:
        if self.passed is bool(self.findings):
            raise ValueError("privacy audit pass state must match findings")
        if self.records_examined < 0:
            raise ValueError("records_examined cannot be negative")


def audit_memory_privacy(
    records: tuple[DurableMemoryRecord, ...],
    expected_scope: MemoryScope,
    *,
    runtime_result: ModelMemoryRuntimeResult | None = None,
) -> MemoryPrivacyAuditResult:
    if not isinstance(records, tuple) or any(not isinstance(record, DurableMemoryRecord) for record in records):
        raise TypeError("privacy audit records must be typed")
    if not isinstance(expected_scope, MemoryScope):
        raise TypeError("privacy audit scope must be typed")
    if runtime_result is not None and not isinstance(runtime_result, ModelMemoryRuntimeResult):
        raise TypeError("runtime result must be typed")
    findings: set[str] = set()
    seen: set[tuple[str, int]] = set()
    for record in records:
        if (record.tenant_id, record.owner_id) != (expected_scope.tenant_id, expected_scope.owner_id):
            findings.add("CROSS_SCOPE_MEMORY")
        if (record.provenance.tenant_id, record.provenance.user_id) != (record.tenant_id, record.owner_id):
            findings.add("PROVENANCE_SCOPE_MISMATCH")
        if record.content_hash != content_digest(record.content):
            findings.add("CONTENT_HASH_MISMATCH")
        if record.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
            findings.add("SENSITIVE_PLAINTEXT_MEMORY")
        if has_secret_like_content(record.content):
            findings.add("SECRET_LIKE_MEMORY_CONTENT")
        identity = (record.memory_id, record.version)
        if identity in seen:
            findings.add("DUPLICATE_MEMORY_VERSION")
        seen.add(identity)
    if runtime_result is not None:
        if any((
            runtime_result.execution_authorized, runtime_result.broker_authorized,
            runtime_result.paper_authorized, runtime_result.live_authorized,
            runtime_result.persistence_performed, runtime_result.external_call_performed,
        )):
            findings.add("RUNTIME_AUTHORITY_OR_SIDE_EFFECT")
        for item in runtime_result.memory_context.items:
            reference = item.reference
            if (reference.tenant_id, reference.owner_id) != (expected_scope.tenant_id, expected_scope.owner_id):
                findings.add("CROSS_SCOPE_RUNTIME_CITATION")
            if reference.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
                findings.add("SENSITIVE_RUNTIME_CITATION")
    ordered = tuple(sorted(findings))
    return MemoryPrivacyAuditResult(not ordered, ordered, len(records), runtime_result is not None)
