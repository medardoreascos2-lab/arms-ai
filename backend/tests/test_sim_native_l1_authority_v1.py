"""Synthetic native frames only; no production streams or native execution."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.services import sim_native_l1_authority_v1 as m
from backend.market_data.fresh_native_adapter_v1 import MAX_FILE, _Tail, _exact_prefix_digest
from backend.services.runtime_admission_v2 import RuntimeAdmissionV2
from backend.services.sim_native_commissioning_policy_v1 import load
from backend.tests.test_sim_native_financial_runtime_service_v3 import environment

NOW = datetime(2026,9,27,23,tzinfo=timezone.utc)


class _ShortRead(BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 7) if size >= 0 else 7)


def test_prefix_digest_accepts_valid_short_reads():
    raw = b'prefix-integrity' * 4096
    assert _exact_prefix_digest(_ShortRead(raw), len(raw)) == sha256(raw).digest()


class Stream:
    def __init__(self, directory, monkeypatch, admission=None, clock=None):
        directory.mkdir(exist_ok=True)
        self.directory, self.now, self.tick = directory, NOW, 0
        self.session, self.seq = str(uuid4()), 0
        self.path = directory/(self.session+'.l1.jsonl')
        monkeypatch.setattr(m, 'private_path', lambda p: Path(p))
        self.admission = admission or RuntimeAdmissionV2(settings=load().api_settings)
        self.reader = m.SimNativeL1AuthorityV1(admission=self.admission, context=lambda:None,
            clock=clock or (lambda:self.now), elapsed=lambda:self.tick, directory=directory)

    def frame(self, kind, payload, **changes):
        value=dict(schema='arms.nt.l1.v1',session=self.session,sequence=self.seq,
            event_time=self.now.isoformat().replace('+00:00','Z'),kind=kind,payload=payload)
        value.update(changes)
        self.seq+=1
        return (json.dumps(value,separators=(',',':'))+'\n').encode()

    def append(self, raw):
        with self.path.open('ab') as f: f.write(raw)

    def hello(self): self.append(self.frame('HELLO',deepcopy(m.IDENTITY)))
    def quote(self, bid=25000, ask=25000.25, **changes):
        at=self.now.isoformat().replace('+00:00','Z')
        self.append(self.frame('QUOTE',dict(bid=bid,ask=ask,bid_time=at,ask_time=at,**changes)))
    def heartbeat(self): self.append(self.frame('HEARTBEAT',dict(connected=True)))
    def advance(self, seconds): self.now+=timedelta(seconds=seconds);self.tick+=seconds
    def get(self): return self.admission.quote_authority.get_quote(symbol='NQ')


class SegmentedStream(Stream):
    def __init__(self, directory, monkeypatch):
        directory.mkdir(exist_ok=True)
        self.directory, self.now, self.tick = directory, NOW, 0
        self.session, self.seq = str(uuid4()), 0
        self.segment_index = 1
        self.path = self._path(self.segment_index)
        self.path.touch()
        self.manifest_path = directory/(self.session+'.l1.manifest.json')
        monkeypatch.setattr(m, 'private_path', lambda p: Path(p))
        self.admission = RuntimeAdmissionV2(settings=load().api_settings)
        self.reader = m.SimNativeL1AuthorityV1(admission=self.admission, context=lambda:None,
            clock=lambda:self.now, elapsed=lambda:self.tick, directory=directory)
        self._write_manifest()

    def _path(self,index):
        return self.directory/(self.session+'.segment.'+str(index).zfill(6)+'.l1.jsonl')

    def _items(self, *, terminated=False, reason=None):
        result=[]
        for index in range(1,self.segment_index+1):
            path=self._path(index)
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            sealed=terminated or index<self.segment_index
            result.append(dict(index=index,file=path.name,
                first_sequence=rows[0]['sequence'] if rows else self.seq,
                last_sequence=rows[-1]['sequence'] if sealed and rows else None,
                bytes=path.stat().st_size if sealed else None,
                sha256=sha256(path.read_bytes()).hexdigest() if sealed else None,
                sealed=sealed))
        return result

    def _write_manifest(self, *, terminated=False, reason=None):
        value=dict(schema='arms.nt.l1.manifest.v1',session=self.session,
            provider='Provider31',instrument='NQ',contract='NQ DEC26',
            segment_capacity_bytes=m.L1_STREAM_MAX_BYTES,
            state='TERMINATED' if terminated else 'ACTIVE',
            terminal_reason=reason if terminated else None,
            segments=self._items(terminated=terminated,reason=reason))
        self.manifest_path.write_text(json.dumps(value,separators=(',',':'))+'\n')

    def rotate(self):
        self.segment_index+=1
        self.path=self._path(self.segment_index)
        self.path.touch()
        self._write_manifest()

    def terminate(self,reason):
        self.append(self.frame('TERMINAL',dict(connected=False,reason=reason)))
        self._write_manifest(terminated=True,reason=reason)


@pytest.fixture
def stream(tmp_path,monkeypatch):
    s=Stream(tmp_path/'l1',monkeypatch)
    yield s
    s.reader.close()


def test_segmented_reader_continuity_hashes_and_exact_terminal(tmp_path,monkeypatch):
    s=SegmentedStream(tmp_path/'segmented',monkeypatch)
    try:
        s.hello();s.quote();s.reader.poll()
        assert s.get()['ask']==25000.25
        s.rotate();s.advance(1);s.heartbeat();s.quote(ask=25000.50);s.reader.poll()
        assert s.get()['ask']==25000.50
        s.rotate();s.advance(1);s.heartbeat();s.quote(ask=25000.75);s.reader.poll()
        assert s.get()['ask']==25000.75
        assert s.reader.sequence==5
        s.terminate('FILE_IO_ERROR');s.reader.poll()
        snapshot=s.reader.get_snapshot()
        assert snapshot['status']=='REVOKED'
        assert snapshot['reason']=='L1_STREAM_TERMINATED:FILE_IO_ERROR'
        assert s.get() is None
        assert s.reader.sequence==6
        assert len(s.reader.sealed_segments)==3
    finally:
        s.reader.close()


def test_segmented_terminal_frame_revokes_before_final_manifest_swap(
    tmp_path,monkeypatch,
):
    s=SegmentedStream(tmp_path/'terminal-race',monkeypatch)
    try:
        s.hello();s.quote();s.reader.poll()
        s.append(s.frame('TERMINAL',dict(connected=False,reason='FILE_IO_ERROR')))
        s.reader.poll()
        assert s.reader.status=='REVOKED'
        assert s.reader.reason=='L1_STREAM_TERMINATED:FILE_IO_ERROR'
        assert s.get() is None
    finally:
        s.reader.close()


@pytest.mark.parametrize('damage',[
    'missing','duplicate','skip','sealed_mutation','session','provider','sequence_gap',
])
def test_segmented_reader_rejects_ambiguous_or_mutated_stream(
    tmp_path,monkeypatch,damage,
):
    s=SegmentedStream(tmp_path/('segmented-'+damage),monkeypatch)
    try:
        s.hello();s.quote();s.reader.poll();s.rotate();s.advance(1);s.heartbeat()
        value=json.loads(s.manifest_path.read_text())
        if damage=='missing':
            s._path(1).unlink()
        elif damage=='duplicate':
            value['segments'].append(deepcopy(value['segments'][-1]))
        elif damage=='skip':
            value['segments'][-1]['index']=3
        elif damage=='sealed_mutation':
            s._path(1).write_bytes(s._path(1).read_bytes().replace(b'25000.25',b'25000.50'))
        elif damage=='session':
            value['session']=str(uuid4())
        elif damage=='provider':
            value['provider']='Simulator'
        elif damage=='sequence_gap':
            s.seq+=1;s.heartbeat()
        if damage in ('duplicate','skip','session','provider'):
            s.manifest_path.write_text(json.dumps(value,separators=(',',':'))+'\n')
        s.reader.poll()
        assert s.reader.status=='REVOKED'
        assert s.get() is None
    finally:
        s.reader.close()


def test_valid_quote_uses_existing_storage_spread_and_news_still_blocks(stream):
    s=stream;s.hello();s.quote();s.reader.poll()
    assert s.get()==dict(symbol='NQ',bid=25000,ask=25000.25,timestamp=NOW)
    assert s.admission.runtime_spread_authority.get_spread_points(symbol='NQ',now=NOW)==.25
    assert s.reader.get_snapshot()['status']=='FRESH'
    assert s.admission.market_hours_provider.calendar_snapshot is None
    s.admission.clock=lambda:NOW
    with pytest.raises(ValueError,match='market hours'):s.admission.validate_market(symbol='NQ')
    with pytest.raises(RuntimeError,match='ONLY_PUBLISHER'):
        s.admission.quote_authority.publish_quote(symbol='NQ',bid=1,ask=2,timestamp=NOW)
    assert s.admission.quote_authority.get_quote(symbol='ES') is None


def test_l1_capacity_is_specific_and_generic_tail_keeps_32_mib(tmp_path,stream):
    assert MAX_FILE==32*1024*1024
    assert m.L1_STREAM_MAX_BYTES==256*1024*1024
    path=tmp_path/'old-boundary.l1.jsonl'
    with path.open('wb') as handle:
        handle.seek(MAX_FILE)
        handle.write(b'\n')
    with pytest.raises(ValueError,match='FILE_LIMIT'):
        _Tail(path)
    tail=_Tail(path,max_file=m.L1_STREAM_MAX_BYTES)
    try:
        assert tail.max_file==m.L1_STREAM_MAX_BYTES
    finally:
        tail.close()
    s=stream;s.hello();s.quote();s.reader.poll()
    assert s.get() is not None and s.reader.tail.max_file==m.L1_STREAM_MAX_BYTES


@pytest.mark.parametrize('published',[False,True])
def test_l1_limit_revokes_oversize_stream(stream,monkeypatch,published):
    s=stream;s.hello();s.quote()
    if published:
        s.reader.poll()
        assert s.get() is not None
        boundary=s.path.stat().st_size
        s.quote()
    else:
        boundary=s.path.stat().st_size-1
    monkeypatch.setattr(m,'L1_STREAM_MAX_BYTES',boundary)
    if published:
        s.reader.tail.max_file=boundary
    s.reader.poll()
    assert s.reader.status=='REVOKED' and s.get() is None
    assert s.admission.quote_authority.get_quote(symbol='NQ') is None


def test_wide_spread_fresh_but_existing_runtime_gate_rejects(stream):
    s=stream;s.hello();s.quote(ask=25005.25);s.reader.poll()
    assert s.reader.get_snapshot()['status']=='FRESH'
    assert s.admission.runtime_spread_authority.get_spread_points(symbol='NQ',now=NOW)==5.25
    s.admission.clock=lambda:NOW
    with pytest.raises(ValueError,match='spread'):s.admission.validate_market(symbol='NQ')


@pytest.mark.parametrize('damage', ['schema','session','gap','bool_sequence','duplicate_field','malformed','unknown',
    'contract','provider','instrument','expiry','timezone','tick','point','template','realtime','read_only','level',
    'future','half','crossed','zero','negative','nan','infinite','bool_price','side_future','side_stale','terminal','disconnected'])
def test_invalid_batch_never_publishes_even_valid_prefix(stream,damage):
    s=stream
    hello=deepcopy(m.IDENTITY)
    mapping={'contract':('contract','NQ MAR27'),'provider':('provider','Simulator'),'instrument':('instrument','ES'),
        'expiry':('expiry','2027-03-01'),'timezone':('application_timezone','Local'),'tick':('tick_size',.5),
        'point':('point_value',10),'template':('trading_hours_template','Other'),'realtime':('realtime',False),
        'read_only':('read_only',False),'level':('level',True)}
    if damage in mapping: k,v=mapping[damage];hello[k]=v
    s.append(s.frame('HELLO',hello));s.quote()
    at=NOW.isoformat().replace('+00:00','Z')
    p=dict(bid=25000,ask=25000.25,bid_time=at,ask_time=at)
    v=dict(schema='arms.nt.l1.v1',session=s.session,sequence=2,event_time=at,kind='QUOTE',payload=p)
    if damage=='schema':v['schema']='wrong'
    elif damage=='session':v['session']=str(uuid4())
    elif damage=='gap':v['sequence']=3
    elif damage=='bool_sequence':v['sequence']=True
    elif damage=='unknown':v['extra']=1
    elif damage=='future':v['event_time']=(NOW+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
    elif damage=='half':del p['ask']
    elif damage in ('crossed','zero','negative','nan','infinite','bool_price'):
        p['bid']={'crossed':25001,'zero':0,'negative':-1,'nan':float('nan'),'infinite':float('inf'),'bool_price':True}[damage]
    elif damage=='side_future':p['bid_time']=(NOW+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
    elif damage=='side_stale':p['bid_time']=(NOW-timedelta(seconds=31)).isoformat().replace('+00:00','Z')
    elif damage=='terminal':v.update(kind='TERMINAL',payload=dict(connected=False,reason='TERMINATED'))
    elif damage=='disconnected':v.update(kind='HEARTBEAT',payload=dict(connected=False))
    wire=json.dumps(v).encode()+b'\n'
    if damage=='duplicate_field':wire=b'{"schema":"bad",'+wire[1:]
    if damage=='malformed':wire=b'not json\n'
    s.append(wire);s.reader.poll()
    assert s.get() is None and s.reader.get_snapshot()['status']=='REVOKED'
    s.heartbeat();s.reader.poll();assert s.get() is None


def test_side_age_not_rejuvenated_and_exact_30_seconds(stream):
    s=stream;s.hello();s.quote();s.reader.poll()
    for _ in range(6):s.advance(5);s.heartbeat();s.reader.poll()
    assert s.get() is not None
    s.advance(.001);s.reader.poll()
    assert s.get() is None and s.reader.get_snapshot()['status']=='STALE'


def test_heartbeat_timeout_and_worker_stall_revoke_before_another_poll(stream):
    s=stream;s.hello();s.quote();s.reader.poll();s.advance(15.001)
    assert s.get() is None
    s.reader.poll();assert s.reader.status=='REVOKED'


@pytest.mark.parametrize('damage',['replace','truncate','overwrite','remove','directory','new_session','gap','rollback','conflict'])
def test_file_and_sequence_integrity_revoke_existing_quote(stream,damage):
    s=stream;s.hello();s.quote();s.reader.poll();assert s.get()
    prior=s.path.read_bytes()
    if damage in ('replace','directory'):
        # Windows may deny rename while a reader handle is open. Release only
        # the harness handle to exercise the pinned-identity check after replacement.
        s.reader.tail.handle.close()
    if damage=='replace':
        replacement=s.directory/'replacement';replacement.write_bytes(prior);replacement.replace(s.path)
    elif damage=='truncate':s.path.write_bytes(prior[:len(prior)//2])
    elif damage=='overwrite':s.path.write_bytes(prior.replace(b'25000.25',b'25000.50'))
    elif damage=='remove':s.path.unlink()
    elif damage=='directory':s.directory.rename(s.directory.with_name('moved'));s.directory.mkdir()
    elif damage=='new_session':(s.directory/(str(uuid4())+'.l1.jsonl')).write_bytes(prior)
    elif damage=='gap':s.seq+=1;s.heartbeat()
    elif damage=='rollback':s.append(prior.splitlines(keepends=True)[0])
    elif damage=='conflict':s.append(prior.splitlines(keepends=True)[1].replace(b'25000.25',b'25000.50'))
    if damage in ('gap','rollback','conflict'):
        assert s.get() is not None  # Unobserved suffix belongs to the next poll.
    else:
        assert s.get() is None
    s.reader.poll()
    assert s.reader.status=='REVOKED' and s.get() is None


def test_exact_duplicate_does_not_renew_liveness(stream):
    s=stream;s.hello();s.quote();s.reader.poll()
    last=s.path.read_bytes().splitlines(keepends=True)[-1]
    s.advance(10);s.append(last);s.reader.poll();assert s.get()
    s.advance(6);s.append(last);s.reader.poll();assert s.get() is None


def test_waiting_hello_half_quote_and_new_reader_requires_new_session(stream,monkeypatch):
    s=stream;s.reader.poll();assert s.reader.status=='WAITING_FOR_STREAM'
    s.path.touch();s.reader.poll();assert s.reader.status=='WAITING_FOR_HELLO'
    s.hello();s.reader.poll();assert s.reader.get_snapshot()['status']=='AWAITING_TWO_SIDED_QUOTE'
    s.quote();s.reader.poll();s.reader.close();s.advance(1)
    replacement=m.SimNativeL1AuthorityV1(admission=s.admission,context=lambda:None,clock=lambda:s.now,
        directory=s.directory,elapsed=lambda:s.tick)
    replacement.poll();assert replacement.status=='REVOKED'
    replacement.close()
    # A distinct operator-selected empty directory and new exporter session work.
    fresh=Stream(s.directory/'new',monkeypatch);fresh.hello();fresh.quote();fresh.reader.poll()
    assert fresh.get() and fresh.session!=s.session
    fresh.reader.close()


def test_get_never_ingests_and_context_failure_revokes(stream):
    s=stream;s.hello();s.quote()
    before=s.path.read_bytes();assert s.get() is None and s.reader.sequence==-1
    s.reader.poll();assert s.get()
    state=(s.reader.sequence,s.reader.last_poll_elapsed,s.reader.quote.copy())
    for _ in range(3):assert s.reader.get_snapshot()['status']=='FRESH'
    assert state==(s.reader.sequence,s.reader.last_poll_elapsed,s.reader.quote.copy()) and before==s.path.read_bytes()
    s.reader.context=Mock(side_effect=ValueError('config changed'))
    assert s.get() is None


def test_utc_and_monotonic_regression_fail_closed(stream):
    s=stream;s.hello();s.quote();s.reader.poll();s.now-=timedelta(seconds=1)
    assert s.get() is None;s.reader.poll();assert s.reader.status=='REVOKED'


@pytest.mark.parametrize('future_microseconds', [0, 1])
def test_batch_uses_post_read_clock_without_future_tolerance(stream, monkeypatch, future_microseconds):
    s=stream;s.path.touch()
    original_read=m._Tail.read
    post_wall=NOW+timedelta(milliseconds=1)
    def concurrent_read(tail, start_tick):
        assert s.now==NOW and start_tick==0  # poll sampled before the append
        s.now=post_wall+timedelta(microseconds=future_microseconds)
        s.hello();s.quote()
        rows=original_read(tail,start_tick)  # real bytes captured before post-read sampling
        s.now=post_wall;s.tick=.001
        return rows
    monkeypatch.setattr(m._Tail,'read',concurrent_read)
    s.reader.poll()
    if future_microseconds:
        assert s.reader.status=='REVOKED' and s.get() is None
        assert s.reader.quotes._quotes=={}
    else:
        assert s.reader.get_snapshot()['status']=='FRESH'
        assert s.get()['timestamp']==post_wall
        assert s.reader.last_poll_wall==post_wall
        assert s.reader.last_poll_elapsed==s.reader.quote_elapsed==.001
        assert s.reader.quote_age==0


@pytest.mark.parametrize('clock', ['wall','monotonic'])
def test_clock_regression_during_read_revokes_before_publication(stream, monkeypatch, clock):
    s=stream;s.hello();s.quote()
    original_read=m._Tail.read
    def regressing_read(tail,start_tick):
        rows=original_read(tail,start_tick)
        if clock=='wall':s.now-=timedelta(microseconds=1)
        else:s.tick=-.001
        return rows
    monkeypatch.setattr(m._Tail,'read',regressing_read)
    s.reader.poll()
    assert s.reader.status=='REVOKED' and s.get() is None
    assert s.reader.quotes._quotes=={}


def test_read_duration_counts_toward_heartbeat_timeout(stream,monkeypatch):
    s=stream;s.hello();s.quote()
    original_read=m._Tail.read
    def delayed_read(tail,start_tick):
        rows=original_read(tail,start_tick)
        s.advance(16)
        return rows
    monkeypatch.setattr(m._Tail,'read',delayed_read)
    s.reader.poll()
    assert s.reader.status=='REVOKED' and s.get() is None
    assert s.reader.quotes._quotes=={}


def test_growth_after_batch_read_publishes_only_completed_snapshot(stream,monkeypatch):
    s=stream;s.hello();s.quote()
    original_read=m._Tail.read
    def growing_read(tail,start_tick):
        rows=original_read(tail,start_tick)
        s.advance(.001);s.quote(ask=25000.50)
        return rows
    monkeypatch.setattr(m._Tail,'read',growing_read)
    s.reader.poll()
    assert s.reader.sequence==1  # appended sequence 2 was not in the read batch
    assert s.reader.get_snapshot()['status']=='FRESH'
    assert s.get()['ask']==25000.25  # Newly appended quote is not ingested by GET.


def test_append_after_completed_poll_keeps_validated_quote_and_get_pure(stream):
    s=stream;s.hello();s.quote();s.reader.poll()
    old=s.get();s.advance(.001);s.quote(ask=25000.50)
    before=s.path.read_bytes()
    state=(s.reader.sequence,s.reader.tail.offset,s.reader.tail.digest.digest(),
        s.reader.last_poll_wall,s.reader.last_poll_elapsed,deepcopy(s.reader.quotes._quotes))
    for _ in range(3):
        assert s.reader.get_snapshot()['status']=='FRESH' and s.get()==old
    assert state==(s.reader.sequence,s.reader.tail.offset,s.reader.tail.digest.digest(),
        s.reader.last_poll_wall,s.reader.last_poll_elapsed,s.reader.quotes._quotes)
    assert s.path.read_bytes()==before
    s.advance(15)
    assert s.get() is None and s.reader.get_snapshot()['status']=='REVOKED'


@pytest.mark.parametrize('already_published',[False,True])
def test_preexisting_backlog_blocks_publication_until_snapshot_consumed(stream,monkeypatch,already_published):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=stream;s.hello();s.quote()
    if already_published:s.reader.poll();s.quote(ask=25000.25)
    start=s.reader.tail.offset if s.reader.tail else 0
    # End exactly at a newline: partial-line protection alone cannot pass this test.
    chunk=s.path.stat().st_size-start
    s.quote(ask=25000.75)
    boundary=s.path.stat().st_size
    monkeypatch.setattr(tail_module,'CHUNK',chunk)
    published=deepcopy(s.reader.quotes._quotes)
    s.reader.poll()
    assert not s.reader.tail.partial and s.reader.tail.offset<boundary
    assert s.reader.quotes._quotes==published and s.get() is None
    assert s.reader.get_snapshot()['status']=='CATCHING_UP'
    assert s.reader.status!='REVOKED'
    s.reader.poll()
    assert s.reader.tail.offset==boundary
    assert s.reader.get_snapshot()['status']=='FRESH' and s.get()['ask']==25000.75


def test_segmented_preexisting_backlog_over_64k_catches_up_without_revocation(
    tmp_path,monkeypatch,
):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/'segmented-backlog',monkeypatch)
    try:
        s.hello()
        while s.path.stat().st_size <= tail_module.CHUNK * 2:
            s.quote(ask=25000.75)
        boundary=s.path.stat().st_size
        s.reader.poll()
        first=s.reader.get_snapshot()
        assert s.reader.tail.offset==tail_module.CHUNK < boundary
        assert first['status']=='CATCHING_UP'
        assert first['status']!='REVOKED'
        assert first['ready'] is False and first['authority'] is False
        assert s.get() is None
        while s.reader.tail.offset < boundary:
            s.reader.poll()
            if s.reader.tail.offset < boundary:
                assert s.reader.get_snapshot()['status']=='CATCHING_UP'
                assert s.get() is None
        snapshot=s.reader.get_snapshot()
        assert snapshot['status']=='FRESH'
        assert snapshot['ready'] is True and snapshot['authority'] is True
        assert s.get()['ask']==25000.75
    finally:
        s.reader.close()


def test_partial_jsonl_record_is_preserved_and_completed_on_later_poll(
    tmp_path,monkeypatch,
):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/'segmented-partial',monkeypatch)
    try:
        s.hello();s.quote()
        at=s.now.isoformat().replace('+00:00','Z')
        raw=s.frame('QUOTE',dict(bid=25000,ask=25000.75,bid_time=at,ask_time=at))
        split=len(raw)//2
        prefix=s.path.stat().st_size
        s.append(raw[:split])
        monkeypatch.setattr(tail_module,'CHUNK',prefix+split)
        s.reader.poll()
        assert s.reader.status=='CATCHING_UP'
        assert s.reader.tail.partial==raw[:split]
        assert s.reader.get_snapshot()['authority'] is False
        assert s.get() is None
        s.append(raw[split:])
        s.reader.poll()
        assert s.reader.tail.partial==b''
        assert s.reader.get_snapshot()['status']=='FRESH'
        assert s.get()['ask']==25000.75
    finally:
        s.reader.close()


def test_append_only_growth_while_catching_up_remains_valid(tmp_path,monkeypatch):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/'segmented-growth',monkeypatch)
    try:
        s.hello()
        while s.path.stat().st_size <= tail_module.CHUNK * 2:
            s.quote()
        s.reader.poll()
        assert s.reader.status=='CATCHING_UP'
        prior_boundary=s.reader.observed_size
        while s.path.stat().st_size <= prior_boundary+tail_module.CHUNK:
            s.quote(ask=25000.50)
        grown_boundary=s.path.stat().st_size
        s.reader.poll()
        assert s.reader.observed_size==grown_boundary
        assert s.reader.status=='CATCHING_UP'
        assert s.reader.get_snapshot()['status']=='CATCHING_UP'
        while s.reader.tail.offset < grown_boundary:
            s.reader.poll()
        assert s.reader.get_snapshot()['status']=='FRESH'
        assert s.get()['ask']==25000.50
    finally:
        s.reader.close()


def test_sequence_gap_during_segmented_catchup_revokes(tmp_path,monkeypatch):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/'segmented-gap',monkeypatch)
    try:
        s.hello()
        while s.path.stat().st_size <= tail_module.CHUNK * 2:
            s.quote()
        s.seq+=1
        s.quote()
        s.reader.poll()
        assert s.reader.status=='CATCHING_UP'
        while s.reader.status=='CATCHING_UP':
            s.reader.poll()
        snapshot=s.reader.get_snapshot()
        assert snapshot['status']=='REVOKED'
        assert snapshot['first_failed_check']=='SEQUENCE_GAP_OR_ROLLBACK'
        assert snapshot['validation_error']=='ValueError:SEQUENCE_GAP_OR_ROLLBACK'
        assert s.get() is None
    finally:
        s.reader.close()


@pytest.mark.parametrize('damage',['provider','session','manifest'])
def test_identity_or_manifest_mutation_during_segmented_catchup_revokes(
    tmp_path,monkeypatch,damage,
):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/('segmented-catchup-'+damage),monkeypatch)
    try:
        s.hello()
        while s.path.stat().st_size <= tail_module.CHUNK * 2:
            s.quote()
        s.reader.poll()
        assert s.reader.status=='CATCHING_UP'
        if damage=='session':
            s.append(s.frame('HEARTBEAT',dict(connected=True),session=str(uuid4())))
        else:
            value=json.loads(s.manifest_path.read_text())
            if damage=='provider':
                value['provider']='Simulator'
            else:
                value['segments'][0]['first_sequence']=1
            s.manifest_path.write_text(json.dumps(value,separators=(',',':'))+'\n')
        while s.reader.status=='CATCHING_UP':
            s.reader.poll()
        snapshot=s.reader.get_snapshot()
        assert snapshot['status']=='REVOKED'
        assert snapshot['first_failed_check'] is not None
        assert snapshot['validation_error'].startswith('ValueError:')
        assert s.get() is None
    finally:
        s.reader.close()


def test_stale_quote_after_segmented_catchup_remains_fail_closed(
    tmp_path,monkeypatch,
):
    from backend.market_data import fresh_native_adapter_v1 as tail_module
    s=SegmentedStream(tmp_path/'segmented-stale',monkeypatch)
    try:
        s.hello()
        while s.path.stat().st_size <= tail_module.CHUNK * 2:
            s.quote()
        s.advance(31);s.heartbeat()
        while s.reader.tail is None or s.reader.tail.offset < s.path.stat().st_size:
            s.reader.poll()
        snapshot=s.reader.get_snapshot()
        assert snapshot['status']=='STALE'
        assert snapshot['ready'] is False and snapshot['authority'] is False
        assert s.get() is None
    finally:
        s.reader.close()


def test_invalid_appended_suffix_revokes_on_next_poll(stream):
    s=stream;s.hello();s.quote();s.reader.poll();old=s.get()
    s.append(b'not json\n')
    assert s.reader.get_snapshot()['status']=='FRESH' and s.get()==old
    assert s.reader.sequence==1
    s.reader.poll()
    assert s.reader.status=='REVOKED' and s.get() is None
    assert s.reader.sequence==1


def test_appended_suffix_does_not_hide_consumed_prefix_overwrite(stream):
    s=stream;s.hello();s.quote();s.reader.poll();s.quote()
    s.path.write_bytes(s.path.read_bytes().replace(b'25000.25',b'25000.50',1))
    assert s.get() is None and s.reader.get_snapshot()['status']=='REVOKED'
    s.reader.poll();assert s.reader.status=='REVOKED'


def test_process_owner_paper_switch_and_get_have_no_publication_side_effects(environment,tmp_path,monkeypatch):
    from backend.api.asgi import create_asgi_app
    from backend.services.sim_native_financial_runtime_service_v3 import SimNativeFinancialRuntimeServiceV3
    monkeypatch.setenv('ARMS_ADMIN_TOKEN','offline-l1-admin')
    root,paths,now,_,_=environment
    clock=[now]
    monkeypatch.setattr(m,'private_path',lambda p:Path(p))
    svc=SimNativeFinancialRuntimeServiceV3(clock=lambda:clock[0])
    paper=tmp_path/'paper.json';paper.write_text('{"active_account":"TOPSTEP_150K"}')
    app=create_asgi_app(account_config_path=paper,state_path=tmp_path/'paper/state.json',sim_native_service_factory=lambda:svc)
    with TestClient(app,headers={'X-ARMS-ADMIN-TOKEN':'offline-l1-admin'}) as c:
        native=svc._runtime.lifecycle.runtime_admission_v2
        hours=native.market_hours_lifecycle
        reader=svc._l1
        s=Stream(root/'l1-stream',monkeypatch);s.reader.close();s.now=now
        s.hello();s.quote();svc.observe()
        assert native.quote_authority.get_quote(symbol='NQ')
        path='/api/v3/dashboard/sim-native-l1-authority'
        state=(reader.sequence,reader.last_poll_elapsed)
        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file() and p.suffix!='.lock'}
        for _ in range(3):assert c.get(path).json()['status']=='FRESH'
        assert c.post(path,json={'bid':1,'ask':2}).status_code==405
        assert state==(reader.sequence,reader.last_poll_elapsed)
        assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file() and p.suffix!='.lock'}
        old_paper=app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2
        old_paper.quote_authority.publish_quote(symbol='NQ',bid=1,ask=2,timestamp=now)
        assert native.quote_authority.get_quote(symbol='NQ')['bid']==25000
        target=next((k,v) for k,v in app.coordinator._catalog['accounts'].items() if v['profile_name']=='TOPSTEP_50K')
        assert c.post('/api/v2/dashboard/account-manager/switch',json={'account_id':target[0],**target[1]}).json()['changed']
        assert svc._l1 is reader and native.market_hours_lifecycle is hours
        assert c.get(path).json()['session']==s.session
        new_paper=app.coordinator.published.runtime.trade_lifecycle_service.runtime_admission_v2
        assert new_paper.quote_authority.get_quote(symbol='NQ') is None
        assert all(not list(p.iterdir()) for p in paths.values())
