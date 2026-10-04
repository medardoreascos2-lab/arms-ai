"""R91B MEDAR coding safety gate tests."""

from backend.medar.coding_safety import CodingSafetyEvidence, evaluate_coding_safety
from backend.medar.coding_task import CodingTask, CommitPolicy
from backend.medar.request import RiskClass


def _task():
    return CodingTask(
        "task", "repo", "goal", ("src/a.py",), ("tests/test_a.py",),
        RiskClass.MODERATE, CommitPolicy.NO_COMMIT,
    )


def test_coding_safety_accepts_reviewed_tested_in_scope_change():
    result = evaluate_coding_safety(_task(), CodingSafetyEvidence(("src/a.py",), True, True))
    assert result.accepted is True
    assert result.blocking_reasons == ()


def test_each_unsafe_condition_blocks_with_no_side_effect():
    result = evaluate_coding_safety(
        _task(),
        CodingSafetyEvidence(
            ("outside.py",), False, False, force_push_requested=True,
            destructive_reset_requested=True, ambiguity_present=True,
        ),
    )
    assert result.accepted is False
    assert set(result.blocking_reasons) == {
        "DIFF_REVIEW_REQUIRED", "TESTS_NOT_PASSED", "FORCE_PUSH_FORBIDDEN",
        "DESTRUCTIVE_RESET_FORBIDDEN", "OUTSIDE_FILE_SCOPE:outside.py",
        "AMBIGUITY_REQUIRES_STOP",
    }
