"""Synthetic fault injection, not new native certification or UTC attestation."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
from backend.market_data.analysis_time_profile_v1 import MarketAnalysisTimeProfileV1, EXPORTER_SHA256
from backend.tests.test_loaded_calendar_sprint13 import witness  # noqa: F401
from tools.native_timing_witness_v1 import IDENTITY, ticks


SESSION='dc953c66-e306-4f17-9436-0b227dd36a58'
BASE=datetime(2026,9,21,14,tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def forbid_account_and_execution_construction(monkeypatch):
    from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1, _CurrentAccountingV1
    from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
    from backend.services.live_market_analysis_service import LiveMarketAnalysisService
    guards=[]
    for cls in (CurrentPaperServiceV1,_CurrentAccountingV1,PaperBrokerConnectorV2,LiveMarketAnalysisService):
        guard=Mock(side_effect=AssertionError('forbidden account or execution construction'))
        monkeypatch.setattr(cls,'__init__',guard);guards.append(guard)
    yield
    for guard in guards:guard.assert_not_called()


def encode(value):
    return json.dumps(value,separators=(',',':')).encode()


def stamp(value):
    return value.strftime('%Y-%m-%dT%H:%M:%S.')+f'{value.microsecond:06d}0Z'


class Stream:
    def __init__(self, **overrides):
        self.qpc=1000;self.seq=0;self.pairseq=0;self.index=0;self.wall_offset=timedelta()
        self.epoch='synthetic-same-host-epoch'
        options=dict(session=SESSION,epoch=self.epoch,frequency=1000,reader_start_qpc=1000,
                     qpc_clock=lambda:(self.epoch,1000,self.qpc),heartbeat_seconds=15,
                     maximum_processing_seconds=90,exporter_sha256=EXPORTER_SHA256)
        options.update(overrides)
        self.profile=MarketAnalysisTimeProfileV1(**options)
        self.send('HELLO',dict(provider='Provider31',contract='NQ DEC26',expiry='2026-12-01',instrument='NQ',
            tick_size=.25,point_value=20,timeframe='1m',trading_hours_template='CME US Index Futures ETH',
            source_timezone='UTC',bar_label='CLOSE',realtime=True,read_only=True))

    def pair(self, qpc):
        utc=stamp(BASE+timedelta(milliseconds=qpc)+self.wall_offset)
        return dict(qpc_before=qpc,qpc_after=qpc+1,utc=utc,utc_ticks=ticks(utc))

    def send(self,kind,payload,pair=None):
        row=dict(schema='arms.nt.market.v1',session=SESSION,sequence=self.seq,
                 event_time=pair['emission']['utc'] if pair else stamp(BASE),kind=kind,payload=payload)
        raw=encode(row)
        if pair:
            pair['canonical_sha256']=sha256(raw).hexdigest()
        self.profile.accept(raw,encode(pair) if pair else None,receipt_qpc=self.qpc)
        self.seq+=1
        return raw,encode(pair) if pair else None

    def bar(self,kind,index,callback):
        self.qpc+=10
        ago=int(kind=='CLOSED');bar_index=index-ago
        label=stamp(BASE+timedelta(minutes=bar_index))
        p=dict(schema='arms.nt.production-timing.v1',session=SESSION,pair_sequence=self.pairseq,
               canonical_sequence=self.seq,canonical_sha256='',kind=kind,source_bar_label=label,
               callback=callback,emission=self.pair(self.qpc-2),qpc_frequency=1000,
               callback_index=index,bar_index=bar_index,bars_ago=ago,state='Realtime',bars_in_progress=0,
               first_tick=True,observation_only=True,runtime_admission=False,**IDENTITY)
        value=20000+bar_index*.25
        result=self.send(kind,dict(bar_time=label,open=value,high=value+1,low=value-1,close=value+.25,volume=10),p)
        self.pairseq+=1
        return result

    def boundary(self):
        if self.index:
            for _ in range(12):
                self.qpc+=5000
                self.send('HEARTBEAT',{'connected':True})
        callback=self.pair(self.qpc+1)
        if self.index>=2:self.bar('CLOSED',self.index,callback)
        result=self.bar('FORMING',self.index,callback)
        self.index+=1
        return result

    def fill(self,count):
        for _ in range(count):self.boundary()
        return self.profile.snapshot()


def assert_disabled(snapshot):
    assert snapshot['paper_entry_authority']==snapshot['sim_execution_authority']=='DISABLED'
    assert snapshot['live_authority'] is False
    assert snapshot['ninjatrader_account_access'] is False
    assert snapshot['paper_trades_opened']==snapshot['broker_order_calls']==0
    assert snapshot['session_status']==snapshot['absolute_time_authority']=='UNKNOWN'
    assert snapshot['source_time_recency']==snapshot['absolute_market_recency']=='UNKNOWN'
    assert snapshot['news_authority']=='UNCERTIFIED'
    assert snapshot['decision_status']=='NOT_PROJECTED'
    assert snapshot['data_freshness']=='NOT_ASSERTED'


def test_healthy_stream_only_exposes_supported_source_relative_properties():
    stream=Stream();snapshot=stream.fill(62)
    assert snapshot['market_stream']=='LIVE'
    assert snapshot['analysis_status']=='SOURCE_RELATIVE_ONLY'
    for key in ('1m','15m','1h','trend','structure','liquidity','fvg'):
        assert snapshot['components'][key]['status']=='SOURCE_RELATIVE_ONLY'
    for key in ('regime','confluence','confidence'):
        assert snapshot['components'][key]==dict(status='NOT_PROJECTED',value=None)
    assert snapshot['components']['1h']['value']['close']==20015.25
    assert len(stream.profile.candles)==60
    assert_disabled(snapshot)


def test_incomplete_htf_never_projected_and_pending_closed_is_atomic():
    stream=Stream();snapshot=stream.fill(4)
    assert snapshot['components']['15m']['value'] is None
    assert snapshot['components']['1h']['value'] is None
    stream.bar('CLOSED',stream.index,stream.pair(stream.qpc+1))
    snapshot=stream.profile.snapshot()
    assert snapshot['market_stream']=='NOT_LIVE'
    assert all(v['value'] is None for v in snapshot['components'].values())


@pytest.mark.parametrize('fault',['heartbeat','sequence_gap','duplicate','out_of_order','delay','restart','reconnect',
    'epoch','clock_regression','clock_unavailable','missing_pair','hash','source_gap','frequency','old_capture','disconnected'])
def test_faults_revoke_all_analysis_and_never_auto_promote(fault):
    stream=Stream();raw,paired=stream.boundary();p=stream.profile
    row=json.loads(raw);pair=json.loads(paired)
    if fault=='heartbeat':stream.qpc+=15001
    elif fault=='epoch':stream.epoch='other'
    elif fault=='clock_regression':stream.qpc-=1
    elif fault=='clock_unavailable':p.clock=lambda:(_ for _ in ()).throw(OSError('unavailable'))
    elif fault in ('restart','reconnect'):p.revoke(fault)
    else:
        row['sequence']=stream.seq
        if fault=='sequence_gap':row['sequence']+=1
        if fault=='duplicate':row['sequence']=0
        if fault=='out_of_order':row['sequence']=-1
        if fault=='delay':pair['emission']['qpc_before']=0
        if fault=='hash':pair['canonical_sha256']='0'*64
        if fault=='source_gap':row['payload']['bar_time']=stamp(BASE+timedelta(minutes=4))
        if fault=='frequency':pair['qpc_frequency']=1001
        if fault=='old_capture':pair['callback']['qpc_before']=0
        if fault=='disconnected':row['kind']='DISCONNECTED'
        # Rebind all but the intentionally wrong hash to reach provenance checks.
        pair['canonical_sequence']=row['sequence'];pair['pair_sequence']=stream.pairseq
        if fault!='hash':pair['canonical_sha256']=sha256(encode(row)).hexdigest()
        with pytest.raises(ValueError):
            p.accept(encode(row),None if fault=='missing_pair' else encode(pair),receipt_qpc=stream.qpc)
    snapshot=p.snapshot()
    assert snapshot['fault']
    assert snapshot['market_stream']=='NOT_LIVE'
    assert all(v['value'] is None for v in snapshot['components'].values())
    assert_disabled(snapshot)
    with pytest.raises(ValueError):p.accept(raw,paired,receipt_qpc=stream.qpc)


def test_source_labels_do_not_attest_host_utc_or_absolute_recency():
    stream=Stream();stream.wall_offset=timedelta(days=-400)
    snapshot=stream.fill(4)
    assert snapshot['analysis_status']=='SOURCE_RELATIVE_ONLY'
    assert_disabled(snapshot)


def test_reviewed_calendar_snapshot_is_not_current_stream_binding(witness):
    _,template,raw=witness
    snapshot=Stream(calendar_evidence=(raw,template)).fill(4)
    assert snapshot['calendar_binding']=='REVIEWED_SNAPSHOT_ONLY'
    assert snapshot['session_authority']=='UNKNOWN'
    assert_disabled(snapshot)
    with pytest.raises(ValueError):Stream(calendar_evidence=(raw+b' ',template))
    with pytest.raises(ValueError):Stream(calendar_evidence=(raw,template.replace(b'CME US Index Futures ETH',b'INVALID')))


def test_fresh_receipts_do_not_keep_old_emissions_live():
    stream=Stream();stream.boundary()
    with pytest.raises(ValueError,match='PROCESSING_AGE_EXPIRED'):
        for _ in range(19):
            stream.qpc+=5000;stream.send('HEARTBEAT',{'connected':True})
    assert stream.profile.snapshot()['market_stream']=='NOT_LIVE'


def test_processing_delay_is_measured_from_emission_not_just_receipt():
    stream=Stream();stream.boundary()
    stream.profile.maximum_processing=5
    # New receipt cannot repair an expired source observation.
    stream.qpc+=10
    with pytest.raises(ValueError):stream.send('HEARTBEAT',{'connected':True})
    assert stream.profile.snapshot()['analysis_status']=='BLOCKED'


def test_api_and_pipeline_cannot_create_account_runtime_or_orders(monkeypatch):
    from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1, _CurrentAccountingV1
    from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
    from backend.services.live_market_analysis_service import LiveMarketAnalysisService
    guards=[]
    for cls in (CurrentPaperServiceV1,_CurrentAccountingV1,PaperBrokerConnectorV2,LiveMarketAnalysisService):
        guard=Mock(side_effect=AssertionError('forbidden execution/account boundary'))
        monkeypatch.setattr(cls,'__init__',guard);guards.append(guard)
    stream=Stream();stream.fill(62)
    app=create_market_analysis_time_app_v1(profile=stream.profile)
    assert not vars(app.state)['_state']
    with TestClient(app) as client:
        for _ in range(5):assert_disabled(client.get('/api/v2/market-analysis/time-profile').json())
        assert client.post('/api/v2/market-analysis/time-profile',json={'enable':True}).status_code==405
        assert client.post('/control',json={'enable':True}).status_code==404
        stream.profile.revoke()
        assert client.get('/api/v2/market-analysis/time-profile').json()['analysis_status']=='BLOCKED'
    for guard in guards:guard.assert_not_called()


def test_exporter_and_existing_admission_untouched_and_snapshots_detached():
    exporter=Path('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs').read_text().replace('\r\n','\n').encode()
    assert sha256(exporter).hexdigest()==EXPORTER_SHA256
    stream=Stream();snapshot=stream.fill(4);saved=deepcopy(snapshot)
    snapshot['components']['1m']['value']['close']=1
    assert stream.profile.snapshot()==saved
    source=Path('backend/market_data/analysis_time_profile_v1.py').read_text()
    imports=[n.module for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
    assert not any(any(word in (name or '') for word in ('accounts','execution','current_paper','live_market_analysis_service')) for name in imports)


@pytest.mark.parametrize('mutation,reason',[
    ('source_gap','CANONICAL_GAP'),('frequency','PAIR_BINDING'),('hash','PAIR_BINDING'),
    ('callback','PAIR_ORDER_OR_OLD_CAPTURE'),('missing_closed','MISSING_CLOSED'),
])
def test_independent_bar_provenance_predicates_reject_before_analysis(mutation,reason):
    stream=Stream();stream.boundary()
    # Capture a structurally valid second boundary, then deliver its exact mutation.
    saved=stream.profile.accept;captured=[]
    stream.profile.accept=lambda *args,**kw:captured.append((args,kw))
    stream.bar('FORMING',1,stream.pair(stream.qpc+1))
    stream.profile.accept=saved
    args,kwargs=captured[0];row=json.loads(args[0]);pair=json.loads(args[1])
    if mutation=='source_gap':
        row['payload']['bar_time']=pair['source_bar_label']=stamp(BASE+timedelta(minutes=2))
    if mutation=='frequency':pair['qpc_frequency']+=1
    if mutation=='callback':pair['callback']['qpc_before']=0
    if mutation=='missing_closed':stream.profile.forming_count=2
    pair['canonical_sha256']=sha256(encode(row)).hexdigest() if mutation!='hash' else '0'*64
    with pytest.raises(ValueError,match=reason):saved(encode(row),encode(pair),**kwargs)
    assert not stream.profile.candles


def test_real_archived_production_rows_cannot_be_reused_as_a_fresh_stream():
    capture=json.loads(Path('backend/tests/production_timing_sprint15w.json').read_text())['native_capture']
    rows=capture['native_canonical_utf8'].encode().splitlines()
    paired=capture['native_timing_utf8'].encode().splitlines()
    first=json.loads(paired[0]);start=json.loads(paired[-1])['emission']['qpc_after']+1000
    profile=MarketAnalysisTimeProfileV1(session=first['session'],epoch='fresh-test-epoch',
        frequency=first['qpc_frequency'],reader_start_qpc=start,
        qpc_clock=lambda:('fresh-test-epoch',first['qpc_frequency'],start),heartbeat_seconds=15,
        maximum_processing_seconds=90,exporter_sha256=EXPORTER_SHA256)
    for raw in rows:
        if json.loads(raw)['kind'] in ('CLOSED','FORMING'):
            with pytest.raises(ValueError,match='PAIR_ORDER_OR_OLD_CAPTURE'):
                profile.accept(raw,paired[0],receipt_qpc=start)
            break
        profile.accept(raw,receipt_qpc=start)
    assert profile.snapshot()['market_stream']=='NOT_LIVE'


def test_clock_inventory_extension_preserves_every_prior_assessment_field():
    review=json.loads(Path('backend/tests/clock_preflight_sprint15t.json').read_text())
    additions=[row for row in review['direct_clock_dependencies'] if row['path']=='backend/market_data/analysis_time_profile_v1.py']
    assert len(additions)==1
    assert additions[0]['introduced_by']=='backend/tests/market_analysis_time_sprint15x.json'
    review['direct_clock_dependencies'].remove(additions[0])
    # Sprint 15Y adds only its explicit file-adapter clock dependency.
    tail=[row for row in review['direct_clock_dependencies'] if row['path']=='backend/market_data/fresh_native_adapter_v1.py']
    assert len(tail)==1 and tail[0]['introduced_by']=='backend/tests/fresh_native_adapter_sprint15y.json'
    review['direct_clock_dependencies'].remove(tail[0])
    startup=[row for row in review['direct_clock_dependencies'] if row['path']=='backend/market_data/analysis_startup_v1.py']
    assert len(startup)==1 and startup[0]['introduced_by']=='backend/tests/analysis_startup_sprint15yr1.json'
    review['direct_clock_dependencies'].remove(startup[0])
    original=sha256(json.dumps(review,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert original=='439139eb808ea2440a34e0d757df5f73e217bd6004ec1b723a8cb3e9bddc4459'
