from backend.multimodal.consent import ConsentState
from backend.multimodal.health_privacy import HealthAccessRequest,HealthPrivacyGrant,HealthRequesterRole,authorize_health_access
def test_health_data_requires_separate_consent_encryption_scope_and_audit():
 g=HealthPrivacyGrant("t","u","s",ConsentState.GRANTED_SESSION,True,True);assert authorize_health_access(g,HealthAccessRequest("t","u","s",HealthRequesterRole.OWNER))
 assert not authorize_health_access(g,HealthAccessRequest("t","other","s",HealthRequesterRole.OWNER))
def test_revoked_family_support_and_admin_access_are_denied_by_default():
 for state in (ConsentState.REVOKED,ConsentState.DENIED,ConsentState.EXPIRED):
  g=HealthPrivacyGrant("t","u","s",state,True,True)
  assert not authorize_health_access(g,HealthAccessRequest("t","u","s",HealthRequesterRole.OWNER))
 g=HealthPrivacyGrant("t","u","s",ConsentState.GRANTED_SESSION,True,True)
 for role in (HealthRequesterRole.FAMILY,HealthRequesterRole.SUPPORT,HealthRequesterRole.ADMIN):assert not authorize_health_access(g,HealthAccessRequest("t","u","s",role))
