from datetime import datetime, timedelta, timezone

from backend.entitlements import FeatureEntitlement
from backend.multimodal.consent import ConsentCapability, ConsentState, ModalityConsent, SessionConsentRegistry
from backend.multimodal.domain import Modality
from backend.multimodal.permissions import MultimodalPermissionBoundary, PermissionCode
from backend.multimodal.request import MultimodalRequest
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def setup(entitlements):
    session = synthetic_customer_session(issued_at=NOW-timedelta(minutes=1), expires_at=NOW+timedelta(hours=1), entitlements=frozenset(entitlements))
    sessions = LocalSyntheticSessionProvider((session,)); consents = SessionConsentRegistry()
    request = MultimodalRequest(session=session, request_id="r-1", modality=Modality.AUDIO_INPUT, content_reference="audio:1", mime_type="audio/wav", created_at=NOW, consent_context={"MICROPHONE": "GRANTED_SESSION"}, permission_context={"VOICE": "ALLOWED"}, source_device="device-1")
    return session, sessions, consents, request


def run(boundary, request):
    calls={"capture":0,"invoke":0,"store":0}
    def capture(value): calls["capture"]+=1; return value
    def invoke(value): calls["invoke"]+=1; return "result"
    def store(value): calls["store"]+=1
    decision,result=boundary.execute(request,NOW,capture=capture,invoke=invoke,store=store)
    return decision,result,calls


def test_denied_request_has_zero_capture_model_storage_and_downstream_action():
    _,sessions,consents,request=setup({FeatureEntitlement.MEDAR_CONVERSATION})
    boundary=MultimodalPermissionBoundary(sessions=sessions,consents=consents,supported=frozenset({Modality.AUDIO_INPUT}))
    decision,result,calls=run(boundary,request)
    assert decision.code == PermissionCode.ENTITLEMENT_REQUIRED
    assert result is None and calls == {"capture":0,"invoke":0,"store":0}


def test_entitled_request_still_requires_real_registry_consent_not_caller_context():
    session,sessions,consents,request=setup({FeatureEntitlement.VOICE})
    boundary=MultimodalPermissionBoundary(sessions=sessions,consents=consents,supported=frozenset({Modality.AUDIO_INPUT}))
    decision,_,calls=run(boundary,request)
    assert decision.code == PermissionCode.CONSENT_REQUIRED and calls["capture"] == 0
    consents.record(ModalityConsent(consent_id="c-1",session_id=session.session_id,user_id=session.user_id,tenant_id=session.tenant_id,capability=ConsentCapability.MICROPHONE,state=ConsentState.GRANTED_SESSION,decided_at=NOW-timedelta(seconds=1),expires_at=NOW+timedelta(minutes=5)))
    decision,result,calls=run(boundary,request)
    assert decision.allowed and result == "result" and calls == {"capture":1,"invoke":1,"store":1}
