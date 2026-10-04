from datetime import datetime, timedelta, timezone

import pytest

from backend.multimodal.audio_validation import AudioInputDescriptor, AudioInputLimits, validate_audio_input
from backend.multimodal.domain import Modality
from backend.multimodal.request import MultimodalRequest
from backend.product.customer_session import synthetic_customer_session

NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)
s=synthetic_customer_session(issued_at=NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1))
r=MultimodalRequest(session=s,request_id="r",modality=Modality.AUDIO_INPUT,content_reference="audio:1",mime_type="audio/wav",created_at=NOW,consent_context={},permission_context={},source_device="d")


def descriptor(**changes):
    values=dict(content_reference="audio:1",owner_session_id=s.session_id,owner_user_id=s.user_id,owner_tenant_id=s.tenant_id,mime_type="audio/wav",format="wav",size_bytes=100,duration_seconds=1.0);values.update(changes);return AudioInputDescriptor(**values)


def test_valid_audio_metadata_passes_without_reading_or_storing_content():
    validate_audio_input(descriptor(),r,AudioInputLimits(max_size_bytes=1000,max_duration_seconds=5))


@pytest.mark.parametrize("changes,error",[
    ({"size_bytes":1001},ValueError),({"duration_seconds":6},ValueError),
    ({"mime_type":"audio/wav","format":"mp3"},ValueError),
    ({"owner_user_id":"other"},PermissionError),
])
def test_invalid_oversized_spoofed_or_foreign_audio_fails_closed(changes,error):
    with pytest.raises(error): validate_audio_input(descriptor(**changes),r,AudioInputLimits(max_size_bytes=1000,max_duration_seconds=5))
