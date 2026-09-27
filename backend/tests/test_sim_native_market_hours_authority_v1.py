"""Offline synthetic freshness mutations; never production calendar certification."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import sim_native_market_hours_authority_v1 as m
from backend.services import sim_native_authority_v3 as auth
from backend.tests.test_loaded_calendar_sprint13 import witness
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment

NOW = datetime(2026, 9, 27, 23, tzinfo=timezone.utc)
KEY = b'offline-calendar-authority-only!!'


def raw(w):
    return (json.dumps(w, separators=(',', ':'))+'\n').encode()


@pytest.fixture
def inputs(witness, monkeypatch):
    w, template, _ = witness
    w = deepcopy(w)
    # This mutation is solely a synthetic freshness test, never native evidence.
    w['event_time'] = (NOW-timedelta(minutes=1)).isoformat().replace('+00:00', 'Z')
    monkeypatch.setattr(m, 'TEMPLATE_SHA256', hashlib.sha256(template).hexdigest())
    config = {**m.PINS, 'authority_id': auth.authority_id(KEY), 'configuration_generation': '3'}
    return w, template, config


def create(inputs, **kwargs):
    w, t, c = inputs
    return m.build(raw(w), t, config=c, policy_id=m.POLICY, key=KEY, now=kwargs.pop('now', NOW), **kwargs)


def check(inputs, payload, signature, **kwargs):
    return m.verify(payload, signature, inputs[1], config=inputs[2], policy_id=m.POLICY,
                    key=KEY, now=kwargs.pop('now', NOW), **kwargs)


def signed(value):
    payload = m.canonical(value)
    return payload, hmac.new(KEY, m.DOMAIN+payload, hashlib.sha256).hexdigest().encode()


def test_valid_bounded_current_and_next_date_existing_provider(inputs):
    before = deepcopy(inputs)
    payload, sig = create(inputs)
    v, p = check(inputs, payload, sig)
    assert v['covered_dates'] == ['2026-09-27','2026-09-28','2026-09-29']
    assert v['closed_dates'] == [] and v['special_hours'] == []
    assert v['expires_us'] == m.utc_us(NOW+timedelta(hours=48))
    assert p.get_market_hours_service().is_market_open(symbol='NQ', timestamp=NOW)
    assert check(inputs,payload,sig,now=NOW+timedelta(days=1))[1].is_date_covered(target_date=NOW.date()+timedelta(days=1))
    assert inputs == before


def test_one_day_expiry_caps_at_chicago_midnight_and_no_age_renewal(inputs):
    p,s = create(inputs, days=1)
    v,_ = check(inputs,p,s,now=NOW+timedelta(hours=1))  # witness older than 30m is fine after issue
    assert v['expires_us']==m.utc_us(datetime(2026,9,28,5,tzinfo=timezone.utc))
    with pytest.raises(ValueError, match='EXPIRED'): check(inputs,p,s,now=datetime(2026,9,28,5,tzinfo=timezone.utc))


@pytest.mark.parametrize('damage', ['stale','future','instrument','contract','template','timezone','sessions',
    'holidays','partials','partial_metadata','unknown','sample_unknown','sample_bounds','kind','includes_end','old_witness','bool_numeric'])
def test_witness_rejections(inputs, damage):
    w=inputs[0]
    if damage=='stale': w['event_time']=(NOW-timedelta(minutes=30,seconds=1)).isoformat().replace('+00:00','Z')
    elif damage=='future': w['event_time']=(NOW+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
    elif damage=='old_witness': w['event_time']='2026-09-20T06:03:11.4179026Z'
    elif damage in ('instrument','contract','template'): w[damage]='WRONG'
    elif damage=='timezone': w['application_timezone']='Eastern Standard Time'
    elif damage=='sessions': w['sessions'][0]['begin_time']=1800
    elif damage=='holidays': w['holiday_dates'].pop()
    elif damage=='partials': w['partial_holiday_dates'].pop()
    elif damage=='partial_metadata': w['partial_holidays_2026'][0]['early_end']=False
    elif damage=='unknown': w['extra']=1
    elif damage=='sample_unknown': w['samples'][0]['extra']=1
    elif damage=='sample_bounds': w['samples'][0]['end']='2026-09-22T21:00:00Z'
    elif damage=='kind': w['samples'][0]['begin_kind']='Unspecified'
    elif damage=='includes_end': w['samples'][0]['includes_end']=False
    elif damage=='bool_numeric': w['bars_value']=True
    with pytest.raises(ValueError): create(inputs)


@pytest.mark.parametrize('day', [datetime(2026,11,25,18,tzinfo=timezone.utc), datetime(2026,1,1,18,tzinfo=timezone.utc)])
def test_exception_dates_never_inferred(inputs, day):
    inputs[0]['event_time']=day.isoformat().replace('+00:00','Z')
    with pytest.raises(ValueError, match='UNSUPPORTED_EXCEPTION_MAPPING'): create(inputs,now=day)


@pytest.mark.parametrize('field,value', [('configuration_generation','2'),('runtime_generation','2'),('risk_version','0'*64),
    ('commissioning_policy_id','0'*64),('backend_account_id','PAPER-OTHER'),('instrument','MNQ DEC26'),
    ('provider','LIVE'),('native_account','Live'),('execution_domain','PAPER'),('authority_id','0'*64),
    ('calendar_witness_sha256','0'*64),('covered_dates',['2026-09-26']),('closed_dates',['2026-09-27']),
    ('special_hours',[{'local_date':'2026-09-27','open_time':'00:00','close_time':'23:59'}]),
    ('expires_us',m.utc_us(NOW+timedelta(hours=49))),('version',True),('extra',False)])
def test_even_resigned_package_mutations_rejected(inputs, field, value):
    v=json.loads(create(inputs)[0]);v[field]=value
    with pytest.raises(ValueError): check(inputs,*signed(v))


@pytest.mark.parametrize('days', [0,4,True])
def test_coverage_limits(inputs,days):
    with pytest.raises(ValueError): create(inputs,days=days)


def test_hmac_canonical_duplicate_and_fixture_rejections(inputs):
    p,s=create(inputs)
    with pytest.raises(ValueError): check(inputs,p,b'0'*64)
    with pytest.raises(ValueError): check(inputs,p+b' ',s)
    duplicate=b'{"schema":"x",'+p[1:]
    signature=hmac.new(KEY,m.DOMAIN+duplicate,hashlib.sha256).hexdigest().encode()
    with pytest.raises(ValueError,match='DUPLICATE'): check(inputs,duplicate,signature)
    with pytest.raises(ValueError): m.review_witness(Path('backend/config/market_hours/certified_market_hours_fixture_v2.json').read_bytes(),inputs[1],issued=NOW)


def test_reauthentication_revokes_removed_tampered_expired_and_config_drift(inputs,tmp_path,monkeypatch):
    folder=tmp_path/'authority-inputs';folder.mkdir()
    p,s=create(inputs)
    (folder/'market-hours-v1.json').write_bytes(p);(folder/'market-hours-v1.sig').write_bytes(s)
    monkeypatch.setattr(auth,'authority_root',lambda:tmp_path)
    monkeypatch.setattr(auth,'load_authority',lambda:KEY)
    monkeypatch.setattr(m,'private_path',lambda p:Path(p))
    monkeypatch.setattr(m,'production_template',lambda:inputs[1])
    clock=[NOW]
    lifecycle=m.SimNativeMarketHoursLifecycleV1(context=lambda now:(inputs[2],m.POLICY),clock=lambda:clock[0])
    assert lifecycle.get_snapshot()['status']=='MARKET_OPEN_CERTIFIED'
    clock[0]=NOW+timedelta(hours=49)
    assert lifecycle.get_snapshot()['status']=='EXPIRED' and lifecycle.get_active_provider() is None
    clock[0]=NOW;inputs[2]['configuration_generation']='4'
    assert lifecycle.get_active_provider() is None
    inputs[2]['configuration_generation']='3'
    (folder/'market-hours-v1.sig').write_bytes(b'bad')
    assert lifecycle.get_active_provider() is None
    (folder/'market-hours-v1.json').unlink()
    assert lifecycle.get_snapshot()['status']=='WITNESS_REQUIRED'


def test_closed_session_uses_existing_guard(inputs):
    now=datetime(2026,9,28,21,30,tzinfo=timezone.utc)
    _,p=check(inputs,*create(inputs),now=now)
    assert not p.get_market_hours_service().is_market_open(symbol='NQ',timestamp=now)


def test_native_composition_and_get_preserve_paper_and_disk(environment, monkeypatch):
    from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
    from backend.services.runtime_admission_v2 import RuntimeAdmissionV2
    from backend.services.sim_native_commissioning_policy_v1 import load
    from backend.api.sim_native_financial_api_v3 import create_sim_native_financial_router_v3
    paper=RuntimeAdmissionV2(settings=load().api_settings)
    prior=paper.market_hours_lifecycle
    svc=SimNativeFinancialRuntimeServiceV3(clock=lambda:environment[2]);svc.start()
    try:
        assert svc.get_snapshot()['status']=='NO_OPERATION'
        native=svc._runtime.lifecycle.runtime_admission_v2
        assert isinstance(native.market_hours_lifecycle,m.SimNativeMarketHoursLifecycleV1)
        assert paper.market_hours_lifecycle is prior
        def disk():
            return {str(p): ('LOCK_PRESENT' if p.suffix == '.lock' else p.read_bytes())
                    for p in environment[0].rglob('*') if p.is_file()}
        before=disk()
        svc.observe=Mock(side_effect=AssertionError('GET observation mutation'))
        svc._runtime.lifecycle.submit_signal=Mock(side_effect=AssertionError('GET execution'))
        app=FastAPI();app.include_router(create_sim_native_financial_router_v3(svc.get_snapshot,read_market_hours=svc.get_market_hours_authority))
        with TestClient(app) as c:
            for _ in range(3):
                response=c.get('/api/v3/dashboard/sim-native-market-hours-authority')
                assert response.json()['market_open'] is False
                assert response.headers['cache-control']=='no-store'
            assert c.post('/api/v3/dashboard/sim-native-market-hours-authority').status_code==405
        assert before==disk()
        assert native.market_hours_provider.calendar_snapshot is None
        assert paper.market_hours_lifecycle is prior
    finally: svc.stop()


def test_operator_publication_readback_and_no_automatic_republication(inputs,environment,monkeypatch):
    from tools.certify_sim_native_market_hours_v1 import publish
    from backend.tests.test_controlled_sim_operation_v3 import KEY as provisioned_test_key
    root=environment[0]
    monkeypatch.setattr(m,'private_path',lambda p:Path(p))
    monkeypatch.setattr(m,'production_template',lambda:inputs[1])
    monkeypatch.setattr(auth,'_restrict_directory',lambda p:None)
    w=inputs[0];w['event_time']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    capture=root/'synthetic.calendar.jsonl';capture.write_bytes(raw(w))
    digest=hashlib.sha256(capture.read_bytes()).hexdigest()
    result=publish(capture,digest,1)
    assert result['schema']==m.SCHEMA
    folder=root/'authority-inputs'
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    assert len(before)==2
    v,_=m.verify(before['market-hours-v1.json'],before['market-hours-v1.sig'],inputs[1],
        config=environment[4],policy_id=m.POLICY,key=provisioned_test_key,now=datetime.now(timezone.utc))
    assert v['calendar_witness_sha256']==digest
    with pytest.raises(ValueError,match='PACKAGE_ALREADY_EXISTS'): publish(capture,digest,1)
    assert all((folder/n).read_bytes()==b for n,b in before.items())
    assert all(not list(p.iterdir()) for p in environment[1].values())


def test_paper_switch_does_not_replace_native_lifecycle_or_package(environment,inputs,tmp_path,monkeypatch):
    from backend.api.asgi import create_asgi_app
    from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
    from backend.tests.test_controlled_sim_operation_v3 import KEY as provisioned_test_key
    monkeypatch.setenv('ARMS_ADMIN_TOKEN','offline-hours-admin')
    root,_,now,_,config=environment
    w=inputs[0];w['event_time']=now.isoformat().replace('+00:00','Z')
    payload,sig=m.build(raw(w),inputs[1],config=config,policy_id=m.POLICY,key=provisioned_test_key,now=now)
    folder=root/'authority-inputs';folder.mkdir()
    (folder/'market-hours-v1.json').write_bytes(payload);(folder/'market-hours-v1.sig').write_bytes(sig)
    monkeypatch.setattr(m,'private_path',lambda p:Path(p))
    monkeypatch.setattr(m,'production_template',lambda:inputs[1])
    svc=SimNativeFinancialRuntimeServiceV3(clock=lambda:now)
    paper_config=tmp_path/'paper.json';paper_config.write_text('{"active_account":"TOPSTEP_150K"}')
    app=create_asgi_app(account_config_path=paper_config,state_path=tmp_path/'paper/state.json',sim_native_service_factory=lambda:svc)
    with TestClient(app,headers={'X-ARMS-ADMIN-TOKEN':'offline-hours-admin'}) as c:
        native=svc._runtime.lifecycle.runtime_admission_v2.market_hours_lifecycle
        path='/api/v3/dashboard/sim-native-market-hours-authority'
        before=c.get(path).json()
        assert before['status'] in ('MARKET_OPEN_CERTIFIED','MARKET_CLOSED')
        assert app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2.market_hours_provider.calendar_snapshot is None
        target=next((k,v) for k,v in app.coordinator._catalog['accounts'].items() if v['profile_name']=='TOPSTEP_50K')
        assert c.post('/api/v2/dashboard/account-manager/switch',json={'account_id':target[0],**target[1]}).json()['changed']
        assert c.get(path).json()==before
        assert svc._runtime.lifecycle.runtime_admission_v2.market_hours_lifecycle is native
        assert app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2.market_hours_provider.calendar_snapshot is None
        assert (folder/'market-hours-v1.json').read_bytes()==payload and (folder/'market-hours-v1.sig').read_bytes()==sig


def test_private_path_rejects_repository_and_remote_before_acl():
    with pytest.raises(ValueError): m.private_path(Path('backend/config/market_hours/certified_market_hours_fixture_v2.json').resolve())
    with pytest.raises(ValueError): m.private_path(Path(r'\\server\share\witness.jsonl'))


def test_uncovered_date_cannot_be_queried_as_open(inputs):
    _,p=check(inputs,*create(inputs))
    assert not p.is_date_covered(target_date=NOW.date()-timedelta(days=1))
    assert not p.get_market_hours_service().is_market_open(symbol='NQ',timestamp=NOW-timedelta(days=1))


def test_expiry_during_authority_read_is_rejected(inputs, monkeypatch):
    payload, signature = create(inputs)
    clock = [NOW + timedelta(hours=48, microseconds=-1)]
    def read(path):
        clock[0] = NOW + timedelta(hours=48)
        return payload if path.suffix == '.json' else signature
    monkeypatch.setattr(m, 'read_bounded', read)
    monkeypatch.setattr(m, 'production_template', lambda: inputs[1])
    monkeypatch.setattr(auth, 'load_authority', lambda: KEY)
    lifecycle = m.SimNativeMarketHoursLifecycleV1(context=lambda now: (inputs[2], m.POLICY), clock=lambda: clock[0])
    assert lifecycle.get_snapshot()['status'] == 'EXPIRED'
    assert lifecycle.get_active_provider() is None


def test_exact_freshness_limit(inputs):
    inputs[0]['event_time'] = (NOW - timedelta(minutes=30)).isoformat().replace('+00:00', 'Z')
    check(inputs, *create(inputs))
