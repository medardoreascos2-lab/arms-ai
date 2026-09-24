"""R5.3-D: actual C# evidence writer with A/B/C + independent Python verifier.
Synthetic filesystem/request/iterator tests; no native NinjaTrader interaction.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import pytest
from tools.verify_session_timestamp_evidence_v1 import verify_evidence

ROOT=Path(__file__).resolve().parents[2]
SOURCES=[ROOT/'integrations/ninjatrader'/('ArmsSessionTimestamp'+part+'V1.cs')
         for part in ('Plan','Executor','Lifecycle','Evidence')]
HARNESS=ROOT/'backend/tests/fixtures/session_timestamp_evidence_harness_sprint16ar53.cs'
CSC=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
CASES=(
    'success_normal','success_inline','success_async','success_all_false','success_false',
    'success_constructor_error','success_advance_error','success_begin_error','success_end_error','success_bad_order','success_bad_kind',
    'success_r0_false','success_r0_constructor_error','success_r0_advance_error','success_r0_begin_error','success_r0_end_error','success_r0_bad_order','success_r0_bad_kind',
    'failure_inline_then_throw','failure_submit_error','failure_context_error','failure_dispose_error',
    'foreign_before_open','writer_clone_no_cross_close','pending_never_seals','wrong_owner_preserves_owner',
    'modified_bytes_no_seal','foreign_after_close','existing_temp_not_overwritten','existing_seal_not_overwritten',
    'seal_not_repeated','late_callback_no_mutation','repeat_dispose_no_mutation')
SUCCESS_MODES=tuple(x[8:] for x in CASES if x.startswith('success_'))

@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    if not CSC.is_file():pytest.fail('WINDOWS_FRAMEWORK_COMPILER_REQUIRED')
    folder=tmp_path_factory.mktemp('r53-evidence-build');exe=folder/'r53-evidence-tests.exe'
    command=[str(CSC),'/nologo','/langversion:5','/target:exe','/out:'+str(exe),
             '/r:System.Core.dll','/r:System.Web.Extensions.dll',*[str(x) for x in SOURCES],str(HARNESS)]
    proc=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=45)
    assert proc.returncode==0 and exe.is_file(),proc.stdout+proc.stderr
    return exe

def invoke(binary,*args):
    proc=subprocess.run([str(binary),*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=90)
    assert proc.returncode==0,proc.stdout+proc.stderr
    return json.loads(proc.stdout)

@pytest.mark.parametrize('case',CASES)
def test_actual_csharp_evidence_writer(binary,tmp_path,case):
    data=invoke(binary,'--case',tmp_path,case)
    assert data['total']==data['passed']==1 and data['failed']==0
    assert data['classification']=='SYNTHETIC_EVIDENCE_IO_ONLY'
    assert data['loaded_ninjatrader_assemblies']==data['real_native_api_calls']==0
    assert data['results'][0]['name']==case

def test_complete_writer_inventory(binary,tmp_path):
    data=invoke(binary,'--all',tmp_path)
    assert data['passed']==data['total']==len(CASES) and data['failed']==0
    assert tuple(x['name'] for x in data['results'])==CASES
    assert data['loaded_ninjatrader_assemblies']==data['real_native_api_calls']==0

def emit(binary,folder,mode):
    folder.mkdir()
    data=invoke(binary,'--emit',folder,mode)
    assert data['classification']=='SYNTHETIC_ONLY' and data['sealed_ok'] is True
    raw=(folder/'session-timestamp-evidence.jsonl').read_bytes()
    seal=(folder/'session-timestamp-evidence.done.json').read_bytes()
    assert len(list(folder.iterdir()))==2
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw+seal
    return raw,seal

@pytest.mark.parametrize('mode',SUCCESS_MODES)
def test_real_writer_output_passes_independent_verifier(binary,tmp_path,mode):
    raw,seal=emit(binary,tmp_path/'capture',mode)
    result=verify_evidence(raw,seal)
    assert result['status']=='PASS_DIAGNOSTIC_CONTRACT_ONLY'
    assert result['origin_claim']=='SYNTHETIC'
    assert result['records']==15 and result['returned_rows']==5
    assert result['native_provenance_attested'] is False
    assert result['template_calendar_attested'] is False
    assert result['runtime_admission'] is False
    assert result['timezone_offset_semantics']=='ALGEBRA_CHECKED_ZONE_RULES_NOT_ATTESTED'
    assert result['call_attempts']<=12 and result['constructor_attempts']<=11

@pytest.fixture(scope='module')
def evidence(binary,tmp_path_factory):
    return emit(binary,tmp_path_factory.mktemp('r53-evidence-fixture')/'capture','normal')

def reseal(rows,original):
    raw=b''.join(json.dumps(x,separators=(',',':')).encode()+b'\n' for x in rows)
    seal=json.loads(original);seal.update(sha256=sha256(raw).hexdigest(),bytes=len(raw),records=len(rows))
    return raw,json.dumps(seal,separators=(',',':')).encode()

PLAN_MUTATIONS=(
    ('returned_rows',True),('maximum_calls',13),('maximum_iterators',12),('template_calendar_attested',True),
    ('raw_first.kind','Utc'),('raw_first.ticks',0),('raw_first.clock','2026-02-30T12:00:00.0000000'),
    ('raw_last.ticks',1),('snapshot_sha256','bad'),('template_sha256',None),
    ('cases.0.ordinal',True),('cases.0.case_id','B_U'),('cases.0.source_index',1),
    ('cases.0.reuse',True),('cases.0.iterator_id','I02'),('cases.0.include_end_time',False),
    ('cases.0.constructor_context','TradingHours'),('cases.0.raw_range',False),
    ('cases.0.provenance','R2_R4_REFERENCE_UTC'),('cases.0.variant','LUTC'),
    ('cases.0.query.kind','Utc'),('cases.0.query.ticks',0),('cases.0.kind_changed',True),
    ('cases.0.tick_delta',1),('cases.0.conversion_performed',True),('cases.0.source_offset_ticks',0),
    ('cases.1.query.kind','Unspecified'),('cases.1.method','IDENTITY_RAW_CLOCK'),
    ('cases.2.source_offset_ticks',False),('cases.2.source_offset_ticks',6000000000000),
    ('cases.2.source_offset_ticks',1),('cases.2.source_zone_id','OTHER'),
    ('cases.2.conversion_performed',False),('cases.2.tick_delta',0),
    ('cases.3.source_index',0),('cases.3.reference_utc.kind','Unspecified'),
    ('cases.6.raw.ticks',0),('cases.10.prerequisite','NONE'),('cases.10.reuse',False),
    ('cases.10.iterator_id','I11'),('cases.10.query.kind','Unspecified'),('cases.11.reference_utc',None),
)

def set_path(obj,path,value):
    parts=path.split('.')
    for part in parts[:-1]:obj=obj[int(part)] if type(obj) is list else obj[part]
    key=int(parts[-1]) if type(obj) is list else parts[-1];obj[key]=value

@pytest.mark.parametrize('path,value',PLAN_MUTATIONS)
def test_resealed_plan_contradictions_rejected(evidence,path,value):
    raw,seal=evidence;rows=[json.loads(x) for x in raw.splitlines()]
    set_path(rows[1]['payload'],path,value)
    with pytest.raises(ValueError):verify_evidence(*reseal(rows,seal))

RESULT_MUTATIONS=(
    ('case_id','B_U'),('outcome','SKIPPED'),('outcome','RETURNED_FALSE'),('returned',False),('returned',1),
    ('guard','OTHER'),('exception_type','OTHER'),('exception_type','PRIVATE_PROVIDER_SENTINEL'),
    ('begin.kind','Unspecified'),('begin.ticks',0),('end',None),('bounds_readable',False),('bounds_valid',False),
    ('constructor_attempts',False),('constructor_attempts',0),('call_attempts',0),('call_attempts',1.0),
)

@pytest.mark.parametrize('path,value',RESULT_MUTATIONS)
def test_resealed_result_contradictions_rejected(evidence,path,value):
    raw,seal=evidence;rows=[json.loads(x) for x in raw.splitlines()]
    set_path(rows[2]['payload'],path,value)
    with pytest.raises(ValueError):verify_evidence(*reseal(rows,seal))

@pytest.mark.parametrize('field,value',[
    ('matrix_completed',False),('stop_guard','OTHER'),('constructor_attempts',12),('call_attempts',11),
    ('begin_read_attempts',11),('end_read_attempts',11),('call_attempts',12.0)])
def test_resealed_total_contradictions(evidence,field,value):
    raw,seal=evidence;rows=[json.loads(x) for x in raw.splitlines()];rows[-1]['payload'][field]=value
    with pytest.raises(ValueError):verify_evidence(*reseal(rows,seal))

@pytest.mark.parametrize('field,value',[
    ('status','PENDING'),('stop_guard','OTHER'),('exception_type','OTHER'),('writer_factory_attempts',2),
    ('request_factory_attempts',True),('submit_attempts',0),('process_attempts',2),('preparation_attempts',0),
    ('request_dispose_attempts',2),('writer_dispose_attempts',0),('duplicate_callbacks',1),('duplicate_callbacks',False),
    ('submit_returned',False),('request_closed',False),('writer_closed',False),('resources_released',False),('ready_for_seal',False)])
def test_lifecycle_seal_requires_closed_owned_resources(evidence,field,value):
    raw,seal=evidence;s=json.loads(seal);s['lifecycle'][field]=value
    with pytest.raises(ValueError):verify_evidence(raw,json.dumps(s).encode())

@pytest.mark.parametrize('field,value',[
    ('sha256','0'*64),('bytes',1),('records',14),('records',15.0),('diagnostic_complete',False),
    ('writer_closed',False),('native_provenance_attested',True),('runtime_admission',True),('execution_authority',True),
    ('certification_evidence',True),('version','old'),('schema','other'),('origin','NATIVE_VERIFIED'),
    ('probe_uuid','invalid'),('request_uuid',None)])
def test_seal_corruption_rejected(evidence,field,value):
    raw,seal=evidence;s=json.loads(seal);s[field]=value
    with pytest.raises(ValueError):verify_evidence(raw,json.dumps(s).encode())

@pytest.mark.parametrize('fault',('unknown','missing','bool_sequence','float_sequence','duplicate','remove','swap','bad_origin','different_uuid','wrong_stage'))
def test_lifecycle_record_shape_strict(evidence,fault):
    raw,seal=evidence;rows=[json.loads(x) for x in raw.splitlines()]
    if fault=='unknown':rows[3]['injected']=1
    elif fault=='missing':del rows[3]['native_provenance_attested']
    elif fault=='bool_sequence':rows[1]['sequence']=True
    elif fault=='float_sequence':rows[1]['sequence']=1.0
    elif fault=='duplicate':rows.insert(3,deepcopy(rows[3]))
    elif fault=='remove':rows.pop(3)
    elif fault=='swap':rows[3],rows[4]=rows[4],rows[3]
    elif fault=='bad_origin':rows[3]['origin']='NATIVE_VERIFIED'
    elif fault=='different_uuid':rows[3]['request_uuid']=rows[3]['probe_uuid']
    elif fault=='wrong_stage':rows[-1]['stage']='EXPERIMENT_COMPLETE'
    with pytest.raises(ValueError):verify_evidence(*reseal(rows,seal))

@pytest.mark.parametrize('fault',('no_newline','oversize','duplicate_key','nan','inf','empty','truncated','bad_utf8','non_object','deep'))
def test_malformed_bytes_rejected(evidence,fault):
    raw,seal=evidence
    if fault=='no_newline':raw=raw[:-1]
    elif fault=='oversize':raw=b'x'*262145
    elif fault=='duplicate_key':seal=seal[:-1]+b',"records":15}'
    elif fault=='nan':seal=seal.replace(b'"records":15',b'"records":NaN')
    elif fault=='inf':seal=seal.replace(b'"records":15',b'"records":Infinity')
    elif fault=='empty':raw=b''
    elif fault=='truncated':raw=raw[:-20]
    elif fault=='bad_utf8':seal=b'\xff'
    elif fault=='non_object':seal=b'[]'
    elif fault=='deep':seal=b'['*1100+b'0'+b']'*1100
    with pytest.raises(ValueError):verify_evidence(raw,seal)

@pytest.mark.parametrize('value',(None,True,False,1,1.0,'',[],{}))
def test_wrong_input_types(evidence,value):
    raw,seal=evidence
    with pytest.raises(ValueError):verify_evidence(value,seal)
    with pytest.raises(ValueError):verify_evidence(raw,value)

def test_cli_has_bounded_reads_and_failure_exit(evidence,tmp_path):
    raw,seal=evidence;p=tmp_path/'e.jsonl';s=tmp_path/'s.json';p.write_bytes(raw);s.write_bytes(seal)
    cmd=[sys.executable,'-B',str(ROOT/'tools/verify_session_timestamp_evidence_v1.py'),'--diagnostic',str(p),'--seal',str(s)]
    good=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert good.returncode==0 and json.loads(good.stdout)['status']=='PASS_DIAGNOSTIC_CONTRACT_ONLY'
    s.write_bytes(b'{}');bad=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert bad.returncode==1 and json.loads(bad.stdout)['status']=='REJECTED'
    assert 'Traceback' not in bad.stderr

def test_new_writer_has_no_native_or_delete_surface():
    src=SOURCES[-1].read_text(encoding='utf-8')
    code=re.sub(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/','',src,flags=re.S)
    assert not re.search(r'\b(NinjaTrader|BarsRequest|SessionIterator|Account|Order|Execution|Process|Timer|DllImport|Activator)\b',code)
    assert not re.search(r'\b(?:File|Directory)\.(?:Delete|Replace)\s*\(',code)
    assert 'File.Delete' not in code and 'Directory.Delete' not in code and 'FileMode.Create,' not in code
    assert 'FileMode.CreateNew' in code and 'stream.Flush(true)' in code
    assert 'Object.ReferenceEquals(this,instanceOwner)' in code
    assert 'Object.ReferenceEquals(s.Matrix,matrix)' in code
