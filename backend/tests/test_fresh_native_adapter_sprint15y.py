"""Deterministic temporary-file appends. Never starts NinjaTrader or a broker."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1, WindowsQpc
from backend.tests.test_analysis_time_sprint15x import (
    Stream, SESSION, encode, assert_disabled, forbid_account_and_execution_construction,
)

EXPORTER=Path('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs').resolve()


class Files:
    def __init__(self, root, *, history=0):
        self.root=root;self.root.mkdir()
        (root/'timing').mkdir()
        self.canonical=root/(SESSION+'.jsonl')
        self.sidecar=root/'timing'/(SESSION+'.production-timing.jsonl')
        self.stream=Stream()
        self.rows=[];self.pairs=[]
        original=self.stream.profile.accept
        def record(raw,pair=None,**kw):
            original(raw,pair,**kw)
            self.rows.append(raw)
            with self.canonical.open('ab') as f:f.write(raw+b'\r\n')
            if pair:
                self.pairs.append(pair)
                with self.sidecar.open('ab') as f:f.write(pair+b'\n')
        self.stream.profile.accept=record
        hello=dict(schema='arms.nt.market.v1',session=SESSION,sequence=0,event_time='2026-09-21T14:00:00.0000000Z',kind='HELLO',payload=dict(
            provider='Provider31',contract='NQ DEC26',expiry='2026-12-01',instrument='NQ',tick_size=.25,point_value=20,
            timeframe='1m',trading_hours_template='CME US Index Futures ETH',source_timezone='UTC',bar_label='CLOSE',realtime=True,read_only=True))
        self.canonical.write_bytes(encode(hello)+b'\r\n')
        self.rows.append(encode(hello))
        for _ in range(history):self.stream.boundary()
        self.adapter=None

    def attach(self):
        self.stream.qpc+=1
        self.adapter=FreshNativeAdapterV1(health_gated=False, directory=self.root,installed_exporter=EXPORTER,
            qpc_clock=lambda:(self.stream.epoch,1000,self.stream.qpc))
        self.adapter.poll()
        return self.adapter

    def boundary(self):
        # Poll every synthetic heartbeat, as the actual background reader does.
        record=self.stream.profile.accept
        def deliver(*a,**kw):
            record(*a,**kw)
            self.adapter.poll()
        self.stream.profile.accept=deliver
        try:self.stream.boundary()
        finally:self.stream.profile.accept=record
        return self.adapter.snapshot()


def test_waiting_then_fresh_stream_and_full_hour(tmp_path):
    folder=tmp_path/'inbox';folder.mkdir()
    now=[1000]
    adapter=FreshNativeAdapterV1(health_gated=False, directory=folder,installed_exporter=EXPORTER,
        qpc_clock=lambda:('fixture',1000,now[0]))
    assert adapter.snapshot()['adapter_status']=='WAITING'
    assert_disabled(adapter.snapshot());adapter.close()
    files=Files(tmp_path/'live');a=files.attach()
    for _ in range(62):snapshot=files.boundary()
    assert snapshot['adapter_status']=='LIVE_TAIL',snapshot['adapter_reason']
    assert snapshot['transport_status']=='TRANSPORT_LIVE'
    for key in ('1m','15m','1h','trend','structure','liquidity','fvg'):
        assert snapshot['components'][key]['status']=='SOURCE_RELATIVE_ONLY'
    assert_disabled(snapshot)
    assert snapshot['order_submit_reachable'] is False
    assert len(a.profile.candles)==60
    a.close()


def test_existing_history_never_becomes_live_and_restart_discards_history(tmp_path):
    files=Files(tmp_path/'inbox',history=10);a=files.attach()
    initial=a.snapshot()
    assert initial['adapter_status']=='BOOTSTRAP'
    assert initial['live_delivered_records']==0
    assert not a.profile.candles
    cursor=initial['startup_cursor']
    assert cursor==files.canonical.stat().st_size
    first=files.boundary()
    assert first['adapter_status']=='LIVE_TAIL',first['adapter_reason']
    assert not a.profile.candles
    files.boundary()
    assert not a.profile.candles  # Partial first observed bar remains excluded.
    snapshot=files.boundary()
    assert len(a.profile.candles)==1
    assert snapshot['components']['15m']['value'] is None
    assert_disabled(snapshot)
    a.close();restarted=files.attach()
    assert restarted.snapshot()['adapter_status']=='BOOTSTRAP'
    assert not restarted.profile.candles
    restarted.close()


@pytest.mark.parametrize('fault',[
    'heartbeat','gap','duplicate','out_of_order','missing_pair','bad_hash','sidecar_session','new_session',
    'truncate','overwrite','replace','malformed','partial_timeout','epoch','clock_backwards','frequency',
    'orphan_pair','sidecar_removed','new_sidecar','terminal','seal',
])
def test_faults_revoke_tail_without_recovery(tmp_path,fault):
    files=Files(tmp_path/'inbox');a=files.attach();files.boundary()
    assert a.status=='LIVE_TAIL'
    if fault=='heartbeat':files.stream.qpc+=15001
    elif fault=='epoch':files.stream.epoch='new-epoch'
    elif fault=='clock_backwards':files.stream.qpc-=100
    elif fault=='frequency':a.clock=lambda:('synthetic-same-host-epoch',1001,files.stream.qpc)
    elif fault=='truncate':files.canonical.write_bytes(b'')
    elif fault=='overwrite':
        raw=files.canonical.read_bytes();files.canonical.write_bytes(raw.replace(b'Provider31',b'Provider30'))
    elif fault=='replace':
        files.canonical.rename(files.root/'retired.txt');files.canonical.write_bytes(b'')
    elif fault=='new_session':(files.root/(str(uuid4())+'.jsonl')).write_bytes(b'')
    elif fault=='new_sidecar':(files.root/'timing'/(str(uuid4())+'.production-timing.jsonl')).write_bytes(b'')
    elif fault=='sidecar_removed':files.sidecar.unlink()
    elif fault=='seal':Path(str(files.sidecar)+'.done.json').write_text('{}')
    elif fault=='malformed':
        with files.canonical.open('ab') as f:f.write(b'{bad}\n')
    elif fault=='partial_timeout':
        with files.canonical.open('ab') as f:f.write(b'{')
        a.poll();files.stream.qpc+=5001
    elif fault=='orphan_pair':
        with files.sidecar.open('ab') as f:f.write(files.pairs[-1]+b'\n')
        a.poll();files.stream.qpc+=5001
    else:
        row=json.loads(files.rows[-1]);pair=json.loads(files.pairs[-1])
        row['sequence']=a.sequence+1
        if fault=='gap':row['sequence']+=1
        if fault=='duplicate':row['sequence']=a.sequence
        if fault=='out_of_order':row['sequence']=0
        if fault=='terminal':row['kind']='DISCONNECTED'
        pair['pair_sequence']=a.pair_sequence+1;pair['canonical_sequence']=row['sequence']
        if fault=='sidecar_session':pair['session']=str(uuid4())
        if fault=='bad_hash':pair['canonical_sha256']='0'*64
        with files.canonical.open('ab') as f:f.write(encode(row)+b'\n')
        if fault!='missing_pair':
            with files.sidecar.open('ab') as f:f.write(encode(pair)+b'\n')
        else:a.poll();files.stream.qpc+=5001
    snapshot=a.snapshot()
    assert snapshot['adapter_status'] in ('REVOKED','DISCONNECTED'),(fault,snapshot)
    assert snapshot['market_stream']=='NOT_LIVE'
    assert all(c['value'] is None for c in snapshot['components'].values())
    assert_disabled(snapshot)
    before=snapshot['adapter_status'];files.stream.qpc+=1
    assert a.snapshot()['adapter_status']==before


def test_partial_canonical_and_late_pair_are_not_published_early(tmp_path):
    files=Files(tmp_path/'inbox');a=files.attach()
    # Generate a valid frame without allowing the reader to see it until split writes finish.
    old_size=files.canonical.stat().st_size
    files.stream.boundary()
    row=files.rows[-1];pair=files.pairs[-1]
    with files.canonical.open('r+b') as f:f.truncate(old_size)
    files.sidecar.write_bytes(b'')
    with files.canonical.open('ab') as f:f.write(row[:25])
    a.poll();assert a.status=='BOOTSTRAP'
    files.stream.qpc+=1
    with files.canonical.open('ab') as f:f.write(row[25:]+b'\r\n')
    a.poll();assert a.status=='BOOTSTRAP'
    with files.sidecar.open('ab') as f:f.write(pair+b'\n')
    assert a.snapshot()['adapter_status']=='LIVE_TAIL'
    a.close()


def test_adapter_api_is_read_only_and_lifespan_closes_reader(tmp_path):
    files=Files(tmp_path/'inbox');a=files.attach()
    app=create_market_analysis_time_app_v1(adapter=a)
    with TestClient(app) as client:
        result=client.get('/api/v2/market-analysis/time-profile')
        assert result.status_code==200
        assert result.json()['adapter_status']=='BOOTSTRAP'
        files.boundary()
        assert client.get('/api/v2/market-analysis/time-profile').json()['adapter_status']=='LIVE_TAIL'
        assert client.post('/api/v2/market-analysis/time-profile',json={'trade':True}).status_code==405
        assert not vars(app.state)['_state']
        assert_disabled(result.json())
    assert a.status=='DISCONNECTED'
    assert a.market.handle.closed


def test_closed_history_and_invalid_source_cannot_attach(tmp_path):
    files=Files(tmp_path/'inbox',history=3)
    Path(str(files.sidecar)+'.done.json').write_text('{}')
    a=files.attach();assert a.status=='DISCONNECTED'
    bad=tmp_path/'unreviewed.cs';bad.write_text('unreviewed')
    with pytest.raises(ValueError,match='INSTALLED_EXPORTER_MISMATCH'):
        FreshNativeAdapterV1(health_gated=False, directory=files.root,installed_exporter=bad,qpc_clock=lambda:('epoch',1000,1))


def test_native_clock_read_only_and_dependency_surface():
    clock=WindowsQpc();one=clock();two=clock()
    assert one[:2]==two[:2] and two[2]>=one[2]
    assert WindowsQpc()()[0]!=one[0]
    for path in ('backend/market_data/fresh_native_adapter_v1.py','backend/api/market_analysis_time_app_v1.py','tools/start_analysis_native_v1.py'):
        tree=ast.parse(Path(path).read_text())
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        assert not any(any(word in (name or '') for word in ('account','broker','execution','current_paper')) for name in imports)


def test_incomplete_line_at_startup_is_bootstrap_even_when_completed_after_attach(tmp_path):
    files=Files(tmp_path/'inbox',history=3)
    data=files.canonical.read_bytes();cut=len(data)-20
    files.canonical.write_bytes(data[:cut])
    a=files.attach()
    assert a.status=='BOOTSTRAP'
    with files.canonical.open('ab') as f:f.write(data[cut:])
    a.poll()
    assert a.status=='BOOTSTRAP' and a.delivered_records==0 and not a.profile.candles
    files.boundary();assert a.status=='LIVE_TAIL'
    a.close()


def test_missing_pair_hides_previously_available_analysis(tmp_path):
    files=Files(tmp_path/'inbox');a=files.attach()
    for _ in range(4):files.boundary()
    assert a.profile.candles
    # Canonical row arrives before sidecar: all components must become unavailable.
    row=json.loads(files.rows[-1]);row['sequence']=a.sequence+1
    with files.canonical.open('ab') as f:f.write(encode(row)+b'\n')
    result=a.snapshot()
    assert result['timing_pair_status']=='WAITING'
    assert result['analysis_status']=='BLOCKED'
    assert all(c['value'] is None for c in result['components'].values())
    a.close()


def test_faulting_background_poll_and_api_clock_fail_closed(tmp_path):
    files=Files(tmp_path/'inbox');a=files.attach();files.boundary()
    a.clock=lambda:(_ for _ in ()).throw(OSError('unavailable'))
    result=a.snapshot()
    assert result['adapter_status']=='REVOKED'
    assert_disabled(result)
    assert result['market_stream']=='NOT_LIVE'


def test_reader_handles_are_compatible_with_native_exporter_sharing(tmp_path):
    import ctypes
    from backend.market_data.fresh_native_adapter_v1 import _Tail
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    create.restype=ctypes.c_void_p
    path=tmp_path/'native-sharing.jsonl'
    writer=create(str(path),0x40000000,1,None,1,0x80,None)  # GENERIC_WRITE, FileShare.Read, CreateNew.
    assert writer!=ctypes.c_void_p(-1).value
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    try:
        reader=_Tail(path)
        assert reader.read(1)==[]
        reader.close()
    finally:kernel.CloseHandle(writer)


def test_launcher_import_does_not_start_adapter():
    import importlib
    module=importlib.import_module('tools.start_analysis_native_v1')
    assert callable(module.main)
    assert 'adapter' not in vars(module)
