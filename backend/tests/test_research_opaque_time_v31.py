from dataclasses import asdict, replace
from datetime import datetime, timedelta

import pytest

from backend.tests.research_opaque_time_v31 import compare_reference, sequence_group_oracle
from backend.tests.test_closed_bar_aggregation_v29r import minutes


CONTRACT = "V29R_CHICAGO_OPEN_REFERENCE_ONLY"


def test_aligned_complete_reference_is_positive_equivalence_control():
    result = compare_reference(minutes(181), declared_reference_contract=CONTRACT)
    assert result["canonical_HTF_counts"] == result["sequence_group_counts"] == {"15m": 12, "1h": 3}
    assert result["counters"]["HTF_context_difference_decisions"] == 0
    assert result["counters"]["full_decision_differences"] == 0
    assert result["decision_digests"][0] == result["decision_digests"][1]


def test_unaligned_reference_changes_completed_HTF_membership():
    data = minutes(60, datetime(2026, 8, 3, 9, 1))
    before = [asdict(c) for c in data]
    result = compare_reference(data, declared_reference_contract=CONTRACT)
    assert result["canonical_HTF_counts"] == {"15m": 3, "1h": 0}
    assert result["sequence_group_counts"] == {"15m": 4, "1h": 1}
    assert result["first_context_difference"]["source_index_1based"] == 15
    assert result["counters"]["HTF_context_difference_decisions"] > 0
    assert [asdict(c) for c in data] == before


def test_gap_resets_pending_only_and_never_bridges_or_flushes_partial():
    data = minutes(15) + minutes(74, datetime(2026, 8, 3, 9, 17))
    snapshots = list(sequence_group_oracle(data))
    assert snapshots[14][1] == {"15m": 1, "1h": 0}
    assert snapshots[15][1] == {"15m": 1, "1h": 0}
    assert snapshots[-1][1] == {"15m": 5, "1h": 1}
    bar = snapshots[-1][0]["1h"][0]
    assert bar.timestamp == datetime(2026, 8, 3, 9, 17)
    assert bar.volume == sum(c.volume for c in data[15:75])


def test_future_changes_cannot_affect_either_earlier_decision_arm():
    original = minutes(200, datetime(2026, 8, 3, 9, 1))
    changed = [replace(c, high=c.high+500, volume=c.volume+999) if i>=100 else c for i,c in enumerate(original)]
    a = compare_reference(original, declared_reference_contract=CONTRACT, retain_trace=True)
    b = compare_reference(changed, declared_reference_contract=CONTRACT, retain_trace=True)
    assert [r for r in a["trace"] if r["index"]<=100] == [r for r in b["trace"] if r["index"]<=100]


def test_opaque_labels_not_silently_declared_canonical():
    with pytest.raises(ValueError, match="explicit reference"):
        compare_reference(minutes(20), declared_reference_contract="UNKNOWN")
    with pytest.raises(ValueError, match="strictly ordered"):
        list(sequence_group_oracle([minutes(1)[0]]*2))


def test_new_contract_oracle_starts_empty_and_snapshots_are_detached():
    first = list(sequence_group_oracle(minutes(60)))
    first[-1][0]["1h"][0].close = -1
    second = list(sequence_group_oracle(minutes(14)))
    assert second[-1][1] == {"15m": 0, "1h": 0}
    again = list(sequence_group_oracle(minutes(60)))
    assert again[-1][0]["1h"][0].close > 0
