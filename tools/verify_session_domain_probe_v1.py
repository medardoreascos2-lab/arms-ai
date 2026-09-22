"""Bounded R5 diagnostic verification only. Integrity is not native provenance or root cause.

Coverage checkpoints can detect contradictory summaries; they do not reconstruct
unrecorded timestamps or certify history. No native APIs are loaded or invoked.
"""
import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import UUID

VERSION = 'ArmsSessionDomainProbeV1/1'
MAX_BYTES, MAX_RECORDS = 262144, 96
OFFSETS = (0, 1, 2, 3, 4, 7)
INITIAL = '2026-09-14T00:00:00.0000000Z'
BEGIN = '2026-09-13T22:00:00.0000000Z'
END = '2026-09-14T21:00:00.0000000Z'
GAP = '2026-09-14T21:00:01.0000000Z'
NEXT = '2026-09-14T22:00:01.0000000Z'
CONFIG = dict(instrument='NQ', contract='NQ DEC26', bars_type='Minute', bars_value=1,
    market_data_type='Last', trading_hours='CME US Index Futures ETH', trading_hours_timezone='Central Standard Time',
    requested_from='2026-09-16', requested_through='2026-09-21', request_date_kind='Unspecified',
    lookup_policy='Repository', merge_policy='DoNotMerge', reset=True, split_adjusted=False,
    dividend_adjusted=False, market_reopen=True, nq_flow=True, connection_stable=True)
FIXED = dict(schema='arms.nt.session-domain-probe.record.v1', classification='DIAGNOSTIC_ONLY',
    certification_evidence=False, runtime_admission=False, probe_version=VERSION, maximum_native_calls=8,
    maximum_iterators=7, maximum_requests=1, root_cause='UNRESOLVED')
FIELDS = set(FIXED) | set('sequence stage operation state component_assembly_mvid request_id sdk_version application_timezone '
    'config probe_uuid snapshot_sha256 returned_rows template_version template_sha256 template_payload coverage '
    'case_id iterator_id constructor mode call_index source_index query query_kind include_end_time boolean_result '
    'session_begin session_end session_begin_kind session_end_kind bounds_valid guard phase exception_type '
    'exception_message native_calls iterator_count request_count findings adjudication'.split())
CALL_DEFAULTS = dict(case_id=None, iterator_id=None, constructor=None, mode=None, call_index=-1, source_index=-1,
    query=None, query_kind='NONE', include_end_time=None, boolean_result=None, session_begin=None, session_end=None,
    session_begin_kind='NONE', session_end_kind='NONE', bounds_valid=False, guard='NONE', phase='NONE',
    exception_type='NONE', exception_message='NONE')


def require(ok):
    if not ok:
        raise ValueError('INVALID_SESSION_DOMAIN_DIAGNOSTIC')


def equal(actual, expected):
    require(type(actual) is type(expected) and actual == expected)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names))


def integer(value, low, high):
    require(type(value) is int and low <= value <= high)


def timestamp(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z', value) is not None)
    datetime.fromisoformat(value)
    return value  # Compare original strings: no loss of 100 ns resolution.


def uuid(value):
    require(type(value) is str and str(UUID(value)) == value)


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result)
        result[key] = value
    return result


def decode(raw):
    def bad(_):
        raise ValueError('INVALID_JSON_CONSTANT')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def shifted(value, days):
    return (datetime.fromisoformat(value) + timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S') + '.0000000Z'


SESSIONS = [(shifted(BEGIN, d), shifted(END, d)) for d in OFFSETS]


def template(raw, expected_hash):
    require(type(raw) is str and len(raw.encode()) <= 10000)
    require(sha256(raw.encode()).hexdigest() == expected_hash)
    data = decode(raw)
    fields(data, ('sessions', 'holidays', 'partials'))
    equal(data['sessions'], [f'{d},1700,{d+1},1600,{d+1}' for d in range(5)])
    for key in ('holidays', 'partials'):
        values = data[key]
        require(type(values) is list and len(values) <= 512)
        require(all(type(v) is str for v in values))
        require(values == sorted(set(values)))
        for v in values:
            date = v[:10]
            require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) is not None)
            datetime.strptime(date, '%Y-%m-%d')
            require(date < '2026-09-13' or date > '2026-09-21')
            if key == 'holidays': equal(v, date)
            else:
                parts = v.split('|')
                require(len(parts) == 5 and parts[1] in ('0','1') and parts[2] in ('0','1'))
                for session in ([] if parts[3] == 'NONE' else [parts[3]]) + ([] if not parts[4] else parts[4].split(';')):
                    require(re.fullmatch(r'[0-6],\d{1,4},[0-6],\d{1,4},[0-6]', session) is not None)
                    for time in (session.split(',')[1], session.split(',')[3]):
                        number = int(time)
                        require(number // 100 < 24 and number % 100 < 60)


def coverage(data, count):
    fields(data, 'returned_rows first first_kind last last_kind strictly_ordered first_last_may_be_partial '
        'after_first_session_count session_bins utc_dates maintenance_count outside_count exact_boundary_count '
        'covered_source_index covered_query covered_session membership post_first maintenance_bins boundary_points'.split())
    equal(data['returned_rows'], count)
    for k in ('first_kind', 'last_kind'): equal(data[k], 'Utc')
    for k in ('strictly_ordered','first_last_may_be_partial'): equal(data[k], True)
    equal(data['membership'], 'TEMPLATE_EXPECTATION_MINUTE_CLOSE_BEGIN_EXCLUSIVE_END_INCLUSIVE')
    first, last = timestamp(data['first']), timestamp(data['last'])
    require(first < last)
    points = {}

    def point(i, t):
        integer(i, 0, count-1); timestamp(t)
        require(t[17:19] == '00' and t[20:27] == '0000000')
        require(first <= t <= last)
        if i in points: equal(points[i], t)
        points[i] = t

    point(0, first); point(count-1, last)

    def bucket(b):
        fields(b, 'count first_index last_index candidate_index first last candidate'.split())
        integer(b['count'], 0, count)
        if b['count'] == 0:
            for k in ('first_index','last_index','candidate_index'): equal(b[k], -1)
            for k in ('first','last','candidate'): equal(b[k], None)
            return
        point(b['first_index'], b['first']); point(b['last_index'], b['last'])
        equal(b['last_index'] - b['first_index'] + 1, b['count'])
        if b['candidate_index'] == -1: equal(b['candidate'], None)
        else:
            integer(b['candidate_index'], max(1,b['first_index']), min(count-2,b['last_index']))
            point(b['candidate_index'], b['candidate'])
            equal(b['candidate_index'], max(1,b['first_index']))

    dates = data['utc_dates']
    require(type(dates) is dict and 1 <= len(dates) <= 32)
    cursor = 0
    for date, b in sorted(dates.items()):
        require(type(date) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) is not None)
        bucket(b); require(b['count'] > 0)
        equal(b['first_index'], cursor); cursor = b['last_index'] + 1
        equal(b['first'][:10], date); equal(b['last'][:10], date)
        equal(b['candidate_index'], -1); equal(b['candidate'], None)
    equal(cursor, count)
    bins = data['session_bins']
    require(type(bins) is list and len(bins) == 6)
    candidates = []
    previous_index = -1
    for j, (b, (begin,end)) in enumerate(zip(bins, SESSIONS)):
        bucket(b)
        if b['count']:
            require(begin < b['first'] <= b['last'] <= end)
            require(b['first_index'] > previous_index); previous_index = b['last_index']
            if b['candidate'] is not None:
                require(begin < b['candidate'] < end)
                if j: candidates.append((b['candidate_index'], j, b['candidate']))
            else:
                start, stop = max(1,b['first_index']), min(count-2,b['last_index'])
                require(start > stop or (start == b['last_index'] and b['last'] == end))
    for k in ('maintenance_count','outside_count','exact_boundary_count','after_first_session_count'):
        integer(data[k],0,count)
    equal(sum(b['count'] for b in bins) + data['maintenance_count'] + data['outside_count'],count)
    gaps = data['maintenance_bins']
    require(type(gaps) is list and len(gaps) == 4)
    for j,b in enumerate(gaps):
        bucket(b); equal(b['candidate_index'],-1); equal(b['candidate'],None)
        if b['count']:
            end = SESSIONS[j][1]
            begin_next = SESSIONS[j+1][0]
            require(end < b['first'] <= b['last'] <= begin_next)
    equal(data['maintenance_count'],sum(b['count'] for b in gaps))
    boundaries = data['boundary_points']
    require(type(boundaries) is list and len(boundaries) <= 12)
    boundary_times = {t for pair in SESSIONS for t in pair}
    seen_boundary = {}
    for item in boundaries:
        fields(item,('index','time')); point(item['index'],item['time'])
        require(item['time'] in boundary_times and item['index'] not in seen_boundary)
        seen_boundary[item['index']] = item['time']
    require(list(seen_boundary) == sorted(seen_boundary))
    equal(data['exact_boundary_count'],len(boundaries))
    for i,t in points.items():
        if t in boundary_times: equal(seen_boundary.get(i),t)
    post = data['after_first_session_count']
    post_bucket = data['post_first']; bucket(post_bucket)
    equal(post_bucket['count'],post); equal(post_bucket['candidate_index'],-1); equal(post_bucket['candidate'],None)
    if post:
        equal(post_bucket['first_index'],count-post); equal(post_bucket['last_index'],count-1)
        require(post_bucket['first'] > END)
    for i,t in points.items():
        if t <= END: require(count-post > i)
        else: require(count-post <= i)
    # Bounds across the independent date summaries must agree with the boundary count.
    require(sum(b['count'] for d,b in dates.items() if d > '2026-09-14') <= post)
    require(post <= sum(b['count'] for d,b in dates.items() if d >= '2026-09-14'))
    selected = min(candidates) if candidates else (-1,-1,None)
    equal(data['covered_source_index'],selected[0]); equal(data['covered_session'],selected[1]); equal(data['covered_query'],selected[2])
    ordered = sorted(points.items())
    require(all(a[1] < b[1] for a,b in zip(ordered,ordered[1:])))
    # Every omitted row is also a distinct minute label. Reject impossible density
    # between checkpoints even when all indices and summary counts were resealed.
    for (ia,ta),(ib,tb) in zip(ordered,ordered[1:]):
        minutes = (datetime.fromisoformat(tb)-datetime.fromisoformat(ta)).total_seconds()/60
        require(ib-ia <= minutes)
    for i,t in ordered:
        day = dates[t[:10]]
        require(day['first_index'] <= i <= day['last_index'])
        memberships = []
        for j,(begin,end) in enumerate(SESSIONS):
            b = bins[j]
            inside = begin < t <= end
            indexed = b['count'] > 0 and b['first_index'] <= i <= b['last_index']
            equal(inside,indexed); memberships.append(inside)
        for j,b in enumerate(gaps):
            inside = SESSIONS[j][1] < t <= SESSIONS[j+1][0]
            indexed = b['count'] > 0 and b['first_index'] <= i <= b['last_index']
            equal(inside,indexed)
    return data


def findings(results, cov):
    answer = []
    if not cov['after_first_session_count'] or cov['covered_query'] is None: answer.append('SNAPSHOT_COVERAGE_FAILURE')
    g,n = results['G'],results['N']
    if not g['boolean_result']: answer.append('MAINTENANCE_GAP_QUERY_FALSE')
    if not n['boolean_result']: answer.append('DIRECT_NEXT_SESSION_QUERY_FALSE')
    def signature(r): return (r['boolean_result'],r['session_begin'],r['session_end'])
    if 'R1' in results:
        answer.append('FRESH_ITERATOR_SAME_RESULT' if signature(results['R1']) == signature(g) else 'ITERATOR_REUSE_DIFFERENCE')
    if 'T_NEXT' in results and signature(results['T_NEXT']) != signature(n): answer.append('CONSTRUCTOR_CONTEXT_DIFFERENCE')
    if not answer or not results['R0']['boolean_result'] or cov['covered_query'] is None: answer.append('UNRESOLVED')
    return answer


def _verify(raw, seal_raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES and raw.endswith(b'\n') and b'\r' not in raw)
    require(type(seal_raw) is bytes and 0 < len(seal_raw) <= 4096)
    lines = raw[:-1].split(b'\n')
    require(1 <= len(lines) <= MAX_RECORDS and all(0 < len(s)+1 <= 16384 for s in lines))
    rows, seal = [decode(s) for s in lines], decode(seal_raw)
    fixed_seal = dict(schema='arms.nt.session-domain-probe.seal.v1', classification='DIAGNOSTIC_ONLY',
        probe_version=VERSION, diagnostic_complete=True, writer_closed=True, adjudication='OBSERVATIONS_ONLY',
        root_cause='UNRESOLVED', certification_evidence=False,runtime_admission=False)
    fields(seal, set(fixed_seal)|set('probe_uuid sha256 records bytes native_calls iterator_count request_count findings'.split()))
    for k,v in fixed_seal.items(): equal(seal[k],v)
    uuid(seal['probe_uuid']); equal(seal['sha256'],sha256(raw).hexdigest())
    equal(seal['bytes'],len(raw)); equal(seal['records'],len(rows)); equal(seal['request_count'],1)
    integer(seal['native_calls'],3,8); integer(seal['iterator_count'],3,7)
    snapshot = None
    for i,row in enumerate(rows):
        fields(row,FIELDS)
        for k,v in FIXED.items(): equal(row[k],v)
        fields(row['config'],CONFIG)
        for k,v in CONFIG.items(): equal(row['config'][k],v)
        equal(row['sequence'],i); equal(row['probe_uuid'],seal['probe_uuid'])
        for k in ('component_assembly_mvid','request_id'):
            uuid(row[k]); equal(row[k],rows[0][k])
        require(type(row['operation']) is str and re.fullmatch('[A-Z_]{1,64}',row['operation']) is not None)
        require(row['state'] in ('DataLoaded','Historical','Transition','Realtime'))
        equal(row['sdk_version'],None if i == 0 else '8.1.8.2'); equal(row['application_timezone'],None if i == 0 else 'UTC')
        equal(row['request_count'],0 if i == 0 else 1)
        if row['stage'] == 'SNAPSHOT_VERIFIED':
            require(snapshot is None)
            integer(row['returned_rows'],3,10002); integer(row['template_version'],1,2147483647)
            digest(row['snapshot_sha256']); digest(row['template_sha256'])
            template(row['template_payload'],row['template_sha256'])
            snapshot = {k:row[k] for k in ('snapshot_sha256','returned_rows','template_version','template_sha256')}
        else: equal(row['template_payload'],None)
        for k in ('snapshot_sha256','returned_rows','template_version','template_sha256'):
            equal(row[k],snapshot[k] if snapshot else (-1 if k=='returned_rows' else None))
        if row['stage'] != 'COVERAGE_VERIFIED': equal(row['coverage'],None)
        integer(row['native_calls'],0,8); integer(row['iterator_count'],0,7)
        if row['stage'] != 'EXPERIMENT_COMPLETE':
            equal(row['findings'],[]); equal(row['adjudication'],'UNRESOLVED')
    # Request may callback inline, but Request must return before completion can seal.
    stages = [r['stage'] for r in rows]
    require(stages.count('REQUEST_RETURNED') == 1)
    returned_index = stages.index('REQUEST_RETURNED')
    require(returned_index in (2,len(rows)-2))
    returned = rows[returned_index]
    stream = [r for r in rows if r is not returned]
    require([r['stage'] for r in stream[:4]] == ['ATTEMPT_STARTED','REQUEST_SUBMITTING','SNAPSHOT_VERIFIED','COVERAGE_VERIFIED'])
    equal(stream[-1]['stage'],'EXPERIMENT_COMPLETE')
    cov = coverage(stream[3]['coverage'],stream[3]['returned_rows'])
    for row in stream[:4]:
        for k,v in CALL_DEFAULTS.items(): equal(row[k],v)
        equal(row['native_calls'],0); equal(row['iterator_count'],0)
    results = {}; pos = 4; calls = 0; iterators = 0

    def case(id, query, execute=True, reason='PREDICATE_FALSE', include=True, source=-1):
        nonlocal pos,calls,iterators
        row = stream[pos]; pos += 1
        equal(row['case_id'],id)
        if not execute:
            equal(row['stage'],'CASE_SKIPPED')
            for k,v in CALL_DEFAULTS.items(): equal(row[k],id if k=='case_id' else reason if k=='guard' else v)
            equal(row['native_calls'],calls); equal(row['iterator_count'],iterators)
            return
        iterators += id != 'R1'
        expected = dict(CALL_DEFAULTS,case_id=id,iterator_id='R' if id in ('R0','R1') else id,
            constructor='TradingHours' if id=='T_NEXT' else 'Bars',mode='REUSED' if id=='R1' else 'FRESH',
            call_index=calls,source_index=source,query=query,query_kind='Utc',include_end_time=include,phase='NOT_CALLED')
        equal(row['stage'],'CALL_BEGIN'); equal(row['native_calls'],calls); equal(row['iterator_count'],iterators)
        for k,v in expected.items(): equal(row[k],v)
        result = stream[pos]; pos += 1; calls += 1
        equal(result['stage'],'CALL_RESULT'); equal(result['native_calls'],calls); equal(result['iterator_count'],iterators)
        changing = {'boolean_result','session_begin','session_end','session_begin_kind','session_end_kind','bounds_valid','phase'}
        for k,v in expected.items():
            if k not in changing: equal(result[k],v)
        equal(result['phase'],'RETURNED')
        require(type(result['boolean_result']) is bool)
        if result['boolean_result']:
            timestamp(result['session_begin']); timestamp(result['session_end'])
            equal(result['session_begin_kind'],'Utc'); equal(result['session_end_kind'],'Utc'); equal(result['bounds_valid'],True)
            j = 0 if id in ('R0','E_TRUE') else cov['covered_session'] if id=='C' else 1
            bounds = (result['session_begin'],result['session_end'])
            require(bounds == SESSIONS[j] or id=='E_FALSE' and bounds == SESSIONS[0])
        else:
            for k in ('session_begin','session_end'): equal(result[k],None)
            for k in ('session_begin_kind','session_end_kind'): equal(result[k],'NONE')
            equal(result['bounds_valid'],False)
        results[id] = result

    case('R0',INITIAL)
    case('R1',GAP,results['R0']['bounds_valid'],'ANCHOR_INVALID')
    case('G',GAP); case('N',NEXT)
    case('C',cov['covered_query'],cov['covered_query'] is not None,'NO_COVERED_INTERIOR_TIMESTAMP',source=cov['covered_source_index'])
    endpoint = results['G']['boolean_result'] is False and results['N']['bounds_valid']
    case('E_TRUE',END,endpoint); case('E_FALSE',END,endpoint,include=False)
    constructor = cov['session_bins'][1]['count'] == 0 or (results['N']['boolean_result'] is False and 'C' in results and results['C']['bounds_valid'])
    case('T_NEXT',NEXT,constructor)
    equal(pos,len(stream)-1)
    end = stream[-1]
    for k,v in CALL_DEFAULTS.items(): equal(end[k],v); equal(returned[k],v)
    for row in (end,seal):
        equal(row['native_calls'],calls); equal(row['iterator_count'],iterators)
        equal(row['findings'],findings(results,cov)); equal(row['adjudication'],'OBSERVATIONS_ONLY')
    equal(returned['native_calls'],0 if returned_index==2 else calls)
    equal(returned['iterator_count'],0 if returned_index==2 else iterators)
    return dict(diagnostic_integrity='VERIFIED', adjudication='OBSERVATIONS_ONLY', findings=end['findings'],
        root_cause='UNRESOLVED', runtime_admission=False, certification_evidence=False,
        native_provenance='NOT_ATTESTED_BY_VERIFIER',probe_uuid=seal['probe_uuid'],records=len(rows),native_calls=calls,
        iterator_count=iterators,coverage=cov,results=results)


def verify_evidence(raw, seal_raw):
    try:
        return _verify(raw,seal_raw)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RecursionError,AttributeError) as error:
        raise ValueError('INVALID_SESSION_DOMAIN_DIAGNOSTIC') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic',required=True,type=Path); parser.add_argument('--seal',required=True,type=Path)
    args = parser.parse_args()
    try:
        with args.diagnostic.open('rb') as f: raw=f.read(MAX_BYTES+1)
        with args.seal.open('rb') as f: seal=f.read(4097)
        print(json.dumps(verify_evidence(raw,seal)))
    except (OSError,ValueError):
        print(json.dumps(dict(diagnostic_integrity='REJECTED',adjudication='UNRESOLVED',root_cause='UNRESOLVED',runtime_admission=False)))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
