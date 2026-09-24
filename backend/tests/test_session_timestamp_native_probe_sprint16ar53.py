"""H: actual NinjaScript host + A-G against explicit F1 SDK and Indicator doubles.
Compiling the SDK-linked library is not executing native NinjaTrader behavior.
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import pytest
from tools.verify_session_timestamp_context_envelope_v1 import read_capture,FILES,SEAL_NAME

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'integrations/ninjatrader/ArmsSessionTimestampInterpretationProbeV1.cs'
HARNESS=ROOT/'backend/tests/fixtures/session_timestamp_native_probe_harness_sprint16ar53.cs'
DOUBLES=ROOT/'backend/tests/fixtures/session_timestamp_native_context_harness_sprint16ar53.cs'
CORES=[ROOT/('integrations/ninjatrader/ArmsSessionTimestamp'+n+'V1.cs') for n in
    ('Plan','Executor','Lifecycle','Evidence','NativeBridge','NativeContext','ContextEnvelope')]
CSC=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK=Path('C:/Program Files/NinjaTrader 8/bin')
CASES=('success_normal', 'success_inline', 'success_async', 'success_all_false', 'success_false', 'success_constructor_error', 'success_advance_error', 'success_begin_error', 'success_end_error', 'success_bad_order', 'success_bad_kind', 'success_r0_false', 'success_r0_constructor_error', 'success_r0_advance_error', 'success_r0_begin_error', 'success_r0_end_error', 'success_r0_bad_order', 'success_r0_bad_kind', 'success_mixed', 'success_duplicate', 'success_decreasing', 'success_misaligned', 'success_rows4503', 'success_rows5520', 'success_rows10002', 'success_irrelevant_exceptions', 'success_dispose_callback', 'success_clone_active', 'success_clone_setdefaults', 'success_clone_after_seal', 'success_repeated_events', 'success_setdefaults_on_owner', 'success_late_snapshot_throw', 'failure_inline_then_throw', 'failure_duplicate_inline', 'failure_callback_error', 'failure_wrong_callback', 'failure_submit_error', 'failure_snapshot_mutation', 'failure_count_mutation', 'failure_gettime_error', 'failure_ohlc_error', 'failure_wrong_returned_template', 'failure_first_utc', 'failure_duplicate_in_matrix', 'failure_terminate_in_matrix', 'failure_gate_in_matrix', 'failure_output_in_matrix', 'failure_chart_in_matrix', 'failure_policy_in_matrix', 'failure_playback_in_matrix', 'failure_timezone_in_matrix', 'failure_foreign_before_prepare', 'failure_request_dispose_error', 'failure_output_on_dispose', 'failure_terminate_on_dispose', 'failure_tamper_on_dispose', 'failure_foreign_on_dispose', 'failure_closed', 'failure_no_flow', 'failure_unstable', 'failure_blank_output', 'failure_null_output', 'failure_missing_output', 'failure_relative_output', 'failure_foreign_before_open', 'failure_playback', 'failure_timezone', 'failure_chart_null', 'failure_chart_instrument', 'failure_chart_period', 'failure_chart_bid', 'failure_chart_template', 'failure_calendar_schedule', 'failure_calendar_holiday', 'failure_request_constructor_error', 'failure_request_configuration_error', 'failure_terminate_pending', 'disabled_ui_only', 'disabled_without_configure', 'disabled_terminated_before_load', 'disabled_defaults', 'disabled_enable_after_disabled', 'two_independent_hosts', 'shared_capture_rejected', 'terminate_concurrent_inflight')
SUCCESS_MODES=('normal', 'inline', 'async', 'all_false', 'false', 'constructor_error', 'advance_error', 'begin_error', 'end_error', 'bad_order', 'bad_kind', 'r0_false', 'r0_constructor_error', 'r0_advance_error', 'r0_begin_error', 'r0_end_error', 'r0_bad_order', 'r0_bad_kind', 'mixed', 'duplicate', 'decreasing', 'misaligned', 'rows4503', 'rows5520', 'rows10002', 'irrelevant_exceptions', 'dispose_callback', 'clone_active', 'clone_setdefaults', 'clone_after_seal', 'repeated_events', 'setdefaults_on_owner', 'late_snapshot_throw')


def checked_run(cmd,timeout=120):
    p=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    assert p.returncode==0,p.stdout+p.stderr
    return p


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    assert CSC.is_file(),'WINDOWS_COMPILER_REQUIRED_NO_SKIP'
    folder=tmp_path_factory.mktemp('r53-host-h')
    target=folder/'host-doubles.exe'
    checked_run([CSC,'/nologo','/langversion:5','/target:exe','/main:NativeProbeHarness','/out:'+str(target),
        '/r:System.Core.dll','/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',
        *CORES,SOURCE,DOUBLES,HARNESS],60)
    assert target.is_file()
    return target


@pytest.fixture(scope='module')
def suite(binary,tmp_path_factory):
    root=tmp_path_factory.mktemp('r53-host-cases')
    report=json.loads(checked_run([binary,'--all',root],300).stdout)
    assert report['classification']=='SYNTHETIC_NINJASCRIPT_HOST_ONLY'
    assert report['total']==report['passed']==len(CASES) and report['failed']==0
    assert report['real_native_api_calls']==report['loaded_ninjatrader_assemblies']==0
    assert [r['name'] for r in report['results']]==list(CASES)
    return {r['name']:r for r in report['results']}


@pytest.mark.parametrize('name',CASES)
def test_indicator_lifecycle_synthetic_contract(suite,name):
    assert suite[name]['status']=='PASS' and suite[name]['detail']=='NONE'


@pytest.mark.parametrize('mode',SUCCESS_MODES)
def test_emitted_native_claim_remains_unattested(binary,tmp_path,mode):
    p=checked_run([binary,'--emit',tmp_path,mode],120)
    report=json.loads(p.stdout)
    assert report['classification']=='SYNTHETIC_NINJASCRIPT_HOST_ONLY' and report['sealed_diagnostic'] is True
    assert report['real_native_api_calls']==report['loaded_ninjatrader_assemblies']==0
    capture=tmp_path/'capture'
    before={x.relative_to(capture).as_posix():sha256(x.read_bytes()).hexdigest() for x in capture.rglob('*') if x.is_file()}
    result=read_capture(capture)
    assert result['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
    assert result['origin_claim']=='OPERATOR_NATIVE_RUN_UNATTESTED'
    assert result['native_provenance_attested'] is False
    assert result['zone_rules_independently_reevaluated'] is False
    assert result['bar_timestamp_conversion'] is False
    assert result['getnextsession_attempts']<=12 and result['iterator_constructor_attempts']<=11
    assert result['certification_evidence'] is False and result['runtime_admission'] is False and result['execution_authority'] is False
    assert before=={x.relative_to(capture).as_posix():sha256(x.read_bytes()).hexdigest() for x in capture.rglob('*') if x.is_file()}
    assert set(before)==set((*FILES,SEAL_NAME))


def test_host_structural_safety_and_delegation():
    text=SOURCE.read_text(encoding='utf-8')
    clean=re.sub(r'//[^\n]*','',text)
    clean=re.sub(r'\[Display\([^\n]*\)\]','',clean)
    assert not re.search(r'\b(Account|Order|Execution|SubmitOrder|CreateOrder|AtmStrategy|Process|Timer|DllImport|Activator)\b',clean)
    for token in ('new BarsRequest(', 'new SessionIterator(', '.GetNextSession(', '.GetTime(', '.GetOpen(',
        '.GetHigh(', '.GetLow(', '.GetClose(', '.GetVolume(', 'File.', 'Directory.', 'ToUniversalTime(', 'ToLocalTime(',
        'SpecifyKind(', 'ConvertTime', '.Connect(', '.Disconnect(', '.Update +=','Task.Run'):
        assert token not in clean
    for token in ('SessionTimestampLifecycleV1','SessionTimestampNativeContextV1','SessionTimestampContextEnvelopeV1',
        'SessionTimestampExecutorV1','SessionTimestampNativeCursorFactoryV1','attempt.IsOwner(this)',
        'owner.FinishObservation()','writer.PublishSeal(host)','dataLoadedSeen=true', 'OPERATOR_NATIVE_RUN_UNATTESTED'):
        assert token in clean
    assert 'catch' in clean and 'e.Message' not in clean and 'error.Message' not in clean and 'StackTrace' not in clean


def test_host_ui_settings_exact_and_only():
    text=SOURCE.read_text(encoding='utf-8')
    assert re.findall(r'public (?:bool|string) (\w+) \{ get; set; \}',text)==[
        'ProbeEnabled','OutputDirectory','MarketReopenConfirmed','NqDataFlowConfirmed','ConnectionStableConfirmed']
    assert text.count('[NinjaScriptProperty]')==5
    assert 'protected override void OnBarUpdate() { }' in text
    assert 'NinjaScript generated code' not in text


def test_setdefaults_does_not_allocate_or_start_resources():
    text=SOURCE.read_text(encoding='utf-8')
    default=text.split('if(State == State.SetDefaults)',1)[1].split('else if(State == State.Configure)',1)[0]
    assert 'new ' not in re.sub(r'//[^\n]*','',default)
    assert '.Start(' not in default and '.Dispose(' not in default
    for token in ('ProbeEnabled=false','OutputDirectory=""','MarketReopenConfirmed=false','NqDataFlowConfirmed=false','ConnectionStableConfirmed=false'):
        assert token in default


def test_installed_sdk_indicator_compile_only(tmp_path):
    assert CSC.is_file() and (SDK/'NinjaTrader.Core.dll').is_file(),'INSTALLED_SDK_REQUIRED_NO_SKIP'
    shim=tmp_path/'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs=[SDK/'NinjaTrader.Core.dll',SDK/'NinjaTrader.Gui.dll',CSC.parent/'WPF/WindowsBase.dll']
    dll=tmp_path/'NativeIndicatorCompileOnly.dll'
    checked_run([CSC,'/nologo','/langversion:5','/target:library','/out:'+str(dll),'/r:System.Core.dll',
        '/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',*['/r:'+str(x) for x in refs],
        *CORES,SOURCE,shim],60)
    assert dll.is_file()
