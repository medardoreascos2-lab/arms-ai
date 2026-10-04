"""Separate wearable-health privacy boundary with default-deny access."""
from dataclasses import dataclass
from enum import Enum
from .consent import ConsentState
class HealthRequesterRole(str,Enum):OWNER="OWNER";FAMILY="FAMILY";SUPPORT="SUPPORT";ADMIN="ADMIN"
@dataclass(frozen=True)
class HealthPrivacyGrant:
 tenant_id:str;user_id:str;session_id:str;consent_state:ConsentState;encrypted_ready:bool;audit_enabled:bool;family_sharing:bool=False
@dataclass(frozen=True)
class HealthAccessRequest:
 tenant_id:str;user_id:str;session_id:str;role:HealthRequesterRole

def authorize_health_access(grant:HealthPrivacyGrant,request:HealthAccessRequest)->bool:
 if request.role!=HealthRequesterRole.OWNER:return False
 return grant.consent_state==ConsentState.GRANTED_SESSION and grant.encrypted_ready and grant.audit_enabled and (grant.tenant_id,grant.user_id,grant.session_id)==(request.tenant_id,request.user_id,request.session_id)
