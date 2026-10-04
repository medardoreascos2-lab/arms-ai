"""Evidence-based MEDAR memory importance assessment, without persistence."""

from dataclasses import dataclass, replace

from backend.medar.memory_candidates import CandidateImportance, MemoryCandidate


@dataclass(frozen=True)
class ImportanceEvidence:
    explicit_user_preference: bool = False
    long_term_goal: bool = False
    technical_solution: bool = False
    decision: bool = False
    observed_outcome: bool = False
    stable_context: bool = False
    verified_critical_safety_rule: bool = False
    repeated_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "explicit_user_preference", "long_term_goal", "technical_solution",
            "decision", "observed_outcome", "stable_context",
            "verified_critical_safety_rule",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        if not isinstance(self.repeated_source_ids, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.repeated_source_ids
        ) or len(set(self.repeated_source_ids)) != len(self.repeated_source_ids):
            raise ValueError("repeated source IDs must be distinct non-empty strings")


@dataclass(frozen=True)
class ImportanceAssessment:
    importance: CandidateImportance
    reason_codes: tuple[str, ...]
    persistence_authorized: bool = False

    def __post_init__(self) -> None:
        if self.persistence_authorized:
            raise ValueError("importance cannot authorize persistence")


def score_memory_importance(candidate: MemoryCandidate, evidence: ImportanceEvidence) -> ImportanceAssessment:
    reasons: list[str] = []
    if evidence.verified_critical_safety_rule:
        return ImportanceAssessment(CandidateImportance.CRITICAL, ("VERIFIED_CRITICAL_SAFETY_RULE",))
    if evidence.explicit_user_preference or candidate.reason_to_remember == "EXPLICIT_USER_PREFERENCE":
        reasons.append("EXPLICIT_USER_PREFERENCE")
    if evidence.long_term_goal:
        reasons.append("LONG_TERM_GOAL")
    if evidence.technical_solution:
        reasons.append("TECHNICAL_SOLUTION")
    if evidence.decision or candidate.reason_to_remember == "LABELED_DECISION":
        reasons.append("DECISION")
    if evidence.observed_outcome or candidate.reason_to_remember == "LABELED_TASK_OUTCOME":
        reasons.append("OBSERVED_OUTCOME")
    if evidence.stable_context:
        reasons.append("STABLE_CONTEXT")
    if len(evidence.repeated_source_ids) >= 2:
        reasons.append("REPEATED_PATTERN")
    if "REPEATED_PATTERN" in reasons or "LONG_TERM_GOAL" in reasons or (
        "TECHNICAL_SOLUTION" in reasons and "OBSERVED_OUTCOME" in reasons
    ):
        return ImportanceAssessment(CandidateImportance.HIGH, tuple(reasons))
    if reasons or candidate.reason_to_remember in {
        "EXPLICIT_REMEMBER_REQUEST", "LABELED_TASK_LESSON", "LABELED_TASK_OUTCOME", "LABELED_DECISION",
    }:
        return ImportanceAssessment(CandidateImportance.MEDIUM, tuple(reasons) or (candidate.reason_to_remember,))
    return ImportanceAssessment(CandidateImportance.LOW, ("NO_HIGH_IMPORTANCE_EVIDENCE",))


def apply_importance(candidate: MemoryCandidate, assessment: ImportanceAssessment) -> MemoryCandidate:
    return replace(candidate, importance=assessment.importance)
