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
    seal = dict(v.FLAGS, schema='arms.r57.historical-utc-calendar-cursor.seal.v1', run_id=evidence['run_id'], complete=True)
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
    assert checked(['git', 'diff', '--name-only']).stdout.strip() == ''
    assert checked(['git', 'diff', '--cached', '--name-only']).stdout.strip() == ''
