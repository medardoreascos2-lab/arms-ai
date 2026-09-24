"""R5.3-A tests of the actual pure C# planner, not of NinjaTrader behavior.

Requires the installed Windows .NET Framework compiler. No broker SDK is loaded.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations/ninjatrader/ArmsSessionTimestampPlanV1.cs"
HARNESS = ROOT / "backend/tests/fixtures/session_timestamp_plan_harness_sprint16ar53.cs"
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
CASES = ('bad_row_count', 'conversion_requires_unspecified', 'dst_offset_is_dynamic', 'exact_datetime_limits', 'explicit_zone_A', 'explicit_zone_B', 'explicit_zone_C', 'fixed_matrix', 'input_not_mutated_and_repeatable', 'kind_only_A', 'kind_only_B', 'kind_only_C', 'limits', 'no_ninjatrader_assemblies', 'one_tick_precision', 'positive_fractional_offset', 'range_is_raw_only', 'readonly_controls', 'reference_queries', 'reject_ambiguous_wall_time', 'reject_bad_snapshot_digest', 'reject_bad_template_digest', 'reject_invalid_wall_time', 'reject_max_saturation', 'reject_min_saturation', 'reject_missing_zone', 'reject_reversed_raw_endpoints', 'reject_utc_or_local_A', 'reuse_prerequisite_truth_table', 'source_and_reference_provenance', 'variable_snapshot_count', 'zero_offset_still_explicit_conversion')

@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    if not CSC.is_file():
        pytest.fail("WINDOWS_FRAMEWORK_COMPILER_REQUIRED: not a native-test pass or skip")
    folder = tmp_path_factory.mktemp("r53-pure-plan")
    exe = folder / "r53-plan-tests.exe"
    command = [str(CSC), "/nologo", "/langversion:5", "/target:exe", "/out:" + str(exe),
               "/r:System.Core.dll", "/r:System.Web.Extensions.dll", str(SOURCE), str(HARNESS)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and exe.is_file(), result.stdout + result.stderr
    return exe

def run(binary, *args):
    result = subprocess.run([str(binary), *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["classification"] == "SYNTHETIC_CORE_ONLY_NOT_NATIVE_EVIDENCE"
    assert data["failed"] == 0
    assert data["native_api_calls"] == 0
    assert data["native_provenance_attested"] is False
    return data

@pytest.mark.parametrize("case", CASES)
def test_actual_csharp_query_planner(binary, case):
    data = run(binary, "--case", case)
    assert data["total"] == data["passed"] == 1
    assert data["results"][0]["name"] == case
    assert data["results"][0]["status"] == "PASS"

def test_complete_harness_inventory(binary):
    data = run(binary, "--all")
    assert data["total"] == data["passed"] == len(CASES)
    assert tuple(item["name"] for item in data["results"]) == CASES

def test_pure_helper_has_no_native_or_filesystem_surface():
    source = SOURCE.read_text(encoding="utf-8")
    # Strip C# string literals and comments before token checks.
    code = re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', '', source, flags=re.S)
    forbidden = r"\b(NinjaTrader|BarsRequest|SessionIterator|Account|Order|Execution|Process|Timer|DllImport|Activator|File|Directory|Assembly)\b"
    assert not re.search(forbidden, code)
    assert not re.search(r"\b(ToUniversalTime|ToLocalTime|Now|UtcNow)\b", code)
    assert "TimeZoneInfo.Local" not in code
    assert len(re.findall(r"DateTime\.SpecifyKind\s*\(", code)) == 1
    assert len(re.findall(r"TimeZoneInfo\.ConvertTimeToUtc\s*\(", code)) == 1
    assert "TimeZoneInfo.ConvertTimeToUtc(raw, zone)" in code
