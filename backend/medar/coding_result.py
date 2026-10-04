"""Auditable result contract for bounded MEDAR coding tasks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CodingTestResult:
    command: str
    passed: bool
    summary: str


@dataclass(frozen=True)
class CodingResult:
    task_id: str
    files_changed: tuple[str, ...]
    tests: tuple[CodingTestResult, ...]
    diff_summary: str
    commit: str | None
    remaining_issues: tuple[str, ...]
    diff_reviewed: bool

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.diff_summary.strip():
            raise ValueError("task identity and diff summary are required")
        if not self.diff_reviewed:
            raise ValueError("coding result requires reviewed diff")
        if not self.tests:
            raise ValueError("coding result requires test evidence")
        if self.commit is not None and not self.commit.strip():
            raise ValueError("commit must be a non-empty identifier when present")

    @property
    def tests_passed(self) -> bool:
        return all(test.passed for test in self.tests)
