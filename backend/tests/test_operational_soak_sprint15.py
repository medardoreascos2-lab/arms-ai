"""Offline launcher boundaries; no native activation or account access."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import socket
import pytest
from backend.backtesting import operational_paper_soak_v1 as cli
from backend.config.api_settings import APISettings
from backend.tests.test_native_harness_preflight_sprint13 import api_settings


def spec():
    return json.loads(Path('backend/tests/native_capture_spec_sprint13.json').read_text())


@pytest.mark.parametrize('at,valid',[
    ('2026-09-21T02:00:00+00:00',True),('2026-09-20T23:59:59+00:00',False),
    ('2026-09-28T00:00:00+00:00',False),('2026-09-21T20:00:00+00:00',False),
    ('2026-09-21T21:30:00+00:00',False),('2026-09-26T12:00:00+00:00',False)])
def test_full_window_and_calendar_runway(api_settings,at,valid):
    now=datetime.fromisoformat(at)
    gate=cli.make_authorities(spec(),APISettings(),lambda:now)
    if valid:
        cli.validate_runway(gate,now,7680)
        cli.validate_runway(gate,now,0)
    else:
        with pytest.raises(ValueError): cli.validate_runway(gate,now,7680)


def test_fresh_selection_excludes_all_old_evidence(tmp_path):
    old=tmp_path/'00000000-0000-4000-8000-000000000001.jsonl'
    old.write_text('OLD')
    baseline=set(tmp_path.glob('*.jsonl'))
    assert cli.fresh_candidate(tmp_path,baseline) is None
    sidecar=tmp_path/'00000000-0000-4000-8000-000000000002.connection.jsonl'
    sidecar.write_text('NEW SIDECAR')
    assert cli.fresh_candidate(tmp_path,baseline) is None
    fresh=tmp_path/'00000000-0000-4000-8000-000000000002.jsonl'
    fresh.write_text('NEW')
    assert cli.fresh_candidate(tmp_path,baseline)==fresh
    (tmp_path/'00000000-0000-4000-8000-000000000003.jsonl').write_text('AMBIGUOUS')
    with pytest.raises(ValueError): cli.fresh_candidate(tmp_path,baseline)
    assert old.read_text()=='OLD'


def test_existing_run_is_not_modified_even_on_preflight_failure(tmp_path,monkeypatch):
    run=tmp_path/'existing'; run.mkdir()
    (run/'report.json').write_text('PRESERVE')
    monkeypatch.setattr('sys.argv',['soak','--spec','absent','--directory',str(tmp_path),
        '--run-directory',str(run),'--preflight-only'])
    with pytest.raises(SystemExit): cli.main()
    assert list(run.iterdir())==[run/'report.json']
    assert (run/'report.json').read_text()=='PRESERVE'


def test_no_implicit_risk_profile_or_watcher_when_configuration_missing(tmp_path,monkeypatch):
    for key in cli.RISK_KEYS: monkeypatch.delenv(key,raising=False)
    run=tmp_path/'new'
    monkeypatch.setattr('sys.argv',['soak','--spec','absent','--directory',str(tmp_path),
        '--run-directory',str(run),'--preflight-only'])
    with pytest.raises(SystemExit): cli.main()
    assert not run.exists()


@pytest.mark.parametrize('activate',[True,False])
def test_bounded_launcher_fresh_selection_report_and_expiry(api_settings,tmp_path,monkeypatch,activate):
    # Synthetic virtual scheduling only. Actual parser/calendar/runtime are used;
    # no native platform, external network or live clock is substituted in production.
    from datetime import timedelta
    from fastapi.testclient import TestClient
    import uvicorn
    elapsed=[0.0]
    origin=datetime(2026,9,21,0,0,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return origin+timedelta(seconds=elapsed[0])
    monkeypatch.setattr(cli,'datetime',Clock)
    reviewed=spec()
    spec_path=tmp_path/'spec.json'; spec_path.write_text(json.dumps(reviewed))
    monkeypatch.setattr(cli,'review',lambda *args:reviewed)
    directory=tmp_path/'evidence'; directory.mkdir()
    old=directory/'00000000-0000-4000-8000-000000000001.jsonl'; old.write_text('PRESERVED')
    session='00000000-0000-4000-8000-000000000002'
    market=directory/(session+'.jsonl')
    seq=[0]
    def emit(kind,payload):
        with market.open('a') as stream:
            stream.write(json.dumps(dict(schema='arms.nt.market.v1',session=session,sequence=seq[0],
                kind=kind,event_time=Clock.now().isoformat(),payload=payload))+'\n')
        seq[0]+=1
    def schedule(_):
        elapsed[0]+=1
        if not activate: return
        if not market.exists():
            payload=dict(provider='Provider31',contract='NQ DEC26',expiry='2026-12-01',instrument='NQ',
                tick_size=.25,point_value=20,timeframe='1m',trading_hours_template='CME US Index Futures ETH',
                source_timezone='UTC',bar_label='CLOSE',realtime=True,read_only=True)
            emit('HELLO',payload)
            connection=dict(same_source=True,source_present=True,callback_present=True,source_snapshot_stable=True,
                callback_provider='Provider31',source_provider='Provider31',decision='CONTINUE',
                callback_previous_price_status='Connecting',callback_previous_connection_status='Connecting')
            for k in ('callback_price_status','callback_connection_status','source_price_status',
                      'source_connection_status','source_price_status_after','source_connection_status_after'):
                connection[k]='Connected'
            market.with_suffix('.connection.jsonl').write_text(json.dumps(dict(
                schema='arms.nt.connection-diagnostic.v1',session=session,sequence=0,kind='CONNECTION_STATUS',
                event_time=Clock.now().isoformat(),callback_received_time=Clock.now().isoformat(),payload=connection))+'\n')
        elif elapsed[0]%60==0:
            emit('CLOSED',dict(bar_time=Clock.now().isoformat(),open=10000,high=10000,low=10000,close=10000,volume=10))
        elif elapsed[0]%5==0: emit('HEARTBEAT',dict(connected=True))
    monkeypatch.setattr(cli,'time',SimpleNamespace(monotonic=lambda:elapsed[0],sleep=schedule))
    published=[]
    class Server:
        def __init__(self,config): self.config=config; self.should_exit=False
        def run(self,**kwargs): pass
    class Worker:
        def __init__(self,target,**kwargs): self.server=target.__self__
        def start(self):
            with TestClient(self.server.config.app) as client:
                published.append(client.get('/api/v2/backtesting/dashboard').json()['paper_research'])
        def is_alive(self): return True
        def join(self,**kwargs): pass
    monkeypatch.setattr(uvicorn,'Server',Server)
    monkeypatch.setattr(cli,'Thread',Worker)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
    run=tmp_path/'run'
    argv=['--spec',str(spec_path),'--directory',str(directory),'--run-directory',str(run),
        '--seconds','65','--activation-seconds','30','--port',str(port),'--enable-local-paper']
    if activate:
        cli.main(argv)
        report=json.loads((run/'report.json').read_text())
        assert report['canonical_candles']==1
        assert report['paper_trades_opened']==report['net_pnl']==0
        assert not any(report['reconciliation'].values())
        assert report['final_snapshot']['paper_ready'] is False
        assert report['native_session']==session
        assert published[0]['execution_mode']=='LOCAL_PAPER'
        assert report['broker_order_calls']==0
    else:
        with pytest.raises(SystemExit): cli.main(argv)
        assert (run/'failure.json').exists()
        assert not (run/'active.json').exists()
        assert not (run/'paper.sqlite').exists()
    assert json.loads((run/'cleanup.json').read_text())['status']=='PASS'
    assert old.read_text()=='PRESERVED'
    assert old.name in json.loads((run/'waiting.json').read_text())['excluded_files']
