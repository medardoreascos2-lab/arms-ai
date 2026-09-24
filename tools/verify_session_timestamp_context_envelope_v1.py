"""R5.3-G: exact byte binding + loaded-context/matrix consistency, not provenance.
The saved .NET zone blob is hash-bound, NOT executed/deserialized by this verifier.
Offsets are algebraically checked; native values/omitted bars are not attested.
"""
from __future__ import annotations
import argparse
from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.verify_session_timestamp_evidence_v1 import (
    verify_evidence, decode, fields, equal, integer, digest, guid, timestamp,
    MAX_TICKS, TICKS_DAY, TICKS_SECOND,
)

VERSION='R5.3-G/context-envelope/1'
MAX_CONTEXT,MAX_CALENDAR,MAX_ZONE,MAX_TOTAL,MAX_SEAL=131072,65536,32768,262144,4096
CONTEXT_NAME='session-timestamp-context.json'
SEAL_NAME='session-timestamp-context.done.json'
MATRIX_NAME='matrix/session-timestamp-evidence.jsonl'
MATRIX_SEAL_NAME='matrix/session-timestamp-evidence.done.json'
FILES=(CONTEXT_NAME,MATRIX_NAME,MATRIX_SEAL_NAME)
FLAGS=dict(native_provenance_attested=False,certification_evidence=False,runtime_admission=False,execution_authority=False)
SEAL_KEYS=set(FLAGS)|set(('schema version classification probe_uuid request_uuid origin diagnostic_complete writer_closed '
    'context_snapshot_sha256 context_template_sha256 returned_rows request_constructor_attempts iterator_constructor_attempts '
    'getnextsession_attempts source_index source_timestamp total_bound_bytes files context_attestation').split())
CONTEXT_KEYS=set(('schema version classification request_configuration_json request_configuration_sha256 '
    'loaded_calendar_json loaded_calendar_sha256 snapshot source_index source_timestamp request_constructor_attempts '
    'application_timezone sdk_version sdk_core_mvid playback_connected operator_confirmations '
    'operator_observations_independently_verified bar_timestamp_conversion native_provenance_attested '
    'certification_evidence runtime_admission validation_scope').split())
CONFIG_KEYS=set(('instrument master expiry_month tick_size point_value bars_period period_value market_data lookup merge '
    'reset_at_eod dividend_adjusted split_adjusted date_semantics submitted_from submitted_through actual_from actual_through').split())
CALENDAR_KEYS=set(('name version zone_id zone_serialized zone_sha256 sessions_hhmm holidays partials relevant_exception_policy references').split())
SNAPSHOT_KEYS=set(('hash_algorithm rows first last sha256 utc_count unspecified_count local_count increasing_pairs duplicate_pairs '
    'decreasing_pairs misaligned_count kind_transitions interpretation').split())
KINDS=('Unspecified','Utc','Local')


def need(ok):
    if not ok: raise ValueError('INVALID_R53_CONTEXT_ENVELOPE')


def raw_bytes(value,limit):
    need(type(value) is bytes and 0<len(value)<=limit)
    return value


def string(value,limit):
    need(type(value) is str and 0<len(value.encode('utf-8'))<=limit and '\x00' not in value)
    return value


def stamp_for(day,hour=0,minute=0,kind='Unspecified',month=9):
    ticks=(date(2026,month,day).toordinal()-1)*TICKS_DAY+(hour*3600+minute*60)*TICKS_SECOND
    return dict(clock=f'2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00.0000000',ticks=ticks,kind=kind)


def outside_reference_dates(ticks):
    integer(ticks)
    day=ticks//TICKS_DAY
    need(not date(2026,9,13).toordinal()-1 <= day <= date(2026,9,22).toordinal()-1)


def session_definition(text):
    # Stored HHmm observation syntax, not a claim of session membership.
    need(type(text) is str and re.fullmatch(r'[0-6]\|[0-9]{1,4}\|[0-6]\|[0-9]{1,4}\|[0-6]',text) is not None)
    parts=text.split('|')
    for pos in (1,3):
        value=int(parts[pos]);need(value<=2400 and value%100<60 and (value//100<24 or value%100==0))


def validate_calendar(value):
    c=fields(value,CALENDAR_KEYS)
    equal(c['name'],'CME US Index Futures ETH');integer(c['version'],0,2147483647)
    equal(c['zone_id'],'Central Standard Time')
    zone=string(c['zone_serialized'],MAX_ZONE)
    need(zone.startswith('Central Standard Time;'))
    equal(digest(c['zone_sha256']),sha256(zone.encode()).hexdigest())
    equal(c['sessions_hhmm'],[f'{i}|1700|{i+1}|1600|{i+1}' for i in range(5)])
    equal(c['relevant_exception_policy'],'REJECT_2026_09_13_THROUGH_22')
    holidays=c['holidays'];partials=c['partials']
    need(type(holidays) is list and type(partials) is list and len(holidays)<=4096 and len(partials)<=4096)
    for collection in (holidays,partials):
        need(all(type(x) is str for x in collection))
        need(collection==sorted(collection) and len(collection)==len(set(collection)))
    seen=set()
    for h in holidays:
        match=re.fullmatch(r'([0-9]{1,19})\|(Unspecified|Utc|Local)',h);need(match is not None)
        ticks=int(match[1]);outside_reference_dates(ticks)
        need(ticks not in seen);seen.add(ticks)
    seen=set()
    for p in partials:
        raw=string(p,MAX_CALENDAR).encode()
        d=fields(decode(raw),('ticks','kind','early','late','constraint','sessions'))
        outside_reference_dates(d['ticks']);need(d['ticks'] not in seen);seen.add(d['ticks'])
        need(type(d['kind']) is str and d['kind'] in KINDS)
        need(type(d['early']) is bool and type(d['late']) is bool)
        if d['constraint'] is not None:session_definition(d['constraint'])
        need(type(d['sessions']) is list and len(d['sessions'])<=32)
        for s in d['sessions']:session_definition(s)
    refs=c['references'];need(type(refs) is list and len(refs)==4)
    walls=(stamp_for(13,17),stamp_for(14,16),stamp_for(14,17),stamp_for(15,16))
    utc=(stamp_for(13,22,kind='Utc'),stamp_for(14,21,kind='Utc'),stamp_for(14,22,kind='Utc'),stamp_for(15,21,kind='Utc'))
    for r,w,u in zip(refs,walls,utc):
        fields(r,('wall','utc','offset_ticks'))
        wt,wk=timestamp(r['wall']);ut,uk=timestamp(r['utc'])
        equal(r['wall'],w);equal(r['utc'],u)
        integer(r['offset_ticks'],-14*3600*TICKS_SECOND,14*3600*TICKS_SECOND)
        equal(ut,wt-r['offset_ticks'])
    return c


def validate_configuration(value):
    c=fields(value,CONFIG_KEYS)
    fixed=dict(instrument='NQ DEC26',master='NQ',expiry_month='2026-12',bars_period='Minute',period_value=1,
        market_data='Last',lookup='Repository',merge='DoNotMerge',reset_at_eod=True,dividend_adjusted=False,split_adjusted=False,
        date_semantics='REQUEST_LOCAL_CALENDAR_DATES')
    for k,v in fixed.items():equal(c[k],v)
    for k,v in (('tick_size',.25),('point_value',20)):
        need(type(c[k]) in (int,float) and math.isfinite(c[k]) and c[k]==v)
    for suffix,day in (('from',16),('through',21)):
        submitted=c['submitted_'+suffix];actual=c['actual_'+suffix]
        st,sk=timestamp(submitted);at,ak=timestamp(actual)
        equal(submitted,stamp_for(day));equal(at,st)
        # F records actual Kind instead of relabelling it; no UTC assumption here.
    return c


def kind_transition_feasible(counts,first,last,transitions):
    """Exact three-Kind run feasibility; inputs have already passed scalar checks.

    For R > 1 runs, Kind i has r_i runs and e_i fixed endpoints, so its
    degree in the run-adjacency multigraph is 2*r_i-e_i. A loopless graph
    on at most three used vertices exists iff each degree <= R-1. Positive
    degrees make it connected; an Euler trail then gives the required run
    order. See the G1 proof and independent exhaustive oracle in docs/tests.
    """
    runs=transitions+1
    if runs==1:
        return first==last and counts[first]==sum(counts.values())
    lower=upper=0
    for kind in KINDS:
        count=counts[kind];ends=int(first==kind)+int(last==kind)
        lo=max(int(count>0),ends)
        hi=min(count,(runs-1+ends)//2)
        if lo>hi:return False
        lower+=lo;upper+=hi
    return lower<=runs<=upper


def validate_snapshot(value,plan):
    s=fields(value,SNAPSHOT_KEYS);n=integer(s['rows'],3,10002)
    equal(s['hash_algorithm'],'R53F_SNAPSHOT_BITS_V1')
    equal(s['interpretation'],'RAW_TICKS_AND_KIND_NOT_NORMALIZED')
    ft,fk=timestamp(s['first']);lt,lk=timestamp(s['last']);equal(fk,'Unspecified');need(ft<=lt)
    equal(s['first'],plan['raw_first']);equal(s['last'],plan['raw_last'])
    equal(n,plan['returned_rows']);equal(digest(s['sha256']),plan['snapshot_sha256'])
    counts={k:integer(s[k.lower()+'_count'],0,n) for k in KINDS}
    need(sum(counts.values())==n and counts[fk]>=1 and counts[lk]>=1)
    if fk==lk:need(counts[fk]>=2)
    inc=integer(s['increasing_pairs'],0,n-1);dup=integer(s['duplicate_pairs'],0,n-1);dec=integer(s['decreasing_pairs'],0,n-1)
    need(inc+dup+dec==n-1)
    if inc==0:need(lt<=ft)
    if inc==dec==0:equal(ft,lt)
    if dec==dup==0:need(lt>ft)
    mis=integer(s['misaligned_count'],0,n)
    known_misaligned=int(ft%(60*TICKS_SECOND)!=0)+int(lt%(60*TICKS_SECOND)!=0)
    need(mis>=known_misaligned and mis<=n-(2-known_misaligned))
    transitions=integer(s['kind_transitions'],0,n-1)
    distinct=sum(v>0 for v in counts.values());need(transitions>=distinct-1)
    if transitions==0:need(fk==lk and counts[fk]==n)
    if distinct==1:equal(transitions,0)
    if transitions==1:need(distinct==2 and fk!=lk)
    if fk!=lk:need(transitions>=1)
    if fk==lk and distinct>1:need(transitions>=2)
    need(kind_transition_feasible(counts,fk,lk,transitions))
    return s


def validate_loaded_context(raw,plan):
    raw_bytes(raw,MAX_CONTEXT);c=fields(decode(raw),CONTEXT_KEYS)
    for k,v in dict(schema='arms.r53.loaded-context.v1',version='R5.3-F/native-context/1',classification='DIAGNOSTIC_ONLY',
        source_index=0,request_constructor_attempts=1,application_timezone='UTC',sdk_version='8.1.8.2',playback_connected=False,
        operator_confirmations='ENABLED_MARKET_OPEN_DATA_FLOW_CONNECTION_STABLE_TRUE',operator_observations_independently_verified=False,
        bar_timestamp_conversion=False,native_provenance_attested=False,certification_evidence=False,runtime_admission=False,
        validation_scope='LOADED_VALUES_CHECKED_AT_OBSERVATION_POINTS_NOT_PROVIDER_ATTESTATION').items():equal(c[k],v)
    guid(c['sdk_core_mvid'])
    cfg=string(c['request_configuration_json'],MAX_CALENDAR).encode()
    cal=string(c['loaded_calendar_json'],MAX_CALENDAR).encode()
    equal(digest(c['request_configuration_sha256']),sha256(cfg).hexdigest())
    equal(digest(c['loaded_calendar_sha256']),sha256(cal).hexdigest())
    validate_configuration(decode(cfg));calendar=validate_calendar(decode(cal))
    equal(c['loaded_calendar_sha256'],plan['template_sha256']);equal(calendar['zone_id'],plan['source_zone_id'])
    snap=validate_snapshot(c['snapshot'],plan)
    timestamp(c['source_timestamp']);equal(c['source_timestamp'],snap['first'])
    for control in plan['cases'][:3]:
        equal(control['source_index'],c['source_index']);equal(control['raw'],c['source_timestamp'])
    return c


def _verify(context_raw,matrix_raw,matrix_seal_raw,envelope_raw):
    raw_bytes(context_raw,MAX_CONTEXT);raw_bytes(matrix_raw,MAX_TOTAL)
    raw_bytes(matrix_seal_raw,MAX_SEAL);raw_bytes(envelope_raw,MAX_SEAL)
    raw=(context_raw,matrix_raw,matrix_seal_raw)
    need(sum(map(len,raw))+len(envelope_raw)<=MAX_TOTAL)
    env=fields(decode(envelope_raw),SEAL_KEYS)
    for k,v in dict(schema='arms.r53.context-envelope.seal.v1',version=VERSION,classification='DIAGNOSTIC_ONLY',
        diagnostic_complete=True,writer_closed=True,source_index=0,request_constructor_attempts=1,
        context_attestation='CAPTURED_VALUES_BOUND_NOT_PROVIDER_ATTESTATION',**FLAGS).items():equal(env[k],v)
    need(type(env['files']) is list and len(env['files'])==3)
    for entry,path,content in zip(env['files'],FILES,raw):
        fields(entry,('path','bytes','sha256'));equal(entry['path'],path)
        equal(entry['bytes'],len(content));equal(digest(entry['sha256']),sha256(content).hexdigest())
    equal(env['total_bound_bytes'],sum(map(len,raw)))
    verified=verify_evidence(matrix_raw,matrix_seal_raw)
    for k in ('probe_uuid','request_uuid'):equal(guid(env[k]),verified[k])
    equal(env['origin'],verified['origin_claim'])
    equal(env['returned_rows'],verified['returned_rows'])
    equal(env['context_snapshot_sha256'],verified['snapshot_sha256'])
    equal(env['context_template_sha256'],verified['template_sha256'])
    equal(env['iterator_constructor_attempts'],verified['constructor_attempts'])
    equal(env['getnextsession_attempts'],verified['call_attempts'])
    plan=decode(matrix_raw.splitlines()[1])['payload']
    context=validate_loaded_context(context_raw,plan)
    timestamp(env['source_timestamp']);equal(env['source_timestamp'],context['source_timestamp'])
    return dict(status='PASS_CONTEXT_ENVELOPE_CONTRACT_ONLY',origin_claim=verified['origin_claim'],probe_uuid=verified['probe_uuid'],
        request_uuid=verified['request_uuid'],returned_rows=verified['returned_rows'],matrix_records=15,bound_file_count=3,
        total_bytes=sum(map(len,raw))+len(envelope_raw),snapshot_sha256=verified['snapshot_sha256'],template_sha256=verified['template_sha256'],
        context_sha256=sha256(context_raw).hexdigest(),iterator_constructor_attempts=verified['constructor_attempts'],
        getnextsession_attempts=verified['call_attempts'],sdk_core_mvid_claim=context['sdk_core_mvid'],
        context_byte_binding=True,bar_timestamp_conversion=False,
        loaded_calendar_rule_evaluation='REFERENCE_OBSERVATIONS_ALGEBRA_CHECKED_SERIALIZED_ZONE_HASH_ONLY',
        zone_rules_independently_reevaluated=False,omitted_bars_independently_reconstructed=False,
        operator_observations_independently_verified=False,**FLAGS)


def verify_envelope(context_raw:bytes,matrix_raw:bytes,matrix_seal_raw:bytes,envelope_raw:bytes):
    try:return _verify(context_raw,matrix_raw,matrix_seal_raw,envelope_raw)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError,AttributeError,UnicodeError):
        raise ValueError('INVALID_R53_CONTEXT_ENVELOPE') from None


def no_links(path):
    for p in (path,*path.parents):
        st=p.lstat()
        need(not p.is_symlink() and not (getattr(st,'st_file_attributes',0)&0x400))


def read_capture(capture:Path):
    capture=Path(capture).absolute();no_links(capture);need(capture.is_dir())
    need({x.name for x in capture.iterdir()}=={CONTEXT_NAME,'matrix',SEAL_NAME})
    matrix=capture/'matrix';no_links(matrix);need(matrix.is_dir())
    need({x.name for x in matrix.iterdir()}=={Path(MATRIX_NAME).name,Path(MATRIX_SEAL_NAME).name})
    blobs=[];identities=[]
    for relative,limit in zip((*FILES,SEAL_NAME),(MAX_CONTEXT,MAX_TOTAL,MAX_SEAL,MAX_SEAL)):
        p=capture/relative;no_links(p);need(p.is_file() and 0<p.stat().st_size<=limit)
        st=p.stat()
        with p.open('rb') as f:blobs.append(f.read(limit+1))
        identities.append((p,st.st_size,st.st_mtime_ns))
    result=verify_envelope(*blobs)
    # Check again without modifying files; no universal adversarial TOCTOU claim.
    for (p,size,mtime),content in zip(identities,blobs):
        no_links(p);st=p.stat();need(st.st_size==size and st.st_mtime_ns==mtime)
        with p.open('rb') as f:need(f.read(len(content)+1)==content)
    need({x.name for x in capture.iterdir()}=={CONTEXT_NAME,'matrix',SEAL_NAME})
    need({x.name for x in matrix.iterdir()}=={Path(MATRIX_NAME).name,Path(MATRIX_SEAL_NAME).name})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',required=True,type=Path);args=parser.parse_args()
    try:print(json.dumps(read_capture(args.capture),sort_keys=True));return 0
    except (OSError,ValueError):
        print(json.dumps(dict(status='REJECTED',reason='INVALID_OR_UNREADABLE_R53_CONTEXT_ENVELOPE')));return 1

if __name__=='__main__':raise SystemExit(main())
