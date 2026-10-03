"""R45C tests for request tracing and fail-closed replay protection."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from backend.phase4.request_replay import (
    Phase4RequestEnvelope,
    ReplayProtectionCode,
    ReplayProtectionPolicy,
    ReplayProtectionScope,
    RequestEffect,
    RequestReplayProtector,
)


NOW = datetime(2026, 10, 4, 4, 0, tzinfo=timezone.utc)
SCOPE = ReplayProtectionScope("service.reader", "tenant-a", "account-1")
DIGEST = sha256(b'{"operation":"backup"}').hexdigest()


def state_request(
    sequence: int,
    *,
    issued_at: datetime = NOW,
    idempotency_key: str = "idem-key-0001",
    payload_sha256: str = DIGEST,
) -> Phase4RequestEnvelope:
    return Phase4RequestEnvelope(
        request_id=f"request-{sequence:04d}",
        operation="LOCAL_BACKUP_CREATE",
        issued_at=issued_at,
        effect=RequestEffect.STATE_CHANGE,
        nonce=f"nonce-{sequence:04d}",
        idempotency_key=idempotency_key,
        payload_sha256=payload_sha256,
    )


def test_read_only_request_id_is_traceable_without_reserving_replay_state():
    protector = RequestReplayProtector()
    request = Phase4RequestEnvelope(
        "request-read-0001",
        "HEALTH_READ",
        NOW,
        RequestEffect.READ_ONLY,
    )
    first = protector.evaluate(SCOPE, request, evaluated_at=NOW)
    second = protector.evaluate(SCOPE, request, evaluated_at=NOW)
    assert first.code is ReplayProtectionCode.READ_ONLY_VALID
    assert second.code is ReplayProtectionCode.READ_ONLY_VALID
    assert protector.reservation_counts == (0, 0, 0)


def test_state_change_requires_nonce_idempotency_and_payload_digest():
    for values in (
        (None, "idem-key-0001", DIGEST),
        ("nonce-0001", None, DIGEST),
        ("nonce-0001", "idem-key-0001", None),
    ):
        with pytest.raises(ValueError, match="require nonce"):
            Phase4RequestEnvelope(
                "request-0001",
                "LOCAL_BACKUP_CREATE",
                NOW,
                RequestEffect.STATE_CHANGE,
                *values,
            )
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        state_request(1, payload_sha256="not-a-digest")


def test_fresh_state_change_is_reserved_but_never_authorizes_execution():
    protector = RequestReplayProtector()
    result = protector.evaluate(SCOPE, state_request(1), evaluated_at=NOW)
    assert result.code is ReplayProtectionCode.FRESH_REQUEST
    assert result.accepted is True
    assert result.replay_safe_to_process is True
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert protector.reservation_counts == (1, 1, 1)


def test_exact_idempotent_retry_is_accepted_without_reprocessing_side_effects():
    protector = RequestReplayProtector()
    protector.evaluate(SCOPE, state_request(1), evaluated_at=NOW)
    replay = protector.evaluate(SCOPE, state_request(2), evaluated_at=NOW)
    assert replay.code is ReplayProtectionCode.IDEMPOTENT_REPLAY
    assert replay.accepted is True
    assert replay.idempotent_replay is True
    assert replay.replay_safe_to_process is False
    assert protector.reservation_counts == (2, 2, 1)


def test_request_id_and_nonce_replays_are_denied_without_state_change():
    protector = RequestReplayProtector()
    original = state_request(1)
    protector.evaluate(SCOPE, original, evaluated_at=NOW)
    before = protector.reservation_counts
    request_replay = protector.evaluate(SCOPE, original, evaluated_at=NOW)
    nonce_replay = Phase4RequestEnvelope(
        "request-0002",
        original.operation,
        NOW,
        RequestEffect.STATE_CHANGE,
        original.nonce,
        "idem-key-0002",
        DIGEST,
    )
    nonce_result = protector.evaluate(SCOPE, nonce_replay, evaluated_at=NOW)
    assert request_replay.code is ReplayProtectionCode.REQUEST_ID_REPLAY
    assert nonce_result.code is ReplayProtectionCode.NONCE_REPLAY
    assert request_replay.accepted is False
    assert nonce_result.replay_safe_to_process is False
    assert protector.reservation_counts == before


def test_idempotency_conflict_is_denied_without_changing_reservations():
    protector = RequestReplayProtector()
    protector.evaluate(SCOPE, state_request(1), evaluated_at=NOW)
    before = protector.reservation_counts
    conflict = protector.evaluate(
        SCOPE,
        state_request(2, payload_sha256=sha256(b"different").hexdigest()),
        evaluated_at=NOW,
    )
    assert conflict.code is ReplayProtectionCode.IDEMPOTENCY_CONFLICT
    assert conflict.accepted is False
    assert protector.reservation_counts == before


def test_timestamps_outside_tolerance_fail_closed_without_reservation():
    protector = RequestReplayProtector()
    stale = protector.evaluate(
        SCOPE,
        state_request(1, issued_at=NOW - timedelta(minutes=5, microseconds=1)),
        evaluated_at=NOW,
    )
    future = protector.evaluate(
        SCOPE,
        state_request(2, issued_at=NOW + timedelta(seconds=30, microseconds=1)),
        evaluated_at=NOW,
    )
    assert stale.code is ReplayProtectionCode.STALE_TIMESTAMP
    assert future.code is ReplayProtectionCode.FUTURE_TIMESTAMP
    assert protector.reservation_counts == (0, 0, 0)


def test_idempotency_is_scoped_by_principal_tenant_account_and_operation():
    protector = RequestReplayProtector()
    protector.evaluate(SCOPE, state_request(1), evaluated_at=NOW)
    other_scope = ReplayProtectionScope("service.reader", "tenant-a", "account-2")
    other_operation = Phase4RequestEnvelope(
        "request-0003",
        "ISOLATED_RESTORE_VALIDATE",
        NOW,
        RequestEffect.STATE_CHANGE,
        "nonce-0003",
        "idem-key-0001",
        DIGEST,
    )
    assert protector.evaluate(
        other_scope, state_request(2), evaluated_at=NOW
    ).code is ReplayProtectionCode.FRESH_REQUEST
    assert protector.evaluate(
        SCOPE, other_operation, evaluated_at=NOW
    ).code is ReplayProtectionCode.FRESH_REQUEST


def test_concurrent_idempotent_requests_allow_only_one_processing_reservation():
    protector = RequestReplayProtector()
    requests = [state_request(sequence) for sequence in range(1, 17)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(
            pool.map(
                lambda request: protector.evaluate(
                    SCOPE,
                    request,
                    evaluated_at=NOW,
                ),
                requests,
            )
        )
    assert sum(item.code is ReplayProtectionCode.FRESH_REQUEST for item in decisions) == 1
    assert sum(item.code is ReplayProtectionCode.IDEMPOTENT_REPLAY for item in decisions) == 15
    assert sum(item.replay_safe_to_process for item in decisions) == 1
    assert protector.reservation_counts == (16, 16, 1)


def test_expired_reservations_can_be_reused_only_after_timestamp_revalidation():
    policy = ReplayProtectionPolicy(
        maximum_age=timedelta(seconds=5),
        maximum_future_skew=timedelta(0),
        reservation_ttl=timedelta(seconds=5),
    )
    protector = RequestReplayProtector(policy)
    protector.evaluate(SCOPE, state_request(1), evaluated_at=NOW)
    renewed = state_request(1, issued_at=NOW + timedelta(seconds=5))
    result = protector.evaluate(
        SCOPE,
        renewed,
        evaluated_at=NOW + timedelta(seconds=5),
    )
    assert result.code is ReplayProtectionCode.FRESH_REQUEST
    assert protector.reservation_counts == (1, 1, 1)


def test_policy_and_envelope_shape_fail_closed():
    with pytest.raises(ValueError, match="complete timestamp window"):
        ReplayProtectionPolicy(reservation_ttl=timedelta(minutes=1))
    with pytest.raises(ValueError, match="cannot carry replay reservations"):
        Phase4RequestEnvelope(
            "request-read-0001",
            "HEALTH_READ",
            NOW,
            RequestEffect.READ_ONLY,
            nonce="nonce-0001",
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        Phase4RequestEnvelope(
            "request-read-0001",
            "HEALTH_READ",
            NOW.replace(tzinfo=None),
            RequestEffect.READ_ONLY,
        )
