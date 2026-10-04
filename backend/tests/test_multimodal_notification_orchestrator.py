from datetime import datetime,timezone
from backend.multimodal.notification_orchestrator import MultimodalNotificationOrchestrator,PresentationAvailability,PresentationMode
from backend.product.notifications import NotificationCategory,NotificationPriority,ProductNotification
N=ProductNotification(notification_id="n",user_id="u",tenant_id="t",category=NotificationCategory.PRODUCT,priority=NotificationPriority.INFO,title="Title",summary="Summary",source_type="TEST",source_reference="fixture:1",created_at=datetime(2026,10,4,tzinfo=timezone.utc))
def test_only_in_app_is_available_and_external_modes_remain_pending():
 plan=MultimodalNotificationOrchestrator().plan(N,tenant_id="t",user_id="u",modes=tuple(PresentationMode));by={x.mode:x for x in plan};assert by[PresentationMode.IN_APP].availability==PresentationAvailability.AVAILABLE;assert by[PresentationMode.VOICE].availability==PresentationAvailability.LOCAL_TEST_ONLY
 for mode in (PresentationMode.PUSH,PresentationMode.EMAIL,PresentationMode.TELEGRAM,PresentationMode.WHATSAPP):assert by[mode].availability==PresentationAvailability.INTEGRATION_PENDING and not by[mode].external_delivery_authorized
def test_notification_scope_mismatch_denies_before_presentation():
 import pytest
 with pytest.raises(PermissionError):MultimodalNotificationOrchestrator().plan(N,tenant_id="t",user_id="other",modes=(PresentationMode.IN_APP,))
