"""Actual exporter with synthetic iterator failures; no native capture or admission."""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_historical_diagnostics_sprint16ar1 import harness, run, CSC, ROOT, SOURCE


@pytest.mark.parametrize('mode,stage,result,bounds', [
    ('iterator_create_throw','CALENDAR_ITERATOR_CREATE_EXCEPTION','NOT_CALLED','NONE'),
    ('iterator_false','CALENDAR_ADVANCE_FALSE','FALSE','NONE'),
    ('iterator_throw','CALENDAR_ADVANCE_EXCEPTION','NOT_RETURNED','NONE'),
    ('late_false','CALENDAR_ADVANCE_FALSE','FALSE','NONE'),
    ('late_throw','CALENDAR_ADVANCE_EXCEPTION','NOT_RETURNED','NONE'),
    ('begin_throw','CALENDAR_SESSION_BOUNDS_READ_EXCEPTION','TRUE','BEGIN'),
    ('end_throw','CALENDAR_SESSION_BOUNDS_READ_EXCEPTION','TRUE','END'),
    ('repeated','CALENDAR_INTERVAL_ORDER','TRUE','COMPLETE'),
    ('nonadvancing','CALENDAR_INTERVAL_ORDER','TRUE','COMPLETE'),
    ('end_before_begin','CALENDAR_INTERVAL_ORDER','TRUE','COMPLETE'),
    ('tiny_sessions','CALENDAR_INTERVAL_LIMIT','TRUE','COMPLETE'),
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
    if mode.startswith('late_'):
        assert failed['calendar_iteration'] == 2
        assert failed['last_successful_query'] is not None
        assert failed['last_successful_session_begin_kind'] == 'Utc'
        assert failed['last_successful_session_end_kind'] == 'Utc'
        assert failed['session_begin'] is None and failed['session_end'] is None
    if mode == 'end_throw':
        assert failed['session_begin'] is not None and failed['session_end'] is None
    if mode == 'tiny_sessions':
        assert failed['calendar_iteration'] == 63
        assert len([r for r in rows if r['stage']=='CALENDAR_QUERY_BEGIN']) == 64
        assert not any(r['stage']=='CALENDAR_ITERATION_COMPLETE' for r in rows)


def test_first_normal_end_weekend_maintenance_and_sunday(harness, tmp_path):
    _, rows = run(harness, tmp_path, 'session_boundaries')
    begins = [r for r in rows if r['stage']=='CALENDAR_QUERY_BEGIN']
    advances = [r for r in rows if r['stage']=='CALENDAR_QUERY_ADVANCED']
    assert begins[0]['calendar_query'] == '2026-09-14T00:00:00.0000000Z'
    assert all(r['include_end_time'] and r['calendar_query_kind']=='Utc' for r in begins)
    assert all(r['requested_from_kind']=='Unspecified' and r['requested_through_kind']=='Unspecified' for r in begins)
    assert all(r['expected_trading_hours']=='CME US Index Futures ETH' for r in begins)
    # Preserve one-tick update exactly, including at the daily break.
    assert all(r['calendar_query'].replace('.0000001','.0000000') == r['last_successful_session_end'] for r in advances)
    intervals = [r for r in rows if r['stage']=='CALENDAR_SESSION_BOUNDS_READ_SUCCESS']
    by_begin={r['session_begin']:r['session_end'] for r in intervals}
    assert by_begin['2026-09-20T22:00:00.0000000Z']=='2026-09-21T21:00:00.0000000Z'
    assert '2026-09-18T22:00:00.0000000Z' not in by_begin
    assert '2026-09-19T22:00:00.0000000Z' not in by_begin
    assert by_begin['2026-09-16T22:00:00.0000000Z']=='2026-09-17T21:00:00.0000000Z'
    assert rows[-1]['stage']=='SEAL_WRITTEN'
    complete=next(r for r in rows if r['stage']=='CALENDAR_ITERATION_COMPLETE')
    assert complete['calendar_query'] >= '2026-09-29T00:00:00.0000000Z'


@pytest.mark.parametrize('kind', ['Utc','Unspecified','Local'])
def test_query_kind_is_observed_without_conversion(harness, tmp_path, kind):
    _, rows=run(harness,tmp_path,'query_'+kind)
    query=next(r for r in rows if r['stage']=='CALENDAR_QUERY_BEGIN')
    assert query['calendar_query_kind']==kind
    assert query['calendar_query'].startswith('2026-09-16T00:00:00.0000000')
    assert any(r['stage']=='CALENDAR_ITERATION_COMPLETE' for r in rows)
    assert not list(tmp_path.glob('*.historical.jsonl'))
    # This proves forwarding/diagnostics, not native SDK acceptance of these Kinds.


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
        '97c0eb3fa899a7fb47096a48fad76f917df5b91c:integrations/ninjatrader/ArmsHistoricalBootstrapV1.cs'],cwd=ROOT))
    target=folder/'baseline.exe'
    result=subprocess.run([str(CSC),'/nologo','/target:exe','/out:'+str(target),
        '/r:System.ComponentModel.DataAnnotations.dll','/r:System.Web.Extensions.dll',str(source),
        str(ROOT/'backend/tests/fixtures/historical_diagnostics_harness_sprint16ar1.cs')],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    return target


@pytest.mark.parametrize('mode',['success','session_boundaries','late_false','late_throw','repeated','tiny_sessions','calendar_kind'])
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
