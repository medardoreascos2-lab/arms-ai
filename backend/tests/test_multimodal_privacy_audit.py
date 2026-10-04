from datetime import datetime, timezone

import pytest

from backend.multimodal.consent import ConsentCapability
from backend.multimodal.privacy_audit import InMemoryPrivacyAudit, PrivacyAuditEvent, PrivacyAuditEventName

NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)


def test_audit_records_fixed_content_free_event_and_scopes_queries():
    audit=InMemoryPrivacyAudit(); event=PrivacyAuditEvent(event_id="e-1",name=PrivacyAuditEventName.MIC_STARTED,session_id="s-1",pseudonymous_subject_id="subject-1",capability=ConsentCapability.MICROPHONE,occurred_at=NOW)
    audit.append(event)
    assert audit.for_session("s-1") == (event,)
    assert audit.for_session("other") == ()


def test_audit_rejects_content_and_has_no_raw_media_field():
    with pytest.raises(ValueError):
        PrivacyAuditEvent(event_id="e",name=PrivacyAuditEventName.CAMERA_STARTED,session_id="s",pseudonymous_subject_id="p",capability=ConsentCapability.CAMERA,occurred_at=NOW,content_included=True)
    with pytest.raises(TypeError):
        PrivacyAuditEvent(event_id="e",name=PrivacyAuditEventName.CAMERA_STARTED,session_id="s",pseudonymous_subject_id="p",capability=ConsentCapability.CAMERA,occurred_at=NOW,raw_media=b"secret")
