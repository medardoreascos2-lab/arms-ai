"""R5.3-E: actual SDK bridge against EXPLICIT SDK DOUBLES; no native run.
SDK reference compile is a separate non-executed library, never the test binary.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import pytest
from tools.verify_session_timestamp_evidence_v1 import verify_evidence

ROOT = Path(__file__).resolve().parents[2]
CORES = [ROOT / ('integrations/ninjatrader/ArmsSessionTimestamp' + n + 'V1.cs')
         for n in ('Plan', 'Executor', 'Lifecycle', 'Evidence')]
SOURCE = ROOT / 'integrations/ninjatrader/ArmsSessionTimestampNativeBridgeV1.cs'
HARNESS = ROOT / 'backend/tests/fixtures/session_timestamp_native_bridge_harness_sprint16ar53.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK = Path('C:/Program Files/NinjaTrader 8/bin')
CASES = ('success_normal', 'success_inline', 'success_async', 'success_all_false', 'success_false', 'success_constructor_error', 'success_advance_error', 'success_begin_error', 'success_end_error', 'success_bad_order', 'success_bad_kind', 'success_r0_false', 'success_r0_constructor_error', 'success_r0_advance_error', 'success_r0_begin_error', 'success_r0_end_error', 'success_r0_bad_order', 'success_r0_bad_kind', 'success_dispose_callback', 'failure_callback_error', 'failure_wrong_callback', 'failure_null_callback', 'failure_submit_error', 'failure_inline_then_throw', 'failure_duplicate_inline', 'failure_context_error', 'failure_terminate_in_submit', 'failure_terminate_in_matrix', 'failure_duplicate_in_matrix', 'failure_dispose_error', 'request_identity', 'request_sender_and_error', 'request_repeated_submit', 'request_after_dispose', 'request_null_callback', 'request_context_rejected', 'request_clone_preserves_owner', 'request_late_callback_ignored', 'request_dispose_throws_once', 'request_dispose_during_submit_rejected', 'factory_clone_preserves_owner', 'cursor_clone_preserves_owner', 'native_identity_preserved', 'factory_duplicate_slot_rejected', 'factory_reuse_construction_rejected', 'factory_foreign_control_rejected', 'factory_invalidation', 'native_query_kind_changed', 'native_query_ticks_changed', 'native_query_inclusion_changed', 'bounds_before_advance_rejected', 'bounds_after_false_rejected', 'end_before_begin_rejected', 'duplicate_begin_rejected', 'ordinary_cursor_reuse_rejected', 'request_and_factory_dependencies', 'checkpoint_blocks_constructor', 'reentrant_native_call_stops_matrix', 'pending_termination')
SUCCESS_MODES = tuple(name[8:] for name in CASES if name.startswith('success_'))

@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    assert CSC.is_file(), 'WINDOWS_COMPILER_REQUIRED_NO_NATIVE_SUBSTITUTE'
    folder = tmp_path_factory.mktemp('r53-native-bridge-doubles')
    target = folder / 'r53-sdk-doubles.exe'
    command = [str(CSC), '/nologo', '/langversion:5', '/target:exe', '/out:' + str(target),
               '/r:System.Core.dll', '/r:System.Web.Extensions.dll',
               *map(str, CORES), str(SOURCE), str(HARNESS)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and target.is_file(), result.stdout + result.stderr
    # No /r:NinjaTrader... is present: all SDK types in this executable are doubles.
    assert not any('/r:' in item and 'NinjaTrader' in item for item in command)
    return target


def run(binary, args):
    result = subprocess.run([str(binary), *args], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data['classification'] == 'SYNTHETIC_SDK_BRIDGE_ONLY'
    return data


@pytest.mark.parametrize('case', CASES)
def test_bridge_actual_csharp_against_doubles(binary, tmp_path, case):
    data = run(binary, ['--case', str(tmp_path), case])
    assert data['total'] == data['passed'] == 1 and data['failed'] == 0
    assert data['loaded_ninjatrader_assemblies'] == data['real_native_api_calls'] == 0
    assert data['results'] == [dict(name=case, status='PASS', detail='NONE')]


def test_complete_bridge_inventory(binary, tmp_path):
    data = run(binary, ['--all', str(tmp_path)])
    assert data['total'] == data['passed'] == len(CASES) and data['failed'] == 0
    assert data['loaded_ninjatrader_assemblies'] == data['real_native_api_calls'] == 0
    assert tuple(r['name'] for r in data['results']) == CASES
    assert all(r['status'] == 'PASS' for r in data['results'])


@pytest.mark.parametrize('mode', SUCCESS_MODES)
def test_bridge_results_pass_unchanged_d_verifier(binary, tmp_path, mode):
    data = run(binary, ['--emit', str(tmp_path), mode])
    assert data['sealed'] is True
    raw = (tmp_path / 'session-timestamp-evidence.jsonl').read_bytes()
    seal = (tmp_path / 'session-timestamp-evidence.done.json').read_bytes()
    result = verify_evidence(raw, seal)
    assert result['status'] == 'PASS_DIAGNOSTIC_CONTRACT_ONLY'
    assert result['origin_claim'] == 'SYNTHETIC'
    assert result['constructor_attempts'] <= 11 and result['call_attempts'] <= 12
    assert result['native_provenance_attested'] is False
    assert result['template_calendar_attested'] is False
    assert result['runtime_admission'] is False
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw + seal


def test_bridge_structural_scope():
    text = SOURCE.read_text(encoding='utf-8')
    code = re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
    assert not re.search(r'\b(Account|Order|Execution|SubmitOrder|CreateOrder|AtmStrategy|Indicator|Strategy|Process|Timer|Task|DllImport|Activator|File|Directory)\b', code)
    assert not re.search(r'\b(ToUniversalTime|ToLocalTime|SpecifyKind|ConvertTimeToUtc|Now|UtcNow)\b', code)
    assert not re.search(r'\.(Update|Connect|Disconnect)\s*[+=(]', code)
    assert code.count('new SessionIterator(bars)') == 1
    assert code.count('iterator.GetNextSession(query,includeEndTime)') == 1
    assert code.count('iterator.ActualSessionBegin') == 1
    assert code.count('iterator.ActualSessionEnd') == 1
    assert code.count('request.Request(') == 1
    assert code.count('request.Dispose(') == 1
    assert 'new BarsRequest' not in code
    assert 'Object.ReferenceEquals(this,instanceOwner)' in code
    assert 'returnedTrue && !beginAttempted' in code
    assert 'returnedTrue && begin.HasValue && !endAttempted' in code


def test_installed_sdk_bridge_compile_only(tmp_path):
    assert CSC.is_file(), 'WINDOWS_COMPILER_REQUIRED'
    refs = [SDK / 'NinjaTrader.Core.dll', SDK / 'NinjaTrader.Gui.dll',
            CSC.parent / 'WPF/WindowsBase.dll']
    assert all(path.is_file() for path in refs), 'INSTALLED_SDK_REQUIRED_NO_SKIP'
    target = tmp_path / 'R53NativeBridgeCompileOnly.dll'
    command = [str(CSC), '/nologo', '/langversion:5', '/target:library', '/out:' + str(target),
               '/r:System.Core.dll', '/r:System.Web.Extensions.dll', '/r:System.ComponentModel.DataAnnotations.dll',
               *['/r:' + str(path) for path in refs], *map(str, CORES), str(SOURCE)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and target.is_file(), result.stdout + result.stderr
    # No shim/doubles and NO loading or invocation of the resulting SDK-linked DLL.
    assert str(HARNESS) not in command
