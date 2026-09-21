"""Offline diagnostic integrity/adjudication only; never grants history or execution authority.

The seal detects corruption, not forgery or native provenance. Synthetic harness
output is intentionally the same shape and must never be called native evidence.
"""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import UUID

VERSION = 'ArmsSessionIteratorProbeV1/1'
MAX_BYTES, MAX_RECORDS, MAX_CALLS = 131072, 64, 4
FIRST = ('2026-09-13T22:00:00.0000000Z', '2026-09-14T21:00:00.0000000Z')
SECOND = ('2026-09-14T22:00:00.0000000Z', '2026-09-15T21:00:00.0000000Z')
INITIAL = '2026-09-14T00:00:00.0000000Z'
QUERIES = {'A_TICK': '2026-09-14T21:00:00.0000001Z', 'B_SECOND': '2026-09-14T21:00:01.0000000Z'}
ERRORS = {'NONE', 'UnauthorizedAccessException', 'IOException', 'ArgumentException',
          'InvalidOperationException', 'NullReferenceException', 'OTHER'}
FIXED = dict(schema='arms.nt.session-iterator-probe.record.v1', classification='DIAGNOSTIC_ONLY',
             certification_evidence=False, runtime_admission=False, probe_version=VERSION,
             instrument='NQ', contract='NQ DEC26', bars_type='Minute', bars_value=1, market_data_type='Last',
             trading_hours='CME US Index Futures ETH', trading_hours_timezone='Central Standard Time',
             application_timezone_required='UTC', requested_from='2026-09-16', requested_through='2026-09-21',
             lookup_policy='Repository', merge_policy='DoNotMerge', market_reopen_confirmed=True,
             nq_data_flow_confirmed=True, connection_stable_confirmed=True, include_end_time=True,
             maximum_native_calls=MAX_CALLS)
FIELDS = set(FIXED) | set('probe_uuid sequence stage operation state sdk_version component_assembly_mvid '
    'trading_hours_version application_timezone source_identity_verified snapshot_id snapshot_sha256 returned_rows '
    'experiment_sequence iterator_local_identity call_index query query_kind boolean_result session_begin session_end '
    'session_begin_kind session_end_kind bounds_valid guard_failure call_phase exception_type exception_message '
    'native_calls native_confirmation'.split())
OUTCOMES = {'PASS', 'FAIL', 'R2_FALSE_RETURN_NOT_REPRODUCED', 'UNRESOLVED'}


def require(condition):
    if not condition:
        raise ValueError('INVALID_PROBE_DIAGNOSTIC')


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def _json(raw):
    def invalid_constant(_):
        raise ValueError('INVALID_PROBE_DIAGNOSTIC')
    return json.loads(raw, object_pairs_hook=_object, parse_constant=invalid_constant)


def _uuid(value):
    require(type(value) is str and str(UUID(value)) == value)


def _hash(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)


def _time(value, kind):
    if value is None:
        require(kind == 'NONE')
        return
    require(type(value) is str and len(value) <= 40)
    suffix = {'Utc': 'Z', 'Unspecified': '', 'Local': r'[+-]\d{2}:\d{2}'}.get(kind)
    require(suffix is not None)
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}' + suffix, value) is not None)
    datetime.fromisoformat(value)  # Validate calendar fields, never round the original query for comparison.


def _result(row):
    result, error = row['boolean_result'], row['exception_type']
    require(result is None or type(result) is bool)
    require(type(row['bounds_valid']) is bool)
    require(error in ERRORS)
    require(row['exception_message'] == ('NONE' if error == 'NONE' else 'REDACTED_NATIVE_OR_GUARD_MESSAGE'))
    for name in ('begin', 'end'):
        _time(row['session_' + name], row['session_' + name + '_kind'])
    begin, end = row['session_begin'], row['session_end']
    if error != 'NONE':
        require(row['bounds_valid'] is False and row['guard_failure'] == 'NONE')
        if row['call_phase'] == 'GET_NEXT_SESSION':
            require(result is None and begin is None and end is None)
        elif row['call_phase'] == 'BEGIN_READ':
            require(result is True and begin is None and end is None)
        else:
            require(row['call_phase'] == 'END_READ' and result is True and begin is not None and end is None)
        return
    require(result is not None and row['call_phase'] == 'RETURNED')
    if result is False:
        require(begin is None and end is None and not row['bounds_valid'] and row['guard_failure'] == 'NONE')
        return
    require(begin is not None and end is not None)
    expected = FIRST if row['call_index'] == 0 else SECOND
    if row['session_begin_kind'] != 'Utc' or row['session_end_kind'] != 'Utc':
        guard = 'UTC_KIND_REQUIRED'
    elif begin >= end:
        guard = 'REVERSED_OR_EMPTY_BOUNDS'
    elif (begin, end) != expected:
        guard = 'R2_ANCHOR_MISMATCH' if row['call_index'] == 0 else 'NEXT_SESSION_MISMATCH'
    else:
        guard = 'NONE'
    require(row['guard_failure'] == guard and row['bounds_valid'] == (guard == 'NONE'))


def _verify_evidence(raw, seal_raw):
    """Return an independently checked diagnostic outcome or raise ValueError.

    A valid sealed UNRESOLVED run is diagnostic completion, not a successful
    native experiment. Missing/corrupt/unsealed evidence is rejected outright.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES and raw.endswith(b'\n'))
    require(type(seal_raw) is bytes and 0 < len(seal_raw) <= 4096)
    lines = raw.splitlines()
    require(0 < len(lines) <= MAX_RECORDS and all(0 < len(line) + 1 <= 8192 for line in lines))
    rows = [_json(line) for line in lines]
    seal = _json(seal_raw)
    seal_fixed = dict(schema='arms.nt.session-iterator-probe.seal.v1', classification='DIAGNOSTIC_ONLY',
                      probe_version=VERSION, diagnostic_complete=True, writer_closed=True,
                      certification_evidence=False, runtime_admission=False)
    require(type(seal) is dict and set(seal) == set(seal_fixed) | {'probe_uuid', 'sha256', 'records', 'bytes', 'native_calls', 'native_confirmation'})
    for k, v in seal_fixed.items(): require(type(seal[k]) is type(v) and seal[k] == v)
    require(type(seal['records']) is int and seal['records'] == len(rows))
    require(type(seal['bytes']) is int and seal['bytes'] == len(raw))
    require(type(seal['native_calls']) is int and 2 <= seal['native_calls'] <= MAX_CALLS)
    require(seal['sha256'] == sha256(raw).hexdigest() and seal['native_confirmation'] in OUTCOMES)
    _uuid(seal['probe_uuid'])
    stages, call_rows = [], []
    snapshot = None
    snapshot_started = False
    seen_calls = 0
    pending = None
    controls = {'ATTEMPT_STARTED', 'REQUEST_SUBMITTING', 'REQUEST_RETURNED', 'SNAPSHOT_VERIFIED', 'EXPERIMENT_COMPLETE'}
    for n, row in enumerate(rows):
        require(type(row) is dict and set(row) == FIELDS)
        for k, v in FIXED.items(): require(type(row[k]) is type(v) and row[k] == v)
        require(type(row['sequence']) is int and row['sequence'] == n)
        require(row['probe_uuid'] == seal['probe_uuid'])
        _uuid(row['component_assembly_mvid']); _uuid(row['snapshot_id'])
        require(row['component_assembly_mvid'] == rows[0]['component_assembly_mvid'] and row['snapshot_id'] == rows[0]['snapshot_id'])
        require(type(row['operation']) is str and re.fullmatch('[A-Z_]{1,64}', row['operation']) is not None)
        require(row['state'] in {'DataLoaded', 'Historical', 'Transition', 'Realtime'})
        require(row['native_confirmation'] in OUTCOMES)
        if row['stage'] not in {'REQUEST_RETURNED', 'EXPERIMENT_COMPLETE'}:
            require(row['native_confirmation'] == 'UNRESOLVED')
        require(row['sdk_version'] == '8.1.8.2' and row['application_timezone'] == 'UTC' or
                n == 0 and row['sdk_version'] is None and row['application_timezone'] is None)
        require(type(row['source_identity_verified']) is bool and row['source_identity_verified'] == (row['snapshot_sha256'] is not None))
        if row['stage'] == 'SNAPSHOT_VERIFIED': snapshot_started = True
        require(row['source_identity_verified'] == snapshot_started)
        require(type(row['returned_rows']) is int and type(row['call_index']) is int)
        if row['source_identity_verified']:
            _hash(row['snapshot_sha256'])
            require(type(row['returned_rows']) is int and 3 <= row['returned_rows'] <= 10002)
            require(type(row['trading_hours_version']) is int)
            current = (row['snapshot_sha256'], row['returned_rows'], row['trading_hours_version'])
            if snapshot is None: snapshot = current
            require(snapshot == current)
        else:
            require(snapshot is None and row['returned_rows'] == -1 and row['trading_hours_version'] is None)
        require(type(row['native_calls']) is int and 0 <= row['native_calls'] <= MAX_CALLS)
        stage = row['stage']; stages.append(stage)
        if stage in controls:
            require(pending is None and row['native_calls'] == seen_calls)
            require(row['experiment_sequence'] is None and row['iterator_local_identity'] is None and row['call_index'] == -1)
            require(row['query'] is None and row['query_kind'] == 'NONE' and row['boolean_result'] is None)
            require(row['session_begin'] is None and row['session_end'] is None and row['session_begin_kind'] == row['session_end_kind'] == 'NONE')
            require(row['bounds_valid'] is False and row['guard_failure'] == row['exception_type'] == row['exception_message'] == row['call_phase'] == 'NONE')
            continue
        require(stage in {'CALL_BEGIN', 'CALL_RESULT'} and snapshot is not None)
        sequence, index = row['experiment_sequence'], row['call_index']
        require(sequence in QUERIES and type(index) is int and index in (0, 1))
        require(row['iterator_local_identity'] == ('A' if sequence == 'A_TICK' else 'B'))
        require(row['query'] == (INITIAL if index == 0 else QUERIES[sequence]) and row['query_kind'] == 'Utc')
        if stage == 'CALL_BEGIN':
            require(pending is None and row['native_calls'] == seen_calls)
            require(row['boolean_result'] is None and row['session_begin'] is None and row['session_end'] is None)
            require(row['session_begin_kind'] == row['session_end_kind'] == 'NONE' and row['bounds_valid'] is False)
            require(row['guard_failure'] == row['exception_type'] == row['exception_message'] == 'NONE' and row['call_phase'] == 'NOT_CALLED')
            pending = row
        else:
            require(pending is not None)
            for k in ('experiment_sequence', 'iterator_local_identity', 'call_index', 'query', 'query_kind'):
                require(row[k] == pending[k])
            seen_calls += 1
            require(row['native_calls'] == seen_calls)
            _result(row); call_rows.append(row); pending = None
    require(pending is None and seen_calls == seal['native_calls'])
    require(stages[0] == 'ATTEMPT_STARTED' and stages[-1] == 'EXPERIMENT_COMPLETE')
    require(all(stages.count(s) == 1 for s in controls))
    require(stages.index('REQUEST_SUBMITTING') < stages.index('SNAPSHOT_VERIFIED') < stages.index('CALL_BEGIN'))
    require(stages.index('REQUEST_SUBMITTING') < stages.index('REQUEST_RETURNED') < len(stages) - 1)
    # Request returns either before an asynchronous callback or after the entire
    # inline callback. It cannot interleave with the locked comparison.
    comparison = ['SNAPSHOT_VERIFIED'] + ['CALL_BEGIN', 'CALL_RESULT'] * seen_calls
    prefix = ['ATTEMPT_STARTED', 'REQUEST_SUBMITTING']
    require(stages in (prefix + ['REQUEST_RETURNED'] + comparison + ['EXPERIMENT_COMPLETE'],
                      prefix + comparison + ['REQUEST_RETURNED', 'EXPERIMENT_COMPLETE']))
    by_sequence = {}
    cursor = 0
    for sequence in ('A_TICK', 'B_SECOND'):
        require(cursor < len(call_rows))
        first = call_rows[cursor]; cursor += 1
        require(first['experiment_sequence'] == sequence and first['call_index'] == 0)
        second = None
        if first['bounds_valid']:
            require(cursor < len(call_rows))
            second = call_rows[cursor]; cursor += 1
            require(second['experiment_sequence'] == sequence and second['call_index'] == 1)
        by_sequence[sequence] = (first, second)
    require(cursor == len(call_rows))
    a0, a1 = by_sequence['A_TICK']; b0, b1 = by_sequence['B_SECOND']
    outcome = 'UNRESOLVED'
    if a0['bounds_valid'] and b0['bounds_valid'] and all(r['exception_type'] == 'NONE' and
            (r['boolean_result'] is False or r['bounds_valid']) for r in (a1, b1)):
        outcome = {(False, True): 'PASS', (False, False): 'FAIL',
                   (True, True): 'R2_FALSE_RETURN_NOT_REPRODUCED'}.get((a1['boolean_result'], b1['boolean_result']), 'UNRESOLVED')
    require(rows[-1]['native_confirmation'] == seal['native_confirmation'] == outcome)
    returned = rows[stages.index('REQUEST_RETURNED')]
    require(returned['native_confirmation'] ==
            ('UNRESOLVED' if stages.index('REQUEST_RETURNED') == 2 else outcome))
    return dict(probe_uuid=seal['probe_uuid'], native_confirmation=outcome, native_calls=seen_calls,
                diagnostic_integrity='VERIFIED', classification='DIAGNOSTIC_ONLY',
                certification_evidence=False, runtime_admission=False, native_provenance='NOT_ATTESTED_BY_VERIFIER')


def verify_evidence(raw, seal_raw):
    """Reject malformed input consistently; never turn parsing errors into an outcome."""
    try:
        return _verify_evidence(raw, seal_raw)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        raise ValueError('INVALID_PROBE_DIAGNOSTIC') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--seal', type=Path, required=True)
    args = parser.parse_args()
    # Bound reads before parsing; no processes, timers or native APIs are invoked.
    try:
        with args.diagnostic.open('rb') as stream: raw = stream.read(MAX_BYTES + 1)
        with args.seal.open('rb') as stream: seal = stream.read(4097)
        print(json.dumps(verify_evidence(raw, seal)))
    except (ValueError, OSError):
        print('{"diagnostic_integrity":"REJECTED","native_confirmation":"UNRESOLVED","runtime_admission":false}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
