"""R83C immutable execution plan tests."""

from dataclasses import FrozenInstanceError, replace

import pytest

from backend.medar.execution_plan import build_execution_plan
from backend.medar.request import RiskClass
from backend.medar.task_model import CognitiveTask, TaskStatus


def _tasks():
    return (
        CognitiveTask("research", None, "research", (), TaskStatus.READY, "web_search", RiskClass.LOW, "web_search_stub"),
        CognitiveTask("risk", None, "risk", (), TaskStatus.READY, "financial_analysis", RiskClass.HIGH, "financial_analysis_stub"),
        CognitiveTask("synthesis", None, "synthesize", ("research", "risk"), TaskStatus.PENDING, "general_analysis", RiskClass.HIGH),
    )


def test_plan_snapshots_tasks_tools_risks_gates_and_expected_evidence():
    plan = build_execution_plan(
        "plan-1",
        "request-1",
        _tasks(),
        created_at="2026-10-03T12:00:00Z",
    )

    assert plan.required_tools == ("web_search_stub", "financial_analysis_stub")
    assert plan.confirmation_gates == ("risk", "synthesis")
    assert len(plan.snapshot_digest) == 64
    assert plan.execution_authorized is False
    assert all(item.expected_evidence for item in plan.expected_evidence)


def test_plan_is_immutable_and_digest_detects_tampering():
    plan = build_execution_plan("plan-1", "request-1", _tasks(), created_at="2026-10-03T12:00:00Z")

    with pytest.raises(FrozenInstanceError):
        plan.revision = 2
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(plan, created_at="different")
