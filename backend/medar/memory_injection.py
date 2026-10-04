"""Fail-closed screening of durable memory before model prompt construction."""

import re
from dataclasses import dataclass

from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.memory_evidence_references import CitedMemoryContext


_INJECTION_PATTERNS = (
    ("INSTRUCTION_OVERRIDE", re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|system|developer)\s+(?:instructions?|messages?)\b", re.I)),
    ("SYSTEM_PROMPT_IMPERSONATION", re.compile(r"(?:<\|\s*system\s*\|>|\[\s*system\s*\]|\bsystem\s+prompt\b|\bdeveloper\s+message\b)", re.I)),
    ("TOOL_OR_COMMAND_INJECTION", re.compile(r"\b(?:call|invoke|run|execute)\s+(?:a\s+)?(?:tool|command|shell|order|trade)\b", re.I)),
    ("AUTHORITY_ESCALATION_INJECTION", re.compile(r"\b(?:enable|grant|assume|bypass)\s+(?:broker|paper|live|execution|admin)\s+(?:authority|trading|mode|access)?\b", re.I)),
)


@dataclass(frozen=True)
class MemoryPromptSafetyDecision:
    accepted: bool
    finding_codes: tuple[str, ...]
    memories_examined: int
    prompt_construction_authorized: bool

    def __post_init__(self) -> None:
        if self.accepted != (not self.finding_codes):
            raise ValueError("memory prompt safety state is inconsistent")
        if self.prompt_construction_authorized != self.accepted:
            raise ValueError("unsafe memory cannot authorize prompt construction")
        if self.memories_examined < 0:
            raise ValueError("memories_examined cannot be negative")


def assess_memory_prompt_safety(context: CitedMemoryContext) -> MemoryPromptSafetyDecision:
    if not isinstance(context, CitedMemoryContext):
        raise TypeError("cited memory context is required")
    findings: set[str] = set()
    for item in context.items:
        if has_secret_like_content(item.content):
            findings.add("SECRET_LIKE_MEMORY")
        for code, pattern in _INJECTION_PATTERNS:
            if pattern.search(item.content):
                findings.add(code)
    ordered = tuple(sorted(findings))
    return MemoryPromptSafetyDecision(not ordered, ordered, len(context.items), not ordered)


def require_memory_prompt_safety(context: CitedMemoryContext) -> None:
    decision = assess_memory_prompt_safety(context)
    if not decision.accepted:
        raise PermissionError("memory prompt safety blocked: " + ",".join(decision.finding_codes))
