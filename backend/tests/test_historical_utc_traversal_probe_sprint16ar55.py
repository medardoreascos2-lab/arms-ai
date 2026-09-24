"""Execute the new C# package with synthetic SDK doubles, never native evidence."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools.verify_historical_utc_traversal_v1 import (
    IncompleteCaptureError, validate_contract, verify_completed_capture,
)

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'integrations/ninjatrader/HistoricalUtcTraversalDiagnosticV1.cs'
HOST = ROOT / 'integrations/ninjatrader/ArmsHistoricalUtcTraversalProbeV1.cs'
HARNESS = ROOT / 'backend/tests/fixtures/historical_utc_traversal_harness_sprint16ar55.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
EVIDENCE = 'historical-utc-traversal.json'
SEAL = 'historical-utc-traversal.done.json'


def checked(command):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    target = tmp_path_factory.mktemp('r55-harness') / 'harness.exe'
    checked([CSC, '/nologo', '/langversion:5', '/define:R55_OFFLINE_TESTS', '/target:exe', '/out:' + str(target),
             '/r:System.Core.dll', '/r:System.Web.Extensions.dll', '/r:System.ComponentModel.DataAnnotations.dll',
             CORE, HOST, HARNESS])
    return target


def run(binary, path, mode):
    path.mkdir(exist_ok=True)
    result = checked([binary, mode, path])
    assert 'PRIVATE_PROVIDER_SENTINEL' not in result.stdout
    counts = json.loads(result.stdout)
    assert counts['classification'] == 'SYNTHETIC_OFFLINE_R55'
    assert counts['requests'] <= 1 and counts['constructors'] <= 1 and counts['calls'] <= 64
    assert counts['request_constructors'] <= 1 and counts['disposes'] <= 1
    if (path / SEAL).exists():
        raw, seal = (path / EVIDENCE).read_bytes(), (path / SEAL).read_bytes()
        assert b'PRIVATE_PROVIDER_SENTINEL' not in raw + seal
        assert str(path).encode() not in raw + seal
        report = verify_completed_capture(path)
        assert report['publication_complete'] is True
        assert report['status'] == 'PASS_R55_HISTORICAL_UTC_TRAVERSAL_CONTRACT_ONLY'
        assert report['native_provenance_attested'] is False and report['execution_authority'] is False
        assert set(p.name for p in path.iterdir()) == {EVIDENCE, SEAL}
        evidence = json.loads(raw)
        t = evidence['traversal']
        assert t['getnextsession_attempts'] == counts['calls']
        assert t['iterator_constructor_attempts'] == counts['constructors']
        assert t['begin_read_attempts'] == counts['begins']
        assert t['end_read_attempts'] == counts['ends']
        assert t['trading_day_read_attempts'] == counts['day_reads']
        assert [c['trading_day'] for c in t['calls'] if c['trading_day_outcome'] == 'RETURNED'] == counts['day_values']
        assert evidence['request_attempts'] == counts['requests'] == 1
        assert evidence['bars_before'] == evidence['bars_after']
        assert evidence['bars_before']['first']['kind'] == 'Unspecified'  # never converted
        return counts, evidence
    return counts, None


@pytest.mark.parametrize('mode', ['success', 'inline', 'async', 'clone', 'reentrant', 'begin_boundary'])
def test_exact_utc_sequence_one_iterator_and_one_shot(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence is not None
    assert counts['constructors'] == counts['requests'] == counts['disposes'] == 1
    calls = evidence['traversal']['calls']
    assert evidence['traversal']['outcome'] == 'REQUESTED_BOUNDARY'
    assert calls[0]['query'] == dict(clock='2026-09-14T00:00:00.0000000', ticks=639249408000000000, kind='Utc')
    for previous, following in zip(calls, calls[1:]):
        assert following['query']['ticks'] == previous['end']['ticks'] + 1
    for call in calls:
        assert call['query']['kind'] == 'Utc' and call['include_end_time'] is True
        assert call['query'] == call['source_after'] and call['source_preserved'] is True
    assert [c['query']['ticks'] for c in calls] == counts['queries']
    assert evidence['request']['submitted_from']['kind'] == 'Unspecified'
    assert evidence['initial_query'] == calls[0]['query']
    assert evidence['traversal']['observed_false'] is False


@pytest.mark.parametrize('mode,ordinal', [('false', 0), ('late_false', 2)])
def test_false_is_valid_observation_and_never_reads_stale_bounds(binary, tmp_path, mode, ordinal):
    counts, evidence = run(binary, tmp_path, mode)
    t = evidence['traversal']
    assert t['observed_false'] is True and t['first_false_ordinal'] == ordinal
    assert t['first_false_query'] == t['calls'][-1]['query']
    assert t['successful_calls_before_false'] == ordinal
    assert counts['calls'] == ordinal + 1 and counts['begins'] == counts['ends'] == ordinal
    assert t['calls'][-1]['begin'] is t['calls'][-1]['end'] is None


def test_operator_dates_drive_runtime_query_without_fixed_range(binary, tmp_path):
    _, evidence = run(binary, tmp_path, 'other_dates')
    assert evidence['request']['configured_from'] == '2026-11-25'
    assert evidence['initial_query']['clock'] == '2026-11-23T00:00:00.0000000'
    assert evidence['calendar_through']['clock'] == '2026-12-05T00:00:00.0000000'


@pytest.mark.parametrize('mode,kind', [('success', 'Unspecified'), ('day_local', 'Local'), ('day_utc', 'Utc')])
def test_trading_day_getter_order_and_exact_native_value(binary, tmp_path, mode, kind):
    counts, evidence = run(binary, tmp_path, mode)
    calls = evidence['traversal']['calls']
    emitted = [c for c in calls if c['phase'] == 'COMPLETE']
    assert len(emitted) == counts['day_reads'] > 1
    expected_operations = []
    for i, call in enumerate(calls, 1):
        expected_operations.extend([f'ADVANCE_{i}', f'BEGIN_{i}', f'END_{i}'])
        if call['phase'] == 'COMPLETE':
            expected_operations.append(f'TRADING_DAY_{i}')
            assert call['trading_day_outcome'] == 'RETURNED'
            assert call['trading_day'] == dict(kind=kind, ticks=call['begin']['ticks'] + 123,
                clock=call['begin']['clock'][:19] + '.0000123')
        else:
            assert call['trading_day'] is None and call['trading_day_outcome'] == 'NOT_READ'
    assert counts['operations'] == expected_operations


@pytest.mark.parametrize('mode,reads', [('day_throw', 1), ('late_day_throw', 3)])
def test_trading_day_exception_stops_before_query_update_or_next_advance(binary, tmp_path, mode, reads):
    counts, evidence = run(binary, tmp_path, mode)
    t = evidence['traversal']; last = t['calls'][-1]
    assert t['outcome'] == 'CALL_EXCEPTION'
    assert last['phase'] == 'TRADING_DAY_READ' and last['exception'] == 'InvalidOperationException'
    assert last['trading_day_outcome'] == 'EXCEPTION' and last['trading_day'] is None
    assert counts['calls'] == counts['begins'] == counts['ends'] == counts['day_reads'] == reads
    assert len(counts['day_values']) == reads - 1
    assert counts['operations'] == [f'{operation}_{i}' for i in range(1, reads + 1)
                                    for operation in ('ADVANCE', 'BEGIN', 'END', 'TRADING_DAY')]


@pytest.mark.parametrize('mode,reads', [('begin_boundary', 0), ('begin_boundary_non_utc', 0), ('end_boundary', 1)])
def test_terminal_lookahead_getter_order_matches_exporter(binary, tmp_path, mode, reads):
    counts, evidence = run(binary, tmp_path, mode)
    t = evidence['traversal']; call = t['calls'][0]
    assert t['outcome'] == 'REQUESTED_BOUNDARY' and counts['calls'] == 1
    assert counts['day_reads'] == reads
    assert counts['operations'] == ['ADVANCE_1', 'BEGIN_1', 'END_1'] + (['TRADING_DAY_1'] if reads else [])
    assert call['phase'] == ('COMPLETE' if reads else 'BOUNDS')
    if mode == 'begin_boundary_non_utc':
        assert call['begin']['kind'] == 'Unspecified' and call['end']['kind'] == 'Local'
        assert call['guard'] == 'NONE' and call['bounds_valid'] is True
    if reads == 0:
        assert call['trading_day'] is None and call['trading_day_outcome'] == 'NOT_READ'


@pytest.mark.parametrize('mode,calls,begins,ends,outcome', [
    ('constructor_throw', 0, 0, 0, 'CONSTRUCTOR_EXCEPTION'),
    ('advance_throw', 1, 0, 0, 'CALL_EXCEPTION'), ('late_throw', 3, 2, 2, 'CALL_EXCEPTION'),
    ('begin_throw', 1, 1, 0, 'CALL_EXCEPTION'), ('end_throw', 1, 1, 1, 'CALL_EXCEPTION'),
    ('bad_order', 1, 1, 1, 'BOUND_REJECTED'), ('repeated', 2, 2, 2, 'BOUND_REJECTED'),
    ('begin_unspecified', 1, 1, 1, 'BOUND_REJECTED'), ('end_local', 1, 1, 1, 'BOUND_REJECTED'),
    ('overflow', 1, 1, 1, 'CALL_EXCEPTION'), ('limit', 64, 64, 64, 'CALL_LIMIT')])
def test_terminal_results_are_bounded_no_retries(binary, tmp_path, mode, calls, begins, ends, outcome):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence['traversal']['outcome'] == outcome
    assert (counts['calls'], counts['begins'], counts['ends']) == (calls, begins, ends)
    assert counts['constructors'] == counts['disposes'] == 1
    if mode == 'limit':
        assert evidence['traversal']['stopped_by_limit'] is True


@pytest.mark.parametrize('kind', ['Utc', 'Unspecified', 'Local'])
def test_input_kind_and_source_preservation_before_native_call(binary, tmp_path, kind):
    counts, _ = run(binary, tmp_path, 'query_' + kind)
    if kind != 'Utc':
        assert counts['constructors'] == counts['calls'] == counts['begins'] == counts['ends'] == 0
        assert counts['direct']['outcome'] == 'QUERY_REJECTED'
    else:
        assert counts['constructors'] == 1 and counts['calls'] > 0


@pytest.mark.parametrize('mode', ['mutate_price', 'mutate_time', 'mutate_hours', 'replace_hours',
    'replace_bars', 'mutate_request', 'change_properties', 'terminate_during_call', 'terminate_in_begin', 'foreign_file',
    'wrong_returned_hours', 'wrong_callback', 'callback_error', 'bad_count', 'dispose_throw',
    'request_throw', 'inline_then_throw', 'request_create_throw', 'pending'])
def test_context_or_lifecycle_failure_never_seals(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence is None and not (tmp_path / SEAL).exists()
    assert counts['requests'] == (0 if mode == 'request_create_throw' else 1)
    if mode in ('wrong_returned_hours', 'wrong_callback', 'callback_error', 'bad_count', 'request_throw', 'pending', 'request_create_throw'):
        assert counts['constructors'] == counts['calls'] == 0
    if mode == 'foreign_file':
        assert (tmp_path / 'foreign.txt').read_text() == 'preserve'
    if mode == 'terminate_during_call':
        assert counts['calls'] == 1 and counts['begins'] == counts['ends'] == 0
    if mode == 'terminate_in_begin':
        assert counts['calls'] == counts['begins'] == 1 and counts['ends'] == 0


@pytest.mark.parametrize('mode', ['concurrent_traversal', 'concurrent_body', 'concurrent_seal'])
def test_concurrent_termination_is_visible_before_callback_release_and_never_seals(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence is None and not (tmp_path / SEAL).exists()
    assert counts['intent_observed'] is counts['termination_waited'] is True
    assert counts['pauses'] == 1 and counts['seal_at_pause'] is False
    assert counts['requests'] == counts['request_constructors'] == counts['constructors'] == counts['disposes'] == 1
    assert 'ARMS_R55_DIAGNOSTIC_COMPLETE_CONTRACT_ONLY' not in counts['prints']
    if mode == 'concurrent_traversal':
        assert counts['calls'] == 1 and counts['begins'] == counts['ends'] == counts['day_reads'] == 0
        assert counts['body_at_pause'] is False
        assert set(p.name for p in tmp_path.iterdir()) == {EVIDENCE + '.tmp'}
    else:
        assert counts['body_at_pause'] is True and (tmp_path / EVIDENCE).is_file()
        body = json.loads((tmp_path / EVIDENCE).read_bytes())
        assert body['request_attempts'] == body['traversal_attempts'] == 1
        for flag in ('execution_authority', 'paper_execution', 'live_execution', 'runtime_admission'):
            assert body[flag] is False
        expected_files = {EVIDENCE, SEAL + '.tmp'} if mode == 'concurrent_seal' else {EVIDENCE}
        assert set(p.name for p in tmp_path.iterdir()) == expected_files
    # Use the actual partial artifacts from this two-thread cancellation, not copies.
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(IncompleteCaptureError):
        verify_completed_capture(tmp_path)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 1 and result.stdout == ''
    assert result.stderr.strip() == 'INCOMPLETE_R55_HISTORICAL_UTC_TRAVERSAL_CAPTURE'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    if mode == 'concurrent_seal':
        # Valid temporary bytes do not establish the final rename's commit.
        assert validate_contract(before[EVIDENCE], before[SEAL + '.tmp'])['status'].startswith('PASS_')


@pytest.mark.parametrize('mode', ['disabled', 'disabled_rearm', 'unconfirmed', 'bad_date', 'wrong_zone', 'playback'])
def test_defaults_and_prerequisites_no_request_or_output(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert counts['requests'] == counts['request_constructors'] == counts['calls'] == 0
    assert evidence is None and list(tmp_path.iterdir()) == []


def test_evidence_never_overwrites_or_deletes(binary, tmp_path):
    run(binary, tmp_path, 'false')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    counts = json.loads(checked([binary, 'success', tmp_path]).stdout)
    assert counts['requests'] == counts['constructors'] == 0
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.fixture(scope='module')
def sample(binary, tmp_path_factory):
    folder = tmp_path_factory.mktemp('r55-evidence')
    run(binary, folder, 'late_false')
    return (folder / EVIDENCE).read_bytes(), (folder / SEAL).read_bytes()


def repack(evidence, seal):
    raw = json.dumps(evidence, separators=(',', ':')).encode()
    seal = deepcopy(seal); seal['bytes'] = len(raw); seal['evidence_sha256'] = sha256(raw).hexdigest()
    return raw, json.dumps(seal).encode()


MUTATIONS = [
    ('execution_authority', True), ('origin', 'CERTIFIED'), ('source_preserved', False),
    ('request_attempts', 2), ('request_attempts', True), ('request_constructor_attempts', 2),
    ('traversal_attempts', 2), ('request.lookup', 'Provider'), ('request.merge', 'MergeBackAdjusted'),
    ('request.actual_from.kind', 'Bogus'), ('request.actual_from.ticks', 0),
    ('request.configured_from', '2026-09-17'), ('request.trading_hours.timezone', 'UTC'),
    ('bars_after.count', 6), ('bars_after.first.kind', 'Utc'), ('bars_before.identity', 'CHART_BARS'),
    ('bars_before.snapshot_sha256', 'x'), ('initial_query.kind', 'Unspecified'), ('calendar_through.ticks', 0),
    ('traversal.constructor_source', 'TradingHours'), ('traversal.iterator_identity', 'ITERATOR_2'),
    ('traversal.iterator_constructor_attempts', 2), ('traversal.getnextsession_attempts', 65),
    ('traversal.begin_read_attempts', 3), ('traversal.end_read_attempts', 3),
    ('traversal.trading_day_read_attempts', 3), ('traversal.trading_day_read_attempts', True),
    ('traversal.calls.0.trading_day.ticks', 0), ('traversal.calls.0.trading_day.kind', 'Bogus'),
    ('traversal.calls.0.trading_day_outcome', 'NOT_READ'), ('traversal.calls.0.trading_day_outcome', 'EXCEPTION'),
    ('traversal.calls.2.trading_day_outcome', 'RETURNED'),
    ('traversal.observed_false', False), ('traversal.first_false_ordinal', 1),
    ('traversal.successful_calls_before_false', 1), ('traversal.stopped_by_limit', True),
    ('traversal.stopped_by_requested_boundary', True), ('traversal.outcome', 'REQUESTED_BOUNDARY'),
    ('traversal.calls.0.query.clock', '2026-09-14T01:00:00.0000000'),
    ('traversal.calls.0.query.kind', 'Local'), ('traversal.calls.0.source_preserved', False),
    ('traversal.calls.0.include_end_time', False), ('traversal.calls.0.ordinal', True),
    ('traversal.calls.1.derivation', 'CONFIGURED_FROM_MINUS_TWO_DAYS_UTC'),
    ('traversal.calls.1.bounds_valid', False), ('traversal.calls.1.guard', 'BOUND_KIND'),
    ('traversal.calls.2.returned', True), ('traversal.calls.2.exception', 'PRIVATE_TEXT'),
    ('traversal.calls.2.phase', 'COMPLETE'), ('traversal.calls.2.source_after.ticks', 0),
]


@pytest.mark.parametrize('path,value', MUTATIONS)
def test_verifier_rejects_resealed_contradictions(sample, path, value):
    evidence, seal = map(json.loads, sample)
    parts = path.split('.'); target = evidence
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    target[parts[-1]] = value
    with pytest.raises(ValueError):
        validate_contract(*repack(evidence, seal))


@pytest.mark.parametrize('assembly', [
    'Harness, Version=8.1.8.20, Culture=neutral',
    'Harness, Version=18.1.8.2, Culture=neutral',
    'Harness, Version=8.1.x.2, Culture=neutral',
    'Harness, Culture=neutral',
    'Harness, Version=8.1.8.2, Version=8.1.8.2',
])
def test_verifier_sdk_version_is_exact_structured_field(sample, assembly):
    evidence, seal = map(json.loads, sample)
    assert evidence['request']['sdk_version'] == '8.1.8.2'
    evidence['request']['sdk_assembly'] = assembly
    with pytest.raises(ValueError, match='R55_SDK'):
        validate_contract(*repack(evidence, seal))


@pytest.mark.parametrize('fault', ['float', 'bool', 'kind', 'clock', 'ticks'])
def test_first_false_summary_uses_strict_timestamp_validation(binary, tmp_path, fault):
    _, evidence = run(binary, tmp_path, 'false')
    seal = json.loads((tmp_path / SEAL).read_bytes())
    fact = evidence['traversal']['first_false_query']
    if fault == 'float':
        replacement = float(fact['ticks'])
        assert replacement == fact['ticks']  # equality alone formerly accepted this
        fact['ticks'] = replacement
    elif fault == 'bool': fact['ticks'] = True
    elif fault == 'kind': fact['kind'] = 'Local'
    elif fault == 'clock': fact['clock'] = '2026-09-14T00:00:00.0000001'
    elif fault == 'ticks': fact['ticks'] += 1
    with pytest.raises(ValueError, match='R55_(INTEGER|KIND|CLOCK_TICKS)'):
        validate_contract(*repack(evidence, seal))


@pytest.mark.parametrize('fault', ['after_false', 'false_bounds', 'source_pair', 'sequence_pair', 'extra', 'hash', 'seal_flags', 'duplicate', 'oversize'])
def test_verifier_graph_and_seal_rejection(sample, fault):
    evidence, seal = map(json.loads, sample)
    if fault == 'after_false':
        evidence['traversal']['calls'].append(deepcopy(evidence['traversal']['calls'][-1]))
        evidence['traversal']['getnextsession_attempts'] += 1
    elif fault == 'false_bounds': evidence['traversal']['calls'][-1]['begin'] = evidence['initial_query']
    elif fault in ('source_pair', 'sequence_pair'):
        c = evidence['traversal']['calls'][1]
        replacement = dict(clock='2026-09-14T23:00:00.0000002', ticks=c['query']['ticks'] + 1, kind='Utc')
        c['query'] = replacement
        if fault == 'sequence_pair': c['source_after'] = deepcopy(replacement)
    elif fault == 'extra': evidence['unknown'] = 1
    elif fault == 'seal_flags': seal['certification_evidence'] = True
    raw, sealed = repack(evidence, seal)
    if fault == 'hash': raw += b' '
    elif fault == 'duplicate': raw = b'{"schema":1,' + raw[1:]
    elif fault == 'oversize': raw = b' ' * 262145
    with pytest.raises(ValueError): validate_contract(raw, sealed)


def capture_cli(*args):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'tools/verify_historical_utc_traversal_v1.py'),
                           *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=60)


def test_verifier_cli_requires_published_pair_and_remains_diagnostic_only(sample, tmp_path):
    raw, seal = sample
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(seal)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'PASS_R55_HISTORICAL_UTC_TRAVERSAL_CONTRACT_ONLY'
    assert report['publication_complete'] is True and report['execution_authority'] is False
    assert 'publication_complete' not in validate_contract(raw, seal)


@pytest.mark.parametrize('names', [
    (EVIDENCE, SEAL + '.tmp'), (EVIDENCE + '.tmp', SEAL),
    (EVIDENCE + '.tmp', SEAL + '.tmp'), (EVIDENCE,), (SEAL,),
    (EVIDENCE + '.tmp',), (SEAL + '.tmp',), (),
    (EVIDENCE, SEAL + '.wrong'), (EVIDENCE + '.wrong', SEAL),
])
def test_completion_rejects_missing_final_pair_without_substitution(sample, tmp_path, names):
    for name in names:
        (tmp_path / name).write_bytes(sample[1] if name.startswith(SEAL) else sample[0])
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(IncompleteCaptureError):
        verify_completed_capture(tmp_path)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 1 and result.stdout == ''
    assert result.stderr.strip() == 'INCOMPLETE_R55_HISTORICAL_UTC_TRAVERSAL_CAPTURE'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('mode', ['false', 'success'])
def test_completion_accepts_false_and_all_true_captures(binary, tmp_path, mode):
    _, evidence = run(binary, tmp_path, mode)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['observed_false'] is (mode == 'false')
    assert evidence['traversal']['observed_false'] is (mode == 'false')


@pytest.mark.parametrize('fault', ['bytes', 'hash', 'contradiction'])
def test_completion_checks_byte_binding_and_contract(sample, tmp_path, fault):
    evidence, seal = map(json.loads, sample)
    if fault == 'bytes': seal['bytes'] += 1
    elif fault == 'hash': seal['evidence_sha256'] = '0' * 64
    else: evidence['traversal']['trading_day_read_attempts'] += 1
    raw, sealed = repack(evidence, seal) if fault == 'contradiction' else (sample[0], json.dumps(seal).encode())
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    with pytest.raises(ValueError): verify_completed_capture(tmp_path)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 1 and 'PASS_' not in result.stdout + result.stderr


@pytest.mark.parametrize('extra', ['unrelated.txt', SEAL + '.tmp', EVIDENCE + '.tmp'])
def test_completion_keeps_exact_pair_directory_contract(sample, tmp_path, extra):
    (tmp_path / EVIDENCE).write_bytes(sample[0]); (tmp_path / SEAL).write_bytes(sample[1])
    (tmp_path / extra).write_bytes(b'preserve')
    with pytest.raises(ValueError, match='R55_CAPTURE_CONTENTS'): verify_completed_capture(tmp_path)
    assert capture_cli('--capture', tmp_path).returncode == 1
    assert (tmp_path / extra).read_bytes() == b'preserve'


@pytest.mark.parametrize('directory_name', [EVIDENCE, SEAL])
def test_completion_requires_regular_final_files(sample, tmp_path, directory_name):
    for name, data in zip((EVIDENCE, SEAL), sample):
        if name == directory_name: (tmp_path / name).mkdir()
        else: (tmp_path / name).write_bytes(data)
    with pytest.raises(ValueError, match='R55_FINAL_ARTIFACT'): verify_completed_capture(tmp_path)
    assert capture_cli('--capture', tmp_path).returncode == 1


@pytest.mark.parametrize('argument_style', ['old_paths', 'file_as_capture', 'extra_seal'])
def test_explicit_temporary_seal_cannot_bypass_cli(sample, tmp_path, argument_style):
    body, temporary = tmp_path / EVIDENCE, tmp_path / (SEAL + '.tmp')
    body.write_bytes(sample[0]); temporary.write_bytes(sample[1])
    args = {'old_paths': (body, temporary), 'file_as_capture': ('--capture', temporary),
            'extra_seal': ('--capture', tmp_path, temporary)}[argument_style]
    result = capture_cli(*args)
    assert result.returncode != 0 and 'PASS_' not in result.stdout + result.stderr
    assert 'Traceback' not in result.stderr and not (tmp_path / SEAL).exists()


@pytest.mark.parametrize('target', ['capture', EVIDENCE, SEAL])
@pytest.mark.parametrize('redirect', ['symlink', 'reparse'])
def test_completion_rejects_redirected_capture_paths(sample, tmp_path, monkeypatch, target, redirect):
    (tmp_path / EVIDENCE).write_bytes(sample[0]); (tmp_path / SEAL).write_bytes(sample[1])
    redirected = tmp_path if target == 'capture' else tmp_path / target
    original_lstat = Path.lstat

    def observed_lstat(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        if path != redirected: return info
        # Inject the OS metadata for a redirected path without requiring Windows
        # symlink privileges. Reads must be rejected before following that path.
        return SimpleNamespace(st_mode=stat.S_IFLNK if redirect == 'symlink' else info.st_mode,
            st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT if redirect == 'reparse' else 0)

    monkeypatch.setattr(Path, 'lstat', observed_lstat)
    with pytest.raises(ValueError, match='R55_(CAPTURE_DIRECTORY|FINAL_ARTIFACT)'):
        verify_completed_capture(tmp_path)


def test_static_no_execution_conversion_or_exporter_surface():
    code = '\n'.join(p.read_text() for p in (CORE, HOST))
    code = re.sub(r'//[^\n]*', '', code)
    code = re.sub(r'\[Display\([^\n]*\)\]', '', code)
    for token in ('ToUniversalTime', 'TimeZoneInfo.Local', 'ConvertTime', 'SessionIteratorQueryDomainAdapterV1',
                  'TradingHoursWallClockToUtc', 'ArmsHistoricalBootstrapV1', 'File.Delete', 'FileMode.Create,',
                  'LookupPolicies.Provider', 'AddDataSeries', '.Update +='):
        assert token not in code
    assert not re.search(r'\b(Account|Order|Execution|Strategy|AtmStrategy|Timer|Process|Activator|DllImport)\b', code)
    assert not re.search(r'\.(Connect|Disconnect|Submit|CreateOrder|Change|Cancel)\s*\(', code)
    assert code.count('new SessionIterator(') == code.count('iterator.GetNextSession(query, true)') == 1
    assert code.count('new BarsRequest(') == code.count('request.Request(Completed)') == 1
    assert re.findall(r'DateTime\.SpecifyKind\(([^\n]+)', code) == [
        'from.AddDays(-2), DateTimeKind.Utc);', 'through.AddDays(8), DateTimeKind.Utc);',
        'from.AddDays(-2), DateTimeKind.Utc)));', 'through.AddDays(8), DateTimeKind.Utc)));']
    assert 'end.AddTicks(1)' in code


def test_protected_existing_sources_equal_expected_head():
    names = ['ArmsHistoricalBootstrapV1.cs', 'ArmsReadOnlyMarketV1.cs', 'ArmsSessionTimestampNativeBridgeV1.cs',
             'ArmsSessionTimestampLifecycleV1.cs', 'ArmsSessionTimestampNativeContextV1.cs',
             'SessionIteratorQueryDomainAdapterV1.cs', 'SessionIteratorQueryDomainNativeComparisonV1.cs',
             'ArmsSessionIteratorQueryDomainRepairProbeV1.cs']
    paths = ['integrations/ninjatrader/' + name for name in names] + ['backend/market_data/native_historical_bootstrap_v1.py']
    for path in paths:
        baseline = subprocess.check_output(['git', 'show', 'c5ae6b3386111048f5b3224f3d2a512665f011a0:' + path], cwd=ROOT)
        assert (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == baseline.replace(b'\r\n', b'\n')


def test_installed_sdk_compile_only(tmp_path):
    sdk = Path('C:/Program Files/NinjaTrader 8/bin')
    shim = tmp_path / 'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs = [sdk / 'NinjaTrader.Core.dll', sdk / 'NinjaTrader.Gui.dll', CSC.parent / 'WPF/WindowsBase.dll',
            'System.Core.dll', 'System.Web.Extensions.dll', 'System.ComponentModel.DataAnnotations.dll']
    checked([CSC, '/nologo', '/langversion:5', '/target:library', '/out:' + str(tmp_path / 'R55CompileOnly.dll'),
             *['/r:' + str(p) for p in refs], CORE, HOST, shim])
    assert (tmp_path / 'R55CompileOnly.dll').is_file()
