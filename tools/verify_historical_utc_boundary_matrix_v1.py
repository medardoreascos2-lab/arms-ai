"""Independent R5.6 evidence integrity verifier. Never attests native provenance."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from uuid import UUID

MAX_BYTES = 262144
EVIDENCE_NAME = 'historical-utc-boundary-matrix.json'
SEAL_NAME = 'historical-utc-boundary-matrix.done.json'
FLAGS = dict(classification='DIAGNOSTIC_ONLY', origin='OPERATOR_NATIVE_RUN_UNATTESTED',
             **{k: False for k in (
                 'native_provenance_attested', 'certification_evidence', 'runtime_admission',
                 'execution_authority', 'exporter_invoked', 'exporter_change',
                 'stored_timestamp_mutation', 'bars_mutation', 'trading_hours_mutation',
                 'paper_execution', 'live_execution')})
ERRORS = {'NONE', 'InvalidOperationException', 'ArgumentException', 'IOException',
          'UnauthorizedAccessException', 'OTHER'}
DAY = 864000000000
MAX_TICKS = 3155378975999999999


def need(ok, reason):
    if not ok:
        raise ValueError('R56_' + reason)


def keys(value, names):
    need(type(value) is dict and set(value) == set(names.split()), 'SCHEMA')


def integer(value, low, high):
    need(type(value) is int and low <= value <= high, 'INTEGER')
    return value


def boolean(value):
    need(type(value) is bool, 'BOOLEAN')
    return value


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'DIGEST')


def unique(pairs):
    result = {}
    for k, v in pairs:
        need(k not in result, 'DUPLICATE_KEY')
        result[k] = v
    return result


def decode(raw, limit):
    need(type(raw) is bytes and 0 < len(raw) <= limit, 'SIZE')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: need(False, 'NONFINITE'))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('R56_JSON') from exc


def tick_of(dt):
    delta = dt - datetime(1, 1, 1)
    return delta.days * DAY + delta.seconds * 10000000 + delta.microseconds * 10


def time_fact(value, kind=None):
    keys(value, 'clock ticks kind')
    need(type(value['clock']) is str and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}', value['clock']) is not None, 'CLOCK')
    ticks = integer(value['ticks'], 0, MAX_TICKS)
    try:
        expected = tick_of(datetime.strptime(value['clock'][:-1], '%Y-%m-%dT%H:%M:%S.%f')) + int(value['clock'][-1])
    except ValueError as exc:
        raise ValueError('R56_CLOCK') from exc
    need(ticks == expected, 'CLOCK_TICKS')
    need(value['kind'] in ('Utc', 'Unspecified', 'Local'), 'KIND')
    need(kind is None or value['kind'] == kind, 'KIND')
    return ticks


def envelope(value, schema, extra):
    need(type(value) is dict and set(value) == set(FLAGS) | {'schema', 'run_id'} | set(extra.split()), 'ENVELOPE')
    need(value['schema'] == schema, 'SCHEMA')
    for k, expected in FLAGS.items():
        need(type(value[k]) is type(expected) and value[k] == expected, 'AUTHORITY_FLAGS')
    try:
        need(type(value['run_id']) is str and str(UUID(value['run_id'])) == value['run_id'], 'RUN_ID')
    except (ValueError, AttributeError) as exc:
        raise ValueError('R56_RUN_ID') from exc


def calendar(value):
    keys(value, 'name version timezone timezone_rules_sha256 calendar_rules_sha256')
    need(value['name'] == 'CME US Index Futures ETH' and value['timezone'] == 'Central Standard Time', 'CALENDAR')
    integer(value['version'], 0, 2147483647)
    digest(value['timezone_rules_sha256']); digest(value['calendar_rules_sha256'])


def request(value):
    fixed = dict(instrument='NQ DEC26', master='NQ', expiry='2026-12-01', tick_size=.25,
                 point_value=20, period='Minute', period_value=1, market_data='Last',
                 lookup='Repository', merge='DoNotMerge', reset=True, dividend_adjusted=False,
                 split_adjusted=False, application_timezone='UTC')
    extra = 'configured_from configured_through submitted_from submitted_through actual_from actual_through trading_hours sdk_version sdk_assembly sdk_mvid'
    need(type(value) is dict and set(value) == set(fixed) | set(extra.split()), 'REQUEST_SCHEMA')
    for k, expected in fixed.items():
        need(type(value[k]) is type(expected) and value[k] == expected, 'REQUEST_CONTRACT')
    dates = []
    for side in ('from', 'through'):
        text = value['configured_' + side]
        need(type(text) is str and re.fullmatch(r'2026-\d{2}-\d{2}', text) is not None, 'DATE')
        date = datetime.strptime(text, '%Y-%m-%d'); dates.append(date)
        need(time_fact(value['submitted_' + side], 'Unspecified') == tick_of(date), 'SUBMITTED_DATE')
        need(time_fact(value['actual_' + side]) == tick_of(date), 'ACTUAL_DATE')
    need(0 <= (dates[1] - dates[0]).days <= 14, 'DATE_RANGE')
    calendar(value['trading_hours'])
    need(type(value['sdk_version']) is str and re.fullmatch(r'\d+\.\d+\.\d+\.\d+', value['sdk_version']) is not None, 'SDK')
    need(type(value['sdk_assembly']) is str and 0 < len(value['sdk_assembly']) <= 512, 'SDK')
    assembly = [part.strip() for part in value['sdk_assembly'].split(',')]
    need(bool(assembly[0]) and len(assembly) > 1, 'SDK')
    attributes = {}
    for part in assembly[1:]:
        field, separator, text = part.partition('=')
        field, text = field.strip(), text.strip()
        need(separator == '=' and bool(field) and bool(text) and field not in attributes, 'SDK')
        attributes[field] = text
    version = attributes.get('Version')
    need(type(version) is str and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', version) is not None
         and version == value['sdk_version'], 'SDK')
    need(type(value['sdk_mvid']) is str and str(UUID(value['sdk_mvid'])) == value['sdk_mvid'], 'SDK')
    return tick_of(dates[0] - timedelta(days=2)), tick_of(dates[1] + timedelta(days=8))


def snapshot(value, hours):
    keys(value, 'identity callback_request_identity_verified count first last instrument expiry period period_value market_data trading_hours snapshot_algorithm snapshot_sha256')
    need(value['identity'] == 'RETURNED_BARS_1' and value['callback_request_identity_verified'] is True, 'BARS_IDENTITY')
    integer(value['count'], 3, 10002)
    time_fact(value['first']); time_fact(value['last'])
    need(value['instrument'] == 'NQ DEC26' and value['expiry'] == '2026-12-01'
         and value['period'] == 'Minute' and integer(value['period_value'], 1, 1) == 1
         and value['market_data'] == 'Last', 'BARS_CONTRACT')
    calendar(value['trading_hours']); need(value['trading_hours'] == hours, 'RETURNED_CALENDAR')
    need(value['snapshot_algorithm'] == 'R55_SNAPSHOT_BITS_V1', 'SNAPSHOT_ALGORITHM')
    digest(value['snapshot_sha256'])


CASES = ('END_INCLUDE_TRUE', 'END_INCLUDE_FALSE', 'END_PLUS_ONE_TICK_INCLUDE_TRUE',
         'END_PLUS_ONE_TICK_INCLUDE_FALSE', 'NEXT_DAY_INTERIOR_CONTROL', 'LATER_DATE_CONTROL')
DERIVATIONS = ('NATIVE_PRIME_END', 'NATIVE_PRIME_END', 'NATIVE_PRIME_END_PLUS_ONE_TICK',
               'NATIVE_PRIME_END_PLUS_ONE_TICK', 'INITIAL_PLUS_ONE_DAY', 'INITIAL_PLUS_TWO_DAYS')
COUNTS = ('getnextsession_attempts', 'begin_read_attempts', 'end_read_attempts', 'trading_day_read_attempts')


def call_contract(call, query, include, derivation, through, anchor):
    keys(call, 'query source_after begin end trading_day derivation phase exception guard classification '
         'trading_day_outcome include_end_time source_preserved bounds_valid returned ' + ' '.join(COUNTS))
    need(time_fact(call['query'], 'Utc') == query, 'QUERY_DERIVATION')
    time_fact(call['source_after'], 'Utc')
    need(call['source_after'] == call['query'] and call['source_preserved'] is True, 'SOURCE_PRESERVATION')
    need(call['include_end_time'] is include and call['derivation'] == derivation, 'QUERY_POLICY')
    need(call['exception'] in ERRORS, 'EXCEPTION')
    returned = call['returned']
    need(returned is None or type(returned) is bool, 'RETURNED')
    boolean(call['bounds_valid'])
    expected = [1, 0, 0, 0]
    phase, classification, guard, valid, day_outcome = 'ADVANCE', 'EXCEPTION', 'NONE', False, 'NOT_READ'
    exception_required = returned is None
    if returned is False:
        phase = classification = 'RETURNED_FALSE'
    elif returned is True:
        phase = 'BEGIN_READ'; expected[1] = 1; exception_required = True
        if call['begin'] is not None:
            begin = time_fact(call['begin']); phase = 'END_READ'; expected[2] = 1
            if call['end'] is not None:
                end = time_fact(call['end']); phase = 'BOUNDS'; exception_required = False
                if begin >= end or end <= 0:
                    guard, classification = 'BOUND_ORDER', 'BOUND_REJECTED'
                elif begin >= through:
                    classification = 'REQUESTED_BOUNDARY'
                elif call['begin']['kind'] != 'Utc' or call['end']['kind'] != 'Utc':
                    guard, classification = 'BOUND_KIND', 'BOUND_REJECTED'
                else:
                    valid = True; phase = 'TRADING_DAY_READ'; expected[3] = 1
                    if call['trading_day'] is None:
                        day_outcome = 'EXCEPTION'; exception_required = True
                    else:
                        time_fact(call['trading_day']); day_outcome = 'RETURNED'; phase = 'COMPLETE'
                        classification = ('PRIME' if anchor is None else 'SAME_AS_PRIME'
                            if call['begin'] == anchor['begin'] and call['end'] == anchor['end'] else
                            'ADVANCING_AFTER_PRIME' if end > anchor['end']['ticks'] else 'OTHER_VALID_SESSION')
    if not expected[1] or call['begin'] is None:
        need(call['begin'] is None and call['end'] is None, 'NO_BOUNDS')
    if not expected[3]:
        need(call['trading_day'] is None, 'NO_TRADING_DAY')
    need((call['exception'] != 'NONE') == exception_required, 'EXCEPTION_PHASE')
    need(call['phase'] == phase and call['classification'] == classification and call['guard'] == guard
         and call['bounds_valid'] == valid and call['trading_day_outcome'] == day_outcome, 'CALL_STATE')
    for name, count in zip(COUNTS, expected):
        integer(call[name], count, count)
    return expected


def matrix_contract(value, initial, through):
    keys(value, 'constructor_source outcome interpretation_allowed conditional_required iterator_constructor_attempts '
         'observations ' + ' '.join(COUNTS))
    need(value['constructor_source'] == 'RETURNED_REPOSITORY_BARS', 'CONSTRUCTOR_SOURCE')
    boolean(value['interpretation_allowed'])
    conditional = value['conditional_required']
    need(conditional is None or type(conditional) is bool, 'CONDITIONAL')
    observations = value['observations']
    need(type(observations) is list, 'OBSERVATIONS')
    count = integer(value['iterator_constructor_attempts'], 1, 12)
    need(len(observations) == count, 'CONSTRUCTOR_COUNT')
    totals = [0, 0, 0, 0]
    canonical, pair_query, stop = None, None, None
    expected_conditional = None
    control_advances = False
    for index, item in enumerate(observations):
        need(stop is None, 'OBSERVATION_AFTER_STOP')
        row, mode = divmod(index, 2)
        need(row < 5 or expected_conditional is True, 'UNNECESSARY_CONTROL')
        keys(item, 'case_id mode iterator_identity source_bars_identity exception phase constructor_ordinal priming_occurred prime observation')
        integer(item['constructor_ordinal'], index + 1, index + 1)
        need(item['case_id'] == CASES[row] and item['mode'] == ('PRIMED_REUSED' if mode == 0 else 'FRESH_DIRECT'), 'MATRIX_ORDER')
        need(item['source_bars_identity'] == 'RETURNED_BARS_1' and item['exception'] in ERRORS, 'ITERATOR_CONTEXT')
        boolean(item['priming_occurred'])
        if item['iterator_identity'] is None:
            need(item['phase'] == 'CONSTRUCTOR' and item['exception'] != 'NONE'
                 and item['prime'] is None and item['observation'] is None and not item['priming_occurred'], 'CONSTRUCTOR_FAILURE')
            stop = 'CONSTRUCTOR_EXCEPTION'
            continue
        need(item['iterator_identity'] == 'ITERATOR_' + str(index + 1), 'ITERATOR_IDENTITY')
        if mode == 0:
            need(item['priming_occurred'] is True, 'PRIMING')
            prime = item['prime']
            counts = call_contract(prime, initial, True, 'CONFIGURED_FROM_MINUS_TWO_DAYS_UTC', through, None)
            totals = [a + b for a, b in zip(totals, counts)]
            if prime['phase'] != 'COMPLETE':
                stop = 'PRIME_REJECTED'
            elif canonical is not None and any(prime[k] != canonical[k] for k in ('begin', 'end', 'trading_day')):
                stop = 'PRIME_DISAGREEMENT'
            else:
                canonical = prime if canonical is None else canonical
            if stop:
                need(item['phase'] == 'PRIME' and item['exception'] == 'NONE' and item['observation'] is None, 'PRIME_STOP')
                continue
            end = prime['end']['ticks']
            pair_query = end if row < 2 else end + 1 if row < 4 else initial + DAY * (1 if row == 4 else 2)
            if pair_query > MAX_TICKS:
                need(item['phase'] == 'DERIVATION' and item['exception'] == 'ArgumentException'
                     and item['observation'] is None, 'OVERFLOW')
                stop = 'DERIVATION_EXCEPTION'
                continue
        else:
            need(item['prime'] is None and item['priming_occurred'] is False, 'FRESH_NO_PRIME')
        need(item['phase'] == 'COMPLETE' and item['exception'] == 'NONE', 'ITERATOR_COMPLETE')
        counts = call_contract(item['observation'], pair_query, row not in (1, 3), DERIVATIONS[row], through, canonical)
        totals = [a + b for a, b in zip(totals, counts)]
        if row == 4:
            control_advances |= item['observation']['classification'] == 'ADVANCING_AFTER_PRIME'
            if mode == 1:
                expected_conditional = not control_advances
    if stop is None:
        need(count == (12 if expected_conditional else 10) and expected_conditional is not None, 'INCOMPLETE_MATRIX')
        stop = 'COMPLETE'
    need(value['outcome'] == stop and value['interpretation_allowed'] == (stop == 'COMPLETE'), 'MATRIX_OUTCOME')
    need(conditional is expected_conditional, 'CONDITIONAL_LOGIC')
    for name, total in zip(COUNTS, totals):
        integer(value[name], total, total)
    need(totals[0] <= 18, 'CALL_BUDGET')


def validate_contract(raw, seal_raw):
    """Bytes only, including valid aborted prefixes; does not establish publication eligibility."""
    evidence, seal = decode(raw, MAX_BYTES), decode(seal_raw, 4096)
    envelope(evidence, 'arms.r56.historical-utc-boundary-matrix.v1',
             'request bars_before bars_after source_preserved snapshot_preserved request_preserved matrix initial_query calendar_through request_attempts request_constructor_attempts matrix_attempts')
    envelope(seal, 'arms.r56.historical-utc-boundary-matrix.seal.v1', 'evidence_sha256 bytes complete')
    digest(seal['evidence_sha256'])
    need(seal['run_id'] == evidence['run_id'] and seal['complete'] is True, 'SEAL')
    need(integer(seal['bytes'], 1, MAX_BYTES) == len(raw) and seal['evidence_sha256'] == sha256(raw).hexdigest(), 'HASH_BINDING')
    for name in ('request_attempts', 'request_constructor_attempts', 'matrix_attempts'):
        integer(evidence[name], 1, 1)
    for name in ('source_preserved', 'snapshot_preserved', 'request_preserved'):
        need(evidence[name] is True, 'PRESERVATION')
    initial, through = request(evidence['request'])
    need(time_fact(evidence['initial_query'], 'Utc') == initial and time_fact(evidence['calendar_through'], 'Utc') == through, 'COVERAGE')
    for name in ('bars_before', 'bars_after'):
        snapshot(evidence[name], evidence['request']['trading_hours'])
    need(evidence['bars_before'] == evidence['bars_after'], 'SNAPSHOT_CHANGED')
    matrix_contract(evidence['matrix'], initial, through)
    return dict(status='PASS_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CONTRACT_ONLY',
                outcome=evidence['matrix']['outcome'], interpretation_allowed=evidence['matrix']['interpretation_allowed'],
                getnextsession_attempts=evidence['matrix']['getnextsession_attempts'], **FLAGS)


def bounded_read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    need(len(value) <= limit, 'SIZE')
    return value


class IncompleteCaptureError(ValueError):
    """The final pair is missing or its conditional row is structurally incomplete."""


def _require_complete_matrix(value):
    # Called after independent graph validation. Preserve A-E aborted-prefix semantics.
    if value['conditional_required'] is None:
        return
    required = 12 if value['conditional_required'] else 10
    observations = value['observations']
    identities = [(CASES[i // 2], 'PRIMED_REUSED' if i % 2 == 0 else 'FRESH_DIRECT')
                  for i in range(required)]
    complete = ([(item['case_id'], item['mode']) for item in observations] == identities
                and all(item['phase'] == 'COMPLETE' and item['observation'] is not None for item in observations)
                and value['outcome'] == 'COMPLETE' and value['interpretation_allowed'] is True
                and value['iterator_constructor_attempts'] == required
                and value['getnextsession_attempts'] == required // 2 * 3)
    if not complete:
        raise IncompleteCaptureError('R56_INCOMPLETE_CONDITIONAL_ROW')


def _final_capture_paths(capture):
    # Match the writer's private, non-reparse directory and exact final pair.
    # lstat rejects redirected final names, including links to .tmp artifacts.
    for directory in (capture, *capture.parents):
        info = directory.lstat()
        need(stat.S_ISDIR(info.st_mode) and not
             (getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT), 'CAPTURE_DIRECTORY')
    paths = (capture / EVIDENCE_NAME, capture / SEAL_NAME)
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError as exc:
            raise IncompleteCaptureError('R56_INCOMPLETE_CAPTURE') from exc
        need(stat.S_ISREG(info.st_mode) and not
             (getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT), 'FINAL_ARTIFACT')
    need({path.name for path in capture.iterdir()} == {EVIDENCE_NAME, SEAL_NAME}, 'CAPTURE_CONTENTS')
    return paths


def verify_completed_capture(capture):
    """Verify the final pair in the supplied directory, then its byte contract.

    No alternate filenames, promotion, repair or write operation is permitted.
    The private capture directory must remain stable during verification.
    """
    capture = Path(capture).absolute()
    evidence, seal = _final_capture_paths(capture)
    raw = bounded_read(evidence, MAX_BYTES)
    result = validate_contract(raw, bounded_read(seal, 4096))
    _require_complete_matrix(decode(raw, MAX_BYTES)['matrix'])
    _final_capture_paths(capture)
    return dict(result, publication_complete=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--capture', required=True, type=Path, help='Directory containing exactly the published final pair')
    args = parser.parse_args()
    try:
        result = verify_completed_capture(args.capture)
    except IncompleteCaptureError:
        parser.exit(1, 'INCOMPLETE_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CAPTURE\n')
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError):
        parser.exit(1, 'FAIL_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CONTRACT\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
