"""Independent R5.5 evidence integrity verifier. Never attests native provenance."""
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
EVIDENCE_NAME = 'historical-utc-traversal.json'
SEAL_NAME = 'historical-utc-traversal.done.json'
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
        raise ValueError('R55_' + reason)


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
        raise ValueError('R55_JSON') from exc


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
        raise ValueError('R55_CLOCK') from exc
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
        raise ValueError('R55_RUN_ID') from exc


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


def traversal(value, initial, through):
    keys(value, 'constructor_source iterator_identity outcome exception iterator_constructor_attempts getnextsession_attempts begin_read_attempts end_read_attempts trading_day_read_attempts observed_false stopped_by_limit stopped_by_requested_boundary first_false_ordinal first_false_query successful_calls_before_false calls')
    need(value['constructor_source'] == 'RETURNED_REPOSITORY_BARS', 'CONSTRUCTOR_SOURCE')
    integer(value['iterator_constructor_attempts'], 1, 1)
    count = integer(value['getnextsession_attempts'], 0, 64)
    begin_reads = integer(value['begin_read_attempts'], 0, 64)
    end_reads = integer(value['end_read_attempts'], 0, 64)
    trading_day_reads = integer(value['trading_day_read_attempts'], 0, 64)
    need(type(value['calls']) is list and len(value['calls']) == count, 'CALL_COUNT')
    for flag in ('observed_false', 'stopped_by_limit', 'stopped_by_requested_boundary'):
        boolean(value[flag])
    integer(value['successful_calls_before_false'], 0, 63)
    need(value['exception'] in ERRORS, 'EXCEPTION')
    next_ticks, last_end = initial, -1
    observed_false = False
    expected_outcome = 'CONSTRUCTOR_EXCEPTION' if count == 0 else None
    need(value['iterator_identity'] == (None if count == 0 else 'ITERATOR_1'), 'ITERATOR_IDENTITY')
    need((value['exception'] != 'NONE') == (count == 0), 'CONSTRUCTOR_EXCEPTION')
    expected_begin = expected_end = expected_trading_day = 0
    for index, call in enumerate(value['calls']):
        keys(call, 'ordinal query source_after begin end trading_day trading_day_outcome derivation exception phase guard include_end_time source_preserved bounds_valid returned')
        integer(call['ordinal'], index, index)
        need(time_fact(call['query'], 'Utc') == next_ticks, 'QUERY_SEQUENCE')
        time_fact(call['source_after'], 'Utc')
        need(call['source_after'] == call['query'] and call['source_preserved'] is True, 'SOURCE_PRESERVATION')
        need(call['include_end_time'] is True, 'INCLUDE_END')
        need(call['derivation'] == ('CONFIGURED_FROM_MINUS_TWO_DAYS_UTC' if index == 0 else 'PRIOR_NATIVE_SESSION_END_PLUS_ONE_TICK'), 'DERIVATION')
        need(call['exception'] in ERRORS, 'EXCEPTION')
        boolean(call['bounds_valid'])
        returned = call['returned']
        need(returned is None or type(returned) is bool, 'RETURNED')
        terminal = None
        trading_day_attempted = False
        if returned is None:
            need(call['phase'] == 'ADVANCE' and call['exception'] != 'NONE', 'ADVANCE_EXCEPTION')
            need(call['begin'] is None and call['end'] is None and not call['bounds_valid'] and call['guard'] == 'NONE', 'NO_BOUNDS')
            terminal = 'CALL_EXCEPTION'
        elif not returned:
            need(call['phase'] == 'RETURNED_FALSE' and call['exception'] == call['guard'] == 'NONE', 'FALSE')
            need(call['begin'] is None and call['end'] is None and not call['bounds_valid'], 'FALSE_BOUNDS')
            observed_false = True; terminal = 'FALSE'
            integer(value['first_false_ordinal'], index, index)
            time_fact(value['first_false_query'], 'Utc')
            need(value['first_false_query'] == call['query'] and value['successful_calls_before_false'] == index, 'FALSE_SUMMARY')
        else:
            expected_begin += 1
            if call['begin'] is None:
                need(call['phase'] == 'BEGIN_READ' and call['exception'] != 'NONE' and call['end'] is None, 'BEGIN_EXCEPTION')
                need(not call['bounds_valid'] and call['guard'] == 'NONE', 'BEGIN_STATE')
                terminal = 'CALL_EXCEPTION'
            else:
                begin = time_fact(call['begin']); expected_end += 1
                if call['end'] is None:
                    need(call['phase'] == 'END_READ' and call['exception'] != 'NONE', 'END_EXCEPTION')
                    need(not call['bounds_valid'] and call['guard'] == 'NONE', 'END_STATE')
                    terminal = 'CALL_EXCEPTION'
                else:
                    end = time_fact(call['end'])
                    guard = ('BOUND_ORDER' if begin >= end or end <= last_end else
                             'BOUND_KIND' if begin < through and
                             (call['begin']['kind'] != 'Utc' or call['end']['kind'] != 'Utc') else 'NONE')
                    need(call['guard'] == guard and call['bounds_valid'] == (guard == 'NONE'), 'BOUND_VALIDITY')
                    if guard != 'NONE':
                        need(call['phase'] == 'BOUNDS' and call['exception'] == 'NONE', 'BOUND_REJECTION')
                        terminal = 'BOUND_REJECTED'
                    elif begin >= through:
                        need(call['phase'] == 'BOUNDS' and call['exception'] == 'NONE', 'BOUNDARY')
                        terminal = 'REQUESTED_BOUNDARY'
                    else:
                        trading_day_attempted = True; expected_trading_day += 1
                        if call['trading_day_outcome'] == 'EXCEPTION':
                            need(call['trading_day'] is None and call['phase'] == 'TRADING_DAY_READ'
                                 and call['exception'] != 'NONE', 'TRADING_DAY_EXCEPTION')
                            terminal = 'CALL_EXCEPTION'
                        else:
                            need(call['trading_day_outcome'] == 'RETURNED', 'TRADING_DAY_OUTCOME')
                            time_fact(call['trading_day'])  # Preserve native Kind; it is not a UTC query.
                            if end == MAX_TICKS:
                                need(call['phase'] == 'QUERY_UPDATE' and call['exception'] == 'ArgumentException', 'OVERFLOW')
                                terminal = 'CALL_EXCEPTION'
                            else:
                                need(call['phase'] == 'COMPLETE' and call['exception'] == 'NONE', 'CALL_COMPLETE')
                                next_ticks, last_end = end + 1, end
                                if next_ticks >= through:
                                    terminal = 'REQUESTED_BOUNDARY'
        if not trading_day_attempted:
            need(call['trading_day'] is None and call['trading_day_outcome'] == 'NOT_READ', 'UNEXPECTED_TRADING_DAY')
        if terminal:
            need(index == count - 1, 'CALL_AFTER_STOP')
            expected_outcome = terminal
    if expected_outcome is None:
        need(count == 64, 'EARLY_STOP'); expected_outcome = 'CALL_LIMIT'
    need(value['outcome'] == expected_outcome and value['observed_false'] == observed_false, 'OUTCOME')
    need(value['stopped_by_limit'] == (expected_outcome == 'CALL_LIMIT')
         and value['stopped_by_requested_boundary'] == (expected_outcome == 'REQUESTED_BOUNDARY'), 'STOP_FLAGS')
    need(begin_reads == expected_begin and end_reads == expected_end and trading_day_reads == expected_trading_day, 'BOUND_READ_COUNTS')
    if not observed_false:
        need(value['first_false_ordinal'] is None and value['first_false_query'] is None
             and value['successful_calls_before_false'] == 0, 'NO_FALSE_SUMMARY')


def validate_contract(raw, seal_raw):
    """Validate supplied bytes only; this cannot establish publication completion."""
    evidence, seal = decode(raw, MAX_BYTES), decode(seal_raw, 4096)
    envelope(evidence, 'arms.r55.historical-utc-traversal.v1',
             'request bars_before bars_after source_preserved snapshot_preserved request_preserved traversal initial_query calendar_through request_attempts request_constructor_attempts traversal_attempts')
    envelope(seal, 'arms.r55.historical-utc-traversal.seal.v1', 'evidence_sha256 bytes complete')
    digest(seal['evidence_sha256'])
    need(seal['run_id'] == evidence['run_id'] and seal['complete'] is True, 'SEAL')
    need(integer(seal['bytes'], 1, MAX_BYTES) == len(raw) and seal['evidence_sha256'] == sha256(raw).hexdigest(), 'HASH_BINDING')
    for name in ('request_attempts', 'request_constructor_attempts', 'traversal_attempts'):
        integer(evidence[name], 1, 1)
    for name in ('source_preserved', 'snapshot_preserved', 'request_preserved'):
        need(evidence[name] is True, 'PRESERVATION')
    initial, through = request(evidence['request'])
    need(time_fact(evidence['initial_query'], 'Utc') == initial and time_fact(evidence['calendar_through'], 'Utc') == through, 'COVERAGE')
    for name in ('bars_before', 'bars_after'):
        snapshot(evidence[name], evidence['request']['trading_hours'])
    need(evidence['bars_before'] == evidence['bars_after'], 'SNAPSHOT_CHANGED')
    traversal(evidence['traversal'], initial, through)
    return dict(status='PASS_R55_HISTORICAL_UTC_TRAVERSAL_CONTRACT_ONLY',
                observed_false=evidence['traversal']['observed_false'], outcome=evidence['traversal']['outcome'],
                getnextsession_attempts=evidence['traversal']['getnextsession_attempts'], **FLAGS)


def bounded_read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    need(len(value) <= limit, 'SIZE')
    return value


class IncompleteCaptureError(ValueError):
    """The required final artifact pair has not been published."""


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
            raise IncompleteCaptureError('R55_INCOMPLETE_CAPTURE') from exc
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
    result = validate_contract(bounded_read(evidence, MAX_BYTES), bounded_read(seal, 4096))
    _final_capture_paths(capture)
    return dict(result, publication_complete=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--capture', required=True, type=Path, help='Directory containing exactly the published final pair')
    args = parser.parse_args()
    try:
        result = verify_completed_capture(args.capture)
    except IncompleteCaptureError:
        parser.exit(1, 'INCOMPLETE_R55_HISTORICAL_UTC_TRAVERSAL_CAPTURE\n')
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError):
        parser.exit(1, 'FAIL_R55_HISTORICAL_UTC_TRAVERSAL_CONTRACT\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
