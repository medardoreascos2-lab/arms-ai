"""Bounded coding task contract for MEDAR planning."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.request import RiskClass


class CommitPolicy(str, Enum):
    NO_COMMIT = "NO_COMMIT"
    REQUIRE_EXPLICIT_AUTHORIZATION = "REQUIRE_EXPLICIT_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"


@dataclass(frozen=True)
class CodingTask:
    task_id: str
    repository: str
    goal: str
    allowed_files: tuple[str, ...]
    required_tests: tuple[str, ...]
    risk: RiskClass
    commit_policy: CommitPolicy

    def __post_init__(self) -> None:
        for name in ("task_id", "repository", "goal"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not self.allowed_files:
            raise ValueError("coding task requires explicit allowed files")
        if any(not item.strip() for item in self.allowed_files):
            raise ValueError("allowed files must be non-empty")
        if not self.required_tests:
            raise ValueError("coding task requires tests")
        if not isinstance(self.risk, RiskClass):
            raise TypeError("risk must be RiskClass")
        if not isinstance(self.commit_policy, CommitPolicy):
            raise TypeError("commit policy must be explicit")
