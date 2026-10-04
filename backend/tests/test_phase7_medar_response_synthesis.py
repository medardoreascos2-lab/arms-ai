"""R87B MEDAR response synthesis tests."""

from backend.medar.agent_contract import AgentOutput
from backend.medar.evidence import aggregate_evidence
from backend.medar.response import ResponseStatus
from backend.medar.response_synthesis import synthesize_response


def test_response_is_synthesized_only_when_evidence_exists():
    bundle = aggregate_evidence(agent_outputs=(
        AgentOutput("agent", "task", "analysis", ("fact-1",), (), 0.82),
    ))
    response = synthesize_response(
        response_id="response-1", request_id="request-1",
        answer="Evidence supports the conclusion.", evidence=bundle,
    )
    assert response.status is ResponseStatus.SUCCESS
    assert response.answer == "Evidence supports the conclusion."
    assert response.confidence == 0.82


def test_missing_evidence_returns_explicit_partial_response_without_claim():
    response = synthesize_response(
        response_id="response-1", request_id="request-1",
        answer="An unsupported claim", evidence=aggregate_evidence(),
    )
    assert response.status is ResponseStatus.PARTIAL
    assert response.answer == "Insufficient evidence to provide a supported answer."
    assert response.confidence == 0.0
    assert response.follow_up_needed is True
    assert "INSUFFICIENT_EVIDENCE" in response.warnings
