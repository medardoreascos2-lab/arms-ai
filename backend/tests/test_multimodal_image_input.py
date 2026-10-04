from datetime import datetime,timedelta,timezone
import pytest
from backend.multimodal.consent import ConsentState
from backend.multimodal.domain import Modality
from backend.multimodal.image_input import ImageInput,ImageLimits,validate_image_input
from backend.multimodal.request import MultimodalRequest
from backend.product.customer_session import synthetic_customer_session
NOW=datetime(2026,10,4,12,tzinfo=timezone.utc);s=synthetic_customer_session(issued_at=NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1));r=MultimodalRequest(session=s,request_id="r",modality=Modality.IMAGE,content_reference="image:1",mime_type="image/png",created_at=NOW,consent_context={},permission_context={},source_device="d")
def image(**change):
 v=dict(content_reference="image:1",owner_session_id=s.session_id,owner_user_id=s.user_id,owner_tenant_id=s.tenant_id,mime_type="image/png",size_bytes=100,width=10,height=10,consent_reference="c-1",consent_state=ConsentState.GRANTED_SESSION);v.update(change);return ImageInput(**v)
def test_valid_jpeg_png_webp_contract_accepts_scoped_image(): validate_image_input(image(),r)
@pytest.mark.parametrize("change,error", [({"owner_tenant_id":"other"},PermissionError),({"consent_state":ConsentState.REVOKED},PermissionError),({"mime_type":"image/gif"},ValueError),({"size_bytes":20_000_000},ValueError),({"width":9000},ValueError)])
def test_image_validation_fails_closed(change,error):
 with pytest.raises(error): validate_image_input(image(**change),r,ImageLimits())
