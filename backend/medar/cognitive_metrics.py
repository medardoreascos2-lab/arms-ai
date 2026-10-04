"""Aggregate, content-free metrics for the MEDAR cognitive runtime."""

from collections import Counter
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class CognitiveMetricsSnapshot:
    requests: int
    domain_routing: Mapping[str, int]
    tool_successes: int
    tool_attempts: int
    agent_failures: int
    replan_count: int
    memory_retrieval_hits: int
    memory_retrieval_queries: int
    uncertainty: Mapping[str, int]
    average_latency_ms: float

    @property
    def tool_success_rate(self) -> float:
        return self.tool_successes / self.tool_attempts if self.tool_attempts else 0.0

    @property
    def memory_retrieval_hit_rate(self) -> float:
        return (
            self.memory_retrieval_hits / self.memory_retrieval_queries
            if self.memory_retrieval_queries else 0.0
        )


class CognitiveMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = 0
        self._domains: Counter[str] = Counter()
        self._tool_successes = 0
        self._tool_attempts = 0
        self._agent_failures = 0
        self._replans = 0
        self._memory_hits = 0
        self._memory_queries = 0
        self._uncertainty: Counter[str] = Counter()
        self._latency_total = 0.0

    def record_request(
        self,
        *,
        domains: tuple[str, ...],
        tool_successes: int = 0,
        tool_attempts: int = 0,
        agent_failures: int = 0,
        replans: int = 0,
        memory_hit: bool | None = None,
        uncertainty: str,
        latency_ms: float,
    ) -> None:
        values = (tool_successes, tool_attempts, agent_failures, replans)
        if any(value < 0 for value in values) or tool_successes > tool_attempts or latency_ms < 0:
            raise ValueError("metric values are invalid")
        with self._lock:
            self._requests += 1
            self._domains.update(domains)
            self._tool_successes += tool_successes
            self._tool_attempts += tool_attempts
            self._agent_failures += agent_failures
            self._replans += replans
            if memory_hit is not None:
                self._memory_queries += 1
                self._memory_hits += int(memory_hit)
            self._uncertainty[uncertainty] += 1
            self._latency_total += latency_ms

    def snapshot(self) -> CognitiveMetricsSnapshot:
        with self._lock:
            average = self._latency_total / self._requests if self._requests else 0.0
            return CognitiveMetricsSnapshot(
                self._requests, MappingProxyType(dict(self._domains)), self._tool_successes,
                self._tool_attempts, self._agent_failures, self._replans, self._memory_hits,
                self._memory_queries, MappingProxyType(dict(self._uncertainty)), average,
            )
