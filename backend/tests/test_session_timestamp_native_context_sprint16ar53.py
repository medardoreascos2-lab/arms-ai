"""F loaded context: SDK reference compilation and explicit synthetic doubles only."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

import pytest
from tools.verify_session_timestamp_evidence_v1 import verify_evidence, timestamp

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'integrations/ninjatrader/ArmsSessionTimestampNativeContextV1.cs'
HARNESS=ROOT/'backend/tests/fixtures/session_timestamp_native_context_harness_sprint16ar53.cs'
CORES=[ROOT/('integrations/ninjatrader/ArmsSessionTimestamp'+n+'V1.cs') for n in ('Plan','Executor','Lifecycle','Evidence','NativeBridge')]
CSC=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK=Path('C:/Program Files/NinjaTrader 8/bin')
CASES=('success_normal', 'success_inline', 'success_async', 'success_all_false', 'success_false', 'success_constructor_error', 'success_advance_error', 'success_begin_error', 'success_end_error', 'success_bad_order', 'success_bad_kind', 'success_r0_false', 'success_r0_constructor_error', 'success_r0_advance_error', 'success_r0_begin_error', 'success_r0_end_error', 'success_r0_bad_order', 'success_r0_bad_kind', 'failure_inline_then_throw', 'failure_duplicate_inline', 'failure_callback_error', 'failure_wrong_callback', 'failure_submit_error', 'failure_mutation_during_matrix', 'failure_policy_during_matrix', 'failure_duplicate_in_matrix', 'failure_terminate_in_matrix', 'gate_disabled', 'gate_closed', 'gate_no_flow', 'gate_unstable', 'gate_terminated', 'gate_output_changed', 'gate_null_settings', 'timezone', 'utc_id_wrong_rules', 'playback', 'instrument_null', 'instrument_name', 'instrument_master', 'instrument_expiry', 'instrument_tick', 'instrument_point', 'calendar_name', 'calendar_zone', 'calendar_rules', 'calendar_sessions', 'calendar_schedule', 'calendar_full_holiday', 'calendar_partial_holiday', 'calendar_holiday_budget', 'calendar_partial_budget', 'constructor_error_cleanup', 'configure_error_cleanup', 'environment_during_create', 'clone_preserves_owner', 'wrong_owner', 'reentrant_environment', 'irrelevant_holidays_recorded', 'factory_repeated', 'request_mutate_lookup', 'request_mutate_merge', 'request_mutate_reset', 'request_mutate_dividend', 'request_mutate_split', 'request_mutate_from', 'request_mutate_through', 'request_mutate_kind', 'request_mutate_period', 'request_mutate_calendar_object', 'request_mutate_calendar_content', 'foreign_callback', 'null_callback', 'bind_count_low', 'bind_count_high', 'bind_first_utc', 'bind_reverse_end', 'bind_unstable', 'bind_gettime', 'bind_ohlc', 'bind_count_mutation', 'bind_bars_period', 'bind_bars_calendar', 'count_4503', 'count_5520', 'count_max', 'mixed_kinds', 'observe_duplicate', 'observe_decreasing', 'observe_misaligned', 'separate_returned_calendar', 'mutate_price', 'mutate_timestamp', 'mutate_count', 'mutate_kind', 'mutate_bars_object', 'mutate_template_version', 'mutate_template_object', 'mutate_environment', 'bind_repeated', 'invalidation', 'foreign_plan_control', 'bound_context_normal')
SUCCESS_MODES=('normal', 'inline', 'async', 'all_false', 'false', 'constructor_error', 'advance_error', 'begin_error', 'end_error', 'bad_order', 'bad_kind', 'r0_false', 'r0_constructor_error', 'r0_advance_error', 'r0_begin_error', 'r0_end_error', 'r0_bad_order', 'r0_bad_kind')

@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    assert CSC.is_file(), 'WINDOWS_COMPILER_REQUIRED_NO_SKIP'
    target=tmp_path_factory.mktemp('r53-f-context')/'harness.exe'
    command=[str(CSC),'/nologo','/langversion:5','/target:exe','/out:'+str(target),
             '/r:System.Core.dll','/r:System.Web.Extensions.dll',*map(str,CORES),str(SOURCE),str(HARNESS)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert result.returncode==0 and target.is_file(), result.stdout+result.stderr
    return target

def run(binary, folder, *args):
    result=subprocess.run([str(binary),*args,str(folder)] if args==('--all',) else [str(binary),args[0],str(folder),*args[1:]],
                          cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
    data=json.loads(result.stdout)
    assert data['classification']=='SYNTHETIC_LOADED_CONTEXT_ONLY'
    return data

@pytest.mark.parametrize('case',CASES)
def test_native_context_actual_csharp_with_doubles(binary,tmp_path,case):
    data=run(binary,tmp_path,'--case',case)
    assert data['total']==data['passed']==1 and data['failed']==0
    assert data['loaded_ninjatrader_assemblies']==data['real_native_api_calls']==0
    assert data['results']==[dict(name=case,status='PASS',detail='NONE')]

def test_complete_native_context_inventory(binary,tmp_path):
    data=run(binary,tmp_path,'--all')
    assert data['total']==data['passed']==len(CASES) and data['failed']==0
    assert data['loaded_ninjatrader_assemblies']==data['real_native_api_calls']==0
    assert tuple(item['name'] for item in data['results'])==CASES
    assert all(item['status']=='PASS' for item in data['results'])

def check_context_sample(folder):
    # This is a test assertion, NOT the future native-context envelope verifier.
    context_raw=(folder/'context.json').read_bytes()
    assert len(context_raw)<=131072 and b'PRIVATE_PROVIDER_SENTINEL' not in context_raw
    data=json.loads(context_raw)
    assert data['schema']=='arms.r53.loaded-context.v1'
    assert data['native_provenance_attested'] is data['certification_evidence'] is data['runtime_admission'] is False
    assert data['bar_timestamp_conversion'] is data['playback_connected'] is False
    assert data['operator_observations_independently_verified'] is False
    assert data['request_constructor_attempts']==1 and data['source_index']==0
    assert str(uuid.UUID(data['sdk_core_mvid']))==data['sdk_core_mvid']
    assert data['sdk_version']=='8.1.8.2' and data['application_timezone']=='UTC'
    config=json.loads(data['request_configuration_json'])
    assert data['request_configuration_sha256']==sha256(data['request_configuration_json'].encode()).hexdigest()
    assert config['lookup']=='Repository' and config['merge']=='DoNotMerge'
    assert config['instrument']=='NQ DEC26' and config['bars_period']=='Minute' and config['period_value']==1
    assert config['market_data']=='Last' and config['date_semantics']=='REQUEST_LOCAL_CALENDAR_DATES'
    assert config['submitted_from']==config['actual_from'] and config['submitted_through']==config['actual_through']
    assert config['submitted_from']['clock']=='2026-09-16T00:00:00.0000000'
    assert config['submitted_through']['clock']=='2026-09-21T00:00:00.0000000'
    calendar=json.loads(data['loaded_calendar_json'])
    assert data['loaded_calendar_sha256']==sha256(data['loaded_calendar_json'].encode()).hexdigest()
    assert calendar['zone_id']=='Central Standard Time'
    assert calendar['zone_sha256']==sha256(calendar['zone_serialized'].encode()).hexdigest()
    assert calendar['sessions_hhmm']==[f'{i}|1700|{i+1}|1600|{i+1}' for i in range(5)]
    assert len(calendar['references'])==4
    for ref in calendar['references']:
        w,wkind=timestamp(ref['wall']);u,ukind=timestamp(ref['utc'])
        assert wkind=='Unspecified' and ukind=='Utc' and u==w-ref['offset_ticks']
    snap=data['snapshot']
    assert snap['hash_algorithm']=='R53F_SNAPSHOT_BITS_V1'
    first,kind=timestamp(snap['first']);last,_=timestamp(snap['last'])
    assert kind=='Unspecified' and last-first==4*600000000
    assert snap['rows']==snap['unspecified_count']==5 and snap['utc_count']==snap['local_count']==0
    assert snap['duplicate_pairs']==snap['decreasing_pairs']==snap['misaligned_count']==snap['kind_transitions']==0
    assert snap['increasing_pairs']==4 and data['source_timestamp']==snap['first']
    # Independently reconstruct only this known synthetic five-row OHLCV fixture.
    import struct
    bits=lambda value: struct.unpack('<q',struct.pack('<d',value))[0]
    raw=b'R53F_SNAPSHOT_BITS_V1|5\n'
    for i in range(5):
        raw+=('|'.join(map(str,[i,first+i*600000000,0,bits(20000),bits(20003),bits(19999),bits(20000.25),10]))+'\n').encode()
    assert snap['sha256']==sha256(raw).hexdigest()
    evidence=(folder/'capture'/'session-timestamp-evidence.jsonl').read_bytes()
    seal=(folder/'capture'/'session-timestamp-evidence.done.json').read_bytes()
    verified=verify_evidence(evidence,seal)
    assert verified['status']=='PASS_DIAGNOSTIC_CONTRACT_ONLY' and verified['origin_claim']=='SYNTHETIC'
    assert verified['snapshot_sha256']==snap['sha256'] and verified['template_sha256']==data['loaded_calendar_sha256']
    assert verified['native_provenance_attested'] is verified['template_calendar_attested'] is False
    assert verified['constructor_attempts']<=11 and verified['call_attempts']<=12
    return verified

@pytest.mark.parametrize('mode',SUCCESS_MODES)
def test_context_binding_into_unchanged_matrix_evidence(binary,tmp_path,mode):
    data=run(binary,tmp_path,'--emit',mode)
    assert data['sealed'] is True
    check_context_sample(tmp_path)

def test_context_structural_boundaries():
    text=SOURCE.read_text(encoding='utf-8')
    code=re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/','',text,flags=re.S)
    assert not re.search(r'\b(Account|Order|Execution|SubmitOrder|CreateOrder|AtmStrategy|Indicator|Strategy|Process|Timer|Task|DllImport|Activator|File|Directory|SessionIterator)\b',code)
    assert 'GetNextSession' not in code and 'request.Request(' not in code
    assert code.count('new BarsRequest(')==1 and code.count('raw.Dispose(')==1
    assert code.count('Connection.PlaybackConnection')==1
    assert 'Object.ReferenceEquals(this,instanceOwner)' in code
    assert 'R53F_SNAPSHOT_BITS_V1' in text
    assert 'SessionTimestampPlanV1.InterpretTradingHoursUtc' in code
    assert 'ToUniversalTime(' not in code and 'ToLocalTime(' not in code
    assert 'SpecifyKind(' not in code and 'TimeZoneInfo.ConvertTime' not in code

def test_native_context_sdk_reference_compile_only(tmp_path):
    assert CSC.is_file(), 'WINDOWS_COMPILER_REQUIRED_NO_SKIP'
    refs=[SDK/'NinjaTrader.Core.dll',SDK/'NinjaTrader.Gui.dll',CSC.parent/'WPF/WindowsBase.dll']
    assert all(x.is_file() for x in refs),'INSTALLED_SDK_REQUIRED_NO_SKIP'
    dll=tmp_path/'R53NativeContextCompileOnly.dll'
    cmd=[str(CSC),'/nologo','/langversion:5','/target:library','/out:'+str(dll),
         '/r:System.Core.dll','/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',
         *['/r:'+str(x) for x in refs],*map(str,CORES),str(SOURCE)]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert result.returncode==0 and dll.is_file(),result.stdout+result.stderr
    assert str(HARNESS) not in cmd
    # DLL is never loaded or executed; only the executable with explicit doubles runs.


# F1: negative controls for the corrected harness dispatch, not production edits.
# A harness that misroutes bind_repeated must not pass these mutation checks.
def check_bind_repeated_mutant(folder, mutation):
    assert mutation in ('removed', 'always_reject')
    folder.mkdir(parents=True, exist_ok=False)
    source=SOURCE.read_text(encoding='utf-8')
    anchor='Require(!bound,"SNAPSHOT_ALREADY_BOUND");BaseCheck();'
    assert source.count(anchor)==1, 'BIND_GUARD_ANCHOR_CHANGED'
    replacement=('BaseCheck();' if mutation=='removed'
                 else 'Require(false,"SNAPSHOT_ALREADY_BOUND");BaseCheck();')
    mutant=folder/'NativeContextMutant.cs'
    mutant.write_text(source.replace(anchor,replacement,1),encoding='utf-8',newline='\n')
    exe=folder/'context-mutant-doubles.exe'
    command=[str(CSC),'/nologo','/langversion:5','/target:exe','/out:'+str(exe),
             '/r:System.Core.dll','/r:System.Web.Extensions.dll',*map(str,CORES),str(mutant),str(HARNESS)]
    (folder/'compile-command.json').write_text(json.dumps(command,indent=2),encoding='utf-8')
    compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=45)
    (folder/'compile-stdout.txt').write_text(compiled.stdout,encoding='utf-8')
    (folder/'compile-stderr.txt').write_text(compiled.stderr,encoding='utf-8')
    assert compiled.returncode==0 and exe.is_file(),compiled.stdout+compiled.stderr
    command=[str(exe),'--case',str(folder),'bind_repeated']
    (folder/'run-command.json').write_text(json.dumps(command,indent=2),encoding='utf-8')
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=45)
    (folder/'run-stdout.txt').write_text(result.stdout,encoding='utf-8')
    (folder/'run-stderr.txt').write_text(result.stderr,encoding='utf-8')
    assert result.returncode==1,result.stdout+result.stderr
    data=json.loads(result.stdout)
    assert data['classification']=='SYNTHETIC_LOADED_CONTEXT_ONLY'
    assert data['total']==data['failed']==1 and data['passed']==0
    assert data['real_native_api_calls']==data['loaded_ninjatrader_assemblies']==0
    detail=('Exception:EXPECTED_CONTEXT_REJECTION' if mutation=='removed'
            else 'NativeContextGuardException:SNAPSHOT_ALREADY_BOUND')
    assert data['results']==[dict(name='bind_repeated',status='FAIL',detail=detail)]
    # Expected test failure demonstrates that the repaired case reaches both binds.
    return dict(mutation=mutation,status='EXPECTED_MUTANT_REJECTED',case='bind_repeated',
                expected_exit=1,observed_exit=result.returncode,native_execution=False)


@pytest.mark.parametrize('mutation', ['removed','always_reject'])
def test_bind_repeated_dispatch_mutation_controls(tmp_path,mutation):
    check_bind_repeated_mutant(tmp_path/('guard-mutant-'+mutation),mutation)
