"""R5.1 synthetic diagnostics; no native request or NinjaTrader assembly execution."""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_session_domain_probe_sprint16ar5 import binary, run, CSC
from tools.verify_session_domain_probe_v1 import verify_evidence


def sidecar(folder):
    raw = (folder / 'session-domain-coverage.jsonl').read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) <= 16 and len(raw) <= 32768
    assert max(map(len, raw.splitlines())) < 2048
    assert [r['sequence'] for r in rows] == list(range(len(rows)))
    assert all(r['classification'] == 'FORENSIC_ONLY' and not r['runtime_admission']
               and not r['certification_evidence'] for r in rows)
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw
    assert all(r['native_calls'] == r['iterator_count'] == 0 for r in rows)
    return rows, raw


@pytest.mark.parametrize('mode,guard,index,previous_index', [
    ('bad_time_kind', 'COVERAGE_KIND_NOT_UTC', 0, -1),
    ('coverage_local', 'COVERAGE_KIND_NOT_UTC', 2, 1),
    ('bad_order', 'COVERAGE_NON_INCREASING', 2, 1),
    ('coverage_duplicate', 'COVERAGE_NON_INCREASING', 2, 1),
    ('coverage_seconds', 'COVERAGE_NOT_MINUTE_ALIGNED', 2, 1),
    ('coverage_ticks', 'COVERAGE_NOT_MINUTE_ALIGNED', 2, 1),
    ('too_many_dates', 'COVERAGE_DATE_BUCKET_LIMIT', 32, 31),
    ('coverage_count_mutation', 'COVERAGE_FINAL_COUNT_CHANGED', 4, 4),
    ('coverage_first_throw', 'COVERAGE_GET_FIRST_FAILED', 0, -1),
    ('coverage_last_throw', 'COVERAGE_GET_LAST_FAILED', 4, -1),
    ('coverage_time_throw', 'COVERAGE_GET_TIME_FAILED', 2, 1),
])
def test_specific_failure_context_no_matrix_or_seal(binary, tmp_path, mode, guard, index, previous_index):
    counts, main, raw, seal = run(binary, tmp_path, mode)
    rows, forensic_raw = sidecar(tmp_path)
    failure = rows[-1]
    assert failure['stage'] == 'COVERAGE_GUARD_FAILED'
    assert failure['guard'] == guard and failure['index'] == index
    assert failure['last_processed_index'] == previous_index
    assert failure['exception_type'] == 'InvalidOperationException'
    assert failure['exception_message'] == 'REDACTED_NATIVE_OR_GUARD_MESSAGE'
    assert counts['native_calls'] == counts['iterator_creates'] == 0
    assert counts['request_disposes'] == counts['request_invokes'] == 1
    assert main[-1]['stage'] == 'ATTEMPT_FAILED' and seal is None
    assert not any(r['stage'] == 'COVERAGE_COMPLETE' for r in rows)
    assert len(main) + len(rows) <= 96 and len(raw) + len(forensic_raw) <= 262144
    with pytest.raises(ValueError): verify_evidence(raw, seal)
    assert failure['returned_rows'] == (33 if mode == 'too_many_dates' else 5)
    if mode == 'coverage_first_throw':
        assert failure['first'] is failure['current'] is failure['last'] is None
    else:
        assert failure['first'] is not None
    if mode in ('coverage_last_throw', 'coverage_time_throw'):
        assert failure['current'] is None and failure['current_kind'] == 'NONE'
    if index == 2:
        assert failure['previous'] == failure['last_processed'] == '2026-09-16T12:01:00.0000000Z'
    if mode == 'bad_time_kind':
        assert failure['current_kind'] == 'Unspecified' and failure['utc_date'] is None
        assert failure['previous_kind'] == 'Unspecified'
    if mode == 'coverage_local': assert failure['current_kind'] == 'Local' and failure['utc_date'] is None
    if mode == 'coverage_duplicate': assert failure['current'] == failure['previous']
    if mode == 'bad_order': assert failure['current'] == '2026-09-16T11:59:00.0000000Z'
    if mode == 'coverage_seconds':
        assert failure['current'] == '2026-09-16T12:02:01.0000000Z'
        assert failure['seconds'] == 1 and failure['ticks_remainder_minute'] == 10000000
    if mode == 'coverage_ticks':
        assert failure['current'] == '2026-09-16T12:02:00.0000001Z'
        assert failure['milliseconds'] == failure['seconds'] == 0
        assert failure['ticks_remainder_second'] == failure['ticks_remainder_minute'] == 1
    if mode == 'too_many_dates': assert failure['date_buckets'] == 32
    if mode == 'coverage_count_mutation': assert failure['observed_count'] == 4


@pytest.mark.parametrize('mode,count', [('maximum',5), ('large',4503), ('coverage_maximum',10002)])
def test_success_bounded_progress_and_unchanged_verifier(binary, tmp_path, mode, count):
    counts, main, raw, seal = run(binary, tmp_path, mode)
    result = verify_evidence(raw, seal)
    rows, forensic_raw = sidecar(tmp_path)
    assert result['coverage']['returned_rows'] == count and counts['native_calls'] > 0
    assert [r['stage'] for r in rows[:3]] == ['COVERAGE_BEGIN','COVERAGE_FIRST_OBSERVED','COVERAGE_LAST_OBSERVED']
    assert rows[-1]['stage'] == 'COVERAGE_COMPLETE'
    assert rows[-1]['last_processed_index'] == count - 1
    assert rows[-1]['last_processed'] == result['coverage']['last']
    assert rows[-1]['observed_count'] == count
    assert [r['index'] for r in rows if r['stage'] == 'COVERAGE_CHECKPOINT'] == list(range(0,count,1024))
    assert len(main)+len(rows) <= 96 and len(raw)+len(forensic_raw) <= 262144
    assert rows[3]['previous_kind'] == 'Unspecified'  # MinValue guard passed without relabeling.
    assert rows[3]['session_classification'] == 'SESSION' and rows[3]['session_bin'] == 2


def test_datetime_kind_comparison_on_installed_framework(tmp_path):
    code = tmp_path / 'Comparison.cs'
    code.write_text('''using System; class Comparison { static int Main() {
        var utc = new DateTime(2026,9,16,12,0,0,DateTimeKind.Utc);
        if (!(utc > DateTime.MinValue)) return 1;
        if (utc > DateTime.SpecifyKind(utc,DateTimeKind.Unspecified)) return 2;
        if (DateTime.SpecifyKind(DateTime.MinValue,DateTimeKind.Utc) > DateTime.MinValue) return 3;
        return 0; } }''')
    exe = tmp_path / 'Comparison.exe'
    built = subprocess.run([str(CSC),'/nologo','/out:'+str(exe),str(code)],capture_output=True,text=True)
    assert built.returncode == 0, built.stdout+built.stderr
    assert subprocess.run([str(exe)],capture_output=True).returncode == 0
