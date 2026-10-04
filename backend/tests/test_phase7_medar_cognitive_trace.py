"""R96A MEDAR cognitive trace tests."""

import pytest

from backend.medar.cognitive_trace import CognitiveTrace, build_cognitive_trace
from backend.medar.uncertainty import UncertaintyLevel


def test_trace_records_required_execution_metadata_with_request_digest():
    trace = build_cognitive_trace(
        request_id="request", normalized_request="private prompt", intent_summary="GENERAL",
        plan_id="plan", agent_ids=("general",), tool_call_ids=("call",),
        memory_read_ids=("memory",), result_status="SUCCESS",
        uncertainty=UncertaintyLevel.MEDIUM_CONFIDENCE, failures=(),
    )
    assert len(trace.request_digest) == 64
    assert "private prompt" not in repr(trace)
    assert trace.agent_ids == ("general",)
    assert trace.hidden_chain_of_thought_stored is False


def test_trace_cannot_store_hidden_chain_of_thought():
    with pytest.raises(ValueError, match="chain-of-thought"):
        CognitiveTrace(
            "request", "a" * 64, "intent", None, (), (), (), "FAILED",
            UncertaintyLevel.INSUFFICIENT_EVIDENCE, (), True,
        )
