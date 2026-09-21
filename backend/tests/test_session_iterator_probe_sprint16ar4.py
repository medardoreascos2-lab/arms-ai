"""Actual R4 C# with synthetic doubles plus offline evidence rejection; not native proof."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from tools.verify_session_iterator_probe_v1 import verify_evidence

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'integrations/ninjatrader/ArmsSessionIteratorProbeV1.cs'
HARNESS = ROOT / 'backend/tests/fixtures/session_iterator_probe_harness_sprint16ar4.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK = Path('C:/Program Files/NinjaTrader 8/bin')


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    if not CSC.exists():
        pytest.skip('Windows Framework compiler required')
    target = tmp_path_factory.mktemp('r4-probe') / 'harness.exe'
    result = subprocess.run([str(CSC), '/nologo', '/out:' + str(target),
        '/r:System.ComponentModel.DataAnnotations.dll', '/r:System.Web.Extensions.dll',
        str(SOURCE), str(HARNESS)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return target


def run(binary, folder, mode):
    folder.mkdir(exist_ok=True)
    result = subprocess.run([str(binary), mode, str(folder)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    counts = json.loads(result.stdout)
    path = folder / 'session-iterator-probe.jsonl'
    raw = path.read_bytes() if path.exists() else b''
    rows = [json.loads(line) for line in raw.splitlines()]
    seal_path = folder / 'session-iterator-probe.done.json'
    seal_raw = seal_path.read_bytes() if seal_path.exists() else None
    assert len(rows) <= 64 and len(raw) <= 131072 and counts['native_calls'] <= 4
    assert [r['sequence'] for r in rows] == list(range(len(rows)))
    assert all(r['classification'] == 'DIAGNOSTIC_ONLY' and not r['runtime_admission']
               and not r['certification_evidence'] for r in rows)
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw + result.stdout.encode()
    assert str(folder).encode() not in raw
    assert not list(folder.glob('*.historical.jsonl'))
    return counts, rows, raw, seal_raw


@pytest.mark.parametrize('mode,expected', [('pass', 'PASS'), ('both_false', 'FAIL'),
    ('both_true', 'R2_FALSE_RETURN_NOT_REPRODUCED'), ('reverse', 'UNRESOLVED')])
def test_four_adjudication_cases_and_seal_integrity(binary, tmp_path, mode, expected):
    counts, rows, raw, seal_raw = run(binary, tmp_path, mode)
    assert counts['request_creates'] == counts['request_invokes'] == counts['request_disposes'] == 1
    assert counts['iterator_creates'] == 2 and counts['native_calls'] == 4
    assert seal_raw is not None
    seal = json.loads(seal_raw)
    assert seal['records'] == len(rows) and seal['bytes'] == len(raw) and seal['sha256'] == sha256(raw).hexdigest()
    assert seal['diagnostic_complete'] and seal['writer_closed']
    assert not seal['certification_evidence'] and not seal['runtime_admission']
    assert seal['native_confirmation'] == rows[-1]['native_confirmation'] == expected
    checked = verify_evidence(raw, seal_raw)
    assert checked['native_confirmation'] == expected and checked['native_provenance'] == 'NOT_ATTESTED_BY_VERIFIER'
    assert set(p.name for p in tmp_path.iterdir()) == {'session-iterator-probe.jsonl', 'session-iterator-probe.done.json'}


def test_separate_instances_identical_snapshot_conditions_and_exact_queries(binary, tmp_path):
    counts, rows, raw, seal = run(binary, tmp_path, 'pass')
    observed = counts['observations']
    assert [(r['iterator'], r['call']) for r in observed] == [(1,1), (1,2), (2,1), (2,2)]
    assert all(r['same_snapshot'] and r['include'] and r['kind'] == 'Utc' for r in observed)
    assert observed[0]['query'] == observed[2]['query'] == '2026-09-14T00:00:00.0000000Z'
    assert observed[1]['query'] == '2026-09-14T21:00:00.0000001Z'
    assert observed[3]['query'] == '2026-09-14T21:00:01.0000000Z'
    results = [r for r in rows if r['stage'] == 'CALL_RESULT']
    assert results[0]['session_begin'] == results[2]['session_begin'] == '2026-09-13T22:00:00.0000000Z'
    assert results[0]['session_end'] == results[2]['session_end'] == '2026-09-14T21:00:00.0000000Z'
    for key in ('snapshot_id', 'snapshot_sha256', 'instrument', 'contract', 'bars_type', 'bars_value',
                'trading_hours', 'trading_hours_version', 'trading_hours_timezone', 'application_timezone'):
        assert len({r[key] for r in results}) == 1
    assert results[1]['boolean_result'] is False
    assert results[1]['session_begin'] is results[1]['session_end'] is None
    assert results[1]['session_begin_kind'] == results[1]['session_end_kind'] == 'NONE'
    assert counts['begin_reads'] == counts['end_reads'] == 3  # No stale reads after false.
    assert verify_evidence(raw, seal)['native_confirmation'] == 'PASS'


@pytest.mark.parametrize('mode', ['advance_throw', 'other_exception', 'begin_throw', 'end_throw',
    'anchor_mismatch', 'repeat_bounds', 'reversed_bounds', 'unspecified', 'local', 'first_false', 'b_first_false'])
def test_native_errors_or_ambiguous_bounds_never_pass(binary, tmp_path, mode):
    counts, rows, raw, seal = run(binary, tmp_path, mode)
    assert seal is not None and verify_evidence(raw, seal)['native_confirmation'] == 'UNRESOLVED'
    assert counts['request_disposes'] == 1
    results = [r for r in rows if r['stage'] == 'CALL_RESULT']
    assert all(len(r['exception_message']) <= 80 for r in results)
    if mode == 'other_exception':
        assert any(r['exception_type'] == 'OTHER' for r in results)
        assert b'SecretException' not in raw
    if mode == 'end_throw':
        assert any(r['session_begin'] is not None and r['session_end'] is None and r['exception_type'] != 'NONE' for r in results)
    if mode in ('unspecified', 'local'):
        assert any(r['session_begin_kind'] == 'Unspecified' or r['session_end_kind'] == 'Local' for r in results)
    if mode == 'first_false':
        assert counts['native_calls'] == 2 and all(r['call_index'] == 0 for r in results)


@pytest.mark.parametrize('mode,invokes', [('closed',0), ('no_flow',0), ('unstable',0), ('timezone',0),
    ('playback',0), ('request_throw',1), ('inline_then_throw',1), ('empty',1), ('too_many',1),
    ('wrong_instrument',1), ('wrong_period',1), ('provider_policy',1), ('wrong_template',1),
    ('callback_error',1), ('wrong_callback',1), ('constructor_throw',1), ('b_constructor_throw',1),
    ('environment_changed',1), ('template_mutated',1), ('snapshot_mutated',1), ('foreign_file',1),
    ('changed_properties',1), ('terminated',1), ('call_cap',1), ('record_cap',1), ('byte_cap',1)])
def test_fail_closed_failures_no_completion_or_retry(binary, tmp_path, mode, invokes):
    counts, rows, raw, seal = run(binary, tmp_path, mode)
    assert counts['request_invokes'] == invokes and seal is None
    assert not any(r['stage'] == 'EXPERIMENT_COMPLETE' for r in rows)
    assert counts['request_disposes'] == counts['request_creates']
    if mode in ('call_cap', 'record_cap', 'byte_cap'):
        assert counts['native_calls'] == 0
    if mode == 'foreign_file':
        assert (tmp_path/'foreign.txt').read_text() == 'untouched'
    if mode not in ('record_cap', 'byte_cap'):
        assert rows[-1]['stage'] == 'ATTEMPT_FAILED' and rows[-1]['native_confirmation'] == 'UNRESOLVED'


@pytest.mark.parametrize('mode', ['inline', 'async', 'clone', 'reentrant'])
def test_callback_lifecycle_clone_and_duplicate_prevention(binary, tmp_path, mode):
    counts, rows, raw, seal = run(binary, tmp_path, mode)
    assert counts['native_calls'] == 4 and counts['iterator_creates'] == 2
    assert counts['request_invokes'] == counts['request_disposes'] == 1
    assert verify_evidence(raw, seal)['native_confirmation'] == 'R2_FALSE_RETURN_NOT_REPRODUCED'
    assert sum(r['stage'] == 'EXPERIMENT_COMPLETE' for r in rows) == 1


def test_disabled_defaults_no_io_or_request(binary, tmp_path):
    counts, rows, _, seal = run(binary, tmp_path, 'defaults')
    assert counts['request_creates'] == counts['request_invokes'] == counts['native_calls'] == 0
    assert rows == [] and seal is None and list(tmp_path.iterdir()) == []


def test_pending_is_not_completion(binary, tmp_path):
    counts, rows, _, seal = run(binary, tmp_path, 'pending')
    assert counts['request_invokes'] == 1 and counts['native_calls'] == counts['request_disposes'] == 0
    assert seal is None and rows[-1]['stage'] == 'REQUEST_RETURNED'


def test_fresh_directory_ownership_prevents_overwrite(binary, tmp_path):
    run(binary, tmp_path, 'pass')
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    counts, _, _, _ = run(binary, tmp_path, 'pass')
    assert counts['request_creates'] == counts['native_calls'] == 0
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.fixture(scope='module')
def evidence(binary, tmp_path_factory):
    _, rows, raw, seal = run(binary, tmp_path_factory.mktemp('r4-evidence'), 'pass')
    return rows, raw, seal


def reseal(rows, original):
    raw = b''.join(json.dumps(r,separators=(',',':')).encode()+b'\n' for r in rows)
    seal = json.loads(original)
    seal.update(sha256=sha256(raw).hexdigest(), records=len(rows), bytes=len(raw))
    return raw, json.dumps(seal).encode()


@pytest.mark.parametrize('field,value', [
    ('instrument','ES'), ('contract','NQ SEP26'), ('bars_value',5), ('bars_value',True),
    ('trading_hours','OTHER'), ('trading_hours_timezone','UTC'), ('application_timezone','Eastern Standard Time'),
    ('query_kind','Unspecified'), ('include_end_time',False), ('iterator_local_identity','A'),
    ('call_index',0), ('bounds_valid',False), ('session_begin_kind','Unspecified'),
    ('query','2026-09-14T21:00:00.0000001Z'), ('native_calls',3), ('snapshot_sha256','0'*64),
    ('sequence',1), ('runtime_admission',True), ('exception_type','PrivateProviderException'),
])
def test_malformed_call_rejected_even_with_recomputed_seal(evidence, field, value):
    rows, _, seal = evidence
    altered = deepcopy(rows)
    target = next(r for r in altered if r['stage']=='CALL_RESULT' and r['experiment_sequence']=='B_SECOND' and r['call_index']==1)
    target[field] = value
    with pytest.raises(ValueError): verify_evidence(*reseal(altered, seal))


@pytest.mark.parametrize('mutation', ['missing_call','duplicate_call','reordered','unknown_field','forged_pass','false_bounds'])
def test_evidence_graph_and_adjudication_fail_closed(evidence, mutation):
    rows, _, seal = evidence
    changed = deepcopy(rows)
    index = next(i for i,r in enumerate(changed) if r['stage']=='CALL_RESULT' and r['experiment_sequence']=='A_TICK' and r['call_index']==1)
    if mutation == 'missing_call': del changed[index-1:index+1]
    elif mutation == 'duplicate_call': changed[index:index] = deepcopy(changed[index-1:index+1])
    elif mutation == 'reordered': changed[index],changed[index-1] = changed[index-1],changed[index]
    elif mutation == 'unknown_field': changed[index]['secret']='unexpected'
    elif mutation == 'forged_pass':
        changed[index].update(boolean_result=True,session_begin='2026-09-14T22:00:00.0000000Z',
            session_end='2026-09-15T21:00:00.0000000Z',session_begin_kind='Utc',session_end_kind='Utc',bounds_valid=True)
    else: changed[index].update(session_begin='2026-09-13T22:00:00.0000000Z',session_begin_kind='Utc')
    for i,r in enumerate(changed): r['sequence']=i
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


@pytest.mark.parametrize('fault', ['hash','count','bytes','uuid','outcome','classification','duplicate_key','incomplete','oversize','non_json'])
def test_seal_mismatch_or_malformed_evidence_rejected(evidence, fault):
    _, raw, seal_raw = evidence
    seal = json.loads(seal_raw)
    if fault=='hash': seal['sha256']='0'*64
    elif fault=='count': seal['records']+=1
    elif fault=='bytes': seal['bytes']+=1
    elif fault=='uuid': seal['probe_uuid']='00000000-0000-0000-0000-000000000000'
    elif fault=='outcome': seal['native_confirmation']='FAIL'
    elif fault=='classification': seal['classification']='HISTORICAL'
    elif fault=='incomplete': seal['diagnostic_complete']=False
    elif fault=='oversize': raw=b'x'*131073
    elif fault=='non_json': raw=b'not JSON\n'
    if fault=='duplicate_key': seal_raw=seal_raw[:-1]+b',"runtime_admission":false}'
    else: seal_raw=json.dumps(seal).encode()
    with pytest.raises(ValueError): verify_evidence(raw,seal_raw)


@pytest.mark.parametrize('value', [None, [], {}, True, 1, ''])
def test_invalid_field_types_are_rejected_without_claiming_an_outcome(evidence, value):
    rows, _, seal = evidence
    changed = deepcopy(rows)
    changed[-1]['native_confirmation'] = value
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


@pytest.mark.parametrize('fault', ['contradictory_return', 'premature_pass', 'return_between_calls',
    'verified_before_callback', 'float_unverified_rows', 'float_control_index'])
def test_control_lifecycle_corruption_cannot_pass(evidence, fault):
    rows, _, seal = evidence
    changed = deepcopy(rows)
    returned = next(r for r in changed if r['stage'] == 'REQUEST_RETURNED')
    if fault == 'contradictory_return': returned['native_confirmation'] = 'FAIL'
    elif fault == 'premature_pass': returned['native_confirmation'] = 'PASS'
    elif fault == 'return_between_calls':
        changed.remove(returned)
        index = next(i for i, r in enumerate(changed) if r['stage'] == 'CALL_RESULT')
        changed.insert(index + 1, returned)
        returned['native_calls'] = 1
        snapshot = next(r for r in changed if r['stage'] == 'SNAPSHOT_VERIFIED')
        for key in ('source_identity_verified', 'snapshot_sha256', 'returned_rows', 'trading_hours_version'):
            returned[key] = snapshot[key]
    elif fault == 'verified_before_callback':
        snapshot = next(r for r in changed if r['stage'] == 'SNAPSHOT_VERIFIED')
        for row in changed[:changed.index(snapshot)]:
            for key in ('source_identity_verified', 'snapshot_sha256', 'returned_rows', 'trading_hours_version'):
                row[key] = snapshot[key]
    elif fault == 'float_unverified_rows': changed[0]['returned_rows'] = -1.0
    else: changed[0]['call_index'] = -1.0
    for i, row in enumerate(changed): row['sequence'] = i
    with pytest.raises(ValueError): verify_evidence(*reseal(changed, seal))


@pytest.mark.parametrize('fault', ['empty', 'truncated', 'missing_newline', 'wrong_schema',
    'wrong_probe_uuid', 'record_overflow', 'malformed_json'])
def test_missing_or_corrupt_records_cannot_pass(evidence, fault):
    rows, raw, seal = evidence
    changed = deepcopy(rows)
    if fault == 'empty': raw = b''
    elif fault == 'truncated': raw = raw[:len(raw)//2]
    elif fault == 'missing_newline': raw = raw[:-1]
    elif fault == 'malformed_json': raw = b'{invalid}\n'
    else:
        if fault == 'wrong_schema': changed[0]['schema'] = 'unknown'
        elif fault == 'wrong_probe_uuid': changed[0]['probe_uuid'] = '00000000-0000-0000-0000-000000000000'
        else: changed = [deepcopy(changed[0]) for _ in range(65)]
        raw, seal = reseal(changed, seal)
    with pytest.raises(ValueError): verify_evidence(raw, seal)


def test_offline_verifier_cli_validates_and_rejects_missing_seal(evidence, tmp_path):
    import sys
    _, raw, seal = evidence
    path, done = tmp_path/'probe.jsonl', tmp_path/'probe.done.json'
    path.write_bytes(raw); done.write_bytes(seal)
    cmd = [sys.executable,'-B',str(ROOT/'tools/verify_session_iterator_probe_v1.py'),
           '--diagnostic',str(path),'--seal',str(done)]
    result = subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert result.returncode == 0 and json.loads(result.stdout)['native_confirmation'] == 'PASS'
    cmd[-1] = str(tmp_path/'missing.json')
    result = subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert result.returncode == 1 and result.stderr == ''
    assert json.loads(result.stdout)['native_confirmation'] == 'UNRESOLVED'


def test_diagnostics_never_admitted_as_certified_history(evidence):
    from backend.market_data.certified_bootstrap_v1 import certify_bootstrap
    _, raw, _ = evidence
    with pytest.raises(ValueError): certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())


def test_structural_execution_boundary_and_unchanged_exporters():
    source = re.sub(r'//[^\n]*', '', SOURCE.read_text())
    # DisplayAttribute.Order sorts UI properties; it is not NinjaTrader.Cbi.Order.
    source = re.sub(r'\[Display\([^\n]*\)\]', '', source)
    assert not re.search(r'\b(Account|Order|SubmitOrder|CreateOrder|Execution|Process|Timer|DllImport|Activator)\b',source)
    assert not re.search(r'\.(Update|Connect|Disconnect)\s*[+=(]',source)
    assert re.findall(r'Connection\.(\w+)',source) == ['PlaybackConnection']
    assert source.count('new BarsRequest(') == source.count('request.Request(') == 1
    assert source.count('new SessionIterator(') == 2
    for name in ('ArmsHistoricalBootstrapV1.cs','ArmsReadOnlyMarketV1.cs'):
        path = 'integrations/ninjatrader/'+name
        baseline = subprocess.check_output(['git','show','c579e9d082c1cf0523c7b9c6aca9f1e83e8e1a41:'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n') == baseline.replace(b'\r\n',b'\n')


def test_installed_sdk_compile(tmp_path):
    if not CSC.exists() or not (SDK/'NinjaTrader.Core.dll').exists():
        pytest.skip('Installed Windows NinjaTrader SDK required')
    shim = tmp_path/'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs = [SDK/'NinjaTrader.Core.dll', SDK/'NinjaTrader.Gui.dll', CSC.parent/'WPF/WindowsBase.dll',
            'System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Core.dll']
    result = subprocess.run([str(CSC),'/nologo','/target:library','/out:'+str(tmp_path/'Probe.dll'),
        *['/r:'+str(p) for p in refs],str(SOURCE),str(shim)],capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
