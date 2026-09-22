"""Focused offline tests for ArmsTimestampDomainProbeV1."""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools.verify_timestamp_domain_probe_v1 import verify_evidence


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "integrations/ninjatrader/ArmsTimestampDomainProbeV1.cs"
)

HARNESS = (
    ROOT
    / "backend/tests/fixtures/"
      "timestamp_domain_probe_harness_sprint16ar52.cs"
)

CSC = (
    Path(os.environ.get("WINDIR", "C:/Windows"))
    / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
)

SDK = Path("C:/Program Files/NinjaTrader 8/bin")


@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    target = (
        tmp_path_factory.mktemp("r52-probe")
        / "harness.exe"
    )

    result = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/out:" + str(target),
            "/r:System.ComponentModel.DataAnnotations.dll",
            "/r:System.Web.Extensions.dll",
            "/r:System.Core.dll",
            str(SOURCE),
            str(HARNESS),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    return target


def run(binary, folder, mode):
    folder.mkdir()

    result = subprocess.run(
        [
            str(binary),
            mode,
            str(folder),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    counts = json.loads(result.stdout)

    diagnostic = (
        folder / "timestamp-domain-probe.jsonl"
    )

    seal_path = (
        folder / "timestamp-domain-probe.done.json"
    )

    raw = (
        diagnostic.read_bytes()
        if diagnostic.exists()
        else None
    )

    seal = (
        seal_path.read_bytes()
        if seal_path.exists()
        else None
    )

    rows = (
        [
            json.loads(line)
            for line in raw.splitlines()
        ]
        if raw
        else []
    )

    return counts, rows, raw, seal


def reseal(rows, original):
    raw = (
        b"".join(
            json.dumps(
                row,
                separators=(",", ":"),
            ).encode() + b"\n"
            for row in rows
        )
    )

    seal = json.loads(original)

    seal["sha256"] = sha256(raw).hexdigest()
    seal["records"] = len(rows)
    seal["bytes"] = len(raw)

    return (
        raw,
        json.dumps(
            seal,
            separators=(",", ":"),
        ).encode(),
    )


@pytest.mark.parametrize(
    "mode,utc,unspecified,local,transitions",
    [
        ("mixed", 2, 3, 0, 1),
        ("all_unspecified", 0, 5, 0, 0),
        ("local", 0, 0, 5, 0),
        ("normal", 5, 0, 0, 0),
    ],
)
def test_kind_characterization(
    binary,
    tmp_path,
    mode,
    utc,
    unspecified,
    local,
    transitions,
):
    counts, rows, raw, seal = run(
        binary,
        tmp_path / mode,
        mode,
    )

    result = verify_evidence(raw, seal)

    assert result["status"] == "PASS"
    assert result["utc_count"] == utc
    assert result["unspecified_count"] == unspecified
    assert result["local_count"] == local
    assert result["transition_count"] == transitions

    assert counts["request_creates"] == 1
    assert counts["request_invokes"] == 1

    assert counts["session_iterator_calls"] == 0
    assert counts["account_access"] is False
    assert counts["order_calls"] == 0
    assert counts["timestamp_conversion"] is False
    assert counts["ninjatrader_assemblies_loaded"] == 0


@pytest.mark.parametrize(
    "mode,duplicate,decreasing,misaligned",
    [
        ("duplicate", 1, 0, 0),
        ("decreasing", 0, 1, 0),
        ("misaligned", 0, 0, 1),
    ],
)
def test_raw_anomalies_are_observed_not_repaired(
    binary,
    tmp_path,
    mode,
    duplicate,
    decreasing,
    misaligned,
):
    _, _, raw, seal = run(
        binary,
        tmp_path / mode,
        mode,
    )

    result = verify_evidence(raw, seal)

    assert result["duplicate_count"] == duplicate
    assert result["decreasing_count"] == decreasing
    assert (
        result["minute_misalignment_count"]
        == misaligned
    )

    assert result["session_iterator_calls"] == 0
    assert result["timestamp_conversion"] is False


@pytest.mark.parametrize(
    "mode",
    [
        "closed",
        "no_flow",
        "unstable",
        "timezone",
        "playback",
        "request_throw",
        "callback_error",
        "wrong_callback",
        "wrong_instrument",
        "wrong_period",
        "provider_policy",
        "wrong_template",
        "empty",
        "too_many",
        "too_many_dates",
        "too_many_transitions",
        "gettime_throw",
        "snapshot_mutated",
        "changed_properties",
        "terminated",
        "record_cap",
        "byte_cap",
    ],
)
def test_fail_closed_has_no_valid_seal(
    binary,
    tmp_path,
    mode,
):
    counts, rows, raw, seal = run(
        binary,
        tmp_path / mode,
        mode,
    )

    assert seal is None

    with pytest.raises(ValueError):
        verify_evidence(raw, seal)

    assert counts["session_iterator_calls"] == 0
    assert counts["account_access"] is False
    assert counts["order_calls"] == 0


@pytest.mark.parametrize(
    "mode",
    [
        "inline",
        "async",
    ],
)
def test_callback_shapes_do_not_duplicate_results(
    binary,
    tmp_path,
    mode,
):
    counts, rows, raw, seal = run(
        binary,
        tmp_path / mode,
        mode,
    )

    result = verify_evidence(raw, seal)

    assert result["status"] == "PASS"
    assert len(rows) == 6

    assert counts["request_creates"] == 1
    assert counts["request_invokes"] == 1


def test_clone_fails_closed_without_seal(
    binary,
    tmp_path,
):
    counts, rows, raw, seal = run(
        binary,
        tmp_path / "clone-fail-closed",
        "clone",
    )

    assert raw is not None
    assert seal is None

    assert rows[-1]["stage"] == "ATTEMPT_FAILED"
    assert (
        rows[-1]["operation"]
        == "TERMINATED_INCOMPLETE"
    )
    assert (
        rows[-1]["exception_type"]
        == "InvalidOperationException"
    )

    assert counts["request_creates"] == 1
    assert counts["request_invokes"] == 1
    assert counts["session_iterator_calls"] == 0
    assert counts["account_access"] is False
    assert counts["order_calls"] == 0


def test_mixed_transition_exact_contract(
    binary,
    tmp_path,
):
    _, rows, raw, seal = run(
        binary,
        tmp_path / "mixed-exact",
        "mixed",
    )

    result = verify_evidence(raw, seal)

    payload = rows[4]["payload"]

    assert payload["first_kind"] == "Unspecified"
    assert payload["last_kind"] == "Utc"

    assert payload["first_unspecified_index"] == 0
    assert payload["last_unspecified_index"] == 2

    assert payload["first_utc_index"] == 3
    assert payload["last_utc_index"] == 4

    assert payload["transition_count"] == 1

    transition = payload["transition_rows"][0]

    assert transition["previous_index"] == 2
    assert transition["index"] == 3

    assert (
        transition["previous_kind"]
        == "Unspecified"
    )

    assert transition["current_kind"] == "Utc"

    assert transition["tick_delta"] == 600000000

    assert result["timestamp_conversion"] is False


@pytest.fixture
def evidence(binary, tmp_path):
    _, rows, raw, seal = run(
        binary,
        tmp_path / "evidence",
        "mixed",
    )

    verify_evidence(raw, seal)

    return rows, raw, seal


@pytest.mark.parametrize(
    "fault",
    [
        "utc_count",
        "transition_count",
        "transition_kind",
        "transition_delta",
        "returned_rows",
        "duplicate_count",
        "bucket_total",
        "conversion",
        "session_calls",
    ],
)
def test_resealed_contradictions_rejected(
    evidence,
    fault,
):
    rows, _, seal = evidence

    changed = deepcopy(rows)
    payload = changed[4]["payload"]

    if fault == "utc_count":
        payload["utc_count"] = 3

    elif fault == "transition_count":
        payload["transition_count"] = 0

    elif fault == "transition_kind":
        payload["transition_rows"][0][
            "current_kind"
        ] = "Unspecified"

    elif fault == "transition_delta":
        payload["transition_rows"][0][
            "tick_delta"
        ] = 1

    elif fault == "returned_rows":
        payload["returned_rows"] = 4

    elif fault == "duplicate_count":
        payload["duplicate_adjacent_timestamps"] = 1

    elif fault == "bucket_total":
        payload["raw_date_buckets"]["2026-09-16"] = 4

    elif fault == "conversion":
        payload["timestamp_conversion"] = True

    elif fault == "session_calls":
        payload["session_iterator_calls"] = 1

    with pytest.raises(ValueError):
        verify_evidence(
            *reseal(changed, seal)
        )


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "records",
        "bytes",
        "request_count",
        "session_calls",
        "conversion",
        "complete",
        "writer",
        "schema",
    ],
)
def test_seal_corruption_rejected(
    evidence,
    fault,
):
    _, raw, original = evidence

    seal = json.loads(original)

    if fault == "hash":
        seal["sha256"] = "0" * 64
    elif fault == "records":
        seal["records"] = 7
    elif fault == "bytes":
        seal["bytes"] += 1
    elif fault == "request_count":
        seal["request_count"] = 2
    elif fault == "session_calls":
        seal["session_iterator_calls"] = 1
    elif fault == "conversion":
        seal["timestamp_conversion"] = True
    elif fault == "complete":
        seal["diagnostic_complete"] = False
    elif fault == "writer":
        seal["writer_closed"] = False
    elif fault == "schema":
        seal["schema"] = "forged"

    encoded = json.dumps(seal).encode()

    with pytest.raises(ValueError):
        verify_evidence(raw, encoded)


def test_structural_safety():
    source = SOURCE.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "new SessionIterator",
        "GetNextSession(",
        "ToUniversalTime(",
        "ToLocalTime(",
        "SpecifyKind(",
        "TimeZoneInfo.ConvertTime",
        "SubmitOrder",
        "CreateOrder",
        "AtmStrategy",
    )

    for token in forbidden:
        assert token not in source

    assert source.count("new BarsRequest(") == 1
    assert source.count("request.Request(") == 1

    assert (
        source.count("session_iterator_calls = 0")
        == 2
    )


def test_installed_sdk_compile(tmp_path):
    if (
        not CSC.exists()
        or not (SDK / "NinjaTrader.Core.dll").exists()
    ):
        pytest.skip("Installed NinjaTrader SDK required")

    shim = tmp_path / "Indicator.cs"

    shim.write_text(
        "namespace NinjaTrader.NinjaScript.Indicators "
        "{ public class Indicator : "
        "NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }",
        encoding="utf-8",
    )

    refs = [
        SDK / "NinjaTrader.Core.dll",
        SDK / "NinjaTrader.Gui.dll",
        CSC.parent / "WPF/WindowsBase.dll",
        "System.ComponentModel.DataAnnotations.dll",
        "System.Web.Extensions.dll",
        "System.Core.dll",
    ]

    result = subprocess.run(
        [
            str(CSC),
            "/nologo",
            "/target:library",
            "/out:" + str(tmp_path / "Probe.dll"),
            *[
                "/r:" + str(reference)
                for reference in refs
            ],
            str(SOURCE),
            str(shim),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )
