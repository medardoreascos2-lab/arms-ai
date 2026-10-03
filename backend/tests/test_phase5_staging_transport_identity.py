"""R53B synthetic OIDC/JWT validation with local test keys only.

HS256 is used only inside this test module to avoid an external identity
provider or crypto dependency. It is not approved for external staging.
"""

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re

import pytest

from backend.entitlements import (
    FeatureEntitlement,
    UserIdentity,
    UserRole,
    UserStatus,
)
from backend.phase3.read_authorization import (
    AccountReadScope,
    AccountScopeMode,
    AuthorizationPrincipal,
)
from backend.phase3.state_contracts import AccountIdentity
from backend.phase4.secret_providers import SecretReference
from backend.phase4.service_identity import (
    ServiceCredentialRotation,
    ServiceIdentity,
    ServicePermission,
    ServiceTenantScope,
)
from backend.phase4.transport_authorization import (
    AuthenticatedServiceTransportPrincipal,
    AuthenticatedUserTransportPrincipal,
    Phase4TransportAction,
    Phase4TransportAuthorizationBoundary,
    Phase4TransportRequest,
    TransportAuthorizationCode,
)


NOW = datetime(2026, 10, 4, 0, 0, tzinfo=timezone.utc)
ISSUER = "https://synthetic-idp.invalid/staging"
AUDIENCE = "arms-ai-staging-api"
KEY_V1 = b"synthetic-r53b-signing-key-v1-not-real"
KEY_V2 = b"synthetic-r53b-signing-key-v2-not-real"
_KID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_TOKEN_BYTES = 8192
_REQUIRED_CLAIMS = frozenset({
    "iss",
    "aud",
    "sub",
    "iat",
    "nbf",
    "exp",
    "jti",
    "principal_type",
    "tenant_id",
    "roles",
    "account_ids",
})


class SyntheticIdentityError(ValueError):
    pass


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value):
    if not isinstance(value, str) or not value or "=" in value:
        raise SyntheticIdentityError("token encoding is invalid")
    if re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise SyntheticIdentityError("token encoding is invalid")
    try:
        return base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError):
        raise SyntheticIdentityError("token encoding is invalid") from None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SyntheticIdentityError("duplicate token field")
        result[key] = value
    return result


def _decode_object(segment, name):
    try:
        value = json.loads(
            _b64decode(segment).decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: (_ for _ in ()).throw(
                SyntheticIdentityError("non-finite token value")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SyntheticIdentityError(f"token {name} is invalid") from None
    if not isinstance(value, dict):
        raise SyntheticIdentityError(f"token {name} is invalid")
    return value


def _numeric_date(value, name):
    if type(value) is not int:
        raise SyntheticIdentityError(f"{name} must be an integer NumericDate")
    return datetime.fromtimestamp(value, tz=timezone.utc)


@dataclass(frozen=True)
class SyntheticSigningKey:
    kid: str
    material: bytes
    active_from: datetime
    retire_at: datetime

    def active_at(self, moment):
        return self.active_from <= moment < self.retire_at


@dataclass(frozen=True)
class CanonicalUser:
    subject: str
    identity: UserIdentity
    roles: frozenset[UserRole]
    account_ids: frozenset[str]


@dataclass(frozen=True)
class CanonicalService:
    subject: str
    identity: ServiceIdentity
    account_ids: frozenset[str]


class SyntheticIssuer:
    local_test_only = True
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, issuer, keys):
        self.issuer = issuer
        self.keys = dict(keys)

    def issue(self, kid, claims):
        key = self.keys[kid]
        header = {"alg": "HS256", "kid": kid, "typ": "JWT"}
        encoded_header = _b64encode(
            json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        encoded_claims = _b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
        signature = hmac.new(key.material, signing_input, hashlib.sha256).digest()
        return f"{encoded_header}.{encoded_claims}.{_b64encode(signature)}"


class SyntheticOidcVerifier:
    local_test_only = True
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    def __init__(self, *, issuer, audience, keys, users, services):
        self.issuer = issuer
        self.audience = audience
        self.keys = dict(keys)
        self.users = dict(users)
        self.services = dict(services)

    def validate(self, token, *, now):
        if not isinstance(token, str) or len(token.encode("utf-8")) > _MAX_TOKEN_BYTES:
            raise SyntheticIdentityError("token size is invalid")
        segments = token.split(".")
        if len(segments) != 3 or any(not segment for segment in segments):
            raise SyntheticIdentityError("token shape is invalid")
        header = _decode_object(segments[0], "header")
        if set(header) != {"alg", "kid", "typ"}:
            raise SyntheticIdentityError("token header fields are invalid")
        if header["alg"] != "HS256" or header["typ"] != "JWT":
            raise SyntheticIdentityError("token header is invalid")
        kid = header["kid"]
        if not isinstance(kid, str) or _KID.fullmatch(kid) is None:
            raise SyntheticIdentityError("token key identifier is invalid")
        key = self.keys.get(kid)
        if key is None or not key.active_at(now):
            raise SyntheticIdentityError("token signing key is unavailable")
        signing_input = f"{segments[0]}.{segments[1]}".encode("ascii")
        expected = hmac.new(key.material, signing_input, hashlib.sha256).digest()
        supplied = _b64decode(segments[2])
        if not hmac.compare_digest(expected, supplied):
            raise SyntheticIdentityError("token signature is invalid")

        claims = _decode_object(segments[1], "claims")
        if set(claims) != _REQUIRED_CLAIMS:
            raise SyntheticIdentityError("token claims are incomplete")
        if claims["iss"] != self.issuer:
            raise SyntheticIdentityError("token issuer is invalid")
        audiences = claims["aud"]
        if isinstance(audiences, str):
            audiences = [audiences]
        if (
            not isinstance(audiences, list)
            or not audiences
            or len(audiences) > 4
            or any(not isinstance(item, str) for item in audiences)
            or len(set(audiences)) != len(audiences)
            or self.audience not in audiences
        ):
            raise SyntheticIdentityError("token audience is invalid")

        issued_at = _numeric_date(claims["iat"], "iat")
        not_before = _numeric_date(claims["nbf"], "nbf")
        expires_at = _numeric_date(claims["exp"], "exp")
        principal_type = claims["principal_type"]
        maximum_lifetime = {
            "user": timedelta(minutes=10),
            "service": timedelta(minutes=5),
        }.get(principal_type)
        if maximum_lifetime is None:
            raise SyntheticIdentityError("principal type is invalid")
        if issued_at > now + timedelta(seconds=60) or not_before > now + timedelta(
            seconds=60
        ):
            raise SyntheticIdentityError("token is not active")
        if expires_at <= now or expires_at <= issued_at:
            raise SyntheticIdentityError("token is expired")
        if expires_at - issued_at > maximum_lifetime:
            raise SyntheticIdentityError("token lifetime is excessive")

        for name in ("sub", "jti", "tenant_id"):
            if not isinstance(claims[name], str) or not claims[name]:
                raise SyntheticIdentityError(f"token {name} is invalid")
        roles = claims["roles"]
        account_ids = claims["account_ids"]
        if (
            not isinstance(roles, list)
            or not roles
            or len(roles) > 8
            or any(not isinstance(item, str) for item in roles)
            or len(set(roles)) != len(roles)
        ):
            raise SyntheticIdentityError("token roles are invalid")
        if (
            not isinstance(account_ids, list)
            or len(account_ids) > 32
            or any(not isinstance(item, str) for item in account_ids)
            or len(set(account_ids)) != len(account_ids)
        ):
            raise SyntheticIdentityError("token account scope is invalid")

        if principal_type == "user":
            return self._user_principal(claims, roles, account_ids, now)
        return self._service_principal(claims, roles, account_ids, now)

    def _user_principal(self, claims, role_names, account_ids, now):
        canonical = self.users.get(claims["sub"])
        if canonical is None or canonical.identity.status is not UserStatus.ACTIVE:
            raise SyntheticIdentityError("canonical user is unavailable")
        if claims["tenant_id"] != canonical.identity.tenant_id:
            raise SyntheticIdentityError("token tenant is invalid")
        try:
            roles = frozenset(UserRole(name) for name in role_names)
        except ValueError:
            raise SyntheticIdentityError("token role is invalid") from None
        if not roles.issubset(canonical.roles):
            raise SyntheticIdentityError("token role escalation is denied")
        accounts = frozenset(account_ids)
        if not accounts.issubset(canonical.account_ids):
            raise SyntheticIdentityError("token account scope is invalid")
        principal = AuthorizationPrincipal(
            identity=canonical.identity,
            roles=roles,
            entitlements=frozenset(FeatureEntitlement),
            account_scope=AccountReadScope(
                canonical.identity.tenant_id,
                AccountScopeMode.EXPLICIT,
                accounts,
            ),
        )
        return AuthenticatedUserTransportPrincipal(
            principal,
            canonical.identity.tenant_id,
            now,
        )

    def _service_principal(self, claims, role_names, account_ids, now):
        canonical = self.services.get(claims["sub"])
        if canonical is None or not canonical.identity.active_at(now):
            raise SyntheticIdentityError("canonical service is unavailable")
        if claims["tenant_id"] not in canonical.identity.tenant_scope.tenant_ids:
            raise SyntheticIdentityError("token tenant is invalid")
        try:
            token_permissions = frozenset(
                ServicePermission(name) for name in role_names
            )
        except ValueError:
            raise SyntheticIdentityError("token role is invalid") from None
        if not token_permissions.issubset(canonical.identity.permissions):
            raise SyntheticIdentityError("token role escalation is denied")
        accounts = frozenset(account_ids)
        if not accounts.issubset(canonical.account_ids):
            raise SyntheticIdentityError("token account scope is invalid")
        narrowed_identity = ServiceIdentity(
            service_id=canonical.identity.service_id,
            tenant_scope=ServiceTenantScope(frozenset({claims["tenant_id"]})),
            permissions=token_permissions,
            credential_reference=canonical.identity.credential_reference,
            expires_at=canonical.identity.expires_at,
            rotation=canonical.identity.rotation,
        )
        return AuthenticatedServiceTransportPrincipal(
            narrowed_identity,
            claims["tenant_id"],
            AccountReadScope(
                claims["tenant_id"],
                AccountScopeMode.EXPLICIT,
                accounts,
            ),
            now,
        )


def _epoch(value):
    return int(value.timestamp())


def _claims(**changes):
    value = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "synthetic-user-1",
        "iat": _epoch(NOW - timedelta(seconds=10)),
        "nbf": _epoch(NOW - timedelta(seconds=10)),
        "exp": _epoch(NOW + timedelta(minutes=5)),
        "jti": "synthetic-jti-1",
        "principal_type": "user",
        "tenant_id": "tenant-a",
        "roles": ["OPERATOR"],
        "account_ids": ["account-1"],
    }
    value.update(changes)
    return value


def _service_identity():
    return ServiceIdentity(
        service_id="phase5.operations-reader",
        tenant_scope=ServiceTenantScope(frozenset({"tenant-a"})),
        permissions=frozenset({
            ServicePermission.HEALTH_READ,
            ServicePermission.OPERATIONS_READ,
        }),
        credential_reference=SecretReference("service/phase5/operations/v1"),
        expires_at=NOW + timedelta(days=1),
        rotation=ServiceCredentialRotation(
            1,
            NOW - timedelta(days=1),
            NOW + timedelta(hours=12),
        ),
    )


def _environment(*, old_retire=NOW + timedelta(minutes=6)):
    keys = (
        SyntheticSigningKey(
            "key_v1", KEY_V1, NOW - timedelta(days=1), old_retire
        ),
        SyntheticSigningKey(
            "key_v2", KEY_V2, NOW - timedelta(minutes=1), NOW + timedelta(days=1)
        ),
    )
    user = CanonicalUser(
        subject="synthetic-user-1",
        identity=UserIdentity("user-1", "tenant-a"),
        roles=frozenset({UserRole.OPERATOR}),
        account_ids=frozenset({"account-1"}),
    )
    service = CanonicalService(
        subject="synthetic-service-1",
        identity=_service_identity(),
        account_ids=frozenset({"account-1"}),
    )
    issuer = SyntheticIssuer(ISSUER, ((key.kid, key) for key in keys))
    verifier = SyntheticOidcVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        keys=((key.kid, key) for key in keys),
        users=((user.subject, user),),
        services=((service.subject, service),),
    )
    return issuer, verifier


def _validate(claims=None, *, kid="key_v2", now=NOW, environment=None):
    issuer, verifier = environment or _environment()
    return verifier.validate(issuer.issue(kid, claims or _claims()), now=now)


def test_valid_user_and_service_tokens_create_no_execution_principals():
    user = _validate()
    service = _validate(
        _claims(
            sub="synthetic-service-1",
            principal_type="service",
            roles=["OPERATIONS_READ"],
            exp=_epoch(NOW + timedelta(minutes=4)),
        )
    )

    assert isinstance(user, AuthenticatedUserTransportPrincipal)
    assert isinstance(service, AuthenticatedServiceTransportPrincipal)
    assert user.tenant_claim == service.tenant_claim == "tenant-a"
    assert user.account_scope.allows("account-1")
    assert service.account_scope.allows("account-1")
    assert service.identity.permissions == frozenset({ServicePermission.OPERATIONS_READ})
    for principal in (user, service):
        assert principal.execution_authorized is False
        assert principal.production_mutation_authorized is False

    boundary = Phase4TransportAuthorizationBoundary(
        frozenset({AccountIdentity("tenant-a", "account-1")})
    )
    for principal in (user, service):
        decision = boundary.evaluate(
            principal,
            Phase4TransportRequest(
                Phase4TransportAction.ACCOUNT_OPERATIONS_READ,
                "tenant-a",
                "account-1",
            ),
            evaluated_at=NOW,
        )
        assert decision.code is TransportAuthorizationCode.ALLOWED
        assert decision.execution_authorized is False


def test_expired_token_is_rejected_without_principal():
    with pytest.raises(SyntheticIdentityError, match="expired"):
        _validate(_claims(exp=_epoch(NOW)))


@pytest.mark.parametrize(
    "claim, value, message",
    (
        ("aud", "other-api", "audience"),
        ("iss", "https://wrong.invalid", "issuer"),
    ),
)
def test_wrong_audience_or_issuer_is_rejected(claim, value, message):
    with pytest.raises(SyntheticIdentityError, match=message):
        _validate(_claims(**{claim: value}))


@pytest.mark.parametrize(
    "mutate, message",
    (
        (
            lambda claims: claims.update(
                nbf=_epoch(NOW + timedelta(seconds=61))
            ),
            "not active",
        ),
        (
            lambda claims: claims.update(
                exp=_epoch(NOW + timedelta(minutes=11))
            ),
            "lifetime",
        ),
        (lambda claims: claims.pop("jti"), "incomplete"),
    ),
)
def test_time_window_and_required_claim_failures_are_denied(mutate, message):
    claims = _claims()
    mutate(claims)
    with pytest.raises(SyntheticIdentityError, match=message):
        _validate(claims)


@pytest.mark.parametrize(
    "changes, message",
    (
        ({"tenant_id": "tenant-b"}, "tenant"),
        ({"account_ids": ["account-2"]}, "account"),
        ({"roles": ["OPERATOR", "TENANT_ADMIN"]}, "escalation"),
    ),
)
def test_tenant_account_and_role_escalation_are_rejected(changes, message):
    with pytest.raises(SyntheticIdentityError, match=message):
        _validate(_claims(**changes))


def test_signature_failure_is_rejected_before_claim_authority():
    issuer, verifier = _environment()
    token = issuer.issue("key_v2", _claims(roles=["TENANT_ADMIN"]))
    header, payload, signature = token.split(".")
    signature_bytes = _b64decode(signature)
    bad_signature = bytes((signature_bytes[0] ^ 1,)) + signature_bytes[1:]
    tampered = f"{header}.{payload}.{_b64encode(bad_signature)}"

    with pytest.raises(SyntheticIdentityError, match="signature"):
        verifier.validate(tampered, now=NOW)

    assert verifier.execution_authorized is False
    assert verifier.production_mutation_authorized is False
    assert verifier.live_trading_authorized is False


def test_key_rotation_accepts_overlap_and_rejects_retired_key():
    issuer, verifier = _environment(old_retire=NOW + timedelta(minutes=2))
    old_token = issuer.issue("key_v1", _claims(jti="old-key-token"))
    new_token = issuer.issue("key_v2", _claims(jti="new-key-token"))

    assert verifier.validate(old_token, now=NOW).authenticated is True
    assert verifier.validate(new_token, now=NOW).authenticated is True
    after_retirement = NOW + timedelta(minutes=2)
    with pytest.raises(SyntheticIdentityError, match="key is unavailable"):
        verifier.validate(old_token, now=after_retirement)
    assert verifier.validate(new_token, now=after_retirement).authenticated is True


def test_local_test_keys_and_tokens_carry_no_external_provider_authority():
    issuer, verifier = _environment()
    assert issuer.local_test_only is True
    assert issuer.execution_authorized is False
    assert issuer.production_mutation_authorized is False
    assert verifier.local_test_only is True
    assert verifier.execution_authorized is False
    assert verifier.live_trading_authorized is False
    assert b"synthetic-r53b" in KEY_V1
    assert b"synthetic-r53b" in KEY_V2
