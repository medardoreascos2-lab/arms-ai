"""Execute actual exporter with synthetic SDK doubles; never native market evidence."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

import pytest

from backend.market_data.certified_bootstrap_v1 import certify_bootstrap
from backend.market_data.native_historical_bootstrap_v1 import EXPORTER_SHA256, REVIEWED_EXPORTER_HASHES
from backend.tests.test_native_historical_bootstrap_sprint16a import (
    native_shape, pack, bundle, TEMPLATE, forbid_account_and_execution_construction,
)
from tools.certify_native_history_v1 import build_bundle

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'integrations/ninjatrader/ArmsHistoricalBootstrapV1.cs'
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
LEGACY = '836ad9d128853129119bd9ea97b93158f6bfaa2f6bf216d80679a53c6e1ef578'


@pytest.fixture(scope='module')
def harness(tmp_path_factory):
    if not CSC.exists():
        pytest.skip('Windows Framework compiler required for offline actual-C# harness')
    target = tmp_path_factory.mktemp('historical-harness') / 'harness.exe'
    result = subprocess.run([str(CSC), '/nologo', '/target:exe', '/out:'+str(target),
        '/r:System.ComponentModel.DataAnnotations.dll', '/r:System.Web.Extensions.dll',
        str(SOURCE), str(ROOT / 'backend/tests/fixtures/historical_diagnostics_harness_sprint16ar1.cs')],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return target


def run(harness, path, mode):
    path.mkdir(exist_ok=True)
    process = subprocess.run([str(harness), mode, str(path)], capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stdout + process.stderr
    counts = json.loads(process.stdout)
    marker = path / 'historical-diagnostic.jsonl'
    raw = marker.read_bytes() if marker.exists() else b''
    trace = [json.loads(line) for line in raw.splitlines()]
    assert len(trace) <= 512 and len(raw) <= 512 * 8192
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw + process.stdout.encode()
    assert str(path).encode() not in raw
    for index, row in enumerate(trace):
        assert row['sequence'] == index
        assert row['schema'] == 'arms.nt.historical-diagnostic.v1'
        assert row['classification'] == 'DIAGNOSTIC_ONLY'
        assert row['certification_evidence'] is False and row['runtime_admission'] is False
        assert row['output_directory_identity'] == sha256(str(path).encode()).hexdigest()
    return counts, trace


@pytest.mark.parametrize('mode', ['success','inline_success','async','clone','late_properties','print_unavailable'])
def test_success_lifecycle_and_one_shot(harness, tmp_path, mode):
    counts, rows = run(harness, tmp_path, mode)
    assert counts['creates'] == counts['invokes'] == counts['disposes'] == 1
    stages = [r['stage'] for r in rows]
    for required in ('INSTANCE_STARTED','CONFIG_VALIDATED','REQUEST_CREATED','REQUEST_SUBMITTED',
                     'CALLBACK_ENTERED','ROWS_RECEIVED','SERIALIZATION_STARTED','SEAL_WRITTEN'):
        assert stages.count(required) == 1
    assert not any(r['attempt_failed'] for r in rows)
    assert rows[0]['from_utc_date'] == '2026-09-16' and rows[0]['through_utc_date'] == '2026-09-21'
    assert rows[0]['state'] == ('DataLoaded' if mode == 'late_properties' else 'Configure')
    histories = list(tmp_path.glob('*.historical.jsonl'))
    assert len(histories) == len(list(tmp_path.glob('*.done.json'))) == 1
    raw = histories[0].read_bytes()
    seal = json.loads(Path(str(histories[0])+'.done.json').read_bytes())
    assert seal['sha256'] == sha256(raw).hexdigest() and seal['bars'] == 3
    assert all(r['classification'] == 'HISTORICAL' and r['realtime'] is False
               for r in map(json.loads, raw.splitlines()))


@pytest.mark.parametrize('mode,failed,invokes', [
    ('bad_date','CONFIG_DATE_PARSE',0), ('changed_properties','EFFECTIVE_PROPERTIES',0),
    ('create_throw','REQUEST_CREATE',0), ('request_throw','REQUEST_INVOKE',1),
    ('empty','ROW_COUNT',1), ('inline_empty','ROW_COUNT',1),
    ('callback_error','CALLBACK_ERROR',1), ('wrong_callback','CALLBACK_IDENTITY',1),
    ('calendar_kind','CALENDAR_BEGIN_UTC_KIND',1), ('bar_kind','BAR_UTC_KIND',1),
    ('iterator_false','CALENDAR_ADVANCE_FALSE',1), ('bad_price','BAR_OHLCV',1),
    ('foreign_file','OUTPUT_OWNERSHIP',1), ('callback_properties','CALLBACK_PROPERTIES',1),
    ('terminated','TERMINATED_BEFORE_COMPLETION',1),
    ('terminate_before_request','TERMINATED_BEFORE_COMPLETION',0),
])
def test_failures_are_persistent_not_history_and_never_retry(harness, tmp_path, mode, failed, invokes):
    counts, rows = run(harness, tmp_path, mode)
    assert counts['invokes'] == invokes
    assert sum(r['stage'] == 'FAILED_'+failed for r in rows) == 1
    assert any(r['attempt_failed'] for r in rows)
    assert not any(r['capture_completed'] for r in rows)
    assert not list(tmp_path.glob('*.historical.jsonl')) and not list(tmp_path.glob('*.done*'))
    if mode in ('empty','inline_empty'):
        assert next(r for r in rows if r['stage'] == 'ROWS_RECEIVED')['returned_rows'] == 0
    if mode.endswith('_kind'):
        assert rows[-1]['observed_time_kind'] == 'Unspecified'
    if mode == 'request_throw':
        assert rows[-1]['exception_type'] == 'IOException'
        assert counts['disposes'] == 1
    if mode == 'foreign_file':
        assert (tmp_path/'foreign.txt').read_text() == 'untouched'


def test_disabled_defaults_no_request_or_io(harness, tmp_path):
    counts, rows = run(harness, tmp_path, 'defaults')
    assert counts['creates'] == counts['invokes'] == counts['disposes'] == 0
    assert rows == [] and list(tmp_path.iterdir()) == []


def test_pending_is_not_success_and_diagnostic_survives_process_end(harness, tmp_path):
    counts, rows = run(harness, tmp_path, 'pending')
    assert counts['invokes'] == 1 and counts['disposes'] == 0
    assert not any(r['capture_completed'] or r['attempt_failed'] for r in rows)
    assert 'REQUEST_SUBMITTED' in [r['stage'] for r in rows]
    assert 'CALLBACK_ENTERED' not in [r['stage'] for r in rows]
    assert not list(tmp_path.glob('*.historical.jsonl'))


@pytest.mark.parametrize('reload_kind', ['indicator','chart'])
def test_reload_requires_fresh_directory_and_never_overwrites(harness, tmp_path, reload_kind):
    first = tmp_path/'first'; second = tmp_path/'second'
    run(harness, first, 'success')
    before = {p.name:p.read_bytes() for p in first.iterdir()}
    counts, _ = run(harness, first, 'success')
    assert counts['creates'] == counts['invokes'] == 0
    assert before == {p.name:p.read_bytes() for p in first.iterdir()}
    counts, _ = run(harness, second, 'success')
    assert counts['invokes'] == 1


def test_marker_write_failure_prevents_request(harness, tmp_path):
    # Existing entry is an unambiguous ownership/writability denial, without changing Windows ACLs.
    (tmp_path/'historical-diagnostic.jsonl').mkdir()
    process = subprocess.run([str(harness),'success',str(tmp_path)], capture_output=True, text=True, timeout=15)
    assert process.returncode == 0
    counts = json.loads(process.stdout)
    assert counts['invokes'] == counts['creates'] == 0
    assert (tmp_path/'historical-diagnostic.jsonl').is_dir()


def test_diagnostic_bytes_are_not_certification(harness, tmp_path):
    run(harness, tmp_path, 'pending')
    raw = (tmp_path/'historical-diagnostic.jsonl').read_bytes()
    with pytest.raises((ValueError, KeyError)):
        certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())
    _, seal = pack(*native_shape())
    with pytest.raises(ValueError):
        build_bundle(raw, seal, TEMPLATE, SOURCE.read_bytes())


def test_reviewed_source_pins_preserve_legacy_and_reject_unknown():
    assert REVIEWED_EXPORTER_HASHES == frozenset((LEGACY,
        'e053d525a0b8e0098006c9ce28feeea4b1449c0835ce6dcaffd64a95c72b2da7', EXPORTER_SHA256))
    assert sha256(SOURCE.read_bytes().replace(b'\r\n',b'\n')).hexdigest() == EXPORTER_SHA256
    h, rows = native_shape()
    envelope = json.loads(bundle(h, rows))
    envelope['authored_sha256'] = LEGACY
    raw = json.dumps(envelope).encode()
    certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())
    envelope['authored_sha256'] = '0'*64
    raw = json.dumps(envelope).encode()
    with pytest.raises(ValueError):
        certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())
    history, seal = pack(h, rows)
    raw, _ = build_bundle(history, seal, TEMPLATE, SOURCE.read_bytes())
    assert json.loads(raw)['authored_sha256'] == EXPORTER_SHA256
    with pytest.raises(ValueError):
        build_bundle(history, seal, TEMPLATE, SOURCE.read_bytes()+b'//unreviewed')
