from datetime import date, datetime, timedelta
from hashlib import sha256
import xml.etree.ElementTree as ET

import pytest

from backend.tests.research_ninjatrader_provenance_v31 import (
    CHICAGO, DAYS, OPEN, UTC, ZONES, analyze_file, canonical_hypothesis,
    expected_open_minutes, possible_instants, read_template, template_placement,
)


def fixture_template(tmp_path):
    root = ET.Element("NinjaTrader")
    node = ET.SubElement(root, "TradingHours")
    ET.SubElement(node, "TimeZone").text = "Central Standard Time"
    sessions = ET.SubElement(node, "Sessions")
    for i in range(5):
        s = ET.SubElement(sessions, "Session")
        for key, value in {"BeginDay": DAYS[(i-1) % 7], "BeginTime": "1700",
                           "EndDay": DAYS[i], "EndTime": "1600", "TradingDay": DAYS[i]}.items():
            ET.SubElement(s, key).text = value
    holidays = ET.SubElement(node, "HolidaysSerializable")
    h = ET.SubElement(holidays, "Holiday")
    ET.SubElement(h, "Date").text = "2024-03-29T00:00:00"
    ET.SubElement(h, "Description").text = "Synthetic full closure fixture"
    partials = ET.SubElement(node, "PartialHolidaysSerializable")
    for day, early, value in [("2024-05-27", True, "1200"), ("2024-12-25", False, "1700")]:
        h = ET.SubElement(partials, "PartialHoliday")
        ET.SubElement(h, "Date").text = day + "T00:00:00"
        ET.SubElement(h, "Description").text = "Synthetic partial fixture"
        ET.SubElement(h, "IsEarlyEnd").text = str(early).lower()
        ET.SubElement(h, "IsLateBegin").text = str(not early).lower()
        ET.SubElement(h, "Sessions")
        c = ET.SubElement(h, "Constraint")
        edge = "End" if early else "Begin"
        for key, text in {"TradingDay": DAYS[date.fromisoformat(day).weekday()],
                          edge + "Day": DAYS[date.fromisoformat(day).weekday()], edge + "Time": value}.items():
            ET.SubElement(c, key).text = text
    path = tmp_path / "template.xml"
    path.write_bytes(ET.tostring(root))
    return path


@pytest.mark.parametrize("zone,hour", [("Eastern", 22), ("Central", 23), ("UTC", 17)])
@pytest.mark.parametrize("label,minute", [("open", 1), ("end", 0)])
def test_six_interpretations_do_not_conflate_timezones(zone, hour, label, minute):
    opened, available = canonical_hypothesis(datetime(2024, 1, 8, 23, 1), ZONES[zone], label)
    assert (opened.hour, opened.minute) == (hour, minute)
    assert available-opened.astimezone(UTC) == timedelta(minutes=1)


@pytest.mark.parametrize("zone", ["Eastern", "Central"])
@pytest.mark.parametrize("label,count", [(datetime(2024, 3, 10, 2, 30), 0),
                                         (datetime(2024, 11, 3, 1, 30), 2)])
def test_local_dst_fold_and_gap_never_guessed(zone, label, count):
    assert len(possible_instants(label, ZONES[zone])) == count
    with pytest.raises(ValueError, match="ambiguous"):
        canonical_hypothesis(label, ZONES[zone], "end")


@pytest.mark.parametrize("raw,offset", [(datetime(2024, 3, 10, 8), -6), (datetime(2024, 11, 3, 7), -5)])
def test_native_utc_end_subtracts_elapsed_minute_across_dst(raw, offset):
    opened, available = canonical_hypothesis(raw, UTC, "end")
    assert (opened.hour, opened.minute) == (1, 59)
    assert opened.utcoffset() == timedelta(hours=offset)
    assert available == raw.replace(tzinfo=UTC)


def test_template_eod_full_early_late_and_normal_boundaries(tmp_path):
    template = read_template(fixture_template(tmp_path))
    def status(text):
        return template_placement(datetime.fromisoformat(text).replace(tzinfo=CHICAGO), template)
    assert status("2024-03-28T17:00") == "HOLIDAY_FULL_CLOSE"
    assert status("2024-03-29T10:00") == "HOLIDAY_FULL_CLOSE"
    assert status("2024-05-27T11:59") == OPEN
    assert status("2024-05-27T12:00") == "HOLIDAY_EARLY_CLOSE"
    assert status("2024-05-27T16:00") == "WEEKDAY_MAINTENANCE"
    assert status("2024-05-27T17:00") == OPEN
    assert status("2024-12-24T17:00") == "HOLIDAY_LATE_OPEN"
    assert status("2024-12-25T17:00") == OPEN
    assert status("2024-06-02T16:59") == "SUNDAY_BEFORE_REOPEN"
    assert status("2024-06-02T17:00") == OPEN


def test_expected_slots_exclude_holidays_maintenance_and_post_expiry(tmp_path):
    template = read_template(fixture_template(tmp_path))
    start = datetime(2024, 5, 26, 17, tzinfo=CHICAGO)
    end = datetime(2024, 5, 27, 17, tzinfo=CHICAGO)
    assert expected_open_minutes(start, end, end+timedelta(days=1), template) == 19*60+1
    assert expected_open_minutes(start, end, start+timedelta(minutes=3), template) == 3


def test_prior_exception_reconciliation_never_clears_a_closed_hours_row(tmp_path):
    template = read_template(fixture_template(tmp_path))
    content = b"20240527 170000;100;100;100;100;1\n20240527 170100;100;100;100;100;1\n20240527 210100;100;100;100;100;1\n"
    path = tmp_path / "native.txt"
    path.write_bytes(content)
    record = {"source_path": str(path), "contract": "JUN24", "sha256_before": sha256(content).hexdigest(),
              "exceptions": [{"line": 3, "raw_label": "2024-05-27T21:01:00", "weekly_placement": "WEEKDAY_MAINTENANCE"}]}
    result = analyze_file(record, template)
    assert len(result["hypotheses"]) == 6
    assert result["hypotheses"]["UTC_end"]["counts"]["weekly_mismatch_rows"] == 1
    assert result["hypotheses"]["UTC_end"]["counts"]["holiday_additional_mismatch_rows"] == 1
    assert result["prior_exceptions"][0]["category"] == "unexplained"
    assert result["prior_exceptions"][0]["admitted"] is False
    assert result["certification"] == "BLOCKED"
    assert path.read_bytes() == content
    with pytest.raises(ValueError, match="hash"):
        analyze_file({**record, "sha256_before": "0"*64}, template)


def test_template_changes_fail_closed(tmp_path):
    path = fixture_template(tmp_path)
    path.write_bytes(path.read_bytes().replace(b"<BeginTime>1700", b"<BeginTime>1800", 1))
    with pytest.raises(ValueError, match="weekly"):
        read_template(path)
