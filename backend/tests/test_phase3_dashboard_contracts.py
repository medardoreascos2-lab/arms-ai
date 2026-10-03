from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.phase3.dashboard_contracts import (
    DashboardProjection, DashboardProjectionKind, Phase3DashboardBundle, REQUIRED_FIELDS,
)

NOW = datetime(2026, 10, 3, 17, tzinfo=timezone.utc)


def projection(kind: DashboardProjectionKind) -> DashboardProjection:
    fields = tuple(sorted((name, value(name)) for name in REQUIRED_FIELDS[kind]))
    return DashboardProjection(f"projection-{kind.value.lower()}", kind, NOW, "a"*64, fields)


def value(name: str):
    if name in {"trading_blocked", "payout_eligible", "human_decision_required"}:
        return False
    if name in {"open_positions", "revision"}:
        return 0
    return "0"


def bundle() -> Phase3DashboardBundle:
    items = tuple(projection(kind) for kind in sorted(DashboardProjectionKind, key=lambda item: item.value))
    return Phase3DashboardBundle(NOW, items)


def test_bundle_contains_every_required_frontend_independent_contract() -> None:
    result = bundle()
    assert {item.kind for item in result.projections} == set(DashboardProjectionKind)
    assert result.frontend_independent is True
    assert result.execution_authorized is False
    assert all(item.read_only and not item.execution_authorized for item in result.projections)


def test_required_fields_are_exact_for_each_projection_kind() -> None:
    for item in bundle().projections:
        assert set(dict(item.fields)) == set(REQUIRED_FIELDS[item.kind])


def test_missing_extra_or_unsorted_fields_are_rejected() -> None:
    item = projection(DashboardProjectionKind.ACCOUNT_STATUS)
    with pytest.raises(ValueError, match="projection contract"):
        replace(item, fields=item.fields[:-1])
    with pytest.raises(ValueError, match="projection contract"):
        replace(item, fields=tuple(sorted(item.fields + (("extra", "x"),))))
    with pytest.raises(ValueError, match="sorted"):
        replace(item, fields=tuple(reversed(item.fields)))


def test_bundle_rejects_missing_duplicate_or_unsorted_kinds() -> None:
    items = bundle().projections
    with pytest.raises(ValueError, match="every kind"):
        Phase3DashboardBundle(NOW, items[:-1])
    with pytest.raises(ValueError, match="every kind"):
        Phase3DashboardBundle(NOW, items[:-1] + (items[0],))
    with pytest.raises(ValueError, match="every kind"):
        Phase3DashboardBundle(NOW, tuple(reversed(items)))


def test_hashes_and_documents_are_deterministic() -> None:
    first = bundle()
    second = bundle()
    assert first.bundle_hash == second.bundle_hash
    assert first.document() == second.document()


def test_naive_timestamps_and_invalid_source_hashes_are_rejected() -> None:
    item = projection(DashboardProjectionKind.PORTFOLIO)
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(item, observed_at=datetime(2026, 10, 3))
    with pytest.raises(ValueError, match="SHA-256"):
        replace(item, source_hash="bad")


def test_contract_values_accept_only_json_scalars() -> None:
    item = projection(DashboardProjectionKind.ACCOUNT_STATUS)
    fields = tuple((key, [] if key == "equity" else val) for key, val in item.fields)
    with pytest.raises(ValueError, match="JSON scalar"):
        replace(item, fields=fields)
