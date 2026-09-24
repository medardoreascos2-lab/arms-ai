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

from tools.verify_historical_utc_boundary_matrix_v1 import (
    IncompleteCaptureError, validate_contract, verify_completed_capture, matrix_contract,
)

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'integrations/ninjatrader/HistoricalUtcBoundaryMatrixDiagnosticV1.cs'
HOST = ROOT / 'integrations/ninjatrader/ArmsHistoricalUtcBoundaryMatrixProbeV1.cs'
HARNESS = ROOT / 'backend/tests/fixtures/historical_utc_boundary_matrix_harness_sprint16ar56.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
EVIDENCE = 'historical-utc-boundary-matrix.json'
SEAL = 'historical-utc-boundary-matrix.done.json'


def checked(command):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    target = tmp_path_factory.mktemp('r56-harness') / 'harness.exe'
    checked([CSC, '/nologo', '/langversion:5', '/define:R56_OFFLINE_TESTS', '/target:exe', '/out:' + str(target),
             '/r:System.Core.dll', '/r:System.Web.Extensions.dll', '/r:System.ComponentModel.DataAnnotations.dll',
             CORE, HOST, HARNESS])
    return target


def run(binary, path, mode):
    path.mkdir(exist_ok=True)
    output = checked([binary, mode, path]).stdout
    assert 'PRIVATE_PROVIDER_SENTINEL' not in output
    counts = json.loads(output)
    assert counts['classification'] == 'SYNTHETIC_OFFLINE_R56'
    assert counts['requests'] <= 1 and counts['constructors'] <= 12 and counts['calls'] <= 18
    assert counts['request_constructors'] <= 1 and counts['disposes'] <= 1
    if not (path / SEAL).exists():
        return counts, None
    raw, seal = (path / EVIDENCE).read_bytes(), (path / SEAL).read_bytes()
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw + seal and str(path).encode() not in raw + seal
    result = verify_completed_capture(path)
    assert result['status'] == 'PASS_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CONTRACT_ONLY'
    assert result['publication_complete'] is True and result['native_provenance_attested'] is False
    evidence = json.loads(raw); matrix = evidence['matrix']
    for field, measured in [('getnextsession_attempts', 'calls'), ('iterator_constructor_attempts', 'constructors'),
                            ('begin_read_attempts', 'begins'), ('end_read_attempts', 'ends'), ('trading_day_read_attempts', 'day_reads')]:
        assert matrix[field] == counts[measured]
    calls = [c for item in matrix['observations'] for c in (item['prime'], item['observation']) if c is not None]
    assert [c['query']['ticks'] for c in calls] == counts['queries']
    assert [c['trading_day'] for c in calls if c['trading_day'] is not None] == counts['day_values']
    assert evidence['bars_before'] == evidence['bars_after']
    assert evidence['bars_before']['first']['kind'] == 'Unspecified'
    assert evidence['request_attempts'] == 1
    return counts, evidence


@pytest.mark.parametrize('mode', ['success', 'inline', 'async', 'clone', 'reentrant', 'other_dates'])
def test_matrix_pairs_exact_queries_and_one_shot(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    matrix = evidence['matrix']; items = matrix['observations']
    assert matrix['outcome'] == 'COMPLETE' and matrix['interpretation_allowed'] is True
    assert matrix['conditional_required'] is False
    assert counts['constructors'] == 10 and counts['calls'] == 15
    assert counts['requests'] == counts['disposes'] == 1
    q0 = evidence['initial_query']; anchor = items[0]['prime']
    expected_queries = [anchor['end']['ticks']] * 2 + [anchor['end']['ticks'] + 1] * 2 + [q0['ticks'] + 864000000000]
    for row in range(5):
        primed, fresh = items[row * 2:row * 2 + 2]
        assert primed['iterator_identity'] != fresh['iterator_identity']
        assert primed['source_bars_identity'] == fresh['source_bars_identity'] == 'RETURNED_BARS_1'
        assert primed['prime'] == anchor
        assert primed['prime']['query'] == q0 and primed['prime']['include_end_time'] is True
        assert fresh['prime'] is None and fresh['priming_occurred'] is False
        for item in (primed, fresh):
            call = item['observation']
            assert call['query']['ticks'] == expected_queries[row] and call['query']['kind'] == 'Utc'
            assert call['query'] == call['source_after'] and call['source_preserved'] is True
            assert call['include_end_time'] is (row not in (1, 3))
    assert items[0]['observation']['classification'] == items[1]['observation']['classification'] == 'SAME_AS_PRIME'
    assert counts['call_facts'][0]['prime'] is True and counts['call_facts'][1]['prime'] is False
    assert counts['call_facts'][2]['prime'] is False and counts['call_facts'][2]['iterator'] == 2
    if mode == 'other_dates':
        assert q0['clock'] == '2026-11-23T00:00:00.0000000'


@pytest.mark.parametrize('mode,conditional', [('false', True), ('mixed', False), ('success', False),
                                            ('same', True), ('other', True), ('one_control', False)])
def test_result_neutral_contract_and_conditional_control(binary, tmp_path, mode, conditional):
    counts, evidence = run(binary, tmp_path, mode)
    matrix = evidence['matrix']
    assert matrix['conditional_required'] is conditional
    assert counts['constructors'] == (12 if conditional else 10)
    assert counts['calls'] == (18 if conditional else 15)
    if conditional:
        for item in matrix['observations'][-2:]:
            assert item['case_id'] == 'LATER_DATE_CONTROL'
            assert item['observation']['query']['ticks'] == evidence['initial_query']['ticks'] + 2 * 864000000000
    if mode == 'false':
        assert counts['begins'] == counts['ends'] == counts['day_reads'] == 6
        for item in matrix['observations']:
            call = item['observation']
            assert call['classification'] == 'RETURNED_FALSE'
            assert call['begin'] is call['end'] is call['trading_day'] is None
    if mode in ('same', 'other'):
        expected = 'SAME_AS_PRIME' if mode == 'same' else 'OTHER_VALID_SESSION'
        assert all(item['observation']['classification'] == expected for item in matrix['observations'])


@pytest.mark.parametrize('mode,phase,reads', [('advance_throw', 'ADVANCE', (0, 0, 0)),
    ('begin_throw', 'BEGIN_READ', (1, 0, 0)), ('end_throw', 'END_READ', (1, 1, 0)),
    ('day_throw', 'TRADING_DAY_READ', (1, 1, 1))])
def test_case_exception_stops_only_that_iterator(binary, tmp_path, mode, phase, reads):
    counts, evidence = run(binary, tmp_path, mode)
    assert counts['constructors'] == 12 and counts['calls'] == 18
    assert evidence['matrix']['outcome'] == 'COMPLETE'
    for item in evidence['matrix']['observations']:
        call = item['observation']
        assert call['classification'] == 'EXCEPTION' and call['exception'] == 'InvalidOperationException'
        assert call['phase'] == phase
        assert tuple(call[k] for k in ('begin_read_attempts', 'end_read_attempts', 'trading_day_read_attempts')) == reads


@pytest.mark.parametrize('mode,outcome,constructors,calls', [
    ('prime_false', 'PRIME_REJECTED', 1, 1), ('prime_advance_throw', 'PRIME_REJECTED', 1, 1),
    ('prime_begin_throw', 'PRIME_REJECTED', 1, 1), ('prime_end_throw', 'PRIME_REJECTED', 1, 1),
    ('prime_day_throw', 'PRIME_REJECTED', 1, 1), ('prime_unspecified', 'PRIME_REJECTED', 1, 1),
    ('prime_local', 'PRIME_REJECTED', 1, 1), ('prime_bad_order', 'PRIME_REJECTED', 1, 1),
    ('prime_boundary', 'PRIME_REJECTED', 1, 1), ('prime_disagree', 'PRIME_DISAGREEMENT', 3, 4),
    ('prime_day_disagree', 'PRIME_DISAGREEMENT', 3, 4), ('constructor_throw', 'CONSTRUCTOR_EXCEPTION', 1, 0),
    ('fresh_constructor_throw', 'CONSTRUCTOR_EXCEPTION', 2, 2), ('tick_overflow', 'DERIVATION_EXCEPTION', 5, 7)])
def test_prime_or_derivation_failure_aborts_interpretation(binary, tmp_path, mode, outcome, constructors, calls):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence['matrix']['outcome'] == outcome and evidence['matrix']['interpretation_allowed'] is False
    assert counts['constructors'] == constructors and counts['calls'] == calls
    assert evidence['matrix']['observations'][-1]['observation'] is None


@pytest.mark.parametrize('mode', ['bad_order', 'begin_unspecified', 'end_local', 'case_boundary'])
def test_case_invalid_bounds_and_terminal_lookahead(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert counts['calls'] == 18 and counts['day_reads'] == 6
    for item in evidence['matrix']['observations']:
        call = item['observation']
        assert call['bounds_valid'] is False and call['trading_day'] is None
        assert call['classification'] == ('REQUESTED_BOUNDARY' if mode == 'case_boundary' else 'BOUND_REJECTED')


@pytest.mark.parametrize('mode,kind', [('success', 'Unspecified'), ('day_local', 'Local'), ('day_utc', 'Utc')])
def test_native_day_kind_and_getter_order_preserved(binary, tmp_path, mode, kind):
    counts, evidence = run(binary, tmp_path, mode)
    assert {v['kind'] for v in counts['day_values']} == {kind}
    assert counts['operations'] == [f'{operation}_{i}' for i in range(1, 16)
                                    for operation in ('ADVANCE', 'BEGIN', 'END', 'TRADING_DAY')]


@pytest.mark.parametrize('kind', ['Utc', 'Unspecified', 'Local'])
def test_raw_query_kind_guard(binary, tmp_path, kind):
    counts, _ = run(binary, tmp_path, 'query_' + kind)
    assert counts['requests'] == 0
    assert counts['direct']['outcome'] == ('COMPLETE' if kind == 'Utc' else 'QUERY_REJECTED')
    assert counts['calls'] == (15 if kind == 'Utc' else 0)


@pytest.mark.parametrize('mode,constructors,calls', [('days_overflow', 9, 13), ('days_overflow_two', 11, 16)])
def test_day_arithmetic_overflow_stops_before_case_call(binary, tmp_path, mode, constructors, calls):
    counts, _ = run(binary, tmp_path, mode)
    assert counts['direct']['outcome'] == 'DERIVATION_EXCEPTION'
    assert counts['direct']['interpretation_allowed'] is False
    assert counts['constructors'] == constructors and counts['calls'] == calls
    # Verify the partial graph independently as well; 9999 dates cannot enter the host.
    from tools.verify_historical_utc_boundary_matrix_v1 import MAX_TICKS, time_fact
    initial = time_fact(counts['direct']['observations'][0]['prime']['query'])
    matrix_contract(counts['direct'], initial, MAX_TICKS)


@pytest.mark.parametrize('mode', ['mutate_price', 'mutate_time', 'mutate_hours', 'replace_hours',
    'replace_bars', 'mutate_request', 'change_properties', 'terminate_during_call', 'terminate_in_begin', 'foreign_file',
    'wrong_returned_hours', 'wrong_callback', 'callback_error', 'bad_count', 'dispose_throw',
    'request_throw', 'inline_then_throw', 'request_create_throw', 'pending'])
def test_context_failure_cannot_complete(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence is None and not (tmp_path / SEAL).exists()


@pytest.mark.parametrize('mode', ['disabled', 'disabled_rearm', 'unconfirmed', 'bad_date', 'wrong_zone', 'playback'])
def test_activation_defaults_and_guards(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert evidence is None and counts['requests'] == counts['constructors'] == 0


@pytest.mark.parametrize('mode', ['concurrent_traversal', 'concurrent_body', 'concurrent_seal'])
def test_cancellation_linearizes_before_seal(binary, tmp_path, mode):
    counts, evidence = run(binary, tmp_path, mode)
    assert counts['intent_observed'] and counts['termination_waited'] and counts['pauses'] == 1
    assert evidence is None and not (tmp_path / SEAL).exists()
    with pytest.raises(IncompleteCaptureError): verify_completed_capture(tmp_path)
    if mode == 'concurrent_seal':
        assert (tmp_path / (SEAL + '.tmp')).exists()
        assert 'publication_complete' not in validate_contract((tmp_path / EVIDENCE).read_bytes(), (tmp_path / (SEAL + '.tmp')).read_bytes())


def test_refuses_overwrite(binary, tmp_path):
    run(binary, tmp_path, 'success')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    counts = json.loads(checked([binary, 'success', tmp_path]).stdout)
    assert counts['requests'] == counts['constructors'] == 0
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.fixture(scope='module')
def sample(binary, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('r56-sample')
    run(binary, tmp_path, 'mixed')
    return (tmp_path / EVIDENCE).read_bytes(), (tmp_path / SEAL).read_bytes()


def repack(evidence, seal):
    raw = json.dumps(evidence, separators=(',', ':')).encode()
    seal['bytes'] = len(raw); seal['evidence_sha256'] = sha256(raw).hexdigest()
    return raw, json.dumps(seal).encode()


@pytest.mark.parametrize('fault', ['case_id', 'mode', 'identity', 'ordinal', 'bars_identity', 'fresh_prime',
    'prime_difference', 'query_tick', 'query_kind', 'include', 'source', 'derivation', 'false_bounds', 'day',
    'counts', 'constructors', 'getter_count', 'classification', 'conditional', 'outcome', 'interpretation',
    'request', 'snapshot', 'hours', 'authority', 'extra', 'exception', 'phase', 'request_count'])
def test_resealed_cross_field_contradictions_rejected(sample, fault):
    evidence, seal = map(json.loads, sample)
    matrix = evidence['matrix']; item = matrix['observations'][0]; call = item['observation']
    if fault == 'case_id': item['case_id'] = 'END_INCLUDE_FALSE'
    elif fault == 'mode': item['mode'] = 'FRESH_DIRECT'
    elif fault == 'identity': item['iterator_identity'] = 'ITERATOR_2'
    elif fault == 'ordinal': item['constructor_ordinal'] = True
    elif fault == 'bars_identity': item['source_bars_identity'] = 'CHART_BARS'
    elif fault == 'fresh_prime': matrix['observations'][1]['prime'] = deepcopy(item['prime'])
    elif fault == 'prime_difference': matrix['observations'][2]['prime']['trading_day']['kind'] = 'Local'
    elif fault == 'query_tick': call['query']['ticks'] += 1; call['source_after'] = deepcopy(call['query'])
    elif fault == 'query_kind': call['query']['kind'] = 'Local'; call['source_after'] = deepcopy(call['query'])
    elif fault == 'include': call['include_end_time'] = False
    elif fault == 'source': call['source_preserved'] = False
    elif fault == 'derivation': call['derivation'] = 'INITIAL_PLUS_ONE_DAY'
    elif fault == 'false_bounds': call['begin'] = deepcopy(item['prime']['begin'])
    elif fault == 'day': call['trading_day'] = deepcopy(item['prime']['trading_day'])
    elif fault == 'counts': matrix['getnextsession_attempts'] += 1
    elif fault == 'constructors': matrix['iterator_constructor_attempts'] -= 1
    elif fault == 'getter_count': call['begin_read_attempts'] = 1
    elif fault == 'classification': call['classification'] = 'ADVANCING_AFTER_PRIME'
    elif fault == 'conditional': matrix['conditional_required'] = True
    elif fault == 'outcome': matrix['outcome'] = 'PRIME_REJECTED'
    elif fault == 'interpretation': matrix['interpretation_allowed'] = False
    elif fault == 'request': evidence['request']['lookup'] = 'Provider'
    elif fault == 'snapshot': evidence['bars_after']['snapshot_sha256'] = '0' * 64
    elif fault == 'hours': evidence['bars_before']['trading_hours']['version'] += 1
    elif fault == 'authority': evidence['runtime_admission'] = True
    elif fault == 'extra': matrix['repair'] = True
    elif fault == 'exception': call['exception'] = 'InvalidOperationException'
    elif fault == 'phase': call['phase'] = 'COMPLETE'
    elif fault == 'request_count': evidence['request_attempts'] = 2
    with pytest.raises(ValueError): validate_contract(*repack(evidence, seal))


@pytest.mark.parametrize('fault', ['valid_tick_shift', 'canonical_end_shift', 'true_same_label', 'true_other_label',
    'true_false_label', 'true_exception', 'true_missing_day', 'unexpected_day_kind_repair',
    'false_end_only', 'false_getter_reads', 'missing_pair', 'extra_pair', 'reordered_pair',
    'bool_counter', 'body_flag', 'seal_flag', 'hash', 'size', 'duplicate_key', 'oversize', 'nonfinite'])
def test_verifier_rejects_consistently_resealed_graph_forgery(sample, fault):
    evidence, seal = map(json.loads, sample)
    matrix = evidence['matrix']; items = matrix['observations']; false_call = items[0]['observation']
    true_call = items[2]['observation']
    if fault == 'valid_tick_shift':
        # Both clock and ticks are internally valid, and before/after agree.
        false_call['query']['clock'] = false_call['query']['clock'][:-1] + '1'
        false_call['query']['ticks'] += 1
        false_call['source_after'] = deepcopy(false_call['query'])
    elif fault == 'canonical_end_shift':
        for item in items[::2]:
            item['prime']['end']['clock'] = item['prime']['end']['clock'][:-1] + '1'
            item['prime']['end']['ticks'] += 1
    elif fault == 'true_same_label': true_call['classification'] = 'SAME_AS_PRIME'
    elif fault == 'true_other_label': true_call['classification'] = 'OTHER_VALID_SESSION'
    elif fault == 'true_false_label': true_call['classification'] = 'RETURNED_FALSE'
    elif fault == 'true_exception': true_call['exception'] = 'IOException'
    elif fault == 'true_missing_day': true_call['trading_day'] = None
    elif fault == 'unexpected_day_kind_repair': items[4]['prime']['trading_day']['kind'] = 'Utc'
    elif fault == 'false_end_only': false_call['end'] = deepcopy(items[0]['prime']['end'])
    elif fault == 'false_getter_reads': false_call['end_read_attempts'] = 1; matrix['end_read_attempts'] += 1
    elif fault == 'missing_pair': matrix['observations'] = items[:-2]; matrix['iterator_constructor_attempts'] -= 2
    elif fault == 'extra_pair': matrix['observations'] += deepcopy(items[-2:]); matrix['iterator_constructor_attempts'] += 2
    elif fault == 'reordered_pair': items[0], items[1] = items[1], items[0]
    elif fault == 'bool_counter': true_call['getnextsession_attempts'] = True
    elif fault == 'body_flag': evidence['execution_authority'] = True
    elif fault == 'seal_flag': seal['exporter_invoked'] = True
    raw, sealed = repack(evidence, seal)
    if fault == 'hash': raw += b' '
    elif fault == 'size': seal['bytes'] += 1; sealed = json.dumps(seal).encode()
    elif fault == 'duplicate_key': raw = b'{"schema":1,' + raw[1:]
    elif fault == 'oversize': raw = b' ' * 262145
    elif fault == 'nonfinite': raw = b'{"x":NaN}'
    with pytest.raises(ValueError): validate_contract(raw, sealed)


def test_conditional_f_cannot_be_omitted_or_falsified(binary, tmp_path):
    run(binary, tmp_path, 'false')
    evidence = json.loads((tmp_path / EVIDENCE).read_bytes())
    seal = json.loads((tmp_path / SEAL).read_bytes())
    matrix = evidence['matrix']; matrix['observations'] = matrix['observations'][:10]
    matrix['iterator_constructor_attempts'] = 10; matrix['getnextsession_attempts'] = 15
    matrix['begin_read_attempts'] = matrix['end_read_attempts'] = matrix['trading_day_read_attempts'] = 5
    for falsify in (False, True):
        matrix['conditional_required'] = not falsify
        with pytest.raises(ValueError): validate_contract(*repack(evidence, seal))


def seal_for(evidence):
    from tools.verify_historical_utc_boundary_matrix_v1 import FLAGS
    return dict(FLAGS, schema='arms.r56.historical-utc-boundary-matrix.seal.v1',
                run_id=evidence['run_id'], complete=True)


@pytest.mark.parametrize('mode,constructors,calls,outcome', [
    ('f_primed_constructor_throw', 11, 15, 'CONSTRUCTOR_EXCEPTION'),
    ('f_prime_false', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_throw', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_begin_throw', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_end_throw', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_day_throw', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_bad_order', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_kind', 11, 16, 'PRIME_REJECTED'),
    ('f_prime_disagree', 11, 16, 'PRIME_DISAGREEMENT'),
    ('f_fresh_constructor_throw', 12, 17, 'CONSTRUCTOR_EXCEPTION'),
])
def test_partial_f_retains_body_without_completion_seal(binary, tmp_path, mode, constructors, calls, outcome):
    counts, completed = run(binary, tmp_path, mode)
    assert completed is None and counts['constructors'] == constructors and counts['calls'] == calls
    assert counts['requests'] == counts['request_constructors'] == counts['disposes'] == 1
    assert set(p.name for p in tmp_path.iterdir()) == {EVIDENCE}
    assert not any('COMPLETE_CONTRACT_ONLY' in p for p in counts['prints'])
    raw = (tmp_path / EVIDENCE).read_bytes(); evidence = json.loads(raw); matrix = evidence['matrix']
    assert matrix['conditional_required'] is True and matrix['interpretation_allowed'] is False
    assert matrix['outcome'] == outcome and matrix['observations'][-1]['observation'] is None
    assert matrix['iterator_constructor_attempts'] == constructors and matrix['getnextsession_attempts'] == calls
    with pytest.raises(IncompleteCaptureError): verify_completed_capture(tmp_path)
    # Low-level bytes may describe the partial attempt; a forged final seal cannot complete it.
    body, sealed = repack(evidence, seal_for(evidence))
    assert 'publication_complete' not in validate_contract(body, sealed)
    forged = tmp_path / 'forged'; forged.mkdir()
    (forged / EVIDENCE).write_bytes(body); (forged / SEAL).write_bytes(sealed)
    with pytest.raises(IncompleteCaptureError, match='INCOMPLETE_CONDITIONAL_ROW'):
        verify_completed_capture(forged)
    cli = capture_cli('--capture', forged)
    assert cli.returncode == 1 and cli.stdout == ''
    assert cli.stderr.strip() == 'INCOMPLETE_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CAPTURE'
    assert (tmp_path / EVIDENCE).read_bytes() == raw
    if mode == 'f_primed_constructor_throw':
        # Exact R5.6-BR reproduction, including the 11/15 prefix and missing fresh mode.
        assert [i['mode'] for i in matrix['observations'] if i['case_id'] == 'LATER_DATE_CONTROL'] == ['PRIMED_REUSED']


def test_f_case_exception_followed_by_cancellation_cannot_publish_partial_pair(binary, tmp_path):
    counts, completed = run(binary, tmp_path, 'f_case_throw_cancel')
    assert completed is None and counts['constructors'] == 11 and counts['calls'] == 17
    assert counts['requests'] == counts['request_constructors'] == counts['disposes'] == 1
    assert set(p.name for p in tmp_path.iterdir()) == {EVIDENCE + '.tmp'}
    with pytest.raises(IncompleteCaptureError): verify_completed_capture(tmp_path)


@pytest.mark.parametrize('mode,classification', [
    ('f_success', 'ADVANCING_AFTER_PRIME'), ('f_one_false', 'RETURNED_FALSE'),
    ('f_both_false', 'RETURNED_FALSE'), ('f_primed_case_throw', 'EXCEPTION'),
    ('f_fresh_case_throw', 'EXCEPTION'), ('f_fresh_begin_throw', 'EXCEPTION'),
    ('f_fresh_end_throw', 'EXCEPTION'), ('f_fresh_day_throw', 'EXCEPTION'),
])
def test_complete_f_pair_can_seal_native_failures_without_retry(binary, tmp_path, mode, classification):
    counts, evidence = run(binary, tmp_path, mode)
    assert counts['constructors'] == 12 and counts['calls'] == 18
    assert counts['requests'] == counts['request_constructors'] == counts['disposes'] == 1
    matrix = evidence['matrix']; pair = matrix['observations'][-2:]
    assert matrix['outcome'] == 'COMPLETE' and matrix['conditional_required'] is True
    assert [(i['case_id'], i['mode']) for i in pair] == [
        ('LATER_DATE_CONTROL', 'PRIMED_REUSED'), ('LATER_DATE_CONTROL', 'FRESH_DIRECT')]
    assert all(i['phase'] == 'COMPLETE' and i['observation'] is not None for i in pair)
    selected = pair[1] if mode.startswith('f_fresh_') else pair[0]
    assert selected['observation']['classification'] == classification
    assert verify_completed_capture(tmp_path)['publication_complete'] is True


@pytest.mark.parametrize('fault', ['only_primed', 'only_fresh', 'duplicate_primed', 'duplicate_fresh',
    'missing', 'third_mode', 'counter_mismatch', 'no_case_observation'])
def test_completed_verifier_rejects_resealed_f_structure(binary, tmp_path, fault):
    source = tmp_path / 'source'; run(binary, source, 'f_success')
    evidence = json.loads((source / EVIDENCE).read_bytes()); matrix = evidence['matrix']
    pair = deepcopy(matrix['observations'][-2:])
    replacement = {
        'only_primed': pair[:1], 'only_fresh': pair[1:],
        'duplicate_primed': [pair[0], deepcopy(pair[0])],
        'duplicate_fresh': [pair[1], deepcopy(pair[1])],
        'missing': [], 'third_mode': pair + [deepcopy(pair[0])],
        'counter_mismatch': pair, 'no_case_observation': pair,
    }[fault]
    matrix['observations'] = matrix['observations'][:10] + replacement
    matrix['iterator_constructor_attempts'] = len(matrix['observations'])
    if fault == 'no_case_observation': matrix['observations'][-1]['observation'] = None
    from tools.verify_historical_utc_boundary_matrix_v1 import COUNTS
    for field in COUNTS:
        matrix[field] = sum(c[field] for i in matrix['observations'] for c in (i['prime'], i['observation']) if c is not None)
    if fault == 'counter_mismatch': matrix['getnextsession_attempts'] -= 1
    raw, sealed = repack(evidence, seal_for(evidence))
    forged = tmp_path / 'forged'; forged.mkdir()
    (forged / EVIDENCE).write_bytes(raw); (forged / SEAL).write_bytes(sealed)
    with pytest.raises(ValueError): verify_completed_capture(forged)
    assert capture_cli('--capture', forged).returncode == 1


def test_f_day_overflow_is_not_publication_eligible(binary, tmp_path):
    from tools.verify_historical_utc_boundary_matrix_v1 import _require_complete_matrix
    counts, _ = run(binary, tmp_path, 'days_overflow_two')
    assert counts['direct']['conditional_required'] is True
    assert counts['direct']['outcome'] == 'DERIVATION_EXCEPTION'
    with pytest.raises(IncompleteCaptureError): _require_complete_matrix(counts['direct'])


def test_no_execution_conversion_or_contaminating_helper_surface():
    code = '\n'.join(p.read_text() for p in (CORE, HOST))
    code = re.sub(r'//[^\n]*', '', code)
    code = re.sub(r'\[Display\([^\n]*\)\]', '', code)
    for token in ('ToUniversalTime', 'TimeZoneInfo.Local', 'ConvertTime', 'SessionIteratorQueryDomainAdapterV1',
                  'ArmsHistoricalBootstrapV1', 'IsInSession', 'IsNewSession', 'CalculateTradingDay',
                  'File.Delete', 'LookupPolicies.Provider', 'AddDataSeries', '.Update +='):
        assert token not in code
    assert not re.search(r'\b(Account|Order|Execution|Strategy|AtmStrategy|Timer|Process|Activator|DllImport)\b', code)
    assert not re.search(r'\.(Connect|Disconnect|Submit|CreateOrder|Change|Cancel)\s*\(', code)
    assert code.count('new SessionIterator(returnedBars)') == code.count('iterator.GetNextSession(query, include)') == 1
    assert code.count('new BarsRequest(') == code.count('request.Request(Completed)') == 1
    assert re.findall(r'DateTime\.SpecifyKind\(([^\n]+)', code) == [
        'from.AddDays(-2), DateTimeKind.Utc);', 'through.AddDays(8), DateTimeKind.Utc);',
        'from.AddDays(-2), DateTimeKind.Utc)));', 'through.AddDays(8), DateTimeKind.Utc)));']


def test_installed_sdk_compile_only(tmp_path):
    sdk = Path('C:/Program Files/NinjaTrader 8/bin')
    shim = tmp_path / 'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs = [sdk / 'NinjaTrader.Core.dll', sdk / 'NinjaTrader.Gui.dll', CSC.parent / 'WPF/WindowsBase.dll',
            'System.Core.dll', 'System.Web.Extensions.dll', 'System.ComponentModel.DataAnnotations.dll']
    checked([CSC, '/nologo', '/langversion:5', '/target:library', '/out:' + str(tmp_path / 'R56CompileOnly.dll'),
             *['/r:' + str(p) for p in refs], CORE, HOST, shim])
    assert (tmp_path / 'R56CompileOnly.dll').is_file()




def capture_cli(*args):
    return subprocess.run([sys.executable, '-B', str(ROOT / 'tools/verify_historical_utc_boundary_matrix_v1.py'),
                           *map(str, args)], cwd=ROOT, capture_output=True, text=True, timeout=60)


def test_verifier_cli_requires_published_pair_and_remains_diagnostic_only(sample, tmp_path):
    raw, seal = sample
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(seal)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['status'] == 'PASS_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CONTRACT_ONLY'
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
    assert result.stderr.strip() == 'INCOMPLETE_R56_HISTORICAL_UTC_BOUNDARY_MATRIX_CAPTURE'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize('mode', ['false', 'success'])
def test_completion_accepts_false_and_all_true_captures(binary, tmp_path, mode):
    _, evidence = run(binary, tmp_path, mode)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['interpretation_allowed'] is True
    assert evidence['matrix']['conditional_required'] is (mode == 'false')


@pytest.mark.parametrize('fault', ['bytes', 'hash', 'contradiction'])
def test_completion_checks_byte_binding_and_contract(sample, tmp_path, fault):
    evidence, seal = map(json.loads, sample)
    if fault == 'bytes': seal['bytes'] += 1
    elif fault == 'hash': seal['evidence_sha256'] = '0' * 64
    else: evidence['matrix']['trading_day_read_attempts'] += 1
    raw, sealed = repack(evidence, seal) if fault == 'contradiction' else (sample[0], json.dumps(seal).encode())
    (tmp_path / EVIDENCE).write_bytes(raw); (tmp_path / SEAL).write_bytes(sealed)
    with pytest.raises(ValueError): verify_completed_capture(tmp_path)
    result = capture_cli('--capture', tmp_path)
    assert result.returncode == 1 and 'PASS_' not in result.stdout + result.stderr


@pytest.mark.parametrize('extra', ['unrelated.txt', SEAL + '.tmp', EVIDENCE + '.tmp'])
def test_completion_keeps_exact_pair_directory_contract(sample, tmp_path, extra):
    (tmp_path / EVIDENCE).write_bytes(sample[0]); (tmp_path / SEAL).write_bytes(sample[1])
    (tmp_path / extra).write_bytes(b'preserve')
    with pytest.raises(ValueError, match='R56_CAPTURE_CONTENTS'): verify_completed_capture(tmp_path)
    assert capture_cli('--capture', tmp_path).returncode == 1
    assert (tmp_path / extra).read_bytes() == b'preserve'


@pytest.mark.parametrize('directory_name', [EVIDENCE, SEAL])
def test_completion_requires_regular_final_files(sample, tmp_path, directory_name):
    for name, data in zip((EVIDENCE, SEAL), sample):
        if name == directory_name: (tmp_path / name).mkdir()
        else: (tmp_path / name).write_bytes(data)
    with pytest.raises(ValueError, match='R56_FINAL_ARTIFACT'): verify_completed_capture(tmp_path)
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
    with pytest.raises(ValueError, match='R56_(CAPTURE_DIRECTORY|FINAL_ARTIFACT)'):
        verify_completed_capture(tmp_path)
