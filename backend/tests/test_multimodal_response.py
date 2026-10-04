import pytest

from backend.multimodal.response import MultimodalDegradedState, MultimodalResponse


def test_response_exposes_only_presentable_evidence_and_provenance():
    response = MultimodalResponse(
        response_id="response-1", request_id="request-1", text="Synthetic response.",
        confidence=0.8, sources=("fixture:1",), warnings=("LOCAL_TEST_ONLY",),
        provenance={"provider": "SYNTHETIC"},
        degraded_state=MultimodalDegradedState.NONE,
    )
    assert response.provenance["provider"] == "SYNTHETIC"
    assert response.confidence == 0.8


def test_response_rejects_invalid_confidence_and_hidden_reasoning_field():
    with pytest.raises(ValueError):
        MultimodalResponse(response_id="r", request_id="q", text=None, confidence=1.1)
    with pytest.raises(TypeError):
        MultimodalResponse(
            response_id="r", request_id="q", text="x", chain_of_thought="hidden"
        )
