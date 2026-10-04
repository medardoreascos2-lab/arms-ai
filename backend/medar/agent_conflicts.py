"""Explicit MEDAR agent disagreement preservation and assessment."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.agent_contract import AgentOutput


class ConflictStatus(str, Enum):
    CONSENSUS = "CONSENSUS"
    DISAGREEMENT = "DISAGREEMENT"
    INSUFFICIENT_OUTPUTS = "INSUFFICIENT_OUTPUTS"


@dataclass(frozen=True)
class ConflictAssessment:
    status: ConflictStatus
    outputs: tuple[AgentOutput, ...]
    shared_evidence: tuple[str, ...]
    differing_summaries: tuple[str, ...]
    uncertainty_reported: bool
    selected_output: AgentOutput | None = None


def assess_agent_conflict(outputs: tuple[AgentOutput, ...]) -> ConflictAssessment:
    if len(outputs) < 2:
        return ConflictAssessment(
            ConflictStatus.INSUFFICIENT_OUTPUTS,
            outputs,
            (),
            tuple(item.summary for item in outputs),
            True,
        )
    task_ids = {item.task_id for item in outputs}
    if len(task_ids) != 1:
        raise ValueError("conflict comparison requires one task")
    evidence_sets = [set(item.evidence) for item in outputs]
    shared = tuple(sorted(set.intersection(*evidence_sets))) if evidence_sets else ()
    summaries = tuple(dict.fromkeys(item.summary.strip() for item in outputs))
    if len(summaries) == 1:
        return ConflictAssessment(
            ConflictStatus.CONSENSUS,
            outputs,
            shared,
            summaries,
            False,
            selected_output=outputs[0],
        )
    return ConflictAssessment(
        ConflictStatus.DISAGREEMENT,
        outputs,
        shared,
        summaries,
        True,
        selected_output=None,
    )
