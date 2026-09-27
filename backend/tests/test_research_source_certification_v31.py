from datetime import datetime
from hashlib import sha256

import pytest

from backend.tests.research_source_certification_v31 import (
    REQUIRED_GATES, analyze_source, certification_status, hypothetical_open,
    naive_dst_status, parse_row, standard_expiry, weekly_placement,
)


@pytest.mark.parametrize("raw,expected", [
    ("2022-03-14T22:01:00", "2022-03-14T17:00:00-05:00"),
    ("2022-12-13T23:01:00", "2022-12-13T17:00:00-06:00"),
    ("2025-03-09T02:14:00", "2025-03-08T20:13:00-06:00"),
    ("2024-11-03T06:31:00", "2024-11-03T01:30:00-05:00"),
    ("2024-11-03T07:31:00", "2024-11-03T01:30:00-06:00"),
])
def test_analysis_mapping_uses_elapsed_utc_minute(raw, expected):
    assert hypothetical_open(datetime.fromisoformat(raw)).isoformat() == expected


@pytest.mark.parametrize("instant,category", [
    ("2022-06-14T15:59:00-05:00", "WITHIN_NORMAL_WEEKLY_HOURS"),
    ("2022-06-14T16:00:00-05:00", "WEEKDAY_MAINTENANCE"),
    ("2022-06-14T17:00:00-05:00", "WITHIN_NORMAL_WEEKLY_HOURS"),
    ("2022-06-17T16:00:00-05:00", "FRIDAY_AFTER_CLOSE"),
    ("2022-06-18T12:00:00-05:00", "SATURDAY_CLOSED"),
    ("2022-06-19T16:59:00-05:00", "SUNDAY_BEFORE_REOPEN"),
    ("2022-06-19T17:00:00-05:00", "WITHIN_NORMAL_WEEKLY_HOURS"),
])
def test_exception_time_placement_does_not_guess_origin(instant, category):
    assert weekly_placement(datetime.fromisoformat(instant)) == category


@pytest.mark.parametrize("gate", REQUIRED_GATES)
def test_missing_or_supporting_evidence_cannot_certify(gate):
    gates = dict.fromkeys(REQUIRED_GATES, "PASS")
    for value in (None, False, True, "SUPPORTING_ONLY", "UNRESOLVED"):
        gates[gate] = value
        assert certification_status(gates) == "BLOCKED"
    del gates[gate]
    assert certification_status(gates) == "BLOCKED"


def test_dst_counterfactual_rejects_nonexistent_and_distinguishes_fold():
    assert naive_dst_status(datetime(2025, 3, 9, 2, 14)) == "nonexistent"
    assert naive_dst_status(datetime(2024, 11, 3, 1, 30)) == "ambiguous"
    assert naive_dst_status(datetime(2024, 11, 3, 2, 30)) == "valid"
    assert standard_expiry("JUN25").isoformat() == "2025-06-20T08:30:00-05:00"
    with pytest.raises(ValueError, match="outside reviewed"):
        standard_expiry("JUN26")


def test_read_only_analysis_keeps_exceptions_and_does_not_certify(tmp_path):
    source = tmp_path / "NQ_JUN22.txt"
    content = b"20220614 210000;100;101;99;100;5\n20220614 220100;100;100;100;100;2\n20220618 170000;100;100;100;100;1\n"
    source.write_bytes(content)
    digest = sha256(content).hexdigest()
    result = analyze_source(source, "JUN22", digest)
    assert result == analyze_source(source, "JUN22", digest)
    assert source.read_bytes() == content
    assert list(tmp_path.iterdir()) == [source]
    assert result["raw_rows"] == 3
    assert result["maintenance_evidence"]["aligned_61_minute_gaps"] == 1
    assert result["exception_count"] == 1
    exception = result["exceptions"][0]
    assert exception["line"] == 3 and exception["flat"]
    assert exception["weekly_placement"] == "SATURDAY_CLOSED"
    assert exception["lifecycle_placement"] == "AFTER_STANDARD_TERMINATION"
    assert exception["resolution"] == "UNEXPLAINED_SOURCE_OBSERVATION"
    assert exception["admitted"] is False
    assert result["certification_status"] == "BLOCKED"


def test_hash_mismatch_fails_before_analysis(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("20220614 210000;100;100;100;100;1\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="hash mismatch"):
        analyze_source(path, "JUN22", "0" * 64)
    assert path.read_bytes() == before


@pytest.mark.parametrize("row", [
    "20220614 210001;100;100;100;100;1",
    "20220614 210000;100;99;101;100;1",
    "20220614 210000;100;100;100;100;-1",
    "20220614 210000;100;100;100;100;1.5",
    "20220614 210000;NaN;100;100;100;1",
])
def test_invalid_source_not_repaired(row):
    with pytest.raises(ValueError):
        parse_row(row)
