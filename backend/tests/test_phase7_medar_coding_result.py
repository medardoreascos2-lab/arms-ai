"""R91C MEDAR coding result contract tests."""

import pytest

from backend.medar.coding_result import CodingResult, CodingTestResult


def test_coding_result_reports_every_required_completion_field():
    test = CodingTestResult("pytest tests/test_a.py", True, "1 passed")
    result = CodingResult(
        "task", ("src/a.py",), (test,), "Added validation", "abc123",
        ("external integration remains",), True,
    )
    assert result.files_changed == ("src/a.py",)
    assert result.tests_passed is True
    assert result.diff_summary == "Added validation"
    assert result.commit == "abc123"
    assert result.remaining_issues == ("external integration remains",)


def test_unreviewed_diff_or_missing_tests_cannot_form_result():
    test = CodingTestResult("pytest", True, "passed")
    with pytest.raises(ValueError, match="reviewed diff"):
        CodingResult("task", (), (test,), "summary", None, (), False)
    with pytest.raises(ValueError, match="test evidence"):
        CodingResult("task", (), (), "summary", None, (), True)
