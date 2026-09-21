"""Synthetic protocol/decision witnesses only; no native execution authority."""
from datetime import timedelta
import json
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from backend.backtesting.operational_paper_v1 import OperationalPaperV1
from backend.api.operational_paper_app_v1 import create_operational_paper_app_v1
from backend.config.api_settings import APISettings
from backend.services.economic_news_runtime_provider_v2 import EconomicNewsRuntimeProviderV2
from backend.services.certified_economic_news_snapshot_v2 import CertifiedEconomicNewsSnapshotV2
from backend.tests.test_ninjatrader_market_sprint11 import setup, hello, frame, bar, SESSION
from backend.tests.test_current_paper_sprint10 import START, config, api_settings
from backend.tests.test_paper_runtime_sprint08 import witness, fill_count


def make(tmp_path, news=True, enabled=True):
    reader, clock = setup(tmp_path)
    snapshot = CertifiedEconomicNewsSnapshotV2(snapshot_version='SYNTHETIC_NEWS', generated_at=START,
        coverage_start=START,coverage_end=START+timedelta(days=1),high_impact_events=[]) if news else None
    op = OperationalPaperV1(validation_service=reader.service,path=reader.path,provider=reader.provider,
        expiry=reader.expiry,config=config(),settings=APISettings(),state_path=tmp_path/'operational.sqlite',
        calendar_check=lambda now: None, news_provider=EconomicNewsRuntimeProviderV2(snapshot=snapshot),
        enable_local_paper=enabled)
    payload = dict(same_source=True,source_present=True,callback_present=True,source_snapshot_stable=True,
        callback_provider=reader.provider,source_provider=reader.provider,decision='CONTINUE')
    for key in ('source_price_status','source_connection_status','source_price_status_after',
                'source_connection_status_after','callback_price_status','callback_connection_status'):
        payload[key]='Connected'
    for key in ('callback_previous_price_status','callback_previous_connection_status'):
        payload[key]='Connecting'
    sidecar=dict(schema='arms.nt.connection-diagnostic.v1',session=SESSION,sequence=0,
        kind='CONNECTION_STATUS',event_time=clock[0].isoformat(),callback_received_time=clock[0].isoformat(),
        payload=payload)
    reader.path.with_suffix('.connection.jsonl').write_text(json.dumps(sidecar)+'\n')
    deliver(op,hello(op.reader,clock))
    return op, clock


def deliver(op, event):
    with op.reader.path.open('a') as stream:
        stream.write(json.dumps(event)+'\n')
    return op.poll()


def advance(op, clock, index, **changes):
    target=START+timedelta(minutes=index+1)
    while clock[0]<target:
        clock[0]=min(clock[0]+timedelta(seconds=5),target)
        deliver(op,frame(clock,op.reader.sequence+1))
    return deliver(op,bar(clock,op.reader.sequence+1,**changes))


@pytest.mark.parametrize('exit_price,pnl', [(10060,1170),(9970,-630)])
def test_protocol_to_local_lifecycle_reconciliation(api_settings,tmp_path,exit_price,pnl):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    witness(op.runtime)
    for i in range(1,8):
        advance(op,clock,i,high=max(10000,exit_price) if i==5 else 10000,
                low=min(10000,exit_price) if i==5 else 10000)
    report=op.report()
    assert report['paper_trades_opened']==report['paper_trades_closed']==1
    assert report['net_pnl']==pnl
    assert not any(report['reconciliation'].values())
    assert fill_count(op.runtime)==1 and fill_count(op.validation._runtime)==0
    assert op.runtime._db.execute('SELECT count(*) FROM operational_decisions').fetchone()[0]==8
    assert op.runtime._db.execute("SELECT count(*) FROM operational_decisions WHERE phase='INFLIGHT'").fetchone()[0]==0
    assert report['final_snapshot']['sim_execution_authority']=='DISABLED'
    assert report['broker_order_calls']==0
    op.close()


@pytest.mark.parametrize('news,enabled',[(False,True),(True,False)])
def test_news_and_intent_block_all_entry_side_effects(api_settings,tmp_path,news,enabled):
    op,clock=make(tmp_path,news,enabled)
    advance(op,clock,0)
    witness(op.runtime)
    for i in range(1,8): advance(op,clock,i)
    assert fill_count(op.runtime)==len(op.runtime._paper.runtime.entries)==0
    assert op.report()['net_pnl']==0
    assert op.get_snapshot()['paper_ready'] is False
    op.close()


@pytest.mark.parametrize('case',['future','stale','duplicate','gap','calendar','sidecar','malformed'])
def test_invalid_input_latches_without_mutating_operational_account(api_settings,tmp_path,case):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    before=op.runtime.get_snapshot()
    event=bar(clock,op.reader.sequence+1)
    if case=='future': event['payload']['bar_time']=(clock[0]+timedelta(minutes=1)).isoformat()
    elif case=='stale': event['event_time']=(clock[0]-timedelta(seconds=31)).isoformat()
    elif case=='duplicate': event['sequence']=op.reader.sequence
    elif case=='gap': event['sequence']+=1
    elif case=='calendar': op.calendar_check=Mock(side_effect=ValueError('unknown calendar'))
    elif case=='sidecar': op.reader.path.with_suffix('.connection.jsonl').write_text('{}\n')
    else: event['schema']='bad'
    with pytest.raises(ValueError): deliver(op,event)
    assert op.runtime.get_snapshot()['account_overview']==before['account_overview']
    assert fill_count(op.runtime)==0
    assert op.get_snapshot()['paper_ready'] is False
    with pytest.raises(RuntimeError): op.poll()
    op.close()


def test_dashboard_reads_do_not_ingest_or_execute(api_settings,tmp_path,monkeypatch):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    monkeypatch.setattr(op,'poll',Mock(side_effect=AssertionError('read consumed')))
    monkeypatch.setattr(op.runtime,'ingest',Mock(side_effect=AssertionError('read ingested')))
    before=op.runtime._db.total_changes
    with TestClient(create_operational_paper_app_v1(runtime=op)) as client:
        for _ in range(3):
            data=client.get('/api/v2/backtesting/dashboard').json()['paper_research']
            assert data['execution_mode']=='LOCAL_PAPER'
            assert data['external_order_authority'] is False
            assert data['ninjatrader_account_access'] is False
            assert data['broker_order_calls']==0
            assert data['canonical_timeframe']=='1m'
            assert data['journal_status']=='RECONCILED'
            assert data['local_account_status']=='AVAILABLE'
            assert 'fault_detail' not in data
        assert client.post('/api/v2/paper/enable').status_code==404
    assert op.runtime._db.total_changes==before
    op.close()


def test_real_detector_htf_soak_no_forced_trades(api_settings,tmp_path):
    op,clock=make(tmp_path)
    for i in range(120): advance(op,clock,i)
    snap=op.get_snapshot()
    assert snap['htf_emitted']=={'15m':8,'1h':2}
    assert op.report()['hold_count']>0
    assert op.report()['paper_trades_opened']==0
    assert not any(op.reconcile().values())
    op.close()


@pytest.mark.parametrize('kind',['account','risk_gate','news_event'])
def test_risk_and_exact_news_block_precede_all_local_fill_effects(api_settings,tmp_path,kind):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    witness(op.runtime,entries=tuple(range(2,10)))
    r=op.runtime._paper.runtime
    if kind=='account':
        state=r.account.capture_state()
        state['state'].update(trading_blocked=True,blocking_reasons=['SYNTHETIC_DAILY_LOSS_BLOCK'])
        r.account.restore_state(snapshot=state)
    elif kind=='risk_gate':
        r.lifecycle.execution_risk_gate_v1.evaluate_trade=Mock(return_value={'execution':'BLOCKED'})
    else:
        op.news=EconomicNewsRuntimeProviderV2(snapshot=CertifiedEconomicNewsSnapshotV2(
            snapshot_version='SYNTHETIC_EVENTS',generated_at=START,coverage_start=START,
            coverage_end=START+timedelta(days=1),
            high_impact_events=[START+timedelta(minutes=i+1) for i in range(8)]))
    for i in range(1,8): advance(op,clock,i)
    assert fill_count(op.runtime)==0
    assert not r.entries and not r.completed and not r.journal.trades
    assert not any(op.reconcile().values())
    op.close()


def test_news_blocks_entry_but_preserves_existing_position_exit(api_settings,tmp_path):
    op,clock=make(tmp_path)
    advance(op,clock,0); witness(op.runtime)
    for i in range(1,5): advance(op,clock,i)
    assert fill_count(op.runtime)==1
    op.news=EconomicNewsRuntimeProviderV2()
    advance(op,clock,5,high=10060)
    assert op.report()['paper_trades_closed']==1
    assert op.report()['net_pnl']==1170
    assert not any(op.reconcile().values())
    op.close()


def test_recovery_namespace_never_reused(api_settings,tmp_path):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    op.close()
    before=(tmp_path/'operational.sqlite').read_bytes()
    fresh=tmp_path/'fresh'; fresh.mkdir()
    reader,_=setup(fresh)
    with pytest.raises(ValueError,match='RECOVERY_REQUIRED'):
        OperationalPaperV1(validation_service=reader.service,path=reader.path,provider=reader.provider,
            expiry=reader.expiry,config=config(),settings=APISettings(),state_path=tmp_path/'operational.sqlite',
            calendar_check=lambda now: None,news_provider=EconomicNewsRuntimeProviderV2())
    assert (tmp_path/'operational.sqlite').read_bytes()==before


def test_trace_write_failure_is_durable_uncertainty_and_no_reexecution(api_settings,tmp_path):
    op,clock=make(tmp_path)
    advance(op,clock,0); witness(op.runtime)
    for i in range(1,4): advance(op,clock,i)
    op.runtime._db.execute("CREATE TRIGGER fail_trace BEFORE UPDATE ON operational_decisions BEGIN SELECT RAISE(FAIL, 'SYNTHETIC_FAILURE'); END")
    op.runtime._db.commit()
    with pytest.raises(ValueError): advance(op,clock,4)
    assert fill_count(op.runtime)==1
    assert op.runtime._db.execute("SELECT count(*) FROM operational_decisions WHERE phase='INFLIGHT'").fetchone()[0]==1
    assert op.reconcile()['unexplained_differences']==1
    with pytest.raises(RuntimeError): op.poll()
    assert fill_count(op.runtime)==1
    op.close()


def test_same_canonical_observation_cannot_book_twice(api_settings,tmp_path):
    op,clock=make(tmp_path)
    advance(op,clock,0); witness(op.runtime)
    for i in range(1,5): advance(op,clock,i)
    row=op.runtime._paper.runtime.current
    before=op.runtime.get_snapshot()
    for _ in range(3):
        assert op.runtime.ingest(row,received_at=row.received_at)==before
    assert fill_count(op.runtime)==1
    assert not any(op.reconcile().values())
    op.close()


def test_validation_cleanup_still_runs_when_paper_shutdown_fails(api_settings,tmp_path,monkeypatch):
    op,clock=make(tmp_path)
    advance(op,clock,0)
    shutdown=op.runtime.shutdown
    def fail():
        shutdown()
        raise OSError('SYNTHETIC_SHUTDOWN_FAILURE')
    monkeypatch.setattr(op.runtime,'shutdown',fail)
    with pytest.raises(OSError): op.close()
    assert op.reader.stopped and op.validation._stopped
    assert op.reader._file is None
