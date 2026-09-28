"""Synthetic packages/keys in temp directories only; never production certification."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.services import sim_native_economic_news_authority_v1 as m
from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_market_hours_authority_v1 import PINS, POLICY
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment

NOW = datetime(2026,9,28,14,30,tzinfo=timezone.utc)
KEY = b'offline-news-authority-only-32bytes'


def document(config, key, now=NOW):
    at = m.utc_us(now)
    return dict(schema=m.SCHEMA,version=1,**m.identity(config,POLICY,key),
        snapshot_version='synthetic-1',source_name='SYNTHETIC TEST ONLY',source_reference='offline:test',source_sha256='a'*64,
        generated_us=at-3_600_000_000,issued_us=at-3_600_000_000,expires_us=at+3_600_000_000,
        coverage_start_us=at-7_200_000_000,coverage_end_us=at+86_400_000_000,
        coverage_intervals=[dict(start_us=at-7_200_000_000,end_us=at+86_400_000_000)],
        blackout_before_seconds=300,blackout_after_seconds=300,high_impact_events=[])


def event(at=NOW, **changes):
    return dict(event_id='synthetic-event',name='Synthetic release',event_us=m.utc_us(at),impact='HIGH',currency='USD',**changes)


def install(root, value, key, *, history=None):
    """Fixture issuance only. Production issuance belongs to the explicit tool."""
    folder=root/'authority-inputs';folder.mkdir(exist_ok=True)
    payload=m.canonical(value)
    if history is None:
        identity={k:value[k] for k in m.identity({**PINS,'authority_id':auth.authority_id(key),'configuration_generation':value['configuration_generation']},POLICY,key)}
        history=dict(schema=m.HISTORY_SCHEMA,identity=identity,entries=[m.entry(value,payload)])
    for name,raw in zip(m.FILES,(payload,m.sign(payload,key),m.history_wire(history,key))):
        (folder/name).write_bytes(raw)
    return folder


@pytest.fixture
def state(tmp_path,monkeypatch):
    config={**PINS,'authority_id':auth.authority_id(KEY),'configuration_generation':'3'}
    s=SimpleNamespace(root=tmp_path,config=config,now=NOW,value=document(config,KEY))
    monkeypatch.setattr(auth,'authority_root',lambda:tmp_path)
    monkeypatch.setattr(auth,'load_authority',lambda:KEY)
    monkeypatch.setattr(m,'read_bounded',lambda p:Path(p).read_bytes())
    s.owner=m.SimNativeEconomicNewsLifecycleV1(context=lambda now:(s.config,POLICY),clock=lambda:s.now)
    s.folder=install(tmp_path,s.value,KEY)
    return s


def verify(value, config, *, now=NOW):
    raw=m.canonical(value)
    return m.verify(raw,m.sign(raw,KEY),config=config,policy_id=POLICY,key=KEY,now=now)


def disk(root):
    return {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file() and p.suffix!='.lock'}


def test_clear_is_authenticated_and_reads_have_no_mutations(state):
    s=state;before=disk(s.root);original=deepcopy(s.value)
    for _ in range(3):
        assert s.owner.get_snapshot()['status']=='CERTIFIED_CLEAR'
        assert s.owner.get_active_provider().get_economic_news_authority() is s.owner
        assert not s.owner.is_news_blocked(symbol='NQ',timestamp=s.now)
    assert before==disk(s.root) and original==s.value
    assert s.owner.is_news_blocked(symbol='ES',timestamp=s.now)
    assert s.owner.is_news_blocked(symbol='NQ',timestamp=s.now.replace(tzinfo=None))


@pytest.mark.parametrize('offset,blocked', [(-300_000_001,False),(-300_000_000,True),(0,True),(300_000_000,True),(300_000_001,False)])
def test_exact_inclusive_blackout_no_tolerance(state,offset,blocked):
    s=state;s.value['high_impact_events']=[event()];install(s.root,s.value,KEY)
    s.now=NOW+timedelta(microseconds=offset)
    assert s.owner.is_news_blocked(symbol='NQ',timestamp=s.now) is blocked
    assert s.owner.get_snapshot()['blocked'] is blocked


@pytest.mark.parametrize('field,value', [
    ('schema','wrong'),('version',2),('version',True),('backend_account_id','PAPER'),('execution_domain','PAPER'),
    ('native_account','Sim102'),('provider','LIVE'),('instrument','MNQ DEC26'),('instrument_root','ES'),
    ('runtime_generation','2'),('risk_version','0'*64),('risk_profile','OTHER'),('authority_id','0'*64),
    ('configuration_generation','2'),('commissioning_policy_id','0'*64),('news_policy_id','0'*64),
    ('blackout_before_seconds',299),('blackout_after_seconds',301),('blackout_before_seconds',True),
    ('snapshot_version',''),('snapshot_version','non ascii \u00e9'),('source_name',''),('source_reference',''),('source_sha256','wrong'),
    ('generated_us',m.utc_us(NOW)+1),('issued_us',m.utc_us(NOW)+1),('issued_us',0),('issued_us',True),
    ('expires_us',m.utc_us(NOW)),('expires_us',m.utc_us(NOW)+m.MAX_LIFE_US),('coverage_end_us',1),
    ('high_impact_events',{}),('coverage_intervals',[]),('extra',1)])
def test_resigned_invalid_packages_block(state,field,value):
    s=state;s.value[field]=value
    with pytest.raises(ValueError):verify(s.value,s.config)


@pytest.mark.parametrize('field',sorted(m.FIELDS))
def test_every_required_field_is_required(state,field):
    del state.value[field]
    with pytest.raises(ValueError):verify(state.value,state.config)


@pytest.mark.parametrize('damage',['outside','duplicate_id','conflict','impact','currency','extra','missing','bool_time'])
def test_invalid_events_rejected(state,damage):
    v=state.value;e=event();v['high_impact_events']=[e]
    if damage=='outside':e['event_us']=v['coverage_start_us']-1
    elif damage=='duplicate_id':v['high_impact_events'].append({**e,'event_us':e['event_us']+1})
    elif damage=='conflict':v['high_impact_events'].append({**e,'event_id':'other-id'})
    elif damage=='impact':e['impact']='LOW'
    elif damage=='currency':e['currency']='EUR'
    elif damage=='extra':e['unknown']=1
    elif damage=='missing':del e['name']
    elif damage=='bool_time':e['event_us']=True
    with pytest.raises(ValueError):verify(v,state.config)


def test_signature_duplicate_keys_and_noncanonical_rejected(state):
    p=m.canonical(state.value)
    for raw,sig in [(p,b'0'*64),(p+b' ',m.sign(p,KEY)),(p.replace(b'a'*64,b'b'*64),m.sign(p,KEY))]:
        with pytest.raises(ValueError):m.verify(raw,sig,config=state.config,policy_id=POLICY,key=KEY,now=NOW)
    for raw in (b'{"schema":"x",'+p[1:],p.replace(b'"version":1',b'"version":1,"version":1')):
        with pytest.raises(ValueError,match='DUPLICATE'):m.verify(raw,m.sign(raw,KEY),config=state.config,policy_id=POLICY,key=KEY,now=NOW)


@pytest.mark.parametrize('position,covered', [('before',False),('start',True),('gap',False),('second_start',True),('end',False),('after',False)])
def test_coverage_gaps_and_boundaries_with_expiry_cap(state,position,covered):
    s=state;t=m.utc_us(NOW)
    s.value.update(coverage_start_us=t-600_000_000,coverage_end_us=t+600_000_000,expires_us=t+600_000_000,
        coverage_intervals=[dict(start_us=t-600_000_000,end_us=t-300_000_000),dict(start_us=t+300_000_000,end_us=t+600_000_000)])
    install(s.root,s.value,KEY)
    offset={'before':-600_000_001,'start':-600_000_000,'gap':0,'second_start':300_000_000,'end':600_000_000,'after':600_000_001}[position]
    s.now=NOW+timedelta(microseconds=offset)
    assert s.owner.get_snapshot()['blocked'] is not covered
    # Coverage end is inclusive, but expiry itself is always exclusive.
    assert m.covered(s.value,s.value['coverage_end_us'])


@pytest.mark.parametrize('damage',['payload','signature','source','remove','history_remove','history_tamper','key','config','policy','future','expired','lock'])
def test_each_lookup_reauthenticates_and_revokes(state,monkeypatch,damage):
    s=state;assert not s.owner.get_snapshot()['blocked']
    if damage=='payload':(s.folder/m.FILES[0]).write_bytes(b'{}')
    elif damage=='signature':(s.folder/m.FILES[1]).write_bytes(b'bad')
    elif damage=='source':
        s.value['source_sha256']='b'*64;p=m.canonical(s.value)
        (s.folder/m.FILES[0]).write_bytes(p);(s.folder/m.FILES[1]).write_bytes(m.sign(p,KEY))
    elif damage=='remove':(s.folder/m.FILES[0]).unlink()
    elif damage=='history_remove':(s.folder/m.FILES[2]).unlink()
    elif damage=='history_tamper':(s.folder/m.FILES[2]).write_bytes(b'{}')
    elif damage=='key':monkeypatch.setattr(auth,'load_authority',lambda:b'wrong-authority-key')
    elif damage=='config':s.config['configuration_generation']='4'
    elif damage=='policy':s.owner.context=lambda now:(s.config,'0'*64)
    elif damage=='future':s.now=NOW-timedelta(hours=2)
    elif damage=='expired':s.now=NOW+timedelta(hours=1)
    elif damage=='lock':(s.folder/m.LOCK).touch()
    before=disk(s.root)
    assert s.owner.get_snapshot()['blocked'] and s.owner.is_news_blocked(symbol='NQ',timestamp=s.now)
    assert disk(s.root)==before


def test_restart_rejects_package_rollback_and_conflicting_version(state):
    s=state;old=deepcopy(s.value);p=m.canonical(old)
    history=dict(schema=m.HISTORY_SCHEMA,identity=m.identity(s.config,POLICY,KEY),entries=[m.entry(old,p)])
    s.value.update(snapshot_version='synthetic-2',issued_us=old['issued_us']+1)
    history['entries'].append(m.entry(s.value,m.canonical(s.value)))
    install(s.root,s.value,KEY,history=history)
    assert s.owner.get_snapshot()['status']=='CERTIFIED_CLEAR'
    for replacement in (old,{**s.value,'source_sha256':'b'*64}):
        install(s.root,replacement,KEY,history=history)
        restarted=m.SimNativeEconomicNewsLifecycleV1(context=s.owner.context,clock=lambda:s.now)
        assert restarted.get_snapshot()['reason']=='ROLLBACK_OR_CONFLICT'


def test_source_metadata_is_an_issuer_assertion_not_vendor_truth(state):
    # A valid issuer may assert different provenance in a newly certified package.
    # The verifier cannot infer vendor completeness from a SHA256 string.
    state.value.update(source_name='Unverified external assertion',source_sha256='b'*64)
    assert verify(state.value,state.config)['source_sha256']=='b'*64


def test_expiry_during_lookup_fails_closed(state,monkeypatch):
    s=state;original=m.read_bounded;count=[0]
    def read(path):
        raw=original(path);count[0]+=1
        if count[0]==4:s.now=NOW+timedelta(hours=1)
        return raw
    monkeypatch.setattr(m,'read_bounded',read)
    assert s.owner.get_snapshot()['status']=='EXPIRED'


def test_pre_io_caller_time_cannot_bypass_current_blackout(state):
    s=state;s.value['high_impact_events']=[event()];install(s.root,s.value,KEY)
    assert s.owner.is_news_blocked(symbol='NQ',timestamp=NOW-timedelta(minutes=5,microseconds=1))


def test_clock_regression_during_history_read_fails_closed(state,monkeypatch):
    s=state;original=m.read_bounded;count=[0]
    def read(path):
        raw=original(path);count[0]+=1
        if count[0]==4:s.now=NOW-timedelta(microseconds=1)
        return raw
    monkeypatch.setattr(m,'read_bounded',read)
    assert s.owner.get_snapshot()['reason']=='CLOCK_REGRESSION'


def test_native_owner_api_and_paper_switch_are_isolated(environment,tmp_path,monkeypatch):
    from backend.api.asgi import create_asgi_app
    from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
    from backend.tests.test_controlled_sim_operation_v3 import KEY as key
    root,paths,now,_,config=environment
    install(root,document(config,key,now),key)
    monkeypatch.setattr(m,'read_bounded',lambda p:Path(p).read_bytes())
    monkeypatch.setenv('ARMS_ADMIN_TOKEN','offline-news-test')
    paper=tmp_path/'paper.json';paper.write_text('{"active_account":"TOPSTEP_150K"}')
    svc=SimNativeFinancialRuntimeServiceV3(clock=lambda:now)
    app=create_asgi_app(account_config_path=paper,state_path=tmp_path/'paper/state.json',sim_native_service_factory=lambda:svc)
    with TestClient(app,headers={'X-ARMS-ADMIN-TOKEN':'offline-news-test'}) as client:
        owner=svc._runtime.lifecycle.runtime_admission_v2.news_lifecycle
        assert isinstance(owner,m.SimNativeEconomicNewsLifecycleV1)
        native=svc._runtime.lifecycle
        denied=Mock(side_effect=AssertionError('read cannot execute/publish'))
        for obj,name in ((native,'submit_signal'),(native.native_admission_producer_v3,'produce'),(svc._integration,'publish_admitted')):
            monkeypatch.setattr(obj,name,denied)
        before=disk(root);finance=svc.get_snapshot();url='/api/v3/dashboard/sim-native-economic-news-authority'
        for _ in range(3):
            response=client.get(url)
            assert response.status_code==200 and response.json()['status']=='CERTIFIED_CLEAR'
            assert response.headers['cache-control']=='no-store'
        assert client.post(url).status_code==405
        assert before==disk(root) and finance==svc.get_snapshot()
        paper_owner=app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2.news_lifecycle
        assert paper_owner is not owner
        target=next((k,v) for k,v in app.coordinator._catalog['accounts'].items() if v['profile_name']=='TOPSTEP_50K')
        assert client.post('/api/v2/dashboard/account-manager/switch',json={'account_id':target[0],**target[1]}).json()['changed']
        assert svc._runtime.lifecycle.runtime_admission_v2.news_lifecycle is owner
        assert app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2.news_lifecycle is not owner
        assert client.get(url).json()['status']=='CERTIFIED_CLEAR'
        (root/'authority-inputs'/m.FILES[0]).unlink()
        before=disk(root)
        assert client.get(url).json()['status']=='PACKAGE_REQUIRED'
        assert owner.is_news_blocked(symbol='NQ',timestamp=now)
        assert finance==svc.get_snapshot() and before==disk(root)
        assert all(not list(p.iterdir()) for p in paths.values())
        denied.assert_not_called()


@pytest.mark.parametrize('condition',['missing','invalid','blackout'])
def test_news_rejection_precedes_native_admission_and_all_financial_effects(environment,tmp_path,monkeypatch,condition):
    from backend.tests.runtime_market_fixture_v81 import publish_test_market, NOW as market_now
    from backend.tests.test_sim_native_account_authority_v3 import request
    from backend.tests.test_controlled_sim_operation_v3 import KEY as key
    root,paths,_,runtime,config=environment
    admission=publish_test_market(runtime.lifecycle,directory=tmp_path/'market',symbol='NQ')
    value=document(config,key,market_now)
    if condition=='blackout':value['high_impact_events']=[event(market_now)]
    install(root,value,key)
    monkeypatch.setattr(m,'read_bounded',lambda p:Path(p).read_bytes())
    if condition=='missing':(root/'authority-inputs'/m.FILES[0]).unlink()
    elif condition=='invalid':(root/'authority-inputs'/m.FILES[1]).write_bytes(b'bad')
    admission.news_lifecycle=m.SimNativeEconomicNewsLifecycleV1(context=lambda now:(config,POLICY),clock=lambda:market_now)
    denied=Mock(side_effect=AssertionError('blocked news must have zero execution effects'))
    for obj,name in ((runtime.lifecycle.native_admission_producer_v3,'produce'),
                     (runtime.lifecycle.execution_manager,'prepare_order'),(runtime.lifecycle.paper_execution_engine,'execute'),
                     (runtime.lifecycle.broker_connector_v2,'submit_order')):
        monkeypatch.setattr(obj,name,denied)
    runtime.store.start()
    try:
        before=disk(root/'authority-inputs');risk=runtime.lifecycle.portfolio_manager_v2.capture_risk_state()
        financial=runtime.store.capture_state()
        result=runtime.lifecycle.submit_signal(**request(runtime))
        assert result['accepted'] is False and result['reason']=='runtime_admission_rejected'
        assert 'news' in result['admission_reason']
        assert runtime.store.admission_digest==''
        assert runtime.lifecycle.get_active_positions()==[] and runtime.lifecycle.trade_journal_v2.trades==[]
        assert runtime.lifecycle.portfolio_manager_v2.capture_risk_state()==risk
        # The durable submission boundary may record a rejected request; it must
        # not change financial participants or create a native admission.
        after=runtime.store.capture_state()
        for field in ('native_financial','account_portfolio','active_positions','execution_records','summary'):
            assert after[field]==financial[field]
        assert disk(root/'authority-inputs')==before
        assert all(not list(p.iterdir()) for p in paths.values())
        denied.assert_not_called()
    finally:runtime.store._durability.release()
