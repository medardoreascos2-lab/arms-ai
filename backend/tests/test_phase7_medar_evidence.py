"""R87A MEDAR evidence aggregation tests."""

from backend.medar.agent_contract import AgentOutput
from backend.medar.evidence import aggregate_evidence
from backend.medar.response import SourceReference
from backend.medar.tool_contract import ToolResult, ToolResultStatus


def test_aggregator_preserves_all_inputs_and_combines_warnings():
    agent = AgentOutput("agent", "task", "summary", ("fact",), ("agent warning",), 0.8)
    tool = ToolResult("call", "tool", ToolResultStatus.BLOCKED, {}, "policy")
    source = SourceReference("source", "Title", "https://example.test")

    bundle = aggregate_evidence(
        agent_outputs=(agent,), tool_results=(tool,), sources=(source,), warnings=("input warning",),
    )

    assert bundle.agent_outputs == (agent,)
    assert bundle.tool_results == (tool,)
    assert bundle.sources == (source,)
    assert bundle.warnings == (
        "input warning", "agent warning", "tool tool returned blocked",
    )
    assert bundle.usable_evidence_count == 2
    assert bundle.is_sufficient is True


def test_empty_bundle_is_explicitly_insufficient():
    bundle = aggregate_evidence()
    assert bundle.is_sufficient is False
    assert bundle.usable_evidence_count == 0
