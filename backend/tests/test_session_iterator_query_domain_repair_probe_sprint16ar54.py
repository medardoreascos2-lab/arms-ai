from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import pytest

from tools.verify_session_iterator_query_domain_repair_v1 import (
    EVIDENCE,
    SEAL,
    verify_capture,
)


ROOT = Path(__file__).resolve().parents[2]

HOST = (
    ROOT
    / "integrations/ninjatrader/"
      "ArmsSessionIteratorQueryDomainRepairProbeV1.cs"
)

ADAPTER = (
    ROOT
    / "integrations/ninjatrader/"
      "SessionIteratorQueryDomainAdapterV1.cs"
)

COMPARISON = (
    ROOT
    / "integrations/ninjatrader/"
      "SessionIteratorQueryDomainNativeComparisonV1.cs"
)

VERIFIER = (
    ROOT
    / "tools/"
      "verify_session_iterator_query_domain_repair_v1.py"
)

CSC = (
    Path(os.environ.get("WINDIR", "C:/Windows"))
    / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
)

SDK = Path("C:/Program Files/NinjaTrader 8/bin")


def stamp(clock, ticks, kind):
    return {
        "clock": clock,
        "ticks": ticks,
        "kind": kind,
    }


def reference():
    probe = str(uuid.uuid4())

    raw_ticks = 639250164000000001
    adapter_ticks = 639250344000000001

    evidence = {
        "schema":
            "arms.r54.native-repair.record.v1",
        "version":
            "R5.4-C/native-repair-host/1",
        "classification":
            "DIAGNOSTIC_ONLY",
        "origin":
            "OPERATOR_NATIVE_RUN_UNATTESTED",
        "probe_uuid":
            probe,
        "diagnostic_complete":
            True,
        "source_before":
            stamp(
                "2026-09-14T21:00:00.0000001",
                raw_ticks,
                "Unspecified",
            ),
        "source_after":
            stamp(
                "2026-09-14T21:00:00.0000001",
                raw_ticks,
                "Unspecified",
            ),
        "source_preserved":
            True,
        "adapter": {
            "source_ticks":
                raw_ticks,
            "source_kind":
                "Unspecified",
            "query_ticks":
                adapter_ticks,
            "query_kind":
                "Utc",
            "source_offset_ticks":
                -180000000000,
            "zone_id":
                "Central Standard Time",
            "zone_fingerprint_sha256":
                "a" * 64,
            "policy":
                "TradingHoursWallClockToUtc",
            "provenance":
                "R53_NATIVE_REGRESSION",
            "conversion_performed":
                True,
        },
        "observations": [
            {
                "case_id":
                    "C_RAW",
                "query":
                    stamp(
                        "2026-09-14T21:00:00.0000001",
                        raw_ticks,
                        "Unspecified",
                    ),
                "returned":
                    False,
                "begin":
                    None,
                "end":
                    None,
                "bounds_readable":
                    False,
                "bounds_valid":
                    False,
                "constructor_attempts":
                    1,
                "call_attempts":
                    1,
            },
            {
                "case_id":
                    "C_SAME_TICKS",
                "query":
                    stamp(
                        "2026-09-14T21:00:00.0000001",
                        raw_ticks,
                        "Utc",
                    ),
                "returned":
                    False,
                "begin":
                    None,
                "end":
                    None,
                "bounds_readable":
                    False,
                "bounds_valid":
                    False,
                "constructor_attempts":
                    2,
                "call_attempts":
                    2,
            },
            {
                "case_id":
                    "C_ADAPTER",
                "query":
                    stamp(
                        "2026-09-15T02:00:00.0000001",
                        adapter_ticks,
                        "Utc",
                    ),
                "returned":
                    True,
                "begin":
                    stamp(
                        "2026-09-14T22:00:00.0000000",
                        639250200000000000,
                        "Utc",
                    ),
                "end":
                    stamp(
                        "2026-09-15T21:00:00.0000000",
                        639251028000000000,
                        "Utc",
                    ),
                "bounds_readable":
                    True,
                "bounds_valid":
                    True,
                "constructor_attempts":
                    3,
                "call_attempts":
                    3,
            },
        ],
        "iterator_constructor_attempts":
            3,
        "getnextsession_attempts":
            3,
        "expected_pattern_confirmed":
            True,
        "native_provenance_attested":
            False,
        "certification_evidence":
            False,
        "runtime_admission":
            False,
        "execution_authority":
            False,
        "exporter_change":
            False,
        "stored_timestamp_mutation":
            False,
    }

    raw = json.dumps(
        evidence,
        separators=(",", ":"),
    ).encode()

    seal = {
        "schema":
            "arms.r54.native-repair.seal.v1",
        "version":
            "R5.4-C/native-repair-host/1",
        "classification":
            "DIAGNOSTIC_ONLY",
        "origin":
            "OPERATOR_NATIVE_RUN_UNATTESTED",
        "probe_uuid":
            probe,
        "diagnostic_complete":
            True,
        "writer_closed":
            True,
        "evidence_file":
            EVIDENCE,
        "evidence_bytes":
            len(raw),
        "evidence_sha256":
            sha256(raw).hexdigest(),
        "expected_pattern_confirmed":
            True,
        "source_preserved":
            True,
        "iterator_constructor_attempts":
            3,
        "getnextsession_attempts":
            3,
        "native_provenance_attested":
            False,
        "certification_evidence":
            False,
        "runtime_admission":
            False,
        "execution_authority":
            False,
    }

    return evidence, seal


def write_capture(tmp_path, evidence, seal):
    capture = tmp_path / "capture"
    capture.mkdir()

    raw = json.dumps(
        evidence,
        separators=(",", ":"),
    ).encode()

    seal = deepcopy(seal)

    seal["evidence_bytes"] = len(raw)
    seal["evidence_sha256"] = sha256(raw).hexdigest()

    (capture / EVIDENCE).write_bytes(raw)

    (capture / SEAL).write_bytes(
        json.dumps(
            seal,
            separators=(",", ":"),
        ).encode()
    )

    return capture


def test_reference_contract(tmp_path):
    evidence, seal = reference()

    result = verify_capture(
        write_capture(
            tmp_path,
            evidence,
            seal,
        )
    )

    assert (
        result["status"]
        == "PASS_R54_REPAIR_DIAGNOSTIC_CONTRACT_ONLY"
    )

    assert result["source_preserved"] is True

    assert (
        result["expected_pattern_confirmed"]
        is True
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "source_after_ticks",
        "source_after_kind",
        "adapter_source_ticks",
        "adapter_query_same_ticks",
        "wrong_case_order",
        "raw_true",
        "adapter_invalid_bounds",
        "constructor_budget",
        "call_budget",
        "authority_true",
        "exporter_true",
    ),
)
def test_resealed_contradictions_rejected(
    tmp_path,
    mutation,
):
    evidence, seal = reference()

    if mutation == "source_after_ticks":
        evidence["source_after"]["ticks"] += 1

    elif mutation == "source_after_kind":
        evidence["source_after"]["kind"] = "Utc"

    elif mutation == "adapter_source_ticks":
        evidence["adapter"]["source_ticks"] += 1

    elif mutation == "adapter_query_same_ticks":
        ticks = evidence["source_before"]["ticks"]
        evidence["adapter"]["query_ticks"] = ticks
        evidence["observations"][2]["query"]["ticks"] = ticks

    elif mutation == "wrong_case_order":
        evidence["observations"][0]["case_id"] = "C_SAME_TICKS"

    elif mutation == "raw_true":
        evidence["observations"][0].update(
            returned=True,
            begin=evidence["observations"][2]["begin"],
            end=evidence["observations"][2]["end"],
            bounds_readable=True,
            bounds_valid=True,
        )

    elif mutation == "adapter_invalid_bounds":
        evidence["observations"][2]["end"] = (
            deepcopy(
                evidence["observations"][2]["begin"]
            )
        )

    elif mutation == "constructor_budget":
        evidence["iterator_constructor_attempts"] = 4
        seal["iterator_constructor_attempts"] = 4

    elif mutation == "call_budget":
        evidence["getnextsession_attempts"] = 4
        seal["getnextsession_attempts"] = 4

    elif mutation == "authority_true":
        evidence["execution_authority"] = True
        seal["execution_authority"] = True

    elif mutation == "exporter_true":
        evidence["exporter_change"] = True

    capture = write_capture(
        tmp_path,
        evidence,
        seal,
    )

    with pytest.raises(ValueError):
        verify_capture(capture)


def test_adapter_false_is_valid_diagnostic_divergence(
    tmp_path,
):
    evidence, seal = reference()

    evidence["observations"][2].update(
        returned=False,
        begin=None,
        end=None,
        bounds_readable=False,
        bounds_valid=False,
    )

    evidence["expected_pattern_confirmed"] = False
    seal["expected_pattern_confirmed"] = False

    result = verify_capture(
        write_capture(
            tmp_path,
            evidence,
            seal,
        )
    )

    assert (
        result["status"]
        == "PASS_R54_REPAIR_DIAGNOSTIC_CONTRACT_ONLY"
    )

    assert (
        result["expected_pattern_confirmed"]
        is False
    )

    assert result["source_preserved"] is True
    assert result["native_provenance_attested"] is False
    assert result["certification_evidence"] is False
    assert result["runtime_admission"] is False
    assert result["execution_authority"] is False


def test_host_exact_ui_and_one_shot_contract():
    text = HOST.read_text(encoding="utf-8")

    assert text.count("[NinjaScriptProperty]") == 5

    for token in (
        "ProbeEnabled = false",
        'OutputDirectory = ""',
        "MarketReopenConfirmed = false",
        "NqDataFlowConfirmed = false",
        "ConnectionStableConfirmed = false",
        "dataLoadedSeen = true",
        "attempted = true",
        "SessionIteratorQueryDomainNativeComparisonV1.Compare",
        '"R53_NATIVE_REGRESSION"',
        '"C_RAW"',
        '"C_SAME_TICKS"',
        '"C_ADAPTER"',
        "FileMode.CreateNew",
        "FileOptions.WriteThrough",
        "ARMS_R54_C STATUS=",
    ):
        assert token in text


def test_host_has_no_trading_or_connection_authority():
    text = HOST.read_text(encoding="utf-8")

    clean = re.sub(
        r"//[^\n]*|/\*.*?\*/",
        "",
        text,
        flags=re.S,
    )

    clean = re.sub(
        r"\[\s*Display\s*\(.*?\)\s*\]",
        "",
        clean,
        flags=re.S,
    )

    forbidden = (
        r"\b(Account|Order|Execution|AtmStrategy|"
        r"SubmitOrder|CreateOrder|Position|"
        r"BarsRequest|Process|Timer|DllImport|Activator)"
        r"\b"
    )

    assert not re.search(forbidden, clean)

    assert ".Connect(" not in clean
    assert ".Disconnect(" not in clean
    assert "DateTime.ToUniversalTime" not in clean
    assert "TimeZoneInfo.Local" not in clean
    assert "File.Delete(" not in clean
    assert "Directory.Delete(" not in clean


def test_host_only_invokes_comparison_once():
    text = HOST.read_text(encoding="utf-8")

    assert (
        text.count(
            "SessionIteratorQueryDomainNativeComparisonV1.Compare"
        )
        == 1
    )


def test_installed_sdk_indicator_compile_only(
    tmp_path,
):
    assert CSC.is_file()

    core = SDK / "NinjaTrader.Core.dll"
    gui = SDK / "NinjaTrader.Gui.dll"

    assert core.is_file()
    assert gui.is_file()

    windows_base = (
        CSC.parent
        / "WPF/WindowsBase.dll"
    )

    assert windows_base.is_file()

    shim = tmp_path / "Indicator.cs"

    shim.write_text(
        "namespace NinjaTrader.NinjaScript.Indicators "
        "{ public class Indicator : "
        "NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }",
        encoding="utf-8",
    )

    target = (
        tmp_path
        / "R54RepairProbeCompileOnly.dll"
    )

    command = [
        CSC,
        "/nologo",
        "/langversion:5",
        "/target:library",
        "/out:" + str(target),
        "/r:System.Core.dll",
        "/r:System.Web.Extensions.dll",
        "/r:System.ComponentModel.DataAnnotations.dll",
        "/r:" + str(core),
        "/r:" + str(gui),
        "/r:" + str(windows_base),
        ADAPTER,
        COMPARISON,
        HOST,
        shim,
    ]

    result = subprocess.run(
        [str(x) for x in command],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        result.stdout + result.stderr
    )

    assert target.is_file()
