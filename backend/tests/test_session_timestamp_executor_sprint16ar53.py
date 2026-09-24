"""R5.3-B actual C# coordinator against synthetic interfaces, never native proof.
The native adapter, request lifecycle, durable evidence and full verifier remain pending.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "integrations/ninjatrader/ArmsSessionTimestampPlanV1.cs"
SOURCE = ROOT / "integrations/ninjatrader/ArmsSessionTimestampExecutorV1.cs"
HARNESS = ROOT / "backend/tests/fixtures/session_timestamp_executor_harness_sprint16ar53.cs"
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
CASES = ('all_true_budget', 'all_false_no_bounds', 'r0_false_skips_r1_only', 'r0_constructor_exception', 'r0_advance_exception', 'r0_begin_exception', 'r0_end_exception', 'r0_invalid_bounds', 'r0_mixed_bound_kinds', 'matching_unspecified_bounds', 'constructor_fault_every_fresh_case', 'advance_fault_every_case', 'begin_fault_every_case', 'end_fault_every_case', 'r1_reuses_r0_only', 'fresh_identity_reuse_rejected', 'null_cursor_rejected', 'null_identity_rejected', 'identity_change_rejected', 'identity_getter_exception', 'reuse_identity_change_rejected', 'null_plan_rejected', 'bad_case_count_rejected', 'bad_order_rejected', 'missing_factory_rejected', 'missing_context_check_rejected', 'context_before_create', 'context_before_advance', 'context_before_begin', 'context_before_end', 'context_before_complete', 'reentrant_executor_cannot_complete', 'repeated_executor_no_more_calls', 'shallow_clone_preserves_owner', 'all_4096_boolean_patterns', 'query_ticks_kind_inclusion_unchanged', 'exception_messages_not_persisted', 'immutable_observation_collection', 'constructor_attempt_charged_first')

@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    if not CSC.is_file():
        pytest.fail("WINDOWS_FRAMEWORK_COMPILER_REQUIRED: no substitute native proof")
    folder = tmp_path_factory.mktemp("r53-executor")
    exe = folder / "r53-executor-tests.exe"
    command = [str(CSC), "/nologo", "/langversion:5", "/target:exe", "/out:" + str(exe),
               "/r:System.Core.dll", "/r:System.Web.Extensions.dll", str(PLAN), str(SOURCE), str(HARNESS)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and exe.is_file(), result.stdout + result.stderr
    return exe

def run(binary, *args):
    result = subprocess.run([str(binary), *args], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["classification"] == "SYNTHETIC_EXECUTOR_ONLY_NOT_NATIVE_EVIDENCE"
    assert data["failed"] == 0
    assert data["real_native_api_calls"] == 0
    assert data["loaded_ninjatrader_assemblies"] == 0
    assert data["native_provenance_attested"] is False
    return data

@pytest.mark.parametrize("case", CASES)
def test_actual_csharp_executor(binary, case):
    data = run(binary, "--case", case)
    assert data["total"] == data["passed"] == 1
    assert data["results"][0]["name"] == case
    assert data["results"][0]["status"] == "PASS"

def test_complete_executor_harness_inventory(binary):
    data = run(binary, "--all")
    assert data["total"] == data["passed"] == len(CASES)
    assert tuple(item["name"] for item in data["results"]) == CASES

def test_executor_has_no_native_filesystem_or_conversion_surface():
    source = SOURCE.read_text(encoding="utf-8")
    code = re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', '', source, flags=re.S)
    forbidden = r"\b(NinjaTrader|BarsRequest|SessionIterator|Account|Order|Execution|Process|Timer|DllImport|Activator|File|Directory|Assembly)\b"
    assert not re.search(forbidden, code)
    assert not re.search(r"\b(ToUniversalTime|ToLocalTime|SpecifyKind|ConvertTimeToUtc|Now|UtcNow)\b", code)
    assert "TimeZoneInfo.Local" not in code
    assert "Object.ReferenceEquals(this, instanceOwner)" in code
    assert "SessionTimestampPlanV1.MaximumIteratorSlots" in code
    assert "SessionTimestampPlanV1.MaximumPlannedCalls" in code
