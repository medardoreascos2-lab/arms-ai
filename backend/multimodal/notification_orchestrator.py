"""Multimodal notification presentation planning; only in-app delivery is real."""
from dataclasses import dataclass
from enum import Enum
from backend.product.notifications import ProductNotification
class PresentationMode(str,Enum):IN_APP="IN_APP";VOICE="VOICE";AVATAR="AVATAR";PUSH="PUSH";EMAIL="EMAIL";TELEGRAM="TELEGRAM";WHATSAPP="WHATSAPP"
class PresentationAvailability(str,Enum):AVAILABLE="AVAILABLE";LOCAL_TEST_ONLY="LOCAL_TEST_ONLY";INTEGRATION_PENDING="INTEGRATION_PENDING"
@dataclass(frozen=True)
class NotificationPresentation:
 notification_id:str;mode:PresentationMode;availability:PresentationAvailability;title:str;summary:str;external_delivery_authorized:bool=False;device_control_authorized:bool=False

class MultimodalNotificationOrchestrator:
 def plan(self,notification:ProductNotification,*,tenant_id:str,user_id:str,modes:tuple[PresentationMode,...])->tuple[NotificationPresentation,...]:
  if (notification.tenant_id,notification.user_id)!=(tenant_id,user_id):raise PermissionError("notification scope mismatch")
  items=[]
  for mode in modes:
   availability=PresentationAvailability.AVAILABLE if mode==PresentationMode.IN_APP else PresentationAvailability.LOCAL_TEST_ONLY if mode in {PresentationMode.VOICE,PresentationMode.AVATAR} else PresentationAvailability.INTEGRATION_PENDING
   items.append(NotificationPresentation(notification.notification_id,mode,availability,notification.title,notification.summary))
  return tuple(items)
