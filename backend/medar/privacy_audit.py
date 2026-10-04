"""Deterministic privacy and authority audit for MEDAR runtime metadata."""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from backend.medar.agent_contract import SpecializedAgent
from backend.medar.memory_read import MemoryQuery
from backend.medar.tool_contract import CognitiveTool


_SENSITIVE_KEYS = frozenset({
    "password", "secret", "token", "api_key", "credential", "private_key",
    "raw_input", "email", "phone", "ssn",
})


@dataclass(frozen=True)
class PrivacyAuditResult:
    passed: bool
    findings: tuple[str, ...]


def _find_sensitive_keys(value: Any, path: str = "root") -> tuple[str, ...]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            child_path = f"{path}.{key}"
            if normalized in _SENSITIVE_KEYS:
                findings.append(f"SENSITIVE_TRACE_FIELD:{child_path}")
            findings.extend(_find_sensitive_keys(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            findings.extend(_find_sensitive_keys(child, f"{path}[{index}]"))
    return tuple(findings)


def audit_cognitive_privacy(
    *,
    agents: tuple[SpecializedAgent, ...],
    tools: tuple[CognitiveTool, ...],
    memory_query: MemoryQuery | None,
    trace_payload: Mapping[str, Any],
) -> PrivacyAuditResult:
    findings = list(_find_sensitive_keys(trace_payload))
    if any(agent.contract.real_world_action_authority for agent in agents):
        findings.append("AGENT_AUTHORITY_LEAK")
    if any(tool.contract.execution_authority for tool in tools):
        findings.append("TOOL_AUTHORITY_LEAK")
    if memory_query is not None and (not memory_query.tenant_id or not memory_query.user_id):
        findings.append("MEMORY_SCOPE_MISSING")
    return PrivacyAuditResult(not findings, tuple(sorted(set(findings))))
