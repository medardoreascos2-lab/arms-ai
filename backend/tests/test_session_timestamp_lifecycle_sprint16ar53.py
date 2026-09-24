"""R5.3-C owner/request/callback lifecycle against synthetic resources only.
No native adapter, disk evidence, seal, indicator or full verifier is implemented here.
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
EXECUTOR = ROOT / "integrations/ninjatrader/ArmsSessionTimestampExecutorV1.cs"
SOURCE = ROOT / "integrations/ninjatrader/ArmsSessionTimestampLifecycleV1.cs"
HARNESS = ROOT / "backend/tests/fixtures/session_timestamp_lifecycle_harness_sprint16ar53.cs"
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
CASES = ('normal_matrix_then_release', 'all_false_still_diagnostic', 'inline_waits_for_submit_return', 'inline_then_throw_never_prepares', 'async_callback', 'callback_other_thread_during_submit_no_deadlock', 'disabled_creates_nothing_then_enabled', 'pending_then_terminate', 'terminate_before_start', 'terminate_during_process_cooperative', 'terminate_during_submit_deferred_dispose', 'terminate_during_factory_no_leak', 'duplicate_inline_prevents_completion', 'duplicate_reentrant_stops_next_call', 'duplicate_concurrent_preserves_inflight_resources', 'late_callbacks_no_more_work', 'callback_from_dispose_ignored', 'callback_error_rejected', 'foreign_request_callback_rejected', 'callback_before_submit_rejected', 'request_identity_null', 'request_identity_throws', 'request_identity_changed', 'request_identity_after_process_changed', 'writer_factory_throws', 'writer_factory_null', 'request_factory_throws_closes_writer', 'request_factory_null_closes_writer', 'request_writer_alias_disposed_once', 'submit_throws', 'processor_throws', 'processor_null', 'incomplete_matrix_rejected', 'prepare_throws', 'request_dispose_failure_never_ready', 'writer_dispose_failure_never_ready', 'both_dispose_failures_attempted_once', 'context_before_open', 'context_before_request_create', 'context_before_submit', 'context_after_submit', 'context_before_process', 'context_after_process', 'context_before_prepare', 'context_after_prepare', 'terminate_during_prepare', 'terminate_during_dispose', 'reentrant_start_not_retried', 'repeat_after_complete_no_mutation', 'repeated_pending_start_releases_once', 'null_owner_rejected', 'wrong_owner_cannot_touch_resources', 'shallow_core_clone_preserves_original', 'shallow_UI_host_clone_preserves_original', 'all_missing_dependency_positions', 'safe_error_redaction', 'independent_owners_no_cross_dispose')

@pytest.fixture(scope="module")
def binary(tmp_path_factory):
    if not CSC.is_file():
        pytest.fail("WINDOWS_FRAMEWORK_COMPILER_REQUIRED: no substitute native proof")
    folder = tmp_path_factory.mktemp("r53-lifecycle")
    exe = folder / "r53-lifecycle-tests.exe"
    command = [str(CSC), "/nologo", "/langversion:5", "/target:exe", "/out:" + str(exe),
               "/r:System.Core.dll", "/r:System.Web.Extensions.dll",
               str(PLAN), str(EXECUTOR), str(SOURCE), str(HARNESS)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and exe.is_file(), result.stdout + result.stderr
    return exe

def run(binary, *args):
    result = subprocess.run([str(binary), *args], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["classification"] == "SYNTHETIC_LIFECYCLE_ONLY_NOT_NATIVE_EVIDENCE"
    assert data["failed"] == 0
    assert data["real_native_api_calls"] == 0
    assert data["loaded_ninjatrader_assemblies"] == 0
    assert data["seal_files_written"] == 0
    assert data["native_provenance_attested"] is False
    return data

@pytest.mark.parametrize("case", CASES)
def test_actual_csharp_request_lifecycle(binary, case):
    data = run(binary, "--case", case)
    assert data["total"] == data["passed"] == 1
    assert data["results"][0]["name"] == case
    assert data["results"][0]["status"] == "PASS"

def test_complete_lifecycle_harness_inventory(binary):
    data = run(binary, "--all")
    assert data["total"] == data["passed"] == len(CASES)
    assert tuple(item["name"] for item in data["results"]) == CASES

def test_lifecycle_has_no_native_disk_or_seal_surface():
    source = SOURCE.read_text(encoding="utf-8")
    code = re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', '', source, flags=re.S)
    forbidden = r"\b(NinjaTrader|BarsRequest|SessionIterator|Account|Order|Execution|Process|Timer|DllImport|Activator|File|Directory|Assembly|Thread|Task)\b"
    assert not re.search(forbidden, code)
    assert not re.search(r"\b(ToUniversalTime|ToLocalTime|SpecifyKind|ConvertTimeToUtc|Now|UtcNow)\b", code)
    assert "Object.ReferenceEquals(this, instanceOwner)" in code
    assert "Object.ReferenceEquals(owner, hostOwner)" in code
    assert code.count("r.Submit(") == 1
    assert "public bool SealWritten { get { return false; } }" in code
    assert "public bool NativeProvenanceAttested { get { return false; } }" in code
