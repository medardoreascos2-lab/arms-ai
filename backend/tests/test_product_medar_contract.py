"""P102A1 Product MEDAR HTTP contract validation."""

import pytest
from pydantic import ValidationError

from backend.api.schemas.product_medar import (
    ProductActionProposal,
    ProductMedarPrompt,
    ProductMedarResponse,
    ProductMedarStatus,
)


def prompt(**overrides):
    body = {
        "request_id": "request-1",
        "conversation_id": "conversation-1",
        "message": "Explain this risk.",
        "locale": "en-US",
        "response_profile": "STANDARD",
        "client_context": {"active_view": "HOME", "timezone": "America/New_York"},
    }
    body.update(overrides)
    return body


def test_caller_identity_and_unknown_context_fields_are_rejected():
    for forbidden in ({"user_id": "another-user"}, {"tenant_id": "another-tenant"},
                      {"session_id": "chosen-session"}):
        with pytest.raises(ValidationError):
            ProductMedarPrompt.model_validate(prompt(**forbidden))
    with pytest.raises(ValidationError):
        ProductMedarPrompt.model_validate(prompt(client_context={"user_id": "another-user"}))


def test_prompt_is_bounded_and_keeps_user_text():
    parsed = ProductMedarPrompt.model_validate(prompt())
    assert parsed.message == "Explain this risk."
    assert parsed.client_context.active_view == "HOME"
    for invalid in ("", " ", "x" * 8193):
        with pytest.raises(ValidationError):
            ProductMedarPrompt.model_validate(prompt(message=invalid))


def test_degraded_response_cannot_claim_an_answer_or_executable_proposal():
    with pytest.raises(ValidationError):
        ProductMedarResponse(request_id="request-1", status=ProductMedarStatus.MEDAR_UNAVAILABLE,
                             answer="Synthetic answer")
    with pytest.raises(ValidationError):
        ProductActionProposal(action_id="a1", description="Trade", requires_confirmation=True,
                              execution_authorized=True)
    response = ProductMedarResponse(request_id="request-1", status=ProductMedarStatus.MEDAR_UNAVAILABLE)
    assert response.answer is None
    assert response.action_proposals == ()


def test_canonical_response_preserves_evidence_and_rejects_hidden_reasoning():
    body = {
        "response_id": "response-1",
        "request_id": "request-1",
        "status": "SUCCESS",
        "answer": "Review the verified risk data.",
        "confidence": 0.8,
        "reasoning_summary": "The available evidence supports review.",
        "sources": [{"source_id": "source-1", "title": "Risk report", "locator": "report:1"}],
        "tool_evidence": [{"evidence_id": "tool-1", "summary": "Read only", "digest": "abc"}],
        "memory_evidence": [{"evidence_id": "memory-1", "summary": "Preference", "digest": "def"}],
        "warnings": ["MARKET_FRESHNESS_UNKNOWN"],
        "follow_up_needed": True,
        "action_proposals": [{"action_id": "review-1", "description": "Review risk", "requires_confirmation": True}],
        "model_provenance": {"provider_id": "local", "model_id": "local-model", "locality": "LOCAL"},
    }
    response = ProductMedarResponse.model_validate(body)
    serialized = response.model_dump(mode="json")
    assert serialized["sources"][0]["source_id"] == "source-1"
    assert serialized["memory_evidence"][0]["evidence_id"] == "memory-1"
    assert serialized["action_proposals"][0]["state"] == "PROPOSED_ONLY"
    assert serialized["action_proposals"][0]["execution_authorized"] is False
    with pytest.raises(ValidationError):
        ProductMedarResponse.model_validate({**body, "chain_of_thought": "private"})
    with pytest.raises(ValidationError):
        ProductMedarResponse.model_validate({**body, "answer": None})


def test_new_degraded_statuses_cannot_fabricate_an_answer():
    for status in (ProductMedarStatus.SESSION_INVALID,
                   ProductMedarStatus.LOCAL_TEST_DISABLED):
        response = ProductMedarResponse(request_id="request-1", status=status)
        assert response.answer is None
        with pytest.raises(ValidationError):
            ProductMedarResponse(request_id="request-1", status=status,
                                 answer="Fabricated")
