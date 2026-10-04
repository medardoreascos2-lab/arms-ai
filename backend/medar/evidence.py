"""Lossless evidence aggregation for MEDAR response synthesis."""

from dataclasses import dataclass

from backend.medar.agent_contract import AgentOutput
from backend.medar.memory_read import MemoryReadResult
from backend.medar.response import SourceReference
from backend.medar.tool_contract import ToolResult, ToolResultStatus


@dataclass(frozen=True)
class EvidenceBundle:
    agent_outputs: tuple[AgentOutput, ...]
    tool_results: tuple[ToolResult, ...]
    memory_results: tuple[MemoryReadResult, ...]
    sources: tuple[SourceReference, ...]
    warnings: tuple[str, ...]
    usable_evidence_count: int

    @property
    def is_sufficient(self) -> bool:
        return self.usable_evidence_count > 0


def aggregate_evidence(
    *,
    agent_outputs: tuple[AgentOutput, ...] = (),
    tool_results: tuple[ToolResult, ...] = (),
    memory_results: tuple[MemoryReadResult, ...] = (),
    sources: tuple[SourceReference, ...] = (),
    warnings: tuple[str, ...] = (),
) -> EvidenceBundle:
    derived_warnings = list(warnings)
    for output in agent_outputs:
        derived_warnings.extend(output.warnings)
    for result in tool_results:
        if result.status is not ToolResultStatus.SUCCESS:
            derived_warnings.append(
                f"tool {result.tool_id} returned {result.status.value.lower()}"
            )
    usable = (
        sum(bool(output.evidence) for output in agent_outputs)
        + sum(result.status is ToolResultStatus.SUCCESS and bool(result.output) for result in tool_results)
        + len(memory_results)
        + len(sources)
    )
    return EvidenceBundle(
        agent_outputs,
        tool_results,
        memory_results,
        sources,
        tuple(dict.fromkeys(derived_warnings)),
        usable,
    )
