"""Fail-closed safety gates for MEDAR coding work."""

from dataclasses import dataclass

from backend.medar.coding_task import CodingTask


@dataclass(frozen=True)
class CodingSafetyEvidence:
    files_changed: tuple[str, ...]
    diff_reviewed: bool
    tests_passed: bool
    force_push_requested: bool = False
    destructive_reset_requested: bool = False
    ambiguity_present: bool = False


@dataclass(frozen=True)
class CodingSafetyDecision:
    accepted: bool
    blocking_reasons: tuple[str, ...]


def evaluate_coding_safety(
    task: CodingTask,
    evidence: CodingSafetyEvidence,
) -> CodingSafetyDecision:
    reasons: list[str] = []
    if not evidence.diff_reviewed:
        reasons.append("DIFF_REVIEW_REQUIRED")
    if not evidence.tests_passed:
        reasons.append("TESTS_NOT_PASSED")
    if evidence.force_push_requested:
        reasons.append("FORCE_PUSH_FORBIDDEN")
    if evidence.destructive_reset_requested:
        reasons.append("DESTRUCTIVE_RESET_FORBIDDEN")
    outside_scope = sorted(set(evidence.files_changed) - set(task.allowed_files))
    if outside_scope:
        reasons.append("OUTSIDE_FILE_SCOPE:" + ",".join(outside_scope))
    if evidence.ambiguity_present:
        reasons.append("AMBIGUITY_REQUIRES_STOP")
    return CodingSafetyDecision(not reasons, tuple(reasons))
