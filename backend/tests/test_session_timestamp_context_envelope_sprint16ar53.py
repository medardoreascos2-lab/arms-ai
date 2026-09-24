"""G: composed C# writer against explicit SDK doubles + strict Python envelope verifier.
Reference vectors test the byte/graph contract, not the truth of native observations.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, datetime, timedelta
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

import pytest
from tools.verify_session_timestamp_context_envelope_v1 import (
    verify_envelope,read_capture,FILES,SEAL_NAME,VERSION,MAX_TICKS,MAX_TOTAL,stamp_for,
    kind_transition_feasible,
)
from tools.verify_session_timestamp_evidence_v1 import verify_evidence

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'integrations/ninjatrader/ArmsSessionTimestampContextEnvelopeV1.cs'
HARNESS=ROOT/'backend/tests/fixtures/session_timestamp_context_envelope_harness_sprint16ar53.cs'
DOUBLES=ROOT/'backend/tests/fixtures/session_timestamp_native_context_harness_sprint16ar53.cs'
CORES=[ROOT/('integrations/ninjatrader/ArmsSessionTimestamp'+n+'V1.cs') for n in ('Plan','Executor','Lifecycle','Evidence','NativeBridge','NativeContext')]
CSC=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK=Path('C:/Program Files/NinjaTrader 8/bin')
SUCCESS_MODES=('normal','inline','async','all_false','false','constructor_error','advance_error','begin_error','end_error','bad_order','bad_kind',
    'r0_false','r0_constructor_error','r0_advance_error','r0_begin_error','r0_end_error','r0_bad_order','r0_bad_kind',
    'mixed','duplicate','decreasing','misaligned','rows4503','rows5520','rows10002','irrelevant_exceptions',
    'clone_writer','foreign_owner_prepare','foreign_owner_publish','native_origin_claim')
FAILURE_MODES=('inline_then_throw','duplicate_inline','callback_error','wrong_callback','submit_error','mutation_during_matrix','policy_during_matrix',
    'duplicate_in_matrix','terminate_in_matrix','foreign_before_open','foreign_before_prepare','foreign_plan','repeat_prepare',
    'mutation_after_prepare','environment_after_prepare','request_dispose_error')
CORRUPTION_MODES=('context_bytes','matrix_bytes','context_missing','foreign_root','foreign_matrix','existing_temp','existing_envelope',
    'environment','invalidation','context_length_state','inner_seal_only')
CASES=tuple('success_'+x for x in SUCCESS_MODES)+tuple('failure_'+x for x in FAILURE_MODES)+tuple('corrupt_'+x for x in CORRUPTION_MODES)+('pending_early_seal',)


def encode(value):return json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def reference_objects():
    """Independent, fixed five-row reference; no SDK and no claimed native provenance."""
    dayticks=864000000000;secticks=10000000;minticks=600000000
    def fromticks(ticks,kind):
        days,rem=divmod(ticks,dayticks);seconds,frac=divmod(rem,secticks);h,rem=divmod(seconds,3600);m,s=divmod(rem,60)
        d=date.fromordinal(days+1)
        return dict(clock=f'{d.isoformat()}T{h:02d}:{m:02d}:{s:02d}.{frac:07d}',ticks=ticks,kind=kind)
    first=stamp_for(15,22,1);last=fromticks(first['ticks']+4*minticks,'Unspecified')
    bits=lambda x:struct.unpack('<q',struct.pack('<d',x))[0]
    snapshot_bytes=b'R53F_SNAPSHOT_BITS_V1|5\n'
    for i in range(5):snapshot_bytes+=('|'.join(map(str,[i,first['ticks']+i*minticks,0,bits(20000),bits(20003),bits(19999),bits(20000.25),10]))+'\n').encode()
    snap=dict(hash_algorithm='R53F_SNAPSHOT_BITS_V1',rows=5,first=first,last=last,sha256=sha256(snapshot_bytes).hexdigest(),
        utc_count=0,unspecified_count=5,local_count=0,increasing_pairs=4,duplicate_pairs=0,decreasing_pairs=0,misaligned_count=0,
        kind_transitions=0,interpretation='RAW_TICKS_AND_KIND_NOT_NORMALIZED')
    config=dict(instrument='NQ DEC26',master='NQ',expiry_month='2026-12',tick_size=.25,point_value=20,bars_period='Minute',period_value=1,
        market_data='Last',lookup='Repository',merge='DoNotMerge',reset_at_eod=True,dividend_adjusted=False,split_adjusted=False,
        date_semantics='REQUEST_LOCAL_CALENDAR_DATES',submitted_from=stamp_for(16),submitted_through=stamp_for(21),actual_from=stamp_for(16),actual_through=stamp_for(21))
    zone='Central Standard Time;-300;Synthetic fixed reference;Synthetic fixed reference;;'
    walls=(stamp_for(13,17),stamp_for(14,16),stamp_for(14,17),stamp_for(15,16))
    calendar=dict(name='CME US Index Futures ETH',version=5119,zone_id='Central Standard Time',zone_serialized=zone,zone_sha256=sha256(zone.encode()).hexdigest(),
        sessions_hhmm=[f'{i}|1700|{i+1}|1600|{i+1}' for i in range(5)],holidays=[],partials=[],
        relevant_exception_policy='REJECT_2026_09_13_THROUGH_22',references=[dict(wall=w,utc=fromticks(w['ticks']+5*3600*secticks,'Utc'),offset_ticks=-5*3600*secticks) for w in walls])
    cfgtext=encode(config).decode();caltext=encode(calendar).decode();calhash=sha256(caltext.encode()).hexdigest()
    context=dict(schema='arms.r53.loaded-context.v1',version='R5.3-F/native-context/1',classification='DIAGNOSTIC_ONLY',
        request_configuration_json=cfgtext,request_configuration_sha256=sha256(cfgtext.encode()).hexdigest(),loaded_calendar_json=caltext,
        loaded_calendar_sha256=calhash,snapshot=snap,source_index=0,source_timestamp=first,request_constructor_attempts=1,
        application_timezone='UTC',sdk_version='8.1.8.2',sdk_core_mvid='b9f356eb-d9d3-4822-8888-14bf46a8c3cf',playback_connected=False,
        operator_confirmations='ENABLED_MARKET_OPEN_DATA_FLOW_CONNECTION_STABLE_TRUE',operator_observations_independently_verified=False,
        bar_timestamp_conversion=False,native_provenance_attested=False,certification_evidence=False,runtime_admission=False,
        validation_scope='LOADED_VALUES_CHECKED_AT_OBSERVATION_POINTS_NOT_PROVIDER_ATTESTATION')
    controls=[];ids=('A_U','A_LUTC','A_THUTC','B_U','B_LUTC','B_THUTC','C_U','C_LUTC','C_THUTC','R0','R1','N')
    for i,case in enumerate(ids):
        rawticks=first['ticks'] if i<3 else stamp_for(14,21)['ticks'] if i<6 else stamp_for(14,21)['ticks']+1 if (i<9 or i==10) else stamp_for(14)['ticks'] if i==9 else stamp_for(14,22,1)['ticks']
        kind='Utc' if i in (9,11) else 'Unspecified'
        variant=('U','LUTC','THUTC')[i%3] if i<9 else 'LUTC' if i==10 else 'REFERENCE_UTC'
        qt=rawticks+(5*3600*secticks if variant=='THUTC' else 0);qkind='Unspecified' if variant=='U' else 'Utc'
        provenance='CALLER_SUPPLIED_BARS_INDEX_0' if i<3 else 'CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE' if i<6 else 'CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE_PLUS_ONE_TICK' if (i<9 or i==10) else 'R2_R4_REFERENCE_UTC' if i==9 else 'TEMPLATE_EXPECTATION_NOT_OBSERVED_BOUND'
        controls.append(dict(ordinal=i+1,case_id=case,family='ABC'[i//3] if i<9 else 'R' if i<11 else 'N',iterator_id='I%02d'%(i+1 if i<10 else 10 if i==10 else 11),
            reuse=i==10,prerequisite='R0_TRUE_READABLE_VALID_BOUNDS' if i==10 else 'NONE',source_index=0 if i<3 else None,provenance=provenance,
            reference_utc=None if i<3 else fromticks(rawticks,'Utc'),constructor_context='Bars',include_end_time=True,
            raw_range=first['ticks']<=rawticks<=last['ticks'],range_interpretation='RAW_TICKS_ONLY_NOT_SESSION_MEMBERSHIP',raw=fromticks(rawticks,kind),query=fromticks(qt,qkind),
            variant=variant,method={'U':'IDENTITY_RAW_CLOCK','LUTC':'SPECIFY_KIND_UTC_SAME_TICKS','THUTC':'EXPLICIT_SOURCE_ZONE_TO_UTC','REFERENCE_UTC':'PRESERVED_REFERENCE_UTC'}[variant],
            source_zone_id='Central Standard Time' if variant=='THUTC' else None,source_offset_ticks=-5*3600*secticks if variant=='THUTC' else None,
            conversion_performed=variant=='THUTC',kind_changed=kind!=qkind,tick_delta=qt-rawticks))
    plan=dict(returned_rows=5,raw_first=first,raw_last=last,snapshot_sha256=snap['sha256'],template_sha256=calhash,source_zone_id='Central Standard Time',template_calendar_attested=False,maximum_calls=12,maximum_iterators=11,cases=controls)
    flags=dict(native_provenance_attested=False,certification_evidence=False,runtime_admission=False,execution_authority=False)
    common=dict(version='R5.3-D/evidence/1',classification='DIAGNOSTIC_ONLY',origin='SYNTHETIC',probe_uuid='01275de9-8f7f-4d30-b8ad-0f0c47ec9e88',request_uuid='16f11aaa-173f-41e2-80c0-45313e7a7c95',**flags)
    rows=[]
    def row(stage,payload):rows.append(dict(schema='arms.r53.evidence.record.v1',sequence=len(rows),stage=stage,payload=payload,**common))
    row('EVIDENCE_STARTED',dict(format='RAW_CLOCK_TEXT_PLUS_TICKS_AND_KIND',source_metadata_attestation='CALLER_SUPPLIED_NOT_INDEPENDENTLY_ATTESTED'))
    row('PLAN_PREPARED',plan)
    for i,case in enumerate(ids):
        row('CASE_RESULT',dict(case_id=case,outcome='RETURNED_TRUE',guard='NONE',exception_type='NONE',returned=True,
            begin=stamp_for(13,22,kind='Utc'),end=stamp_for(14,21,kind='Utc'),bounds_readable=True,bounds_valid=True,constructor_attempts=i+1 if i<10 else i,call_attempts=i+1))
    row('EVIDENCE_PREPARED',dict(matrix_completed=True,stop_guard='NONE',constructor_attempts=11,call_attempts=12,begin_read_attempts=12,end_read_attempts=12))
    lc=dict(status='READY_FOR_SEAL_NOT_SEALED',stop_guard='NONE',exception_type='NONE',writer_factory_attempts=1,request_factory_attempts=1,submit_attempts=1,
        process_attempts=1,preparation_attempts=1,request_dispose_attempts=1,writer_dispose_attempts=1,duplicate_callbacks=0,
        submit_returned=True,request_closed=True,writer_closed=True,resources_released=True,ready_for_seal=True)
    ms=dict(schema='arms.r53.evidence.seal.v1',diagnostic_complete=True,writer_closed=True,lifecycle=lc,sha256='',bytes=0,records=15,**common)
    env=dict(schema='arms.r53.context-envelope.seal.v1',version=VERSION,classification='DIAGNOSTIC_ONLY',origin='SYNTHETIC',probe_uuid=common['probe_uuid'],request_uuid=common['request_uuid'],
        diagnostic_complete=True,writer_closed=True,context_snapshot_sha256=snap['sha256'],context_template_sha256=calhash,returned_rows=5,request_constructor_attempts=1,
        iterator_constructor_attempts=11,getnextsession_attempts=12,source_index=0,source_timestamp=first,total_bound_bytes=0,files=[],
        context_attestation='CAPTURED_VALUES_BOUND_NOT_PROVIDER_ATTESTATION',**flags)
    # Remove unintended sharing: evidence mutation tests alter one observation at a time.
    return tuple(deepcopy(x) for x in (context,rows,ms,env))


def reseal_objects(context,rows,ms,env):
    ctx=encode(context);mr=b''.join(encode(r)+b'\n' for r in rows)
    ms=deepcopy(ms);ms.update(sha256=sha256(mr).hexdigest(),bytes=len(mr),records=len(rows));msraw=encode(ms)
    env=deepcopy(env);env['files']=[dict(path=p,bytes=len(b),sha256=sha256(b).hexdigest()) for p,b in zip(FILES,(ctx,mr,msraw))]
    env['total_bound_bytes']=len(ctx)+len(mr)+len(msraw)
    return ctx,mr,msraw,encode(env)


def reference_vector():return reseal_objects(*reference_objects())


def set_path(obj,path,value):
    parts=path.split('.')
    for part in parts[:-1]:obj=obj[int(part)] if type(obj) is list else obj[part]
    obj[int(parts[-1]) if type(obj) is list else parts[-1]]=value


CONTEXT_MUTATIONS=(('schema','bad'),('version','bad'),('classification','CERTIFIED'),('source_index',1),('source_index',False),
    ('request_constructor_attempts',True),('request_constructor_attempts',2),('application_timezone','Central Standard Time'),('sdk_version','8.1.8.1'),
    ('sdk_core_mvid','invalid'),('playback_connected',True),('operator_confirmations','NONE'),('operator_observations_independently_verified',True),
    ('bar_timestamp_conversion',True),('native_provenance_attested',True),('certification_evidence',True),('runtime_admission',True),('validation_scope','CERTIFIED'),
    ('request_configuration_sha256','0'*64),('loaded_calendar_sha256','0'*64),('source_timestamp.ticks',0),('source_timestamp.kind','Utc'),
    ('snapshot.hash_algorithm','sha256'),('snapshot.rows',5.0),('snapshot.rows',True),('snapshot.first.kind','Utc'),('snapshot.last.ticks',0),('snapshot.sha256','0'*64),
    ('snapshot.utc_count',True),('snapshot.unspecified_count',4),('snapshot.kind_transitions',1),('snapshot.duplicate_pairs',1),
    ('snapshot.misaligned_count',5),('snapshot.interpretation','UTC_NORMALIZED'))
CONFIG_MUTATIONS=(('instrument','MNQ DEC26'),('master','MNQ'),('expiry_month','2026-09'),('tick_size',True),('tick_size',.5),('point_value',2),
    ('bars_period','Day'),('period_value',True),('period_value',2),('market_data','Bid'),('lookup','Provider'),('merge','MergeBackAdjusted'),
    ('reset_at_eod',False),('dividend_adjusted',True),('split_adjusted',True),('date_semantics','UTC_RANGE'),('submitted_from.kind','Utc'),
    ('submitted_through.ticks',0),('actual_from.ticks',0),('actual_through.kind','Unknown'))
CALENDAR_MUTATIONS=(('name','OTHER'),('version',True),('zone_id','UTC'),('zone_sha256','0'*64),('zone_serialized','UTC;0;UTC;UTC;UTC;'),
    ('sessions_hhmm',['0|1800|1|1600|1']*5),('relevant_exception_policy','IGNORE'),('references.0.offset_ticks',0),
    ('references.0.wall.kind','Utc'),('references.0.utc.kind','Unspecified'),('references.0.utc.ticks',0),('holidays',None),('partials',None))
SEAL_MUTATIONS=(('schema','bad'),('version','bad'),('classification','CERTIFIED'),('origin','NATIVE_VERIFIED'),('probe_uuid','aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa'),
    ('request_uuid','bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb'),('diagnostic_complete',False),('writer_closed',False),('returned_rows',True),('returned_rows',4),
    ('request_constructor_attempts',True),('iterator_constructor_attempts',12),('getnextsession_attempts',11),('source_index',False),
    ('source_timestamp.kind','Utc'),('context_snapshot_sha256','0'*64),('context_template_sha256','0'*64),('native_provenance_attested',True),
    ('certification_evidence',True),('runtime_admission',True),('execution_authority',True),('context_attestation','PROVEN_NATIVE'))


def mutate_context(path,value):
    c,r,m,e=reference_objects();set_path(c,path,value);return reseal_objects(c,r,m,e)


def mutate_embedded(key,path,value):
    c,r,m,e=reference_objects();inner=json.loads(c[key]);set_path(inner,path,value);c[key]=encode(inner).decode()
    hashkey='request_configuration_sha256' if key=='request_configuration_json' else 'loaded_calendar_sha256'
    c[hashkey]=sha256(c[key].encode()).hexdigest()
    if key=='loaded_calendar_json':r[1]['payload']['template_sha256']=c[hashkey];e['context_template_sha256']=c[hashkey]
    return reseal_objects(c,r,m,e)


def mutate_seal(path,value):
    c,r,m,e=reference_objects();set_path(e,path,value);return reseal_objects(c,r,m,e)


def rejected(blobs):
    with pytest.raises(ValueError):verify_envelope(*blobs)


@pytest.mark.parametrize('path,value',CONTEXT_MUTATIONS)
def test_resealed_context_contradictions(path,value):rejected(mutate_context(path,value))

@pytest.mark.parametrize('path,value',CONFIG_MUTATIONS)
def test_rehashed_configuration_contradictions(path,value):rejected(mutate_embedded('request_configuration_json',path,value))

@pytest.mark.parametrize('path,value',CALENDAR_MUTATIONS)
def test_rehashed_calendar_contradictions(path,value):rejected(mutate_embedded('loaded_calendar_json',path,value))

@pytest.mark.parametrize('path,value',SEAL_MUTATIONS)
def test_envelope_authority_identity_and_counters(path,value):rejected(mutate_seal(path,value))


def test_reference_contract_and_explicit_limits():
    data=verify_envelope(*reference_vector())
    assert data['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
    assert data['returned_rows']==5 and data['bound_file_count']==3
    assert data['zone_rules_independently_reevaluated'] is False
    assert data['omitted_bars_independently_reconstructed'] is False
    assert data['operator_observations_independently_verified'] is False
    assert data['native_provenance_attested'] is data['certification_evidence'] is data['runtime_admission'] is data['execution_authority'] is False


@pytest.mark.parametrize('kind',('Unspecified','Utc','Local'))
def test_actual_request_date_kind_is_recorded_not_normalized(kind):
    blobs=mutate_embedded('request_configuration_json','actual_from.kind',kind)
    assert verify_envelope(*blobs)['bar_timestamp_conversion'] is False


@pytest.mark.parametrize('level',('context','config','calendar','snapshot','envelope','file_descriptor'))
def test_exact_field_sets_at_every_level(level):
    blobs=list(reference_vector())
    if level in ('context','snapshot','config','calendar'):
        c,r,m,e=reference_objects()
        if level=='context':c['unexpected']=0
        elif level=='snapshot':c['snapshot']['unexpected']=0
        else:
            key='request_configuration_json' if level=='config' else 'loaded_calendar_json'
            obj=json.loads(c[key]);obj['unexpected']=0;c[key]=encode(obj).decode()
            hk='request_configuration_sha256' if level=='config' else 'loaded_calendar_sha256';c[hk]=sha256(c[key].encode()).hexdigest()
            if level=='calendar':r[1]['payload']['template_sha256']=c[hk];e['context_template_sha256']=c[hk]
        rejected(reseal_objects(c,r,m,e));return
    e=json.loads(blobs[3]);(e if level=='envelope' else e['files'][0])['unexpected']=0;blobs[3]=encode(e);rejected(blobs)


@pytest.mark.parametrize('position',range(4))
def test_each_bound_input_rejects_truncation_or_wrong_type(position):
    original=reference_vector()
    for changed in (None,'text',b'',original[position][:-1]):
        blobs=list(original);blobs[position]=changed;rejected(blobs)


@pytest.mark.parametrize('fault',('duplicate_context_key','duplicate_envelope_key','nan','bool_length','float_total','path_traversal','descriptor_order','unknown_schema','missing_file'))
def test_json_and_manifest_fail_closed(fault):
    c,m,ms,e=reference_vector();env=json.loads(e)
    if fault=='duplicate_context_key':c=c[:-1]+b',"source_index":0}';env['files'][0].update(bytes=len(c),sha256=sha256(c).hexdigest());env['total_bound_bytes']=len(c)+len(m)+len(ms)
    elif fault=='duplicate_envelope_key':rejected((c,m,ms,e[:-1]+b',"source_index":0}'));return
    elif fault=='nan':rejected((c,m,ms,e[:-1]+b',"source_index":NaN}'));return
    elif fault=='bool_length':env['files'][0]['bytes']=True
    elif fault=='float_total':env['total_bound_bytes']=float(env['total_bound_bytes'])
    elif fault=='path_traversal':env['files'][0]['path']='../context.json'
    elif fault=='descriptor_order':env['files'].reverse()
    elif fault=='unknown_schema':env['schema']='arms.r53.evidence.seal.v1'
    elif fault=='missing_file':env['files'].pop()
    rejected((c,m,ms,encode(env)))


@pytest.mark.parametrize('fault',('holiday','partial','duplicate_holiday','invalid_holiday_ticks','negative_transition','mixed_without_transition','impossible_endpoint_counts','invalid_partial_time'))
def test_calendar_exception_and_snapshot_crosschecks(fault):
    c,r,m,e=reference_objects();cal=json.loads(c['loaded_calendar_json'])
    if fault=='holiday':cal['holidays']=[str(stamp_for(14)['ticks'])+'|Unspecified']
    elif fault=='partial':cal['partials']=[encode(dict(ticks=stamp_for(14)['ticks'],kind='Unspecified',early=True,late=False,constraint=None,sessions=[])).decode()]
    elif fault=='duplicate_holiday':cal['holidays']=['0|Unspecified','0|Unspecified']
    elif fault=='invalid_holiday_ticks':cal['holidays']=[str(MAX_TICKS+1)+'|Unspecified']
    elif fault=='negative_transition':c['snapshot']['kind_transitions']=-1
    elif fault=='mixed_without_transition':c['snapshot']['unspecified_count']=4;c['snapshot']['utc_count']=1
    elif fault=='impossible_endpoint_counts':c['snapshot'].update(unspecified_count=1,utc_count=4,kind_transitions=2)
    elif fault=='invalid_partial_time':cal['partials']=[encode(dict(ticks=0,kind='Unspecified',early=True,late=False,constraint='0|2560|1|1700|1',sessions=[])).decode()]
    c['loaded_calendar_json']=encode(cal).decode();c['loaded_calendar_sha256']=sha256(c['loaded_calendar_json'].encode()).hexdigest()
    r[1]['payload']['template_sha256']=e['context_template_sha256']=c['loaded_calendar_sha256']
    rejected(reseal_objects(c,r,m,e))


def aggregate_objects(counts,last_kind,transitions):
    """Synthetic bars with real fingerprint bytes; only the transition claim varies.

    Their grouped interior is one possible ordering, not an attested ordering.
    The verifier only decides whether SOME ordering fits the summary.
    """
    c,r,m,e=reference_objects();s=c['snapshot'];n=sum(counts)
    labels=('Unspecified','Utc','Local');remaining=dict(zip(labels,counts))
    remaining['Unspecified']-=1;remaining[last_kind]-=1
    assert n>=3 and min(remaining.values())>=0
    kinds=['Unspecified']+[k for k in labels for _ in range(remaining[k])]+[last_kind]
    first=s['first'];last=deepcopy(first);last['ticks']+=(n-1)*600000000;last['kind']=last_kind
    last['clock']=(datetime.fromisoformat(first['clock'])+timedelta(minutes=n-1)).isoformat(timespec='microseconds')+'0'
    bits=lambda x:struct.unpack('<q',struct.pack('<d',x))[0]
    raw=f'R53F_SNAPSHOT_BITS_V1|{n}\n'.encode()
    raw+=b''.join(('|'.join(map(str,[i,first['ticks']+i*600000000,labels.index(k),bits(20000),bits(20003),bits(19999),bits(20000.25),10]))+'\n').encode() for i,k in enumerate(kinds))
    s.update(rows=n,last=last,sha256=sha256(raw).hexdigest(),increasing_pairs=n-1,
        unspecified_count=counts[0],utc_count=counts[1],local_count=counts[2],kind_transitions=transitions)
    plan=r[1]['payload'];plan.update(returned_rows=n,raw_last=deepcopy(last),snapshot_sha256=s['sha256'])
    for case in plan['cases']:case['raw_range']=first['ticks']<=case['raw']['ticks']<=last['ticks']
    e.update(returned_rows=n,context_snapshot_sha256=s['sha256'])
    return c,r,m,e


def check_aggregate_binding(blobs):
    """Assert dependent byte/hash links before testing acceptance or rejection."""
    c,m,ms,e=blobs;seal=json.loads(e);inner=json.loads(ms)
    assert seal['files']==[dict(path=p,bytes=len(b),sha256=sha256(b).hexdigest()) for p,b in zip(FILES,(c,m,ms))]
    assert seal['total_bound_bytes']==len(c)+len(m)+len(ms)
    assert inner['sha256']==sha256(m).hexdigest() and inner['bytes']==len(m)
    assert inner['records']==len(m.splitlines())
    context=json.loads(c);plan=json.loads(m.splitlines()[1])['payload']
    assert context['snapshot']['sha256']==plan['snapshot_sha256']==seal['context_snapshot_sha256']
    assert verify_evidence(m,ms)['status']=='PASS_DIAGNOSTIC_CONTRACT_ONLY'


def test_g1_reported_impossible_transitions_resealed():
    # This must fail if the feasibility call is removed, even with all seals valid.
    objects=aggregate_objects((4,0,1),'Unspecified',2)
    positive=reseal_objects(*objects);check_aggregate_binding(positive)
    assert verify_envelope(*positive)['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
    objects[0]['snapshot']['kind_transitions']=4
    negative=reseal_objects(*objects);check_aggregate_binding(negative)
    rejected(negative)


@pytest.mark.parametrize('counts,last_kind,transitions,possible',(
    ((5,0,0),'Unspecified',0,True),((5,0,0),'Unspecified',1,False),
    ((3,1,1),'Unspecified',4,True),
    ((3,0,2),'Local',2,False),((3,0,2),'Local',3,True),((3,0,2),'Local',4,False),
    ((3,0,2),'Unspecified',3,False),((3,0,2),'Unspecified',4,True),
    ((2,2,1),'Unspecified',2,False),((2,2,1),'Unspecified',3,True),((2,2,1),'Unspecified',4,True),
    ((1,1,1),'Local',2,True),((1,1,1),'Local',1,False),
    ((1,3,1),'Utc',2,True),((1,3,1),'Utc',4,False),
    ((10002,0,0),'Unspecified',0,True),((10002,0,0),'Unspecified',1,False),
    ((10000,1,1),'Unspecified',4,True),((10000,1,1),'Unspecified',5,False),
    ((5001,5001,0),'Utc',10001,True),((5001,5001,0),'Utc',10000,False),
    ((5002,5000,0),'Unspecified',10000,True),((5002,5000,0),'Unspecified',10001,False),
    ((3334,3334,3334),'Unspecified',10001,True),
))
def test_g1_resealed_aggregate_feasibility(counts,last_kind,transitions,possible):
    blobs=reseal_objects(*aggregate_objects(counts,last_kind,transitions))
    check_aggregate_binding(blobs)
    if possible:
        result=verify_envelope(*blobs)
        assert result['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
        assert result['omitted_bars_independently_reconstructed'] is result['native_provenance_attested'] is False
    else:rejected(blobs)


@pytest.mark.parametrize('field',('unspecified_count','utc_count','local_count','kind_transitions'))
@pytest.mark.parametrize('value',(True,1.0,-1))
def test_g1_aggregate_strict_scalars(field,value):
    objects=aggregate_objects((3,1,1),'Unspecified',4)
    objects[0]['snapshot'][field]=value
    blobs=reseal_objects(*objects);check_aggregate_binding(blobs);rejected(blobs)


@pytest.mark.parametrize('field,value',(
    ('unspecified_count',4),('utc_count',0),('kind_transitions',5),
    ('rows',1),('rows',2),('first.kind','Unknown'),('last.kind','Unknown'),
))
def test_g1_aggregate_contract_not_relaxed(field,value):
    objects=aggregate_objects((3,1,1),'Unspecified',4)
    set_path(objects[0]['snapshot'],field,value)
    blobs=reseal_objects(*objects);check_aggregate_binding(blobs);rejected(blobs)


@pytest.mark.parametrize('n',range(1,9))
def test_g1_exhaustive_kind_oracle(n):
    # Direct enumeration is independent of runs, degrees and verifier bounds.
    # n=1,2 exercise only the mathematical helper, never the context contract.
    labels=('Unspecified','Utc','Local');observed=set()
    for seq in product(labels,repeat=n):
        observed.add((tuple(seq.count(k) for k in labels),seq[0],seq[-1],
            sum(a!=b for a,b in zip(seq,seq[1:]))))
    possible=impossible=0
    for u in range(n+1):
        for utc in range(n-u+1):
            counts=(u,utc,n-u-utc)
            for first,last in product(labels,repeat=2):
                for transitions in range(n):
                    key=(counts,first,last,transitions);expected=key in observed
                    assert kind_transition_feasible(dict(zip(labels,counts)),first,last,transitions)==expected,key
                    possible+=expected;impossible+=not expected
    assert possible==len(observed) and impossible>0


def test_inner_seal_without_envelope_is_not_full_evidence():
    c,m,ms,e=reference_vector();assert verify_evidence(m,ms)['status']=='PASS_DIAGNOSTIC_CONTRACT_ONLY'
    rejected((c,m,ms,None));rejected((c,m,ms,ms))


def test_bounds_and_omitted_bars_not_authenticated_by_resealing():
    # A fully coherent forged replacement hash cannot be disproved without bar data.
    c,r,m,e=reference_objects();digest='a'*64;c['snapshot']['sha256']=digest;r[1]['payload']['snapshot_sha256']=digest;e['context_snapshot_sha256']=digest
    result=verify_envelope(*reseal_objects(c,r,m,e))
    assert result['omitted_bars_independently_reconstructed'] is False and result['native_provenance_attested'] is False


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    assert CSC.is_file(),'WINDOWS_FRAMEWORK_COMPILER_REQUIRED_NO_SKIP'
    exe=tmp_path_factory.mktemp('r53-context-envelope')/'harness.exe'
    command=[str(CSC),'/nologo','/langversion:5','/target:exe','/main:ContextEnvelopeHarness','/out:'+str(exe),
        '/r:System.Core.dll','/r:System.Web.Extensions.dll',*map(str,CORES),str(SOURCE),str(DOUBLES),str(HARNESS)]
    p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert p.returncode==0 and exe.is_file(),p.stdout+p.stderr
    return exe


def invoke(binary,folder,action,*args):
    p=subprocess.run([str(binary),action,str(folder),*args],cwd=ROOT,capture_output=True,text=True,timeout=180)
    assert p.returncode==0,p.stdout+p.stderr
    d=json.loads(p.stdout);assert d['classification']=='SYNTHETIC_CONTEXT_ENVELOPE_ONLY';return d


@pytest.mark.parametrize('case',CASES)
def test_actual_csharp_envelope_lifetime_and_failures(binary,tmp_path,case):
    d=invoke(binary,tmp_path,'--case',case)
    assert d['total']==d['passed']==1 and d['failed']==0
    assert d['real_native_api_calls']==d['loaded_ninjatrader_assemblies']==0
    assert d['results']==[dict(name=case,status='PASS',detail='NONE')]


def test_complete_envelope_case_inventory(binary,tmp_path):
    d=invoke(binary,tmp_path,'--all');assert d['total']==d['passed']==len(CASES) and d['failed']==0
    assert tuple(x['name'] for x in d['results'])==CASES
    assert d['real_native_api_calls']==d['loaded_ninjatrader_assemblies']==0


@pytest.mark.parametrize('mode',SUCCESS_MODES)
def test_actual_composed_writer_output_verified(binary,tmp_path,mode):
    d=invoke(binary,tmp_path,'--emit',mode);assert d['sealed'] is True
    result=read_capture(tmp_path/'capture')
    assert result['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
    assert result['origin_claim']==('OPERATOR_NATIVE_RUN_UNATTESTED' if mode=='native_origin_claim' else 'SYNTHETIC')
    assert result['returned_rows']==int(mode[4:]) if mode.startswith('rows') else result['returned_rows']==5
    assert result['getnextsession_attempts']<=12 and result['iterator_constructor_attempts']<=11
    assert result['native_provenance_attested'] is result['zone_rules_independently_reevaluated'] is False
    assert result['runtime_admission'] is result['execution_authority'] is False
    assert len(list((tmp_path/'capture').rglob('*')))==5  # one dir plus four files


def write_vector(folder,blobs):
    folder.mkdir();(folder/'matrix').mkdir()
    for p,b in zip((*FILES,SEAL_NAME),blobs):(folder/p).write_bytes(b)


@pytest.mark.parametrize('fault',('none','foreign_root','foreign_matrix','missing_envelope','missing_context','missing_inner_seal','directory_for_file'))
def test_readonly_directory_layout(tmp_path,fault):
    root=tmp_path/'capture';write_vector(root,reference_vector())
    if fault=='foreign_root':(root/'unexpected').write_bytes(b'KEEP')
    if fault=='foreign_matrix':(root/'matrix'/'unexpected').write_bytes(b'KEEP')
    if fault=='missing_envelope':(root/SEAL_NAME).rename(tmp_path/'saved-seal')
    if fault=='missing_context':(root/FILES[0]).rename(tmp_path/'saved-context')
    if fault=='missing_inner_seal':(root/FILES[2]).rename(tmp_path/'saved-inner-seal')
    if fault=='directory_for_file':(root/FILES[0]).rename(tmp_path/'saved-context');(root/FILES[0]).mkdir()
    if fault=='none':assert read_capture(root)['status']=='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY'
    else:
        with pytest.raises((ValueError,OSError)):read_capture(root)


def test_cli_does_not_accept_missing_envelope(tmp_path):
    root=tmp_path/'capture';write_vector(root,reference_vector())
    command=[sys.executable,'-B',str(ROOT/'tools/verify_session_timestamp_context_envelope_v1.py'),'--capture',str(root)]
    p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30);assert p.returncode==0,p.stdout+p.stderr
    (root/SEAL_NAME).rename(tmp_path/'saved');p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert p.returncode==1 and json.loads(p.stdout)['status']=='REJECTED'


def test_context_envelope_structural_boundaries():
    text=SOURCE.read_text();clean=re.sub(r'//[^\n]*','',text)
    for token in ('new BarsRequest(','.GetNextSession(','.GetTime(','.GetOpen(','.GetClose(','.GetHigh(','.GetLow(','.GetVolume(',
        '.ToUniversalTime(','.ToLocalTime(','.SpecifyKind(','.ConvertTime','File.Delete(','Directory.Delete(','Account.', 'AtmStrategy','SubmitOrder','CreateOrder'):
        assert token not in clean
    for token in ('FileMode.CreateNew','FileShare.Read','matrixWriter.PublishSeal(owner)','context.CheckEnvironment(owner)',
        'Object.ReferenceEquals(this,instanceOwner)','context.Revalidate(owner)'):
        assert token in clean


def test_installed_sdk_compile_envelope_no_execution(tmp_path):
    assert CSC.is_file() and (SDK/'NinjaTrader.Core.dll').is_file(),'INSTALLED_SDK_REQUIRED_NO_SKIP'
    refs=[SDK/'NinjaTrader.Core.dll',SDK/'NinjaTrader.Gui.dll',CSC.parent/'WPF/WindowsBase.dll']
    target=tmp_path/'EnvelopeCompileOnly.dll'
    command=[str(CSC),'/nologo','/langversion:5','/target:library','/out:'+str(target),'/r:System.Core.dll',
        '/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',*['/r:'+str(x) for x in refs],*map(str,CORES),str(SOURCE)]
    p=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert p.returncode==0 and target.is_file(),p.stdout+p.stderr


def private_verifier_checks():
    # Same pure-Python contracts run privately before promotion and via pytest after.
    checks=0
    test_reference_contract_and_explicit_limits();checks+=1
    for p,v in CONTEXT_MUTATIONS:test_resealed_context_contradictions(p,v);checks+=1
    for p,v in CONFIG_MUTATIONS:test_rehashed_configuration_contradictions(p,v);checks+=1
    for p,v in CALENDAR_MUTATIONS:test_rehashed_calendar_contradictions(p,v);checks+=1
    for p,v in SEAL_MUTATIONS:test_envelope_authority_identity_and_counters(p,v);checks+=1
    for k in ('Unspecified','Utc','Local'):test_actual_request_date_kind_is_recorded_not_normalized(k);checks+=1
    for level in ('context','config','calendar','snapshot','envelope','file_descriptor'):test_exact_field_sets_at_every_level(level);checks+=1
    for i in range(4):test_each_bound_input_rejects_truncation_or_wrong_type(i);checks+=1
    for f in ('duplicate_context_key','duplicate_envelope_key','nan','bool_length','float_total','path_traversal','descriptor_order','unknown_schema','missing_file'):
        test_json_and_manifest_fail_closed(f);checks+=1
    for f in ('holiday','partial','duplicate_holiday','invalid_holiday_ticks','negative_transition','mixed_without_transition','impossible_endpoint_counts','invalid_partial_time'):
        test_calendar_exception_and_snapshot_crosschecks(f);checks+=1
    test_inner_seal_without_envelope_is_not_full_evidence();checks+=1
    test_bounds_and_omitted_bars_not_authenticated_by_resealing();checks+=1
    return checks
