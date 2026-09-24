"""R5.3-D byte-integrity and matrix-contract verifier. No NinjaTrader API.
Does NOT attest native provenance, omitted bars, loaded calendar, or timezone
meaning. THUTC offsets are checked algebraically, not against an unseen zone.
"""
from __future__ import annotations
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import uuid

VERSION = 'R5.3-D/evidence/1'
MAX_BYTES, MAX_RECORD, MAX_SEAL = 262144, 32768, 4096
MAX_TICKS = 3155378975999999999
TICKS_SECOND, TICKS_DAY = 10000000, 864000000000
FLAGS = dict(native_provenance_attested=False, certification_evidence=False,
             runtime_admission=False, execution_authority=False)
COMMON = set(FLAGS) | set('schema version classification origin probe_uuid request_uuid sequence stage payload'.split())
SEAL_FIELDS = set(FLAGS) | set('schema version classification origin probe_uuid request_uuid sha256 bytes records diagnostic_complete writer_closed lifecycle'.split())
PLAN_FIELDS = set('returned_rows raw_first raw_last snapshot_sha256 template_sha256 source_zone_id template_calendar_attested maximum_calls maximum_iterators cases'.split())
CONTROL_FIELDS = set('ordinal case_id family iterator_id reuse prerequisite source_index provenance reference_utc constructor_context include_end_time raw_range range_interpretation raw query variant method source_zone_id source_offset_ticks conversion_performed kind_changed tick_delta'.split())
RESULT_FIELDS = set('case_id outcome guard exception_type returned begin end bounds_readable bounds_valid constructor_attempts call_attempts'.split())
IDS = ('A_U','A_LUTC','A_THUTC','B_U','B_LUTC','B_THUTC','C_U','C_LUTC','C_THUTC','R0','R1','N')
ERRORS = {'InvalidOperationException','ArgumentException','NullReferenceException','OverflowException','OTHER'}


def need(ok):
    if not ok:
        raise ValueError('INVALID_R53_EVIDENCE')


def fields(value, keys):
    need(type(value) is dict and set(value) == set(keys))
    return value


def equal(value, expected):
    need(type(value) is type(expected) and value == expected)


def integer(value, low=0, high=MAX_TICKS):
    need(type(value) is int and low <= value <= high)
    return value


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)
    return value


def guid(value):
    need(type(value) is str and str(uuid.UUID(value)) == value)
    return value


def decode(raw):
    def unique(items):
        result = {}
        for k, v in items:
            need(k not in result)
            result[k] = v
        return result
    def reject(value):
        raise ValueError('INVALID_R53_JSON_CONSTANT')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=reject)


def timestamp(value):
    fields(value, ('clock','ticks','kind'))
    t = integer(value['ticks'])
    need(type(value['kind']) is str and value['kind'] in ('Unspecified','Utc','Local'))
    s = value['clock']
    need(type(s) is str and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{7}', s) is not None)
    d = date(int(s[:4]),int(s[5:7]),int(s[8:10]))
    h,m,sec = int(s[11:13]), int(s[14:16]), int(s[17:19])
    need(0<=h<24 and 0<=m<60 and 0<=sec<60)
    expected = (d.toordinal()-1)*TICKS_DAY+(h*3600+m*60+sec)*TICKS_SECOND+int(s[20:])
    equal(t, expected)
    return t, value['kind']


def ref_ticks(day, hour=0, minute=0):
    return (date(2026,9,day).toordinal()-1)*TICKS_DAY+(hour*3600+minute*60)*TICKS_SECOND


def validate_plan(p):
    fields(p, PLAN_FIELDS)
    rows = integer(p['returned_rows'],3,10002)
    first,fkind=timestamp(p['raw_first']);last,_=timestamp(p['raw_last'])
    equal(fkind,'Unspecified');need(first<=last)
    digest(p['snapshot_sha256']);digest(p['template_sha256'])
    zone=p['source_zone_id'];need(type(zone) is str and 0<len(zone)<=256 and not any(ord(x)<32 for x in zone))
    equal(p['template_calendar_attested'],False)
    equal(p['maximum_calls'],12);equal(p['maximum_iterators'],11)
    need(type(p['cases']) is list and len(p['cases'])==12)
    for i,c in enumerate(p['cases']):
        fields(c,CONTROL_FIELDS)
        equal(c['ordinal'],i+1);equal(c['case_id'],IDS[i])
        equal(c['family'],'ABC'[i//3] if i<9 else 'R' if i<11 else 'N')
        equal(c['iterator_id'],'I%02d'%(i+1 if i<10 else 10 if i==10 else 11))
        equal(c['reuse'],i==10)
        equal(c['prerequisite'],'R0_TRUE_READABLE_VALID_BOUNDS' if i==10 else 'NONE')
        equal(c['source_index'],0 if i<3 else None)
        equal(c['constructor_context'],'Bars');equal(c['include_end_time'],True)
        equal(c['range_interpretation'],'RAW_TICKS_ONLY_NOT_SESSION_MEMBERSHIP')
        raw,rkind=timestamp(c['raw']);query,qkind=timestamp(c['query'])
        expected_raw = first if i<3 else ref_ticks(14,21) if i<6 else ref_ticks(14,21)+1 if (i<9 or i==10) else ref_ticks(14) if i==9 else ref_ticks(14,22,1)
        equal(raw,expected_raw);equal(rkind,'Utc' if i in (9,11) else 'Unspecified')
        if i<3:
            equal(c['reference_utc'],None)
            equal(c['provenance'],'CALLER_SUPPLIED_BARS_INDEX_0')
        else:
            rt,rk=timestamp(c['reference_utc']);equal(rt,expected_raw);equal(rk,'Utc')
            expected_provenance = 'CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE' if i<6 else 'CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE_PLUS_ONE_TICK' if (i<9 or i==10) else 'R2_R4_REFERENCE_UTC' if i==9 else 'TEMPLATE_EXPECTATION_NOT_OBSERVED_BOUND'
            equal(c['provenance'],expected_provenance)
        equal(c['raw_range'],first<=raw<=last)
        variant=('U','LUTC','THUTC')[i%3] if i<9 else 'LUTC' if i==10 else 'REFERENCE_UTC'
        equal(c['variant'],variant)
        method={'U':'IDENTITY_RAW_CLOCK','LUTC':'SPECIFY_KIND_UTC_SAME_TICKS','THUTC':'EXPLICIT_SOURCE_ZONE_TO_UTC','REFERENCE_UTC':'PRESERVED_REFERENCE_UTC'}[variant]
        equal(c['method'],method)
        equal(qkind,'Unspecified' if variant=='U' else 'Utc')
        delta=integer(c['tick_delta'],-MAX_TICKS,MAX_TICKS);equal(delta,query-raw)
        equal(c['kind_changed'],rkind!=qkind);equal(c['conversion_performed'],variant=='THUTC')
        if variant=='THUTC':
            equal(c['source_zone_id'],zone)
            offset=integer(c['source_offset_ticks'],-14*3600*TICKS_SECOND,14*3600*TICKS_SECOND)
            need(offset%(60*TICKS_SECOND)==0);equal(query,raw-offset)
        else:
            equal(c['source_zone_id'],None);equal(c['source_offset_ticks'],None);equal(query,raw)
    equal(p['cases'][7]['query'],p['cases'][10]['query'])
    return rows


def validate_results(results, summary):
    fields(summary,'matrix_completed stop_guard constructor_attempts call_attempts begin_read_attempts end_read_attempts'.split())
    equal(summary['matrix_completed'],True);equal(summary['stop_guard'],'NONE')
    creates=calls=begins=ends=0;r0_ok=False
    for i,o in enumerate(results):
        fields(o,RESULT_FIELDS);equal(o['case_id'],IDS[i])
        returned=o['returned'];need(returned is None or type(returned) is bool)
        for k in ('bounds_readable','bounds_valid'):
            need(type(o[k]) is bool)
        outcome=o['outcome'];need(type(outcome) is str)
        if i==10 and not r0_ok:
            equal(outcome,'SKIPPED');equal(o['guard'],'R0_TRUE_READABLE_VALID_BOUNDS_NOT_MET')
            equal(o['exception_type'],'NONE');equal(returned,None)
            equal(o['begin'],None);equal(o['end'],None);equal(o['bounds_readable'],False);equal(o['bounds_valid'],False)
        else:
            need(outcome!='SKIPPED')
            if i!=10:creates+=1
            if outcome=='CONSTRUCTOR_EXCEPTION':
                need(i!=10)
                equal(returned,None);equal(o['begin'],None);equal(o['end'],None)
                equal(o['bounds_readable'],False);equal(o['bounds_valid'],False)
                equal(o['guard'],'NONE');need(o['exception_type'] in ERRORS)
            else:
                calls+=1
                if outcome in ('ADVANCE_EXCEPTION','RETURNED_FALSE'):
                    equal(returned,None if outcome=='ADVANCE_EXCEPTION' else False)
                    equal(o['begin'],None);equal(o['end'],None);equal(o['bounds_readable'],False);equal(o['bounds_valid'],False)
                    equal(o['guard'],'NONE')
                    if outcome=='ADVANCE_EXCEPTION':need(o['exception_type'] in ERRORS)
                    else:equal(o['exception_type'],'NONE')
                else:
                    equal(returned,True);begins+=1
                    if outcome=='BEGIN_READ_EXCEPTION':
                        equal(o['begin'],None);equal(o['end'],None);equal(o['bounds_readable'],False);equal(o['bounds_valid'],False)
                        equal(o['guard'],'NONE');need(o['exception_type'] in ERRORS)
                    else:
                        bt,bk=timestamp(o['begin']);ends+=1
                        if outcome=='END_READ_EXCEPTION':
                            equal(o['end'],None);equal(o['bounds_readable'],False);equal(o['bounds_valid'],False)
                            equal(o['guard'],'NONE');need(o['exception_type'] in ERRORS)
                        else:
                            et,ek=timestamp(o['end']);equal(o['bounds_readable'],True)
                            valid=bk==ek and bt<et;equal(o['bounds_valid'],valid)
                            equal(outcome,'RETURNED_TRUE' if valid else 'BOUNDS_INVALID')
                            equal(o['guard'],'NONE' if valid else 'BOUNDS_KIND_MISMATCH' if bk!=ek else 'BOUNDS_NON_POSITIVE')
                            equal(o['exception_type'],'NONE')
            if i==9:r0_ok=returned is True and o['bounds_readable'] and o['bounds_valid']
        equal(o['constructor_attempts'],creates);equal(o['call_attempts'],calls)
    need(creates<=11 and calls<=12 and begins<=12 and ends<=12)
    for k,v in [('constructor_attempts',creates),('call_attempts',calls),('begin_read_attempts',begins),('end_read_attempts',ends)]:equal(summary[k],v)
    return creates,calls,begins,ends


def _verify(raw, seal_raw):
    need(type(raw) is bytes and 0<len(raw)<=MAX_BYTES and raw.endswith(b'\n') and b'\r' not in raw)
    need(type(seal_raw) is bytes and 0<len(seal_raw)<=MAX_SEAL)
    lines=raw[:-1].split(b'\n');need(len(lines)==15 and all(0<len(x)+1<=MAX_RECORD for x in lines))
    rows=[decode(x) for x in lines];seal=fields(decode(seal_raw),SEAL_FIELDS)
    equal(seal['schema'],'arms.r53.evidence.seal.v1');equal(seal['version'],VERSION);equal(seal['classification'],'DIAGNOSTIC_ONLY')
    equal(seal['sha256'],sha256(raw).hexdigest());equal(seal['bytes'],len(raw));equal(seal['records'],len(rows))
    equal(seal['diagnostic_complete'],True);equal(seal['writer_closed'],True)
    for k,v in FLAGS.items():equal(seal[k],v)
    probe,request=guid(seal['probe_uuid']),guid(seal['request_uuid']);need(probe!=request)
    origin=seal['origin'];need(type(origin) is str and origin in ('SYNTHETIC','OPERATOR_NATIVE_RUN_UNATTESTED'))
    stages=['EVIDENCE_STARTED','PLAN_PREPARED']+['CASE_RESULT']*12+['EVIDENCE_PREPARED']
    for i,row in enumerate(rows):
        fields(row,COMMON);equal(row['schema'],'arms.r53.evidence.record.v1');equal(row['version'],VERSION)
        equal(row['classification'],'DIAGNOSTIC_ONLY');equal(row['origin'],origin)
        equal(row['probe_uuid'],probe);equal(row['request_uuid'],request)
        equal(row['sequence'],i);equal(row['stage'],stages[i])
        for k,v in FLAGS.items():equal(row[k],v)
    p0=fields(rows[0]['payload'],('format','source_metadata_attestation'))
    equal(p0['format'],'RAW_CLOCK_TEXT_PLUS_TICKS_AND_KIND')
    equal(p0['source_metadata_attestation'],'CALLER_SUPPLIED_NOT_INDEPENDENTLY_ATTESTED')
    plan=rows[1]['payload'];n=validate_plan(plan)
    creates,calls,begins,ends=validate_results([x['payload'] for x in rows[2:14]],rows[14]['payload'])
    lc=fields(seal['lifecycle'],'status stop_guard exception_type writer_factory_attempts request_factory_attempts submit_attempts process_attempts preparation_attempts request_dispose_attempts writer_dispose_attempts duplicate_callbacks submit_returned request_closed writer_closed resources_released ready_for_seal'.split())
    equal(lc['status'],'READY_FOR_SEAL_NOT_SEALED');equal(lc['stop_guard'],'NONE');equal(lc['exception_type'],'NONE')
    for k in ('writer_factory_attempts','request_factory_attempts','submit_attempts','process_attempts','preparation_attempts','request_dispose_attempts','writer_dispose_attempts'):equal(lc[k],1)
    equal(lc['duplicate_callbacks'],0)
    for k in ('submit_returned','request_closed','writer_closed','resources_released','ready_for_seal'):equal(lc[k],True)
    return dict(status='PASS_DIAGNOSTIC_CONTRACT_ONLY',origin_claim=origin,probe_uuid=probe,request_uuid=request,
                records=15,returned_rows=n,constructor_attempts=creates,call_attempts=calls,begin_read_attempts=begins,end_read_attempts=ends,
                snapshot_sha256=plan['snapshot_sha256'],template_sha256=plan['template_sha256'],
                native_provenance_attested=False,template_calendar_attested=False,
                timezone_offset_semantics='ALGEBRA_CHECKED_ZONE_RULES_NOT_ATTESTED',
                certification_evidence=False,runtime_admission=False,execution_authority=False)


def verify_evidence(raw: bytes, seal_raw: bytes):
    try:
        return _verify(raw,seal_raw)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError,AttributeError) as exc:
        raise ValueError('INVALID_R53_EVIDENCE') from None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic',type=Path,required=True);parser.add_argument('--seal',type=Path,required=True)
    args=parser.parse_args()
    try:
        with args.diagnostic.open('rb') as f:raw=f.read(MAX_BYTES+1)
        with args.seal.open('rb') as f:seal=f.read(MAX_SEAL+1)
        print(json.dumps(verify_evidence(raw,seal),sort_keys=True));return 0
    except (OSError,ValueError):
        print(json.dumps(dict(status='REJECTED',reason='INVALID_OR_UNREADABLE_R53_EVIDENCE')));return 1

if __name__=='__main__':
    raise SystemExit(main())
