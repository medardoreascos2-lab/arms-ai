"""Request tracing and replay protection without execution authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from threading import Lock

from backend.phase3.state_contracts import AccountIdentity, TenantIdentity


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be an 8-128 character safe identifier")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


class RequestEffect(str, Enum):
    READ_ONLY = "READ_ONLY"
    STATE_CHANGE = "STATE_CHANGE"


@dataclass(frozen=True)
class ReplayProtectionPolicy:
    maximum_age: timedelta = timedelta(minutes=5)
    maximum_future_skew: timedelta = timedelta(seconds=30)
    reservation_ttl: timedelta = timedelta(minutes=10)

    def __post_init__(self) -> None:
        for name in ("maximum_age", "maximum_future_skew", "reservation_ttl"):
            value = getattr(self, name)
            if not isinstance(value, timedelta):
                raise ValueError(f"{name} must be a timedelta")
        if self.maximum_age <= timedelta(0):
            raise ValueError("maximum_age must be positive")
        if self.maximum_future_skew < timedelta(0):
            raise ValueError("maximum_future_skew cannot be negative")
        if self.reservation_ttl < self.maximum_age + self.maximum_future_skew:
            raise ValueError("reservation_ttl must cover the complete timestamp window")


@dataclass(frozen=True)
class ReplayProtectionScope:
    principal_id: str
    tenant_id: str
    account_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.principal_id, "principal_id")
        TenantIdentity(self.tenant_id)
        if self.account_id is not None:
            AccountIdentity(self.tenant_id, self.account_id)

    @property
    def key(self) -> tuple[str, str, str | None]:
        return (self.principal_id, self.tenant_id, self.account_id)


@dataclass(frozen=True)
class Phase4RequestEnvelope:
    request_id: str
    operation: str
    issued_at: datetime
    effect: RequestEffect
    nonce: str | None = None
    idempotency_key: str | None = None
    payload_sha256: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.request_id, "request_id")
        _identifier(self.operation, "operation")
        if not isinstance(self.effect, RequestEffect):
            raise ValueError("effect must be a RequestEffect")
        object.__setattr__(self, "issued_at", _utc(self.issued_at, "issued_at"))
        protected = (self.nonce, self.idempotency_key, self.payload_sha256)
        if self.effect is RequestEffect.READ_ONLY:
            if any(value is not None for value in protected):
                raise ValueError("read-only requests cannot carry replay reservations")
            return
        if self.nonce is None or self.idempotency_key is None or self.payload_sha256 is None:
            raise ValueError(
                "state-changing requests require nonce, idempotency_key, and payload_sha256"
            )
        _identifier(self.nonce, "nonce")
        _identifier(self.idempotency_key, "idempotency_key")
        if _SHA256.fullmatch(self.payload_sha256) is None:
            raise ValueError("payload_sha256 must be a lowercase SHA-256 digest")


class ReplayProtectionCode(str, Enum):
    READ_ONLY_VALID = "READ_ONLY_VALID"
    FRESH_REQUEST = "FRESH_REQUEST"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    STALE_TIMESTAMP = "STALE_TIMESTAMP"
    FUTURE_TIMESTAMP = "FUTURE_TIMESTAMP"
    REQUEST_ID_REPLAY = "REQUEST_ID_REPLAY"
    NONCE_REPLAY = "NONCE_REPLAY"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


_ACCEPTED_CODES = frozenset({
    ReplayProtectionCode.READ_ONLY_VALID,
    ReplayProtectionCode.FRESH_REQUEST,
    ReplayProtectionCode.IDEMPOTENT_REPLAY,
})


@dataclass(frozen=True)
class ReplayProtectionDecision:
    accepted: bool
    code: ReplayProtectionCode
    replay_safe_to_process: bool
    idempotent_replay: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool or not isinstance(self.code, ReplayProtectionCode):
            raise ValueError("replay decision is invalid")
        if self.accepted != (self.code in _ACCEPTED_CODES):
            raise ValueError("replay decision code does not match accepted state")
        if type(self.replay_safe_to_process) is not bool:
            raise ValueError("replay_safe_to_process must be boolean")
        if type(self.idempotent_replay) is not bool:
            raise ValueError("idempotent_replay must be boolean")
        expected_process = self.code in {
            ReplayProtectionCode.READ_ONLY_VALID,
            ReplayProtectionCode.FRESH_REQUEST,
        }
        if self.replay_safe_to_process != expected_process:
            raise ValueError("replay processing flag does not match decision code")
        if self.idempotent_replay != (
            self.code is ReplayProtectionCode.IDEMPOTENT_REPLAY
        ):
            raise ValueError("idempotent flag does not match decision code")


def _decision(code: ReplayProtectionCode) -> ReplayProtectionDecision:
    return ReplayProtectionDecision(
        accepted=code in _ACCEPTED_CODES,
        code=code,
        replay_safe_to_process=code in {
            ReplayProtectionCode.READ_ONLY_VALID,
            ReplayProtectionCode.FRESH_REQUEST,
        },
        idempotent_replay=code is ReplayProtectionCode.IDEMPOTENT_REPLAY,
    )


@dataclass(frozen=True)
class _Reservation:
    payload_sha256: str
    expires_at: datetime


class RequestReplayProtector:
    """In-memory replay admission; separate authorization is always required."""

    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, policy: ReplayProtectionPolicy | None = None) -> None:
        self._policy = policy or ReplayProtectionPolicy()
        if not isinstance(self._policy, ReplayProtectionPolicy):
            raise ValueError("policy must be ReplayProtectionPolicy")
        self._request_ids: dict[str, datetime] = {}
        self._nonces: dict[tuple[tuple[str, str, str | None], str], datetime] = {}
        self._idempotency: dict[
            tuple[tuple[str, str, str | None], str, str], _Reservation
        ] = {}
        self._lock = Lock()

    @property
    def reservation_counts(self) -> tuple[int, int, int]:
        with self._lock:
            return (
                len(self._request_ids),
                len(self._nonces),
                len(self._idempotency),
            )

    def evaluate(
        self,
        scope: ReplayProtectionScope,
        envelope: Phase4RequestEnvelope,
        *,
        evaluated_at: datetime,
    ) -> ReplayProtectionDecision:
        if not isinstance(scope, ReplayProtectionScope):
            raise ValueError("scope must be ReplayProtectionScope")
        if not isinstance(envelope, Phase4RequestEnvelope):
            raise ValueError("envelope must be Phase4RequestEnvelope")
        now = _utc(evaluated_at, "evaluated_at")
        if envelope.issued_at > now + self._policy.maximum_future_skew:
            return _decision(ReplayProtectionCode.FUTURE_TIMESTAMP)
        if now - envelope.issued_at > self._policy.maximum_age:
            return _decision(ReplayProtectionCode.STALE_TIMESTAMP)
        if envelope.effect is RequestEffect.READ_ONLY:
            return _decision(ReplayProtectionCode.READ_ONLY_VALID)

        expires_at = now + self._policy.reservation_ttl
        nonce_key = (scope.key, envelope.nonce)
        idempotency_key = (scope.key, envelope.operation, envelope.idempotency_key)
        with self._lock:
            request_expiry = self._request_ids.get(envelope.request_id)
            if request_expiry is not None and request_expiry > now:
                return _decision(ReplayProtectionCode.REQUEST_ID_REPLAY)
            nonce_expiry = self._nonces.get(nonce_key)
            if nonce_expiry is not None and nonce_expiry > now:
                return _decision(ReplayProtectionCode.NONCE_REPLAY)
            existing = self._idempotency.get(idempotency_key)
            if existing is not None and existing.expires_at > now:
                if existing.payload_sha256 != envelope.payload_sha256:
                    return _decision(ReplayProtectionCode.IDEMPOTENCY_CONFLICT)
                self._prune(now)
                self._request_ids[envelope.request_id] = expires_at
                self._nonces[nonce_key] = expires_at
                return _decision(ReplayProtectionCode.IDEMPOTENT_REPLAY)

            self._prune(now)
            self._request_ids[envelope.request_id] = expires_at
            self._nonces[nonce_key] = expires_at
            self._idempotency[idempotency_key] = _Reservation(
                envelope.payload_sha256,
                expires_at,
            )
            return _decision(ReplayProtectionCode.FRESH_REQUEST)

    def _prune(self, now: datetime) -> None:
        self._request_ids = {
            key: expiry for key, expiry in self._request_ids.items() if expiry > now
        }
        self._nonces = {
            key: expiry for key, expiry in self._nonces.items() if expiry > now
        }
        self._idempotency = {
            key: reservation
            for key, reservation in self._idempotency.items()
            if reservation.expires_at > now
        }
