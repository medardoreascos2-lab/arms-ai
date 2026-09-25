"""Independent R5.7 evidence integrity verifier. Never attests native provenance."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
from uuid import UUID

MAX_BYTES = 1048576
EVIDENCE_NAME = 'historical-utc-calendar-cursor.json'
SEAL_NAME = 'historical-utc-calendar-cursor.done.json'
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
        raise ValueError('R57_' + reason)


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
        raise ValueError('R57_JSON') from exc


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
        raise ValueError('R57_CLOCK') from exc
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
        raise ValueError('R57_RUN_ID') from exc


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
    need(value['sdk_version'] == '8.1.8.2', 'SDK')
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


def date_value(value):
    need(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None, 'CALENDAR_DATE')
    return datetime.strptime(value, '%Y-%m-%d')


def hhmm(value):
    integer(value, 0, 2359)
    need(value % 100 < 60, 'SESSION_TIME')
    return timedelta(hours=value // 100, minutes=value % 100)


def session_structure(value):
    keys(value, 'begin_day begin_time end_day end_time trading_day')
    for k in ('begin_day', 'end_day', 'trading_day'):
        integer(value[k], 0, 6)
    hhmm(value['begin_time']); hhmm(value['end_time'])


def session(value):
    session_structure(value)
    need(value['end_day'] == value['trading_day'], 'UNSUPPORTED_SESSION_SHAPE')


def transition(value, year):
    keys(value, 'fixed month day week day_of_week time_ticks')
    boolean(value['fixed']); integer(value['month'], 1, 12); integer(value['day'], 1, 31)
    integer(value['week'], 1, 5); integer(value['day_of_week'], 0, 6)
    t = integer(value['time_ticks'], 0, DAY - 1)
    need(t % 10 == 0, 'UNSUPPORTED_TRANSITION_PRECISION')
    from calendar import monthrange
    last = monthrange(year, value['month'])[1]
    if value['fixed']:
        day = min(value['day'], last)
    else:
        first = datetime(year, value['month'], 1)
        day = 1 + (value['day_of_week'] - (first.weekday() + 1) % 7) % 7 + 7 * (value['week'] - 1)
        if day > last:
            day -= 7
    return datetime(year, value['month'], day) + timedelta(microseconds=t // 10)


class CapturedZone:
    """Independent positive-DST rule evaluator. No OS/local timezone or fixture fallback."""
    def __init__(self, value):
        keys(value, 'id base_offset_ticks supports_dst years adjustments')
        need(value['id'] == 'Central Standard Time' and value['years'] == [2025, 2026, 2027], 'ZONE_ID')
        for year in value['years']: integer(year, 2025, 2027)
        self.base = integer(value['base_offset_ticks'], -14 * DAY // 24, 14 * DAY // 24)
        need(self.base % 600000000 == 0 and boolean(value['supports_dst']), 'ZONE_OFFSET')
        need(type(value['adjustments']) is list and 0 < len(value['adjustments']) <= 128, 'ZONE_RULES')
        self.rules = value['adjustments']
        last = None
        for r in self.rules:
            keys(r, 'start end delta_ticks transition_start transition_end')
            a, z = date_value(r['start']), date_value(r['end'])
            need(a <= z and (last is None or a > last), 'ZONE_RULE_ORDER'); last = z
            delta = integer(r['delta_ticks'], 1, 2 * DAY // 24)
            need(delta % 600000000 == 0, 'ZONE_DELTA')
            for year in (2025, 2026, 2027):
                start, end = transition(r['transition_start'], year), transition(r['transition_end'], year)
                need(start < end and start + timedelta(microseconds=delta // 10) < end, 'UNSUPPORTED_ZONE_SHAPE')

    def rule(self, date):
        need(date.year in (2025, 2026, 2027), 'ZONE_YEAR')
        rules = [r for r in self.rules if date_value(r['start']) <= date.replace(hour=0, minute=0, second=0, microsecond=0) <= date_value(r['end'])]
        need(len(rules) == 1, 'ZONE_COVERAGE')
        r = rules[0]
        # Rule changes within a year need a separately reviewed evaluator.
        need(date_value(r['start']) <= datetime(date.year, 1, 1)
             and date_value(r['end']) >= datetime(date.year, 12, 31), 'UNSUPPORTED_PART_YEAR_ZONE')
        return r

    def wall(self, value):
        r = self.rule(value)
        start, end = transition(r['transition_start'], value.year), transition(r['transition_end'], value.year)
        delta = timedelta(microseconds=r['delta_ticks'] // 10)
        need(not start <= value < start + delta, 'INVALID_CALENDAR_WALL_TIME')
        need(not end - delta <= value < end, 'AMBIGUOUS_CALENDAR_WALL_TIME')
        offset = self.base + (r['delta_ticks'] if start + delta <= value < end - delta else 0)
        return tick_of(value) - offset


def calendar(value):
    keys(value, 'name version timezone timezone_rules_json timezone_rules_sha256 calendar_rules_json calendar_rules_sha256')
    need(value['name'] == 'CME US Index Futures ETH' and value['timezone'] == 'Central Standard Time', 'CALENDAR')
    integer(value['version'], 0, 2147483647)
    decoded = []
    for prefix, limit in (('calendar', 131072), ('timezone', 32768)):
        raw = value[prefix + '_rules_json']; need(type(raw) is str, 'CALENDAR_RULES_REQUIRED')
        digest(value[prefix + '_rules_sha256'])
        need(sha256(raw.encode()).hexdigest() == value[prefix + '_rules_sha256'], 'CALENDAR_HASH')
        decoded.append(decode(raw.encode(), limit))
    rules, zone = decoded
    keys(rules, 'sessions holidays partials')
    for name in rules:
        need(type(rules[name]) is list and len(rules[name]) <= 4096, 'CALENDAR_LIST')
    need(bool(rules['sessions']), 'NO_SESSIONS')
    for s in rules['sessions']:
        session(s)
    need(len({json.dumps(s, sort_keys=True) for s in rules['sessions']}) == len(rules['sessions']), 'DUPLICATE_RULE')
    holidays, partials = [], {}
    for d in rules['holidays']:
        t = time_fact(d, 'Unspecified'); need(t % DAY == 0, 'HOLIDAY_DATE'); holidays.append(t)
    need(holidays == sorted(set(holidays)), 'HOLIDAY_ORDER')
    previous = -1
    for p in rules['partials']:
        keys(p, 'date early late constraint sessions')
        t = time_fact(p['date'], 'Unspecified')
        need(t % DAY == 0 and t > previous and t not in holidays, 'PARTIAL_DATE'); previous = t
        boolean(p['early']); boolean(p['late'])
        need(type(p['sessions']) is list and len(p['sessions']) <= 32, 'SPECIAL_SESSION_LIST')
        if p['constraint'] is not None:
            session_structure(p['constraint'])
        for s in p['sessions']:
            session_structure(s)
        partials[t] = p
    return rules['sessions'], set(holidays), partials, CapturedZone(zone)


def special_influence(p, sessions, zone):
    """Enclose a single-endpoint edit, never evaluate its unsupported semantics.

    Proof is deliberately limited to one ordinary session per trading weekday,
    no replacement, and one active endpoint on the named trading date. Include
    the preceding/current/following recurring groups and the active endpoint.
    Splits, unknown mappings and missing offset coverage have no finite proof.
    """
    c = p['constraint']
    if c is None or p['sessions'] or p['early'] == p['late']:
        return None
    by_day = {s['trading_day']: s for s in sessions}
    if len(by_day) != len(sessions):
        return None
    d = date_value(p['date']['clock'][:10]); weekday = (d.weekday() + 1) % 7
    endpoint = 'end' if p['early'] else 'begin'
    if weekday not in by_day or c['trading_day'] != weekday or c[endpoint + '_day'] != weekday:
        return None
    # Establish the local order of the recurring groups, including week wrap.
    # A single group can cross midnight, but cannot span multiple trading days.
    for s in sessions:
        lag = (s['trading_day'] - s['begin_day']) % 7
        if lag > 1 or hhmm(s['end_time']) + timedelta(days=lag) <= hhmm(s['begin_time']):
            return None
        preceding = min(i for i in range(1, 8) if (s['trading_day'] - i) % 7 in by_day)
        prior = by_day[(s['trading_day'] - preceding) % 7]
        if hhmm(prior['end_time']) - timedelta(days=preceding) >= hhmm(s['begin_time']) - timedelta(days=lag):
            return None
    try:
        before = min(i for i in range(1, 8) if (weekday - i) % 7 in by_day)
        after = min(i for i in range(1, 8) if (weekday + i) % 7 in by_day)
        points = [d + hhmm(c[endpoint + '_time'])]
        for offset in (-before, 0, after):
            day = d + timedelta(days=offset); s = by_day[(weekday + offset) % 7]
            points.extend((day - timedelta(days=(s['trading_day'] - s['begin_day']) % 7) + hhmm(s['begin_time']),
                           day + hhmm(s['end_time'])))
        low, high = min(points), max(points)
        # Use *possible* offsets over the entire envelope, not a guessed DST
        # fold or the machine zone. Captured rule date extents may cover years
        # outside the exact wall evaluator's 2025..2027 range.
        day = low.replace(hour=0, minute=0, second=0, microsecond=0)
        offsets = {zone.base}
        while day <= high:
            rules = [r for r in zone.rules if date_value(r['start']) <= day <= date_value(r['end'])]
            if len(rules) != 1:
                return None
            offsets.add(zone.base + rules[0]['delta_ticks'])
            day += timedelta(days=1)
        return tick_of(low) - max(offsets), tick_of(high) - min(offsets)
    except OverflowError:
        return None


def special_relevant(bounds, initial, through):
    return bounds is None or (bounds[1] >= initial and bounds[0] < through)


def scoped_partials(sessions, partials, zone, initial, through):
    result = {}
    for t, p in partials.items():
        bounds = special_influence(p, sessions, zone)
        if not special_relevant(bounds, initial, through):
            continue
        need(bounds is not None and p['early'] and not p['late'] and not p['sessions'],
             'UNSUPPORTED_SPECIAL_SESSION')
        c = p['constraint']; session(c)
        result[t] = c
    return result


def expected_calendar(hours, initial, through):
    sessions, holidays, partials, zone = calendar(hours)
    partials = scoped_partials(sessions, partials, zone, initial, through)
    day = datetime(1, 1, 1) + timedelta(days=initial // DAY - 8)
    last = datetime(1, 1, 1) + timedelta(days=through // DAY + 8)
    expected = []
    while day <= last:
        weekday, day_ticks = (day.weekday() + 1) % 7, tick_of(day)
        if day_ticks not in holidays:
            for s in sessions:
                if s['trading_day'] != weekday:
                    continue
                start_day = day - timedelta(days=(weekday - s['begin_day']) % 7)
                start = zone.wall(start_day + hhmm(s['begin_time']))
                end_time = s['end_time']
                if day_ticks in partials:
                    p = partials[day_ticks]
                    need(p['end_day'] == weekday, 'PARTIAL_DAY')
                    end_time = p['end_time']
                    need(hhmm(end_time) <= hhmm(s['end_time']), 'PARTIAL_NOT_EARLY')
                end = zone.wall(day + hhmm(end_time))
                need(start < end, 'CALENDAR_BOUND_ORDER')
                if end >= initial and start < through:
                    expected.append((start, 'Utc', end, 'Utc', day_ticks, 'Unspecified'))
        day += timedelta(days=1)
    expected.sort()
    need(all(a[2] < b[0] for a, b in zip(expected, expected[1:])), 'CALENDAR_OVERLAP')
    return expected


def date_classes(hours, schedule):
    sessions, holidays, partials, zone = calendar(hours)
    result = []
    for i, q in enumerate(schedule):
        d = date_value(q['clock'][:10]); tags = []
        weekday = (d.weekday() + 1) % 7
        if weekday in (5, 6, 0):
            tags.append({5: 'FRIDAY', 6: 'SATURDAY', 0: 'SUNDAY'}[weekday])
        if q['ticks'] in holidays:
            tags.append('FULL_HOLIDAY')
        elif q['ticks'] in partials:
            tags.append('PARTIAL_HOLIDAY_OR_SPECIAL')
        elif any(s['trading_day'] == weekday for s in sessions):
            tags.append('ORDINARY')
        r = zone.rule(d)
        if any(abs((d.date() - transition(r[k], d.year).date()).days) <= 1 for k in ('transition_start', 'transition_end')):
            tags.append('DST_TRANSITION_WINDOW')
        if i == 0: tags.append('RANGE_START_EDGE')
        if i == len(schedule) - 1: tags.append('RANGE_END_EDGE')
        result.append(dict(ordinal=i, date=d.strftime('%Y-%m-%d'), tags=tags))
    return result


def call_contract(c, path, ordinal, constructor, query):
    keys(c, 'ordinal constructor_ordinal path iterator_identity derivation phase exception guard query source_before source_after begin end trading_day include_end_time source_preserved returned getnextsession_attempts getnextsession_completed begin_read_attempts end_read_attempts trading_day_read_attempts')
    integer(c['ordinal'], ordinal, ordinal); integer(c['constructor_ordinal'], constructor['ordinal'], constructor['ordinal'])
    need(c['path'] == path and c['iterator_identity'] == constructor['identity'], 'CALL_IDENTITY')
    time_fact(c['source_before'], 'Utc'); time_fact(c['source_after'], 'Utc')
    need(time_fact(c['query'], 'Utc') == query and c['source_before'] == c['query'] == c['source_after']
         and c['source_preserved'] is True, 'SOURCE_PRESERVATION')
    need(c['include_end_time'] is True and c['derivation'] == 'UTC_CALENDAR_DATE_CURSOR', 'QUERY_POLICY')
    need(c['exception'] in ERRORS, 'EXCEPTION')
    returned = c['returned']; need(returned is None or type(returned) is bool, 'RETURNED')
    phase, guard, exception = 'ADVANCE', 'NONE', returned is None
    counts = [1, int(returned is not None), 0, 0, 0]
    if returned is False:
        phase = 'RETURNED_FALSE'
    if returned is True:
        phase = 'BEGIN_READ'; counts[2] = 1; exception = True
        if c['begin'] is not None:
            begin = time_fact(c['begin']); phase = 'END_READ'; counts[3] = 1
            if c['end'] is not None:
                end = time_fact(c['end']); phase = 'BOUNDS'; exception = False
                if begin >= end:
                    guard = 'BOUND_ORDER'
                elif c['begin']['kind'] != 'Utc' or c['end']['kind'] != 'Utc':
                    guard = 'BOUND_KIND'
                else:
                    phase = 'TRADING_DAY_READ'; counts[4] = 1; exception = True
                    if c['trading_day'] is not None:
                        time_fact(c['trading_day']); phase = 'COMPLETE'; exception = False
    if not counts[2]: need(c['begin'] is None, 'NO_BEGIN')
    if not counts[3]: need(c['end'] is None, 'NO_END')
    if not counts[4]: need(c['trading_day'] is None, 'NO_DAY')
    need(c['phase'] == phase and c['guard'] == guard and (c['exception'] != 'NONE') == exception, 'CALL_STATE')
    for k, n in zip(('getnextsession_attempts', 'getnextsession_completed', 'begin_read_attempts', 'end_read_attempts', 'trading_day_read_attempts'), counts):
        integer(c[k], n, n)
    return 'NATIVE_EXCEPTION' if exception else 'BOUND_REJECTED' if guard != 'NONE' else None


def session_tuple(c):
    return tuple(v for key in ('begin', 'end', 'trading_day') for v in (c[key]['ticks'], c[key]['kind']))


def unique_sessions(calls):
    result = []
    for c in calls:
        if c['phase'] != 'COMPLETE': continue
        item = session_tuple(c)
        if result and item == result[-1]: continue
        if result:
            need(item[2] > result[-1][2] and item[0] >= result[-1][2], 'NATIVE_BACKWARD_OR_OVERLAP')
        result.append(item)
    return result


def cursor_contract(value, initial, through, hours, request_fact):
    keys(value, 'analysis_location traversal_complete schedule paths')
    need(value['analysis_location'] == 'INDEPENDENT_OFFLINE_VERIFIER', 'ANALYSIS_LOCATION')
    schedule = value['schedule']; n = (through - initial) // DAY + 1
    need(11 <= n <= 25 and type(schedule) is list and len(schedule) == n, 'SCHEDULE_COUNT')
    for i, q in enumerate(schedule): need(time_fact(q, 'Utc') == initial + i * DAY, 'SCHEDULE')
    paths = value['paths']; need(type(paths) is list and len(paths) == 2, 'PATHS')
    constructor_ordinal = 0; complete = True; summaries = {}; dedup = {}; false_success = []
    for index, p in enumerate(paths):
        keys(p, 'path outcome constructors calls'); name = ('REUSED', 'FRESH')[index]
        need(p['path'] == name, 'PATH_ORDER')
        constructors, calls = p['constructors'], p['calls']
        need(type(constructors) is list and type(calls) is list and len(calls) <= n, 'PATH_COUNTS')
        need(1 <= len(constructors) <= (1 if index == 0 else n), 'CONSTRUCTOR_COUNT')
        for j, c in enumerate(constructors):
            keys(c, 'ordinal identity exception source bars_identity completed'); constructor_ordinal += 1
            integer(c['ordinal'], constructor_ordinal, constructor_ordinal)
            need(c['identity'] == 'ITERATOR_' + str(constructor_ordinal) and c['source'] == 'RETURNED_REPOSITORY_BARS'
                 and c['bars_identity'] == 'RETURNED_BARS_1' and c['exception'] in ERRORS, 'CONSTRUCTOR_IDENTITY')
            need(boolean(c['completed']) == (c['exception'] == 'NONE'), 'CONSTRUCTOR_STATE')
            if not c['completed']: need(j == len(constructors) - 1, 'CONSTRUCTOR_AFTER_FAILURE')
        failed_constructor = not constructors[-1]['completed']
        need(not failed_constructor or (not calls if index == 0 else len(calls) == len(constructors) - 1), 'FAILED_CONSTRUCTOR_CALL')
        if index == 1 and not failed_constructor: need(len(calls) == len(constructors), 'FRESH_ACCOUNTING')
        stop = None
        for i, call in enumerate(calls):
            need(stop is None, 'CALL_AFTER_STOP')
            c = constructors[0 if index == 0 else i]; need(c['completed'], 'UNCONSTRUCTED_CALL')
            stop = call_contract(call, name, i, c, initial + i * DAY)
        need(not (failed_constructor and stop is not None), 'CONSTRUCTOR_AFTER_CALL_FAILURE')
        outcome = 'CONSTRUCTOR_EXCEPTION' if failed_constructor else stop if stop else 'COMPLETE'
        need(p['outcome'] == outcome, 'PATH_OUTCOME')
        if outcome == 'COMPLETE': need(len(calls) == n, 'MISSING_OBSERVATIONS')
        else: complete = False
        items = unique_sessions(calls); dedup[name] = [t for t in items if t[2] >= initial and t[0] < through]
        for call in calls:
            if call['returned'] is False:
                later = next((c for c in calls[call['ordinal'] + 1:] if c['phase'] == 'COMPLETE'), None)
                false_success.append(dict(path=name, false_ordinal=call['ordinal'], next_success_ordinal=None if later is None else later['ordinal'], session=None if later is None else session_tuple(later)))
        prefix = name.lower()
        summaries.update({prefix + '_constructor_attempts': len(constructors), prefix + '_constructors_completed': sum(c['completed'] for c in constructors),
                          prefix + '_getnextsession_attempts': len(calls), prefix + '_getnextsession_completed': sum(c['getnextsession_completed'] for c in calls),
                          prefix + '_false_count': sum(c['returned'] is False for c in calls), prefix + '_success_count': sum(c['phase'] == 'COMPLETE' for c in calls),
                          prefix + '_exception_count': sum(c['exception'] != 'NONE' for c in calls) + int(failed_constructor),
                          'deduplicated_' + prefix + '_session_count': len(dedup[name])})
    need(boolean(value['traversal_complete']) == complete, 'TRAVERSAL_COMPLETE')
    comparisons = []
    for i in range(n):
        a, b = [p['calls'][i] if i < len(p['calls']) else None for p in paths]
        if a is None or b is None: category = 'NOT_OBSERVED'
        elif a['exception'] != 'NONE' or b['exception'] != 'NONE':
            fields = ('phase', 'exception', 'returned', 'begin', 'end', 'trading_day', 'guard')
            category = 'BOTH_EXCEPTION' if all(a[k] == b[k] for k in fields) else 'EXCEPTION_DIFFERENCE'
        elif a['guard'] != 'NONE' or b['guard'] != 'NONE': category = 'BOUND_REJECTED'
        elif a['returned'] is False and b['returned'] is False: category = 'BOTH_FALSE'
        elif a['returned'] is False: category = 'REUSED_FALSE_FRESH_TRUE'
        elif b['returned'] is False: category = 'REUSED_TRUE_FRESH_FALSE'
        else: category = 'BOTH_TRUE_SAME' if session_tuple(a) == session_tuple(b) else 'BOTH_TRUE_DIFFERENT'
        comparisons.append(dict(ordinal=i, category=category))
    expected = expected_calendar(hours, initial, through)
    tags = date_classes(hours, schedule)
    configured_start = tick_of(date_value(request_fact['configured_from']))
    configured_end = tick_of(date_value(request_fact['configured_through']) + timedelta(days=1))
    def edges(items):
        return [dict(session=t, region='LOOKBACK' if t[2] < configured_start else 'LOOKAHEAD' if t[0] >= configured_end else 'REQUEST_OVERLAP') for t in items]
    matches = sum(c['category'] in ('BOTH_FALSE', 'BOTH_TRUE_SAME') for c in comparisons)
    summaries.update(schedule_count=n, schedule_first=schedule[0], schedule_last=schedule[-1], total_constructor_attempts=constructor_ordinal,
        total_getnextsession_attempts=sum(len(p['calls']) for p in paths), fresh_reused_match_count=matches, fresh_reused_mismatch_count=n-matches,
        expected_session_count=len(expected), reused_coverage_match=complete and dedup['REUSED'] == expected,
        fresh_coverage_match=complete and dedup['FRESH'] == expected,
        false_followed_by_success_count=sum(x['next_success_ordinal'] is not None for x in false_success),
        date_classes_covered=sorted({tag for row in tags for tag in row['tags']}), source_preserved=True, request_preserved=True, snapshot_preserved=True)
    return dict(summary=summaries, comparisons=comparisons, false_followed_by_success=false_success, date_classes=tags,
        expected_intervals=expected, deduplicated_intervals=dedup, range_edges={p: edges(v) for p, v in dedup.items()}, publication_eligible=complete)


def validate_contract(raw, seal_raw):
    evidence, seal = decode(raw, MAX_BYTES), decode(seal_raw, 4096)
    envelope(evidence, 'arms.r57.historical-utc-calendar-cursor.v1',
             'request bars_before bars_after source_preserved snapshot_preserved request_preserved cursor initial_query calendar_through request_attempts request_constructor_attempts cursor_attempts')
    envelope(seal, 'arms.r57.historical-utc-calendar-cursor.seal.v1', 'evidence_sha256 bytes complete')
    digest(seal['evidence_sha256'])
    need(seal['run_id'] == evidence['run_id'] and seal['complete'] is True, 'SEAL')
    need(integer(seal['bytes'], 1, MAX_BYTES) == len(raw) and seal['evidence_sha256'] == sha256(raw).hexdigest(), 'HASH_BINDING')
    for k in ('request_attempts', 'request_constructor_attempts', 'cursor_attempts'): integer(evidence[k], 1, 1)
    for k in ('source_preserved', 'snapshot_preserved', 'request_preserved'): need(evidence[k] is True, 'PRESERVATION')
    initial, through = request(evidence['request'])
    need(time_fact(evidence['initial_query'], 'Utc') == initial and time_fact(evidence['calendar_through'], 'Utc') == through, 'COVERAGE')
    for k in ('bars_before', 'bars_after'): snapshot(evidence[k], evidence['request']['trading_hours'])
    need(evidence['bars_before'] == evidence['bars_after'], 'SNAPSHOT_CHANGED')
    analysis = cursor_contract(evidence['cursor'], initial, through, evidence['request']['trading_hours'], evidence['request'])
    return dict(status='PASS_R57_HISTORICAL_UTC_CALENDAR_CURSOR_CONTRACT_ONLY', **analysis, **FLAGS)


def bounded_read(path, limit):
    with path.open('rb') as stream:
        value = stream.read(limit + 1)
    need(len(value) <= limit, 'SIZE')
    return value


class IncompleteCaptureError(ValueError):
    """The final pair is missing or either traversal path is incomplete."""


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
            raise IncompleteCaptureError('R57_INCOMPLETE_CAPTURE') from exc
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
    if not result['publication_eligible']:
        raise IncompleteCaptureError('R57_PARTIAL_TRAVERSAL')
    _final_capture_paths(capture)
    return dict(result, publication_complete=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--capture', required=True, type=Path, help='Directory containing exactly the published final pair')
    args = parser.parse_args()
    try:
        result = verify_completed_capture(args.capture)
    except IncompleteCaptureError:
        parser.exit(1, 'INCOMPLETE_R57_HISTORICAL_UTC_CALENDAR_CURSOR_CAPTURE\n')
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError):
        parser.exit(1, 'FAIL_R57_HISTORICAL_UTC_CALENDAR_CURSOR_CONTRACT\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
