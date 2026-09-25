"""Behavioral R5.7 tests with synthetic SDK doubles. Never native evidence."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from tools import verify_historical_utc_calendar_cursor_v1 as v

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'integrations/ninjatrader/HistoricalUtcCalendarCursorDiagnosticV1.cs'
HOST = ROOT / 'integrations/ninjatrader/ArmsHistoricalUtcCalendarCursorProbeV1.cs'
HARNESS = ROOT / 'backend/tests/fixtures/historical_utc_calendar_cursor_harness_sprint16ar57.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
EVIDENCE, SEAL = v.EVIDENCE_NAME, v.SEAL_NAME


def checked(command):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    target = tmp_path_factory.mktemp('r57-harness') / 'harness.exe'
    checked([CSC, '/nologo', '/langversion:5', '/define:R57_OFFLINE_TESTS', '/target:exe', '/out:' + str(target),
             '/r:System.Core.dll', '/r:System.Web.Extensions.dll', '/r:System.ComponentModel.DataAnnotations.dll', CORE, HOST, HARNESS])
    return target


def run(binary, path, mode, verify=True):
    path.mkdir(exist_ok=True)
    result = checked([binary, mode, path])
    assert 'PRIVATE_PROVIDER_SENTINEL' not in result.stdout
    counts = json.loads(result.stdout)
    assert counts['classification'] == 'SYNTHETIC_OFFLINE_R57'
    assert counts['requests'] <= 1 and counts['request_constructors'] <= 1 and counts['disposes'] <= 1
    assert counts['constructors'] <= 26 and counts['calls'] <= 50
    evidence = json.loads((path / EVIDENCE).read_bytes()) if (path / EVIDENCE).exists() else None
    report = v.verify_completed_capture(path) if verify and (path / SEAL).exists() else None
    if report:
        assert report['publication_complete'] is True
        assert report['status'] == 'PASS_R57_HISTORICAL_UTC_CALENDAR_CURSOR_CONTRACT_ONLY'
        assert all(report[k] is False for k, x in v.FLAGS.items() if x is False)
        assert report['summary']['total_getnextsession_attempts'] == counts['calls']
        assert report['summary']['total_constructor_attempts'] == counts['constructors']
        calls = [c for p in evidence['cursor']['paths'] for c in p['calls']]
        assert [c['query']['ticks'] for c in calls] == counts['queries']
        assert [c['trading_day'] for c in calls if c['trading_day']] == counts['day_values']
        for key, counter in [('begin_read_attempts', 'begins'), ('end_read_attempts', 'ends'), ('trading_day_read_attempts', 'day_reads')]:
            assert sum(c[key] for c in calls) == counts[counter]
        assert evidence['bars_before'] == evidence['bars_after']
        assert 'PRIVATE_PROVIDER_SENTINEL' not in json.dumps(evidence)
        assert str(path) not in json.dumps(evidence)
    return counts, evidence, report


@pytest.fixture(scope='module')
def sample(binary, tmp_path_factory):
    folder = tmp_path_factory.mktemp('r57-sample')
    _, evidence, report = run(binary, folder, 'success')
    return evidence, json.loads((folder / SEAL).read_bytes()), report


def reseal(evidence, seal):
    raw = json.dumps(evidence, separators=(',', ':')).encode()
    seal = deepcopy(seal); seal.update(bytes=len(raw), evidence_sha256=sha256(raw).hexdigest())
    return raw, json.dumps(seal).encode()


@pytest.mark.parametrize('mode', ['success', 'inline', 'async', 'clone', 'reentrant', 'other_dates', 'min_range', 'max_range', 'year_start', 'year_end'])
def test_exact_schedule_request_identity_one_shot(binary, tmp_path, mode):
    counts, evidence, report = run(binary, tmp_path, mode)
    assert report
    schedule = evidence['cursor']['schedule']; n = len(schedule)
    assert 11 <= n <= 25
    assert n == (25 if mode == 'max_range' else 11 if mode in ('min_range', 'year_start', 'year_end') else n)
    initial, through = v.request(evidence['request'])
    assert [q['ticks'] for q in schedule] == list(range(initial, through + v.DAY, v.DAY))
    assert all(q['kind'] == 'Utc' for q in schedule)
    assert counts['constructors'] == n + 1 and counts['calls'] == 2*n
    assert counts['requests'] == counts['request_constructors'] == counts['disposes'] == 1
    a, b = evidence['cursor']['paths']
    assert len(a['constructors']) == 1 and len(b['constructors']) == n
    assert len({c['iterator_identity'] for c in a['calls']}) == 1
    assert len({c['iterator_identity'] for c in b['calls']}) == n
    for path in (a, b):
        for i, c in enumerate(path['calls']):
            assert c['ordinal'] == i and c['query'] == schedule[i]
            assert c['query'] == c['source_before'] == c['source_after']
            assert c['source_preserved'] is True and c['include_end_time'] is True
    assert report['summary']['reused_coverage_match'] is True
    assert report['summary']['fresh_coverage_match'] is True


@pytest.mark.parametrize('mode', ['query_Unspecified', 'query_Local', 'overflow_low', 'overflow_high', 'over_bound'])
def test_predeclared_schedule_rejects_before_native_calls(binary, tmp_path, mode):
    counts, _, report = run(binary, tmp_path, mode)
    assert counts['direct']['exception'] == 'ArgumentException'
    assert counts['constructors'] == counts['calls'] == counts['requests'] == 0
    assert report is None


@pytest.mark.parametrize('mode,category', [('success', 'BOTH_TRUE_SAME'), ('false', 'BOTH_FALSE'),
    ('reused_false', 'REUSED_FALSE_FRESH_TRUE'), ('fresh_false', 'REUSED_TRUE_FRESH_FALSE'), ('different', 'BOTH_TRUE_DIFFERENT')])
def test_comparison_categories_and_false_getter_suppression(binary, tmp_path, mode, category):
    _, evidence, report = run(binary, tmp_path, mode)
    assert category in {c['category'] for c in report['comparisons']}
    for p in evidence['cursor']['paths']:
        for c in p['calls']:
            if c['returned'] is False:
                assert c['begin'] is c['end'] is c['trading_day'] is None
                assert c['begin_read_attempts'] == c['end_read_attempts'] == c['trading_day_read_attempts'] == 0
    if mode == 'success':
        assert report['summary']['false_followed_by_success_count'] > 0
        for row in report['false_followed_by_success']:
            if row['next_success_ordinal'] is not None:
                assert row['next_success_ordinal'] > row['false_ordinal'] and row['session']


def test_exact_duplicates_are_retained_raw_and_deduplicated(binary, tmp_path):
    _, evidence, report = run(binary, tmp_path, 'duplicate')
    assert report['summary']['reused_success_count'] > report['summary']['deduplicated_reused_session_count']
    assert report['summary']['reused_coverage_match'] is True
    assert len(evidence['cursor']['paths'][0]['calls']) == len(evidence['cursor']['schedule'])


@pytest.mark.parametrize('mode', ['contradictory', 'backward', 'overlap'])
def test_contradictory_and_out_of_order_observations_fail_closed(binary, tmp_path, mode):
    _, _, _ = run(binary, tmp_path, mode, verify=False)
    with pytest.raises(ValueError, match='BACKWARD_OR_OVERLAP'):
        v.verify_completed_capture(tmp_path)


@pytest.mark.parametrize('mode', ['missing', 'extra', 'bounds_difference', 'false', 'day_local', 'day_utc'])
def test_integrity_pass_does_not_require_coverage_success(binary, tmp_path, mode):
    _, _, report = run(binary, tmp_path, mode)
    assert report['summary']['reused_coverage_match'] is False
    assert report['summary']['fresh_coverage_match'] is False
    assert report['runtime_admission'] is False


@pytest.mark.parametrize('mode,tag', [('success', 'ORDINARY'), ('success', 'FRIDAY'), ('success', 'SATURDAY'),
    ('success', 'SUNDAY'), ('holiday', 'FULL_HOLIDAY'), ('early_close', 'PARTIAL_HOLIDAY_OR_SPECIAL'),
    ('spring_dst', 'DST_TRANSITION_WINDOW'), ('fall_dst', 'DST_TRANSITION_WINDOW'),
    ('success', 'RANGE_START_EDGE'), ('success', 'RANGE_END_EDGE')])
def test_captured_rules_drive_calendar_and_date_classes(binary, tmp_path, mode, tag):
    _, evidence, report = run(binary, tmp_path, mode)
    assert tag in report['summary']['date_classes_covered']
    assert report['summary']['reused_coverage_match'] is True
    hours = evidence['request']['trading_hours']
    rules = json.loads(hours['calendar_rules_json'])
    assert rules['sessions'] and rules['holidays'] and rules['partials']
    assert json.loads(hours['timezone_rules_json'])['adjustments']
    assert {x['region'] for x in report['range_edges']['REUSED']} >= {'LOOKBACK', 'REQUEST_OVERLAP', 'LOOKAHEAD'} if mode == 'success' else True


@pytest.mark.parametrize('mode', ['constructor_throw', 'fresh_constructor_throw', 'advance_throw', 'begin_throw', 'end_throw', 'day_throw', 'bad_order', 'begin_unspecified', 'end_local'])
def test_partial_path_stops_and_cannot_publish_completion(binary, tmp_path, mode):
    counts, evidence, report = run(binary, tmp_path, mode)
    assert evidence is not None and report is None and not (tmp_path / SEAL).exists()
    assert evidence['cursor']['traversal_complete'] is False
    with pytest.raises(v.IncompleteCaptureError): v.verify_completed_capture(tmp_path)
    # A forged final seal cannot turn a valid partial prefix into a complete capture.
    seal = dict(v.FLAGS, schema='arms.r57.historical-utc-calendar-cursor.seal.v2',
                diagnostic_profile=evidence['diagnostic_profile'], run_id=evidence['run_id'], complete=True)
    raw, seal_raw = reseal(evidence, seal)
    result = v.validate_contract(raw, seal_raw)
    assert result['publication_eligible'] is False
    assert result['summary']['total_getnextsession_attempts'] == counts['calls']
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(seal_raw)
    with pytest.raises(v.IncompleteCaptureError): v.verify_completed_capture(tmp_path)


@pytest.mark.parametrize('mode', ['mutate_price', 'mutate_time', 'mutate_hours', 'replace_hours', 'replace_bars', 'mutate_request',
    'change_properties', 'wrong_returned_hours', 'wrong_callback', 'callback_error', 'bad_count', 'request_throw', 'request_create_throw',
    'inline_then_throw', 'dispose_throw', 'terminate_during_call', 'foreign_file', 'pending'])
def test_preservation_and_context_failures_never_seal(binary, tmp_path, mode):
    _, _, report = run(binary, tmp_path, mode)
    assert report is None and not (tmp_path / SEAL).exists()


@pytest.mark.parametrize('mode', ['disabled', 'disabled_rearm', 'unconfirmed', 'bad_date', 'wrong_zone', 'playback'])
def test_default_disabled_and_prerequisite_guards(binary, tmp_path, mode):
    counts, _, report = run(binary, tmp_path, mode)
    assert counts['requests'] == counts['calls'] == 0 and report is None


@pytest.mark.parametrize('mode', ['concurrent_traversal', 'concurrent_body', 'concurrent_seal'])
def test_concurrent_termination_linearizes_before_seal(binary, tmp_path, mode):
    counts, _, report = run(binary, tmp_path, mode)
    assert counts['intent_observed'] and counts['termination_waited'] and counts['pauses'] == 1
    assert not counts['seal_at_pause'] and report is None
    assert not (tmp_path / SEAL).exists()


def test_existing_output_is_never_overwritten(binary, tmp_path):
    sentinel = tmp_path / EVIDENCE; sentinel.write_bytes(b'preserve')
    output = json.loads(checked([binary, 'success', tmp_path]).stdout)
    assert output['requests'] == 0 and sentinel.read_bytes() == b'preserve'


@pytest.mark.parametrize('fault', ['ticks_bool', 'ticks_float', 'kind', 'clock', 'include', 'ordinal', 'identity', 'constructor',
    'getter_false', 'source', 'extra_call', 'missing_call', 'schedule', 'summary', 'coverage', 'authority', 'sdk', 'sdk_substring',
    'snapshot', 'request', 'hash_only', 'rules_hash', 'zone_hash', 'request_count', 'path_order', 'extra_field',
    'before_float', 'after_float', 'before_bool', 'end_float', 'day_float', 'constructor_bool'])
def test_resealed_contradictions_fail(sample, fault):
    e, seal, _ = deepcopy(sample); c = e['cursor']['paths'][0]['calls'][0]
    if fault == 'ticks_bool': c['query']['ticks'] = True
    elif fault == 'ticks_float': c['query']['ticks'] = float(c['query']['ticks'])
    elif fault == 'kind': c['query']['kind'] = 'Unspecified'
    elif fault == 'clock': c['query']['clock'] = '2026-01-01T00:00:00.0000000'
    elif fault == 'include': c['include_end_time'] = False
    elif fault == 'ordinal': c['ordinal'] = True
    elif fault == 'identity': c['iterator_identity'] = 'ITERATOR_2'
    elif fault == 'constructor': c['constructor_ordinal'] = 2
    elif fault == 'getter_false':
        c = next(x for x in e['cursor']['paths'][0]['calls'] if x['returned'] is False); c['begin_read_attempts'] = 1
    elif fault == 'source': c['source_after']['ticks'] += 1
    elif fault == 'extra_call': e['cursor']['paths'][0]['calls'].append(deepcopy(c))
    elif fault == 'missing_call': e['cursor']['paths'][0]['calls'].pop()
    elif fault == 'schedule': e['cursor']['schedule'].pop()
    elif fault == 'summary': e['summary'] = {'reused_coverage_match': True}
    elif fault == 'coverage': e['cursor']['reused_coverage_match'] = True
    elif fault == 'authority': e['runtime_admission'] = True
    elif fault == 'sdk': e['request']['sdk_version'] = '8.1.8.20'
    elif fault == 'sdk_substring': e['request']['sdk_assembly'] = 'x, Version=8.1.8.20, Hint=8.1.8.2'
    elif fault == 'snapshot': e['bars_after']['snapshot_sha256'] = '0'*64
    elif fault == 'request': e['request']['lookup'] = 'Provider'
    elif fault == 'hash_only': del e['request']['trading_hours']['calendar_rules_json']
    elif fault == 'rules_hash': e['request']['trading_hours']['calendar_rules_sha256'] = '0'*64
    elif fault == 'zone_hash': e['request']['trading_hours']['timezone_rules_sha256'] = '0'*64
    elif fault == 'request_count': e['request_attempts'] = 2
    elif fault == 'path_order': e['cursor']['paths'].reverse()
    elif fault == 'extra_field': c['secret'] = 'unrecognized'
    elif fault == 'before_float': c['source_before']['ticks'] = float(c['source_before']['ticks'])
    elif fault == 'after_float': c['source_after']['ticks'] = float(c['source_after']['ticks'])
    elif fault == 'before_bool': c['source_before']['ticks'] = True
    elif fault == 'end_float': c['end']['ticks'] = float(c['end']['ticks'])
    elif fault == 'day_float': c['trading_day']['ticks'] = float(c['trading_day']['ticks'])
    elif fault == 'constructor_bool': e['cursor']['paths'][0]['constructors'][0]['ordinal'] = True
    with pytest.raises(ValueError): v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('fault', ['unsupported_partial', 'duplicate_holiday', 'missing_zone_rule', 'overlap_rules', 'ambiguous_wall', 'invalid_wall'])
def test_calendar_never_falls_back_to_fixture(sample, fault):
    e, seal, _ = deepcopy(sample); hours = e['request']['trading_hours']
    rules = json.loads(hours['calendar_rules_json']); zone = json.loads(hours['timezone_rules_json'])
    if fault == 'unsupported_partial': rules['partials'][0]['late'] = True
    elif fault == 'duplicate_holiday': rules['holidays'].append(rules['holidays'][0])
    elif fault == 'missing_zone_rule': zone['adjustments'] = []
    elif fault == 'overlap_rules': zone['adjustments'].append(zone['adjustments'][0])
    else:
        evaluator = v.CapturedZone(zone)
        point = datetime(2026, 11, 1, 1, 30) if fault == 'ambiguous_wall' else datetime(2026, 3, 8, 2, 30)
        with pytest.raises(ValueError, match='CALENDAR_WALL_TIME'): evaluator.wall(point)
        return
    for prefix, value in [('calendar', rules), ('timezone', zone)]:
        hours[prefix + '_rules_json'] = json.dumps(value, separators=(',', ':'))
        hours[prefix + '_rules_sha256'] = sha256(hours[prefix + '_rules_json'].encode()).hexdigest()
    e['bars_before']['trading_hours'] = deepcopy(hours); e['bars_after']['trading_hours'] = deepcopy(hours)
    with pytest.raises(ValueError): v.validate_contract(*reseal(e, seal))


def test_changed_captured_calendar_changes_independent_expectation(sample):
    e, seal, original = deepcopy(sample)
    hours = e['request']['trading_hours']; rules = json.loads(hours['calendar_rules_json'])
    rules['sessions'][0]['end_time'] = 1500
    hours['calendar_rules_json'] = json.dumps(rules, separators=(',', ':'))
    hours['calendar_rules_sha256'] = sha256(hours['calendar_rules_json'].encode()).hexdigest()
    for name in ('bars_before', 'bars_after'): e[name]['trading_hours'] = deepcopy(hours)
    report = v.validate_contract(*reseal(e, seal))
    assert report['expected_intervals'] != original['expected_intervals']
    assert report['summary']['reused_coverage_match'] is False
    assert report['summary']['fresh_coverage_match'] is False


def test_expected_clock_values_are_independent_known_calendar_values(sample):
    _, _, report = sample
    first = report['expected_intervals'][0]
    assert first == (v.tick_of(datetime(2026, 9, 13, 22)), 'Utc', v.tick_of(datetime(2026, 9, 14, 21)), 'Utc',
                     v.tick_of(datetime(2026, 9, 14)), 'Unspecified')


@pytest.mark.parametrize('target', ['body', 'seal', 'directory'])
def test_redirected_artifact_rejected(sample, tmp_path, monkeypatch, target):
    import stat
    from types import SimpleNamespace
    e, seal, _ = sample; raw, sealed = reseal(e, seal)
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    original = Path.lstat
    redirected = tmp_path if target == 'directory' else tmp_path / (EVIDENCE if target == 'body' else SEAL)
    def fake(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == redirected:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return info
    monkeypatch.setattr(Path, 'lstat', fake)
    with pytest.raises(ValueError): v.verify_completed_capture(tmp_path)


@pytest.mark.parametrize('fault', ['body_missing', 'seal_missing', 'temp_seal', 'extra', 'directory', 'bytes', 'hash', 'duplicate_json', 'partial'])
def test_final_pair_and_byte_binding(sample, tmp_path, fault):
    e, seal, _ = deepcopy(sample); raw, sealed = reseal(e, seal)
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    if fault == 'body_missing': (tmp_path / EVIDENCE).unlink()
    elif fault == 'seal_missing': (tmp_path / SEAL).unlink()
    elif fault == 'temp_seal': (tmp_path / SEAL).rename(tmp_path / (SEAL + '.tmp'))
    elif fault == 'extra': (tmp_path / 'extra').write_text('extra')
    elif fault == 'directory': (tmp_path / SEAL).unlink(); (tmp_path / SEAL).mkdir()
    elif fault == 'bytes': (tmp_path / EVIDENCE).write_bytes(raw + b' ')
    elif fault == 'hash':
        obj = json.loads(sealed); obj['evidence_sha256'] = '0'*64; (tmp_path / SEAL).write_text(json.dumps(obj))
    elif fault == 'duplicate_json': (tmp_path / EVIDENCE).write_bytes(b'{"x":1,"x":2}')
    elif fault == 'partial':
        e['cursor']['paths'][0]['calls'].pop(); raw, sealed = reseal(e, seal)
        (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    with pytest.raises(ValueError): v.verify_completed_capture(tmp_path)


def test_cli_result_is_diagnostic_only(sample, tmp_path):
    e, seal, _ = sample; raw, sealed = reseal(e, seal)
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    result = checked([sys.executable, '-B', ROOT / 'tools/verify_historical_utc_calendar_cursor_v1.py', '--capture', tmp_path])
    report = json.loads(result.stdout)
    assert report['summary']['reused_coverage_match'] is True and report['execution_authority'] is False
    wrong = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/verify_historical_utc_calendar_cursor_v1.py'), '--seal', str(tmp_path / SEAL)], capture_output=True)
    assert wrong.returncode != 0


def test_installed_sdk_compile_only(tmp_path):
    sdk = Path('C:/Program Files/NinjaTrader 8/bin')
    shim = tmp_path / 'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs = [sdk / 'NinjaTrader.Core.dll', sdk / 'NinjaTrader.Gui.dll', CSC.parent / 'WPF/WindowsBase.dll',
            'System.Core.dll', 'System.Web.Extensions.dll', 'System.ComponentModel.DataAnnotations.dll']
    checked([CSC, '/nologo', '/langversion:5', '/target:library', '/out:' + str(tmp_path / 'R57CompileOnly.dll'),
             *['/r:' + str(p) for p in refs], CORE, HOST, shim])
    assert (tmp_path / 'R57CompileOnly.dll').is_file()


def test_no_production_conversion_or_execution_surface():
    code = '\n'.join(p.read_text() for p in (CORE, HOST))
    code = re.sub(r'//[^\n]*', '', code)
    for token in ('ToUniversalTime', 'TimeZoneInfo.Local', 'ConvertTime', 'SessionIteratorQueryDomainAdapterV1',
                  'ArmsHistoricalBootstrapV1', 'IsInSession', 'IsNewSession', 'CalculateTradingDay', 'GetTradingDay',
                  'File.Delete', 'LookupPolicies.Provider', 'AddDataSeries', '.Update +=', 'AddTicks', 'AddSeconds'):
        assert token not in code
    assert not re.search(r'\b(Account|Order|Execution|Strategy|AtmStrategy|Timer|Process|Activator|DllImport)\b', re.sub(r'\[Display\([^\n]*\)\]', '', code))
    assert code.count('new SessionIterator(returnedBars)') == code.count('iterator.GetNextSession(query, true)') == 1
    assert code.count('new BarsRequest(') == code.count('request.Request(Completed)') == 1
    for path in (CORE, HOST, ROOT / 'tools/verify_historical_utc_calendar_cursor_v1.py'):
        assert not re.search(r'(import .*sprint16|from backend|using Arms.AI.Diagnostics.R5[3456])', path.read_text())


def test_existing_tracked_sources_unchanged():
    allowed = {'tools/verify_historical_utc_calendar_cursor_v1.py',
               'integrations/ninjatrader/ArmsHistoricalUtcCalendarCursorProbeV1.cs',
               'backend/tests/fixtures/historical_utc_calendar_cursor_harness_sprint16ar57.cs',
               'backend/tests/test_historical_utc_calendar_cursor_probe_sprint16ar57.py',
               'docs/architecture/historical_utc_calendar_cursor_probe_sprint16ar57.md'}
    assert set(checked(['git', 'diff', '--name-only']).stdout.splitlines()) <= allowed
    assert checked(['git', 'diff', '--cached', '--name-only']).stdout.strip() == ''


def special(date='2024-12-25', early=False):
    d = datetime.strptime(date, '%Y-%m-%d'); weekday = (d.weekday() + 1) % 7
    return dict(date=dict(clock=date + 'T00:00:00.0000000', ticks=v.tick_of(d), kind='Unspecified'),
                early=early, late=not early,
                constraint=dict(begin_day=weekday, begin_time=1700, end_day=weekday if early else 0,
                                end_time=1200 if early else 0, trading_day=weekday), sessions=[])


def install_rules(e, rules, prefix='calendar'):
    """Mutate only synthetic in-memory copies; bind each captured snapshot."""
    hours = e['request']['trading_hours']
    hours[prefix + '_rules_json'] = json.dumps(rules, separators=(',', ':'))
    hours[prefix + '_rules_sha256'] = sha256(hours[prefix + '_rules_json'].encode()).hexdigest()
    for name in ('bars_before', 'bars_after'): e[name]['trading_hours'] = deepcopy(hours)


def with_special(sample, rule):
    e, seal, original = deepcopy(sample)
    rules = json.loads(e['request']['trading_hours']['calendar_rules_json'])
    rules['partials'].append(rule); rules['partials'].sort(key=lambda p: p['date']['ticks'])
    install_rules(e, rules)
    return e, seal, original


def test_irrelevant_late_open_retained_without_recurring_constraint_invariant(sample):
    e, seal, original = with_special(sample, special())
    untouched = deepcopy(e)
    hours = e['request']['trading_hours']
    sessions, _, partials, zone = v.calendar(hours)
    p = partials[v.tick_of(datetime(2024, 12, 25))]
    assert p == special() and p['constraint']['end_day'] != p['constraint']['trading_day']
    assert v.special_influence(p, sessions, zone) == (
        v.tick_of(datetime(2024, 12, 23, 22)), v.tick_of(datetime(2024, 12, 26, 22)))
    result = v.validate_contract(*reseal(e, seal))
    assert result['expected_intervals'] == original['expected_intervals']
    assert result['summary'] == original['summary']
    assert e == untouched


@pytest.mark.parametrize('date', ['2026-09-16', '2026-09-30'])
def test_relevant_late_open_including_adjacent_crossing_fails_before_coverage(sample, monkeypatch, date):
    e, seal, _ = with_special(sample, special(date))
    hours = e['request']['trading_hours']; initial, through = v.request(e['request'])
    sessions, _, partials, zone = v.calendar(hours)
    p = partials[v.tick_of(datetime.strptime(date, '%Y-%m-%d'))]
    bounds = v.special_influence(p, sessions, zone)
    assert bounds is not None and v.special_relevant(bounds, initial, through)
    if date.endswith('30'):
        assert p['date']['ticks'] >= through and bounds[0] < through
    monkeypatch.setattr(v, 'date_classes', lambda *_: pytest.fail('coverage must not complete'))
    with pytest.raises(ValueError, match='UNSUPPORTED_SPECIAL_SESSION'):
        v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('fault', ['both_flags', 'neither_flag', 'replacement', 'null_constraint',
                                 'mapping', 'split', 'long_group', 'offset_gap'])
def test_unknown_influence_fails_closed_even_far_away(sample, fault):
    p = special()
    if fault == 'both_flags': p['early'] = True
    elif fault == 'neither_flag': p['late'] = False
    elif fault == 'replacement': p['sessions'] = [deepcopy(p['constraint'])]
    elif fault == 'null_constraint': p['constraint'] = None
    elif fault == 'mapping': p['constraint']['begin_day'] = 2
    e, seal, _ = with_special(sample, p)
    rules = json.loads(e['request']['trading_hours']['calendar_rules_json'])
    if fault == 'split':
        s = deepcopy(rules['sessions'][0]); s['begin_time'] = 1800; rules['sessions'].append(s)
        install_rules(e, rules)
    elif fault == 'long_group':
        rules['sessions'][0]['begin_day'] = (rules['sessions'][0]['trading_day'] - 2) % 7
        install_rules(e, rules)
    elif fault == 'offset_gap':
        zone = json.loads(e['request']['trading_hours']['timezone_rules_json'])
        zone['adjustments'][0]['start'] = '2025-01-01'; install_rules(e, zone, 'timezone')
    with pytest.raises(ValueError, match='UNSUPPORTED_SPECIAL_SESSION'):
        v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('edge,expected', [('touch_C0', True), ('before_C0', False),
                                         ('touch_C1', False), ('before_C1', True)])
def test_proven_envelope_tick_edges(sample, edge, expected):
    e, _, _ = with_special(sample, special())
    sessions, _, partials, zone = v.calendar(e['request']['trading_hours'])
    p = partials[v.tick_of(datetime(2024, 12, 25))]
    low, high = v.special_influence(p, sessions, zone)
    initial, through = {'touch_C0': (high, high + v.DAY), 'before_C0': (high + 1, high + v.DAY),
                        'touch_C1': (low - v.DAY, low), 'before_C1': (low - v.DAY, low + 1)}[edge]
    assert v.special_relevant((low, high), initial, through) is expected
    if expected:
        with pytest.raises(ValueError, match='UNSUPPORTED_SPECIAL_SESSION'):
            v.scoped_partials(sessions, {p['date']['ticks']: p}, zone, initial, through)
    else:
        assert v.scoped_partials(sessions, {p['date']['ticks']: p}, zone, initial, through) == {}


@pytest.mark.parametrize('fault', ['bool', 'float', 'day', 'time', 'field', 'kind', 'order', 'duplicate', 'sessions_type', 'member'])
def test_malformed_irrelevant_rule_still_rejected_globally(sample, fault):
    p = special()
    if fault == 'bool': p['constraint']['end_day'] = False
    elif fault == 'float': p['constraint']['begin_time'] = 1700.0
    elif fault == 'day': p['constraint']['end_day'] = 7
    elif fault == 'time': p['constraint']['end_time'] = 1260
    elif fault == 'field': p['constraint']['extra'] = 0
    elif fault == 'kind': p['date']['kind'] = 'Utc'
    elif fault == 'sessions_type': p['sessions'] = {}
    elif fault == 'member': p['sessions'] = [{'begin_day': 3}]
    e, seal, _ = with_special(sample, p)
    if fault in ('order', 'duplicate'):
        rules = json.loads(e['request']['trading_hours']['calendar_rules_json'])
        if fault == 'order': rules['partials'].reverse()
        else: rules['partials'].insert(0, deepcopy(p))
        install_rules(e, rules)
    with pytest.raises(ValueError): v.validate_contract(*reseal(e, seal))


def test_recurring_end_day_semantics_not_relaxed(sample):
    e, seal, _ = with_special(sample, special())
    rules = json.loads(e['request']['trading_hours']['calendar_rules_json'])
    rules['sessions'][0]['end_day'] = (rules['sessions'][0]['trading_day'] + 1) % 7
    install_rules(e, rules)
    with pytest.raises(ValueError, match='UNSUPPORTED_SESSION_SHAPE'): v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('kind', ['early', 'holiday'])
def test_in_scope_supported_rules_change_exact_independent_expectation(sample, kind):
    e, seal, original = deepcopy(sample); day = v.tick_of(datetime(2026, 9, 16))
    rules = json.loads(e['request']['trading_hours']['calendar_rules_json'])
    if kind == 'early':
        rules['partials'].append(special('2026-09-16', early=True))
        rules['partials'].sort(key=lambda p: p['date']['ticks'])
    else:
        rules['holidays'].append(special('2026-09-16')['date']); rules['holidays'].sort(key=lambda p: p['ticks'])
    install_rules(e, rules); result = v.validate_contract(*reseal(e, seal))
    expected = list(original['expected_intervals'])
    i = next(i for i, t in enumerate(expected) if t[4] == day)
    if kind == 'early':
        t = expected[i]; expected[i] = (*t[:2], v.tick_of(datetime(2026, 9, 16, 17)), *t[3:])
    else: expected.pop(i)
    assert result['expected_intervals'] == expected
    assert result['summary']['reused_coverage_match'] is result['summary']['fresh_coverage_match'] is False


@pytest.mark.parametrize('edit', ['remove', 'change'])
@pytest.mark.parametrize('binding', ['stale_seal', 'stale_rule_hash', 'stale_snapshot', 'all_valid'])
def test_irrelevance_does_not_remove_evidence_binding(sample, edit, binding):
    e, seal, original = with_special(sample, special()); _, sealed = reseal(e, seal)
    old_hours = deepcopy(e['request']['trading_hours'])
    rules = json.loads(old_hours['calendar_rules_json'])
    if edit == 'remove': rules['partials'].pop(0)
    else: rules['partials'][0]['constraint']['begin_time'] = 1800
    install_rules(e, rules)
    if binding == 'stale_rule_hash': e['request']['trading_hours']['calendar_rules_sha256'] = old_hours['calendar_rules_sha256']
    elif binding == 'stale_snapshot': e['bars_after']['trading_hours'] = old_hours
    raw, new_sealed = reseal(e, seal)
    if binding == 'all_valid':
        assert v.validate_contract(raw, new_sealed)['summary'] == original['summary']
    else:
        with pytest.raises(ValueError): v.validate_contract(raw, sealed if binding == 'stale_seal' else new_sealed)


def test_native_observations_cannot_change_special_relevance(sample):
    e, seal, _ = with_special(sample, special()); hours = e['request']['trading_hours']
    before = v.validate_contract(*reseal(e, seal))
    for path in e['cursor']['paths']:
        for c in path['calls']:
            c.update(returned=False, phase='RETURNED_FALSE', begin=None, end=None, trading_day=None,
                     begin_read_attempts=0, end_read_attempts=0, trading_day_read_attempts=0)
    after = v.validate_contract(*reseal(e, seal))
    assert after['expected_intervals'] == before['expected_intervals']
    assert after['summary']['reused_coverage_match'] is after['summary']['fresh_coverage_match'] is False
    assert e['request']['trading_hours'] == hours
    rules = json.loads(hours['calendar_rules_json']); rules['partials'][0] = special('2026-09-16')
    rules['partials'].sort(key=lambda p: p['date']['ticks']); install_rules(e, rules)
    with pytest.raises(ValueError, match='UNSUPPORTED_SPECIAL_SESSION'): v.validate_contract(*reseal(e, seal))


def test_original_native_artifact_hashes_when_available():
    capture = Path('D:/ARMS_AI_R57_CAPTURE/20260924_233411')
    if not capture.exists():
        pytest.skip('Operator capture not available; never substitute a fixture')
    for name, expected in [(EVIDENCE, '1f455401f1fc3705898fff27e56c21fdbf9365751451656ebf0a15edaada6129'),
                           (SEAL, '6a59311bb91f0a9b57f8c9644429eb05c3e44e658c09de68869f72bca34c7713')]:
        assert sha256((capture / name).read_bytes()).hexdigest() == expected


@pytest.fixture(scope='module')
def mar_sample(binary, tmp_path_factory):
    folder = tmp_path_factory.mktemp('r57-mar-sample')
    _, evidence, report = run(binary, folder, 'mar_success')
    return evidence, json.loads((folder / SEAL).read_bytes()), report


@pytest.mark.parametrize('prefix,profile,instrument,expiry', [
    ('', 'NQ_DEC26', 'NQ DEC26', '2026-12-01'),
    ('mar_', 'NQ_MAR26_DST', 'NQ MAR26', '2026-03-01')])
def test_closed_profile_host_request_and_publication(binary, tmp_path, prefix, profile, instrument, expiry):
    counts, e, report = run(binary, tmp_path, prefix + 'success')
    assert counts['lookup_names'] == [instrument]
    assert counts['request_constructors'] == counts['requests'] == counts['disposes'] == 1
    assert e['schema'] == 'arms.r57.historical-utc-calendar-cursor.v2'
    seal = json.loads((tmp_path / SEAL).read_bytes())
    assert seal['schema'] == 'arms.r57.historical-utc-calendar-cursor.seal.v2'
    assert e['diagnostic_profile'] == seal['diagnostic_profile'] == report['diagnostic_profile'] == profile
    request = e['request']
    assert request['instrument'] == instrument and request['expiry'] == expiry and request['master'] == 'NQ'
    assert {k: request[k] for k in ('period', 'period_value', 'market_data', 'lookup', 'merge', 'reset', 'dividend_adjusted', 'split_adjusted')} == dict(
        period='Minute', period_value=1, market_data='Last', lookup='Repository', merge='DoNotMerge',
        reset=True, dividend_adjusted=False, split_adjusted=False)
    for name in ('bars_before', 'bars_after'):
        assert e[name]['instrument'] == instrument and e[name]['expiry'] == expiry
        assert e[name]['trading_hours'] == request['trading_hours']
    assert request['trading_hours']['version'] == 5119
    for path in e['cursor']['paths']:
        assert all(c['source'] == 'RETURNED_REPOSITORY_BARS' and c['bars_identity'] == 'RETURNED_BARS_1' for c in path['constructors'])
    assert report['summary']['reused_coverage_match'] is report['summary']['fresh_coverage_match'] is True
    assert report['summary']['fresh_reused_mismatch_count'] == 0
    assert report['summary']['false_followed_by_success_count'] > 0


@pytest.mark.parametrize('mode', ['disabled', 'profile_unknown', 'lookup_name', 'lookup_expiry', 'lookup_master', 'lookup_tick', 'lookup_point'])
@pytest.mark.parametrize('prefix', ['', 'mar_'])
def test_profile_preconstruction_rejections(binary, tmp_path, prefix, mode):
    counts, e, report = run(binary, tmp_path, prefix + mode)
    assert counts['request_constructors'] == counts['requests'] == counts['constructors'] == counts['calls'] == 0
    assert e is report is None and not (tmp_path / SEAL).exists()
    if mode in ('disabled', 'profile_unknown'): assert counts['lookup_names'] == []


@pytest.mark.parametrize('mode', ['wrong_from', 'wrong_through'])
def test_mar_date_rejected_before_lookup_or_request(binary, tmp_path, mode):
    counts, _, report = run(binary, tmp_path, 'mar_' + mode)
    assert counts['lookup_names'] == []
    assert counts['request_constructors'] == counts['requests'] == counts['calls'] == 0
    assert report is None


@pytest.mark.parametrize('mode', ['request_name', 'request_expiry', 'request_master', 'calendar_name', 'calendar_version',
                                 'calendar_timezone', 'returned_name', 'returned_expiry', 'returned_master',
                                 'wrong_returned_hours', 'returned_calendar_rules'])
@pytest.mark.parametrize('prefix', ['', 'mar_'])
def test_profile_identity_and_calendar_guards_before_traversal(binary, tmp_path, prefix, mode):
    counts, _, report = run(binary, tmp_path, prefix + mode)
    assert counts['request_constructors'] == 1
    assert counts['requests'] == (1 if mode.startswith('returned_') or mode == 'wrong_returned_hours' else 0)
    assert counts['constructors'] == counts['calls'] == 0
    assert report is None and not (tmp_path / SEAL).exists()


@pytest.mark.parametrize('mode,calls', [('profile_change_before_callback', 0), ('profile_change_during', 1),
                                      ('profile_change_before_seal', None)])
@pytest.mark.parametrize('prefix', ['', 'mar_'])
def test_profile_is_frozen_changes_fail_without_retarget_or_seal(binary, tmp_path, prefix, mode, calls):
    counts, e, report = run(binary, tmp_path, prefix + mode)
    instrument = 'NQ MAR26' if prefix else 'NQ DEC26'
    assert counts['lookup_names'] == [instrument]
    assert counts['request_constructors'] == counts['requests'] == counts['disposes'] == 1
    expected_calls = (22 if prefix else 32) if calls is None else calls
    assert counts['calls'] == expected_calls
    assert report is None and not (tmp_path / SEAL).exists()
    if e is not None:
        assert e['request']['instrument'] == instrument
        assert e['diagnostic_profile'] == ('NQ_MAR26_DST' if prefix else 'NQ_DEC26')


def test_mar_schedule_and_independent_dst_expectation(mar_sample):
    e, _, report = mar_sample
    assert e['request']['configured_from'] == e['request']['configured_through'] == '2026-03-06'
    initial, through = v.request(e['request'], 'NQ_MAR26_DST')
    assert initial == v.tick_of(datetime(2026, 3, 4)) and through == v.tick_of(datetime(2026, 3, 14))
    assert len(e['cursor']['schedule']) == 11
    assert [q['ticks'] for q in e['cursor']['schedule']] == list(range(initial, through + v.DAY, v.DAY))
    assert report['summary']['total_constructor_attempts'] == 12
    assert report['summary']['total_getnextsession_attempts'] == 22
    expected = {t[4]: t for t in report['expected_intervals']}
    for date, begin, end in [(datetime(2026, 3, 6), datetime(2026, 3, 5, 23), datetime(2026, 3, 6, 22)),
                             (datetime(2026, 3, 9), datetime(2026, 3, 8, 22), datetime(2026, 3, 9, 21))]:
        assert expected[v.tick_of(date)] == (v.tick_of(begin), 'Utc', v.tick_of(end), 'Utc', v.tick_of(date), 'Unspecified')
    assert len(expected) == 8
    tags = {r['date']: r['tags'] for r in report['date_classes']}
    assert all('DST_TRANSITION_WINDOW' in tags[d] for d in ('2026-03-07', '2026-03-08', '2026-03-09'))
    assert 'SATURDAY' in tags['2026-03-07'] and 'SUNDAY' in tags['2026-03-08']


@pytest.mark.parametrize('which', ['dec', 'mar'])
@pytest.mark.parametrize('fault', ['missing_profile', 'unknown_profile', 'null_profile', 'bool_profile', 'number_profile',
    'object_profile', 'missing_seal_profile', 'seal_profile', 'body_profile', 'v1_seal', 'unknown_schema',
    'request_instrument', 'request_expiry', 'request_master', 'before_instrument', 'after_expiry',
    'period', 'period_bool', 'market_data', 'lookup', 'merge', 'reset', 'dividend', 'split',
    'calendar_version', 'calendar_version_bool', 'calendar_name', 'calendar_timezone', 'authority', 'ticks_bool',
    'snapshot_calendar', 'extra_request_profile', 'stale_seal'])
def test_v2_resealed_profile_contradictions(sample, mar_sample, which, fault):
    e, seal, _ = deepcopy(mar_sample if which == 'mar' else sample)
    req = e['request']; other = 'NQ_DEC26' if which == 'mar' else 'NQ_MAR26_DST'
    if fault == 'missing_profile': del e['diagnostic_profile']
    elif fault == 'unknown_profile': e['diagnostic_profile'] = 'NQ_OTHER'
    elif fault == 'null_profile': e['diagnostic_profile'] = None
    elif fault == 'bool_profile': e['diagnostic_profile'] = True
    elif fault == 'number_profile': e['diagnostic_profile'] = 0
    elif fault == 'object_profile': e['diagnostic_profile'] = {'instrument': req['instrument']}
    elif fault == 'missing_seal_profile': del seal['diagnostic_profile']
    elif fault == 'seal_profile': seal['diagnostic_profile'] = other
    elif fault == 'body_profile': e['diagnostic_profile'] = seal['diagnostic_profile'] = other
    elif fault == 'v1_seal': seal['schema'] = 'arms.r57.historical-utc-calendar-cursor.seal.v1'
    elif fault == 'unknown_schema': e['schema'] = 'arms.r57.historical-utc-calendar-cursor.v3'
    elif fault == 'request_instrument': req['instrument'] = 'NQ 03-26' if which == 'mar' else 'NQ MAR26'
    elif fault == 'request_expiry': req['expiry'] = '2026-03-02' if which == 'mar' else '2026-03-01'
    elif fault == 'request_master': req['master'] = 'ES'
    elif fault == 'before_instrument': e['bars_before']['instrument'] = 'NQ OTHER'
    elif fault == 'after_expiry': e['bars_after']['expiry'] = '2026-01-01'
    elif fault == 'period': req['period'] = 'Tick'
    elif fault == 'period_bool': req['period_value'] = True
    elif fault == 'market_data': req['market_data'] = 'Bid'
    elif fault == 'lookup': req['lookup'] = 'Provider'
    elif fault == 'merge': req['merge'] = 'MergeBackAdjusted'
    elif fault == 'reset': req['reset'] = False
    elif fault == 'dividend': req['dividend_adjusted'] = True
    elif fault == 'split': req['split_adjusted'] = True
    elif fault.startswith('calendar_'):
        field, value = {'calendar_version': ('version', 5120), 'calendar_version_bool': ('version', True),
                        'calendar_name': ('name', 'OTHER'), 'calendar_timezone': ('timezone', 'UTC')}[fault]
        req['trading_hours'][field] = value
        for k in ('bars_before', 'bars_after'): e[k]['trading_hours'] = deepcopy(req['trading_hours'])
    elif fault == 'authority': e['execution_authority'] = True
    elif fault == 'ticks_bool': e['cursor']['schedule'][0]['ticks'] = True
    elif fault == 'snapshot_calendar': e['bars_after']['trading_hours']['version'] = 5120
    elif fault == 'extra_request_profile': req['diagnostic_profile'] = other
    elif fault == 'stale_seal':
        raw, sealed = reseal(e, seal)
        with pytest.raises(ValueError, match='HASH_BINDING'): v.validate_contract(raw + b' ', sealed)
        return
    with pytest.raises(ValueError): v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('side', ['from', 'through'])
def test_mar_verifier_date_rejection_is_profile_policy(mar_sample, side):
    e, seal, _ = deepcopy(mar_sample)
    e['request']['configured_' + side] = '2026-03-07'
    with pytest.raises(ValueError, match='PROFILE_DATE'): v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('mode', ['false', 'bounds_difference', 'different', 'missing', 'extra', 'duplicate',
                                 'concurrent_traversal', 'concurrent_body', 'concurrent_seal', 'terminate_during_call'])
def test_mar_retains_comparison_and_lifecycle_behavior(binary, tmp_path, mode):
    counts, _, report = run(binary, tmp_path, 'mar_' + mode)
    if mode.startswith('concurrent_') or mode == 'terminate_during_call':
        assert report is None and not (tmp_path / SEAL).exists()
        if mode.startswith('concurrent_'): assert counts['intent_observed'] and counts['termination_waited']
    else:
        assert report['summary']['reused_coverage_match'] is (mode == 'duplicate' or mode == 'different')
        assert report['summary']['fresh_coverage_match'] is (mode == 'duplicate')
        if mode == 'different': assert report['summary']['fresh_reused_mismatch_count'] > 0


def legacy_pair(e, seal):
    e, seal = deepcopy(e), deepcopy(seal)
    e['schema'] = 'arms.r57.historical-utc-calendar-cursor.v1'
    seal['schema'] = 'arms.r57.historical-utc-calendar-cursor.seal.v1'
    del e['diagnostic_profile']; del seal['diagnostic_profile']
    return e, seal


def test_v1_dispatch_preserves_existing_dec_contract(sample, mar_sample):
    e, seal = legacy_pair(*sample[:2])
    original = v.validate_contract(*reseal(e, seal))
    assert 'diagnostic_profile' not in original
    assert original['summary'] == sample[2]['summary']
    # v1 previously allowed any strictly typed nonnegative version; v2 pins 5119.
    for obj in (e['request'], e['bars_before'], e['bars_after']): obj['trading_hours']['version'] = 5120
    assert v.validate_contract(*reseal(e, seal))['summary'] == original['summary']
    mar, mar_seal = legacy_pair(*mar_sample[:2])
    with pytest.raises(ValueError, match='REQUEST_CONTRACT'): v.validate_contract(*reseal(mar, mar_seal))


@pytest.mark.parametrize('side', ['body', 'seal'])
def test_v1_profile_injection_not_accepted(sample, side):
    e, seal = legacy_pair(*sample[:2])
    (e if side == 'body' else seal)['diagnostic_profile'] = 'NQ_DEC26'
    with pytest.raises(ValueError, match='ENVELOPE'): v.validate_contract(*reseal(e, seal))


@pytest.mark.parametrize('folder,body_hash,seal_hash', [
    ('D:/ARMS_AI_R57_CAPTURE/20260924_233411', '1f455401f1fc3705898fff27e56c21fdbf9365751451656ebf0a15edaada6129',
     '6a59311bb91f0a9b57f8c9644429eb05c3e44e658c09de68869f72bca34c7713'),
    ('D:/ARMS_AI_R57_EARLY_CLOSE_CAPTURE/20260925_012758', '23c30d899cc037c06361b027e90a8a91e74b96ad5360fbb8190a5510b29b126c',
     '36fa1a8e780d1348c01fd841c82614102b7629ab080cced997e854254da4fa63')])
def test_legacy_native_captures_unchanged_when_available(folder, body_hash, seal_hash):
    path = Path(folder)
    if not path.exists(): pytest.skip('Operator capture not available; never substitute synthetic evidence')
    before = [(path / n).read_bytes() for n in (EVIDENCE, SEAL)]
    assert [sha256(b).hexdigest() for b in before] == [body_hash, seal_hash]
    report = v.verify_completed_capture(path)
    assert report['summary']['reused_coverage_match'] is report['summary']['fresh_coverage_match'] is True
    assert 'diagnostic_profile' not in report
    assert [(path / n).read_bytes() for n in (EVIDENCE, SEAL)] == before


def test_cursor_core_bytes_remain_identical():
    assert sha256(CORE.read_bytes()).hexdigest() == 'f7e4ded5f99d9488ec8b7f2349c47d1d9ee05b1a7c77d6438796acbfc0ffea72'
