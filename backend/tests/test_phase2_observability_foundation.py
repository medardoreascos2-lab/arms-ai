from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.observability import (
    InMemoryPhase2TelemetrySink,
    Phase2Event,
    Phase2EventSeverity,
    Phase2Metric,
    Phase2MetricUnit,
    Phase2Observability,
    Phase2TelemetryCategory,
    TelemetryWriteStatus,
    safe_telemetry_attributes,
)


NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)


def _observability(capacity: int = 100):
    sink = InMemoryPhase2TelemetrySink(capacity=capacity)
    return Phase2Observability(sink, clock=lambda: NOW), sink


def test_standard_recorders_cover_all_required_categories_and_names():
    observability, sink = _observability()

    results = (
        observability.record_rule_evaluation(
            outcome="BLOCKED",
            accepted=False,
            duration_ms=Decimal("2.5"),
            firm_id="topstep",
            program_id="xfa",
            profile_version="2026.10",
        ),
        observability.record_profile_freshness(
            status="FRESH",
            age_seconds=Decimal("30"),
            firm_id="topstep",
            program_id="xfa",
            profile_version="2026.10",
        ),
        observability.record_api_call(
            operation="get_account_status",
            outcome="SUCCESS",
            duration_ms=Decimal("4.25"),
        ),
        observability.record_notification(
            provider="TEST",
            status="DELIVERED",
            attempts=1,
            event_type="RULE_BLOCKED",
        ),
        observability.record_account_analytics(
            operation="portfolio_summary",
            outcome="PARTIAL",
            account_count=3,
            missing_data_count=1,
            duration_ms=Decimal("7"),
        ),
    )

    assert all(result.status is TelemetryWriteStatus.RECORDED for result in results)
    records = sink.snapshot()
    assert {record.category for record in records} == set(Phase2TelemetryCategory)
    assert all(record.name.startswith("arms.phase2.") for record in records)
    assert {
        record.name for record in records
    } >= {
        "arms.phase2.rule_evaluation.completed",
        "arms.phase2.rule_evaluation.duration",
        "arms.phase2.profile_freshness.age",
        "arms.phase2.api_call.duration",
        "arms.phase2.notification.attempts",
        "arms.phase2.account_analytics.missing_data",
    }
    assert all(record.execution_authorized is False for record in records)
    assert all(record.canonical_admin_authorized is False for record in records)
    assert all(result.execution_authorized is False for result in results)
    assert all(result.canonical_admin_authorized is False for result in results)


def test_standard_records_contain_only_sanitized_aggregate_attributes():
    observability, sink = _observability()

    observability.record_notification(
        provider="TELEGRAM",
        status="RETRY_EXHAUSTED",
        attempts=3,
        event_type="PAYOUT_ELIGIBLE",
    )

    records = sink.snapshot()
    assert records
    assert all(
        dict(record.attributes) == {
            "event_type": "PAYOUT_ELIGIBLE",
            "provider": "TELEGRAM",
            "status": "RETRY_EXHAUSTED",
        }
        for record in records
    )
    serialized = repr(records).lower()
    for forbidden in ("token", "password", "payload", "destination", "account_id"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("attributes", "match"),
    [
        ({"api_key": "abc"}, "sensitive"),
        ({"account_id": "acct-1"}, "sensitive"),
        ({"safe": "Bearer abc"}, "sensitive"),
        ({"safe": "contains spaces"}, "safe label"),
        ({"safe": 1.5}, "safe strings"),
        ({"safe": ["nested"]}, "safe strings"),
        ({"safe": Decimal("NaN")}, "safe strings"),
    ],
)
def test_attributes_reject_sensitive_or_unbounded_data(attributes, match):
    with pytest.raises(ValueError, match=match):
        safe_telemetry_attributes(attributes)


def test_direct_records_reject_malformed_unsorted_and_duplicate_attributes():
    base = {
        "name": "arms.phase2.api_call.count",
        "category": Phase2TelemetryCategory.API_CALL,
        "value": Decimal(1),
        "unit": Phase2MetricUnit.COUNT,
        "observed_at": NOW,
    }

    with pytest.raises(ValueError, match="immutable tuple"):
        Phase2Metric(**base, attributes=[("outcome", "SUCCESS")])
    with pytest.raises(ValueError, match="key/value pairs"):
        Phase2Metric(**base, attributes=(("outcome", "SUCCESS", "extra"),))
    with pytest.raises(ValueError, match="duplicate"):
        Phase2Metric(
            **base,
            attributes=(("outcome", "SUCCESS"), ("outcome", "FAILED")),
        )
    with pytest.raises(ValueError, match="sorted and safe"):
        Phase2Metric(
            **base,
            attributes=(("status", "OK"), ("operation", "read")),
        )


def test_records_require_aware_timestamps_and_valid_namespace():
    with pytest.raises(ValueError, match="timezone-aware"):
        Phase2Event(
            "arms.phase2.api_call.completed",
            Phase2TelemetryCategory.API_CALL,
            Phase2EventSeverity.INFO,
            datetime(2026, 10, 3, 13, 0),
        )
    with pytest.raises(ValueError, match="arms.phase2"):
        Phase2Event(
            "arms.v8.api_call.completed",
            Phase2TelemetryCategory.API_CALL,
            Phase2EventSeverity.INFO,
            NOW,
        )


def test_recorders_reject_invalid_counts_durations_and_clock():
    observability, _ = _observability()
    with pytest.raises(ValueError, match="duration_ms"):
        observability.record_api_call(
            operation="read",
            outcome="SUCCESS",
            duration_ms=Decimal("-0.1"),
        )
    with pytest.raises(ValueError, match="cannot exceed"):
        observability.record_account_analytics(
            operation="summary",
            outcome="PARTIAL",
            account_count=1,
            missing_data_count=2,
            duration_ms=Decimal(1),
        )
    with pytest.raises(ValueError, match="attempts"):
        observability.record_notification(
            provider="TEST",
            status="FAILED",
            attempts=True,
            event_type="RULE_BLOCKED",
        )
    invalid_clock = Phase2Observability(
        InMemoryPhase2TelemetrySink(),
        clock=lambda: datetime(2026, 10, 3, 13, 0),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        invalid_clock.record_api_call(
            operation="read",
            outcome="SUCCESS",
            duration_ms=Decimal(1),
        )


def test_profile_freshness_without_age_omits_age_metric():
    observability, sink = _observability()

    result = observability.record_profile_freshness(
        status="UNKNOWN",
        age_seconds=None,
        firm_id="apex",
        program_id="performance",
        profile_version="2026.10",
    )

    assert result.recorded_records == 2
    assert all(not record.name.endswith(".age") for record in sink.snapshot())


def test_bounded_sink_rejects_whole_batch_without_partial_write():
    observability, sink = _observability(capacity=3)
    first = observability.record_api_call(
        operation="read",
        outcome="SUCCESS",
        duration_ms=Decimal(1),
    )
    before = sink.snapshot()

    second = observability.record_notification(
        provider="TEST",
        status="DELIVERED",
        attempts=1,
        event_type="RULE_BLOCKED",
    )

    assert first.status is TelemetryWriteStatus.RECORDED
    assert second.status is TelemetryWriteStatus.SINK_UNAVAILABLE
    assert second.recorded_records == 0
    assert sink.snapshot() == before


def test_sink_exception_is_contained_without_error_or_secret_detail():
    class FailingSink:
        def write(self, records):
            raise RuntimeError("password=do-not-leak")

    observability = Phase2Observability(FailingSink(), clock=lambda: NOW)
    result = observability.record_api_call(
        operation="read",
        outcome="FAILED",
        duration_ms=Decimal(1),
    )

    assert result.status is TelemetryWriteStatus.SINK_UNAVAILABLE
    assert result.attempted_records == 3
    assert result.recorded_records == 0
    assert "do-not-leak" not in repr(result)
    assert result.execution_authorized is False


def test_records_and_snapshots_are_immutable_views():
    observability, sink = _observability()
    observability.record_api_call(
        operation="read",
        outcome="SUCCESS",
        duration_ms=Decimal(1),
    )

    snapshot = sink.snapshot()
    assert isinstance(snapshot, tuple)
    with pytest.raises(FrozenInstanceError):
        snapshot[0].name = "arms.phase2.changed"
