"""R96C MEDAR cognitive privacy audit tests."""

from backend.medar.agents import initial_agents
from backend.medar.privacy_audit import audit_cognitive_privacy
from backend.medar.tool_registry import default_tool_registry


def test_default_runtime_authorities_and_redacted_trace_pass_privacy_audit():
    result = audit_cognitive_privacy(
        agents=initial_agents(), tools=default_tool_registry().tools, memory_query=None,
        trace_payload={"request_digest": "a" * 64, "agent_ids": ["general"]},
    )
    assert result.passed is True
    assert result.findings == ()


def test_pii_secret_and_raw_request_fields_are_detected_in_nested_trace():
    result = audit_cognitive_privacy(
        agents=initial_agents(), tools=default_tool_registry().tools, memory_query=None,
        trace_payload={"request": {"raw_input": "private", "api_key": "secret"}},
    )
    assert result.passed is False
    assert result.findings == (
        "SENSITIVE_TRACE_FIELD:root.request.api_key",
        "SENSITIVE_TRACE_FIELD:root.request.raw_input",
    )
