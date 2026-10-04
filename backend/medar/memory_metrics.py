"""Thread-safe, content-free metrics for one scoped MEDAR memory runtime."""

from collections import Counter
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Mapping

from backend.medar.durable_memory_record import DurableMemoryRecord
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.sqlite_memory_store import MemoryScope


@dataclass(frozen=True)
class MemoryMetricsSnapshot:
    tenant_id: str
    owner_id: str
    records_observed: int
    records_by_domain: Mapping[str, int]
    records_by_status: Mapping[str, int]
    records_by_sensitivity: Mapping[str, int]
    retrieval_queries: int
    retrieval_hits: int
    stale_records_skipped: int
    blocked_queries: int
    backup_successes: int
    restore_successes: int
    authority_granted: bool = False

    def __post_init__(self) -> None:
        if self.authority_granted:
            raise ValueError("memory metrics cannot grant authority")

    @property
    def retrieval_hit_rate(self) -> float:
        return self.retrieval_hits / self.retrieval_queries if self.retrieval_queries else 0.0


class MemoryMetrics:
    def __init__(self, scope: MemoryScope) -> None:
        if not isinstance(scope, MemoryScope):
            raise TypeError("memory metrics require a typed scope")
        if has_secret_like_content(scope.tenant_id) or has_secret_like_content(scope.owner_id):
            raise PermissionError("secret-like metric scope is rejected")
        self._scope = scope
        self._lock = Lock()
        self._records = 0
        self._domains: Counter[str] = Counter()
        self._statuses: Counter[str] = Counter()
        self._sensitivities: Counter[str] = Counter()
        self._queries = self._hits = self._stale = self._blocked = 0
        self._backups = self._restores = 0

    def observe_record(self, record: DurableMemoryRecord) -> None:
        if not isinstance(record, DurableMemoryRecord):
            raise TypeError("typed durable memory record is required")
        if (record.tenant_id, record.owner_id) != (self._scope.tenant_id, self._scope.owner_id):
            raise PermissionError("memory metric scope mismatch")
        with self._lock:
            self._records += 1
            self._domains[record.domain.value] += 1
            self._statuses[record.status.value] += 1
            self._sensitivities[record.sensitivity.value] += 1

    def record_retrieval(self, *, hits: int, stale_skipped: int = 0, blocked: bool = False) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (hits, stale_skipped)):
            raise ValueError("memory retrieval metrics must be nonnegative integers")
        if not isinstance(blocked, bool):
            raise TypeError("blocked must be boolean")
        if blocked and hits:
            raise ValueError("blocked retrieval cannot report hits")
        with self._lock:
            self._queries += 1
            self._hits += hits
            self._stale += stale_skipped
            self._blocked += int(blocked)

    def record_backup(self, *, restored: bool = False) -> None:
        if not isinstance(restored, bool):
            raise TypeError("restored must be boolean")
        with self._lock:
            if restored:
                self._restores += 1
            else:
                self._backups += 1

    def snapshot(self) -> MemoryMetricsSnapshot:
        with self._lock:
            return MemoryMetricsSnapshot(
                self._scope.tenant_id, self._scope.owner_id, self._records,
                MappingProxyType(dict(self._domains)), MappingProxyType(dict(self._statuses)),
                MappingProxyType(dict(self._sensitivities)), self._queries, self._hits,
                self._stale, self._blocked, self._backups, self._restores,
            )
