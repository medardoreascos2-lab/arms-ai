"""R91A MEDAR coding task model tests."""

import pytest

from backend.medar.coding_task import CodingTask, CommitPolicy
from backend.medar.request import RiskClass


def test_coding_task_captures_repository_scope_tests_risk_and_commit_policy():
    task = CodingTask(
        "task-1", "C:/repo", "Fix bug", ("src/app.py",), ("tests/test_app.py",),
        RiskClass.MODERATE, CommitPolicy.REQUIRE_EXPLICIT_AUTHORIZATION,
    )
    assert task.allowed_files == ("src/app.py",)
    assert task.required_tests == ("tests/test_app.py",)
    assert task.commit_policy is CommitPolicy.REQUIRE_EXPLICIT_AUTHORIZATION


def test_missing_file_scope_or_tests_fails_closed():
    with pytest.raises(ValueError, match="allowed files"):
        CodingTask("task", "repo", "goal", (), ("test",), RiskClass.LOW, CommitPolicy.NO_COMMIT)
    with pytest.raises(ValueError, match="tests"):
        CodingTask("task", "repo", "goal", ("file",), (), RiskClass.LOW, CommitPolicy.NO_COMMIT)
