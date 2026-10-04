"""R80B MEDAR response model tests."""

import pytest

from backend.medar.response import (
    ActionProposal,
    CognitiveResponse,
    EvidenceReference,
    ResponseStatus,
    SourceReference,
)


def test_response_carries_traceable_evidence_and_reasoning_summary():
    response = CognitiveResponse(
        response_id="res-1",
        request_id="req-1",
        status=ResponseStatus.PARTIAL,
        answer="Available evidence supports a bounded conclusion.",
        confidence=0.7,
        reasoning_summary="Compared two sources and retained one warning.",
        sources=(SourceReference("src-1", "Primary source", "https://example.test"),),
        tool_evidence=(EvidenceReference("tool-1", "calculator output", "a" * 64),),
        warnings=("CURRENT_DATA_REQUIRED",),
        follow_up_needed=True,
        action_proposals=(ActionProposal("act-1", "Fetch current data", True),),
    )

    assert response.status is ResponseStatus.PARTIAL
    assert response.reasoning_summary.startswith("Compared")
    assert response.action_proposals[0].execution_authorized is False


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True])
def test_invalid_confidence_is_rejected(confidence):
    with pytest.raises((TypeError, ValueError)):
        CognitiveResponse("res", "req", ResponseStatus.SUCCESS, "answer", confidence, "summary")


def test_response_cannot_embed_an_authorized_action():
    with pytest.raises(ValueError, match="cannot authorize"):
        ActionProposal("act", "perform external action", True, execution_authorized=True)
