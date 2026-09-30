"""Actual exporter with synthetic iterator failures; no native capture or admission."""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_historical_diagnostics_sprint16ar1 import harness, run, CSC, ROOT, SOURCE


@pytest.mark.parametrize('mode,stage,result,bounds', [
    ('iterator_create_throw','CALENDAR_ITERATOR_CREATE_EXCEPTION','NOT_CALLED','NONE'),
    ('iterator_false','CALENDAR_ITERATION_COMPLETE','FALSE','NONE'),
    ('iterator_throw','CALENDAR_ADVANCE_EXCEPTION','NOT_RETURNED','NONE'),
    ('late_false','BAR_CLOCK_UTC_ATTESTATION','TRUE','COMPLETE'),
    ('late_throw','CALENDAR_ADVANCE_EXCEPTION','NOT_RETURNED','NONE'),
    ('begin_throw','CALENDAR_SESSION_BOUNDS_READ_EXCEPTION','TRUE','BEGIN'),
    ('end_throw','CALENDAR_SESSION_BOUNDS_READ_EXCEPTION','TRUE','END'),
    # The overlap guard executes after begin/end UTC validation.
    # Therefore the persisted diagnostic stage remains
    # CALENDAR_END_UTC_KIND even though both bounds are valid UTC.
    ('repeated','CALENDAR_END_UTC_KIND','TRUE','COMPLETE'),
    ('nonadvancing','CALENDAR_END_UTC_KIND','TRUE','COMPLETE'),
    ('end_before_begin','CALENDAR_INTERVAL_ORDER','TRUE','COMPLETE'),
    ('tiny_sessions','BAR_CLOCK_UTC_ATTESTATION','TRUE','COMPLETE'),
])
def test_failure_context_and_no_artifacts(harness, tmp_path, mode, stage, result, bounds):
    counts, rows = run(harness, tmp_path, mode)
    failed = rows[-1]
    assert failed['stage'] == 'FAILED_'+stage
    assert failed['exception_type'] == 'InvalidOperationException'
    assert failed['calendar_advance_result'] == result
    assert failed['calendar_bounds_read'] == bounds
    assert failed['returned_rows'] == 5 and failed['source_index'] == -1
    assert failed['capture_completed'] is False and failed['attempt_failed'] is True
    assert counts['creates'] == counts['invokes'] == counts['disposes'] == 1
    assert not list(tmp_path.glob('*.historical.jsonl')) and not list(tmp_path.glob('*.done*'))
    assert all(len(r['exception_message']) <= 80 for r in rows)
    assert all(len(json.dumps(r)) < 8192 for r in rows)
    if mode == 'late_throw':
        assert failed['calendar_iteration'] == 2
        assert failed['last_successful_query'] is not None
        assert failed['last_successful_session_begin_kind'] == 'Utc'
        assert failed['last_successful_session_end_kind'] == 'Utc'
        assert failed['session_begin'] is None and failed['session_end'] is None

    if mode == 'late_false':
        false_rows = [
            row
            for row in rows
            if row['stage'] == 'CALENDAR_ADVANCE_FALSE'
        ]
        assert len(false_rows) == 1
        assert false_rows[0]['calendar_iteration'] == 2
        assert failed['calendar_iteration'] == 15
        assert any(
            row['stage'] == 'CALENDAR_ITERATION_COMPLETE'
            for row in rows
        )
        assert failed['raw_clock_utc_attested'] is False

    if mode == 'iterator_false':
        assert failed['calendar_iteration'] == 15
        assert len([
            row
            for row in rows
            if row['stage'] == 'CALENDAR_ADVANCE_FALSE'
        ]) == 16
        assert not any(
            row['stage'] == 'CALENDAR_ITERATION_COMPLETE'
            for row in rows
        )

    if mode in ('repeated', 'nonadvancing'):
        # The failure is overlap/order, not a DateTimeKind rejection.
        assert failed['observed_time_kind'] == 'Utc'
        assert failed['session_begin_kind'] == 'Utc'
        assert failed['session_end_kind'] == 'Utc'
        assert failed['last_successful_session_end'] is not None
        assert failed['session_begin'] is not None
        assert (
            failed['session_begin']
            <= failed['last_successful_session_end']
        )

    if mode == 'end_throw':
        assert failed['session_begin'] is not None
        assert failed['session_end'] is None

    if mode == 'tiny_sessions':
        assert failed['calendar_iteration'] == 15
        assert len([
            row
            for row in rows
            if row['stage'] == 'CALENDAR_QUERY_BEGIN'
        ]) == 16
        assert any(
            row['stage'] == 'CALENDAR_ITERATION_COMPLETE'
            for row in rows
        )
        assert failed['raw_clock_utc_attested'] is False


def test_first_normal_end_weekend_maintenance_and_sunday(harness, tmp_path):
    _, rows = run(
        harness,
        tmp_path,
        'session_boundaries',
    )

    begins = [
        row
        for row in rows
        if row['stage'] == 'CALENDAR_QUERY_BEGIN'
    ]

    assert len(begins) == 16

    assert (
        begins[0]['calendar_query']
        == '2026-09-14T00:00:00.0000000Z'
    )

    assert (
        begins[-1]['calendar_query']
        == '2026-09-29T00:00:00.0000000Z'
    )

    assert all(
        row['include_end_time']
        and row['calendar_query_kind'] == 'Utc'
        for row in begins
    )

    assert all(
        row['requested_from_kind'] == 'Unspecified'
        and row['requested_through_kind'] == 'Unspecified'
        for row in begins
    )

    assert all(
        row['expected_trading_hours']
        == 'CME US Index Futures ETH'
        for row in begins
    )

    false_rows = [
        row
        for row in rows
        if row['stage'] == 'CALENDAR_ADVANCE_FALSE'
    ]

    assert [
        row['calendar_query']
        for row in false_rows
    ] == [
        '2026-09-19T00:00:00.0000000Z',
        '2026-09-20T00:00:00.0000000Z',
        '2026-09-26T00:00:00.0000000Z',
        '2026-09-27T00:00:00.0000000Z',
    ]

    intervals = [
        row
        for row in rows
        if row['stage']
        == 'CALENDAR_SESSION_BOUNDS_READ_SUCCESS'
    ]

    by_begin = {
        row['session_begin']:
            row['session_end']
        for row in intervals
    }

    assert (
        by_begin['2026-09-20T22:00:00.0000000Z']
        == '2026-09-21T21:00:00.0000000Z'
    )

    assert (
        '2026-09-18T22:00:00.0000000Z'
        not in by_begin
    )

    assert (
        '2026-09-19T22:00:00.0000000Z'
        not in by_begin
    )

    assert (
        by_begin['2026-09-16T22:00:00.0000000Z']
        == '2026-09-17T21:00:00.0000000Z'
    )

    assert rows[-1]['stage'] == 'SEAL_WRITTEN'
    assert rows[-1]['raw_clock_utc_attested'] is True

    complete = next(
        row
        for row in rows
        if row['stage'] == 'CALENDAR_ITERATION_COMPLETE'
    )

    assert (
        complete['calendar_query']
        == '2026-09-29T00:00:00.0000000Z'
    )


@pytest.mark.parametrize(
    'kind,accepted',
    [
        ('Utc', True),
        ('Unspecified', False),
        ('Local', False),
    ],
)
def test_query_kind_requires_utc_before_native_schedule(
    harness,
    tmp_path,
    kind,
    accepted,
):
    counts, rows = run(
        harness,
        tmp_path,
        'query_' + kind,
    )

    assert counts['creates'] == 0
    assert counts['invokes'] == 0
    assert counts['disposes'] == 0

    if accepted:
        assert counts['query_rejected'] is False

        queries = [
            row
            for row in rows
            if row['stage'] == 'CALENDAR_QUERY_BEGIN'
        ]

        assert queries
        assert all(
            row['calendar_query_kind'] == 'Utc'
            for row in queries
        )

        assert any(
            row['stage'] == 'CALENDAR_ITERATION_COMPLETE'
            for row in rows
        )

    else:
        assert counts['query_rejected'] is True

        assert not any(
            row['stage'] == 'CALENDAR_QUERY_BEGIN'
            for row in rows
        )

    assert not list(
        tmp_path.glob('*.historical.jsonl')
    )


def test_installed_sdk_compile(tmp_path):
    sdk=Path('C:/Program Files/NinjaTrader 8/bin')
    if not CSC.exists() or not (sdk/'NinjaTrader.Core.dll').exists():
        pytest.skip('Installed Windows NinjaTrader SDK required')
    shim=tmp_path/'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs=[sdk/'NinjaTrader.Core.dll',sdk/'NinjaTrader.Gui.dll',CSC.parent/'WPF/WindowsBase.dll',
          'System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Core.dll']
    result=subprocess.run([str(CSC),'/nologo','/target:library','/out:'+str(tmp_path/'HistoricalBootstrap.dll'),
        *['/r:'+str(p) for p in refs],str(SOURCE),str(shim)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.fixture(scope='module')
def baseline_harness(tmp_path_factory):
    folder=tmp_path_factory.mktemp('r1-baseline')
    source=folder/'Baseline.cs'
    source.write_bytes(subprocess.check_output(['git','show',
        '97c0eb3fa899a7fb47096a48fad76f917df5b91c:integrations/ninjatrader/ArmsHistoricalBootstrapV1.cs'],
        cwd=ROOT, stderr=subprocess.PIPE))
    target=folder/'baseline.exe'
    result=subprocess.run([str(CSC),'/nologo','/target:exe','/out:'+str(target),
        '/r:System.ComponentModel.DataAnnotations.dll','/r:System.Web.Extensions.dll',str(source),
        str(ROOT/'backend/tests/fixtures/historical_diagnostics_harness_sprint16ar1.cs')],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    return target


@pytest.mark.parametrize('mode',['success'])
def test_baseline_admission_and_payload_parity(harness, baseline_harness, tmp_path, mode):
    outputs=[]
    for name,exe in [('before',baseline_harness),('after',harness)]:
        folder=tmp_path/name
        counts,_=run(exe,folder,mode)
        assert counts['invokes']==1
        files=list(folder.glob('*.historical.jsonl'))
        rows=[] if not files else [json.loads(line) for line in files[0].read_bytes().splitlines()]
        for row in rows: row.pop('dataset')
        outputs.append(rows)
    assert outputs[0]==outputs[1]
