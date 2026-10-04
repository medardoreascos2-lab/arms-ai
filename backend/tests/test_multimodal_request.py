from datetime import datetime, timedelta, timezone

import pytest

from backend.multimodal.domain import Modality
from backend.multimodal.request import MultimodalRequest
from backend.product.customer_session import synthetic_customer_session

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def session():
    return synthetic_customer_session(issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(hours=1))


def test_request_identity_is_derived_only_from_trusted_session():
    trusted = session()
    request = MultimodalRequest(
        session=trusted, request_id="request-1", modality=Modality.AUDIO_INPUT,
        content_reference="media:audio-1", mime_type="audio/wav", created_at=NOW,
        consent_context={"MICROPHONE": "GRANTED_SESSION"},
        permission_context={"VOICE": "ALLOWED"}, source_device="device-1",
        metadata={"environment": "LOCAL_TEST_ONLY"},
    )
    assert (request.session_id, request.user_id, request.tenant_id) == (
        trusted.session_id, trusted.user_id, trusted.tenant_id,
    )
    assert request.identity_source == "TRUSTED_PRODUCT_SESSION"


def test_request_rejects_untrusted_session_and_has_no_identity_override_arguments():
    with pytest.raises(PermissionError):
        MultimodalRequest(
            session=None, request_id="request-1", modality=Modality.TEXT,
            content_reference="content:1", mime_type="text/plain", created_at=NOW,
            consent_context={}, permission_context={}, source_device="device-1",
        )
    with pytest.raises(TypeError):
        MultimodalRequest(
            session=session(), user_id="attacker", tenant_id="attacker",
            request_id="request-1", modality=Modality.TEXT,
            content_reference="content:1", mime_type="text/plain", created_at=NOW,
            consent_context={}, permission_context={}, source_device="device-1",
        )
