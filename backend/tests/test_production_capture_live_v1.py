"""Offline adapter traces. No network, native process or runtime changes."""
from copy import deepcopy
from pathlib import Path

import pytest

from tools import production_capture_live_v1 as live
from backend.tests.test_native_receipt_ledger_v1 import RUN, SESSION, pair
from backend.tests.test_production_capture_contract_sprint15wr1 import recorded, synthetic_probes


def adapter(tmp_path):
    return live.LiveAdapter(tmp_path, dict(run_id=RUN,qpc_frequency=10,initial_qpc=pair(0)),pair(2))


def requested(a):
    a.step(pair(10),session=SESSION)
    a.step(pair(3310),closed=3)
    assert a.engine.state=='REMOVE_REQUESTED'


def ack(a):
    live.write_json(a.folder/'remove-ack.json',dict(run_id=RUN,native_session=SESSION,
                    request_id=a.engine.request_id,qpc=pair(3320),native_closure=False))
    a.step(pair(3330),closed=3)


@pytest.mark.parametrize('case,reason',[
    ('activation','ACTIVATION_TIMEOUT'),('capture','MINIMUM_CLOSED_NOT_OBSERVED'),
    ('ack','REMOVE_REQUEST_NOT_ACKNOWLEDGED'),('closure','WRITER_CLOSURE_TIMEOUT'),
    ('death','CLOCK_COLLECTOR_STOPPED_EARLY'),('qpc','QPC_REGRESSION'),
    ('frequency','QPC_FREQUENCY_CHANGED'),('wrong_ack','WRONG_REMOVE_ACK')])
def test_adapter_faults_latch(tmp_path,case,reason):
    a=adapter(tmp_path)
    if case=='activation': a.step(pair(6003))
    elif case=='capture': a.step(pair(10),session=SESSION); a.step(pair(3310))
    elif case in ('ack','closure','wrong_ack'):
        requested(a)
        if case=='ack': a.step(pair(3911),closed=3)
        elif case=='closure': ack(a); a.step(pair(3631),closed=3)
        else:
            live.write_json(tmp_path/'remove-ack.json',dict(run_id='wrong',native_session=SESSION))
            a.step(pair(3320),closed=3)
    elif case=='death': a.step(pair(10),collector_alive=False)
    elif case=='qpc': a.step(pair(1))
    else: a.step(pair(10,11))
    assert a.engine.state=='FAILED' and a.engine.reason==reason
    before=a.engine.snapshot()
    assert a.step(pair(99999))==before


def test_request_ack_closure_and_final_timeout(tmp_path,monkeypatch):
    a=adapter(tmp_path); requested(a)
    request=live.parse((tmp_path/'remove-request.json').read_bytes())
    assert request['instructions']=='Remove only the dedicated ArmsReadOnlyMarketV1 capture instance'
    ack(a)
    assert a.engine.state=='WAITING_FOR_CLOSURE'
    proof=dict(status='PASS',session=SESSION,qpc_frequency=10,
               first_callback={'qpc_before':20},last_emission={'qpc_after':3340})
    monkeypatch.setattr(live.production,'adjudicate',lambda *x:proof)
    a.step(pair(3350),closed=3,sealed=(b'a',b'b',b'c'))
    assert a.engine.state=='FINAL_CLOCK' and a.engine.snapshot()['collector_must_continue']
    a.step(pair(3651),closed=3)
    assert a.engine.reason=='FINAL_CLOCK_TIMEOUT'


@pytest.mark.parametrize('wrong_identity',[None,'request_id','run_id','native_session'])
def test_remove_close_then_explicit_ack_race(tmp_path,monkeypatch,wrong_identity):
    a=adapter(tmp_path);requested(a)
    proof=dict(status='PASS',session=SESSION,qpc_frequency=10,
               first_callback={'qpc_before':20},last_emission={'qpc_after':3320})
    monkeypatch.setattr(live.production,'adjudicate',lambda *x:proof)
    a.step(pair(3340),closed=3,sealed=(b'a',b'b',b'c'))
    assert a.engine.snapshot()['pending_closure'] and a.engine.state=='REMOVE_REQUESTED'
    assert a.engine.snapshot()['collector_must_continue']
    monkeypatch.setattr(live,'load_run',lambda p:(tmp_path,dict(run_id=RUN,qpc_frequency=10)))
    monkeypatch.setattr(live,'qpc_pair',lambda:pair(3350))
    live.acknowledge(tmp_path)
    if wrong_identity:
        row=live.parse((tmp_path/'remove-ack.json').read_bytes());row[wrong_identity]='wrong'
        (tmp_path/'remove-ack.json').write_bytes(live.canonical(row))
    result=a.step(pair(3360),closed=3)
    assert a.engine.closure_qpc==3341 and result['runtime_admission'] is False
    if wrong_identity:
        assert result['reason']=='REQUEST_ACK_IDENTITY'
        assert a.step(pair(3370))==result
    else:
        assert result['state']=='FINAL_CLOCK' and not result['pending_closure']
        assert result['collector_must_continue']
        assert [e['kind'] for e in a.engine.events]==['CAPTURE_COMPLETE_REMOVE_REQUEST',
            'SEALED_WRITERS_OBSERVED_PENDING_ACK','REMOVE_REQUEST_ACKNOWLEDGED','SEALED_WRITERS_ACCEPTED']


def test_clock_attempt_allowlist_retains_invalid(tmp_path,monkeypatch):
    worker=live.ClockCollector(tmp_path,RUN,10)
    samples=iter([pair(10),pair(20),pair(30),pair(40)])
    monkeypatch.setattr(live,'qpc_pair',lambda:next(samples))
    monkeypatch.setattr(live.clock,'resolve',lambda r:'192.0.2.1')
    raw=live.canonical(dict(reference=live.REFERENCES[0],epoch=RUN,status='PROBE_INVALID_OR_UNAVAILABLE'))
    bridge=dict(before=pair(20),after=pair(30),measurement_sha256=live.digest(raw))
    monkeypatch.setattr(live.production,'acquire_clock_measurement',lambda *a:(raw,bridge))
    assert worker.attempt(live.REFERENCES[0])==(raw,bridge)
    with pytest.raises(ValueError,match='ALLOWLISTED'): worker.attempt('evil.example')


@pytest.mark.parametrize('case',['pre','post','hash'])
def test_existing_coverage_enforced(case):
    _,proof=recorded(); closure=proof['last_emission']['qpc_after']+100
    kw=synthetic_probes(proof,closure)
    if case=='pre': kw['measurements']=kw['measurements'][3:]; kw['bridges']=kw['bridges'][3:]
    if case=='post': kw['measurements']=kw['measurements'][:3]; kw['bridges']=kw['bridges'][:3]
    if case=='hash': kw['bridges'][0]['measurement_sha256']='0'*64
    with pytest.raises(ValueError): live.coverage(proof,**kw)


def test_prepare_private_paths_pins_no_reuse(tmp_path,monkeypatch):
    monkeypatch.setattr(live,'base_directory',lambda:tmp_path)
    monkeypatch.setattr(live,'qpc_pair',lambda:pair())
    monkeypatch.setattr(live,'uuid4',lambda:RUN)
    folder=live.prepare()
    _,manifest=live.load_run(folder)
    assert manifest['source_sha256']==live.source_pins()
    assert manifest['repo_head']==live.head() and manifest['runtime_admission'] is False
    with pytest.raises(FileExistsError): live.prepare()
    monkeypatch.setattr(live,'head',lambda:'changed')
    with pytest.raises(ValueError,match='SOURCE_PIN'): live.load_run(folder)


def test_manifest_canonical_inventory_and_safety():
    assert live.canonical({'b':2,'a':1})==live.canonical({'a':1,'b':2})
    for name in ('tools/production_capture_live_v1.py','tools/native_receipt_ledger_v1.py'):
        source=(live.ROOT/name).read_text()
        for forbidden in ('from fastapi','backend.api','runtime_context','Account.Submit','Account.CreateOrder',
                          'RequestOneShotSubmit = true','RequestEmergencyFlatten = true'):
            assert forbidden not in source


def test_inventory_all_artifacts(tmp_path):
    live.write_json(tmp_path/'a.json',{'runtime_admission':False})
    result=live.inventory(tmp_path)
    assert result=={'a.json':{'bytes':len((tmp_path/'a.json').read_bytes()),
                            'sha256':live.digest((tmp_path/'a.json').read_bytes())}}


def test_complete_transition_with_real_archive_and_coverage(tmp_path):
    archive,proof=recorded()
    f=proof['qpc_frequency']; first=proof['first_callback']['qpc_before']
    last=proof['last_emission']['qpc_after']
    def p(q): return pair(q,f)
    a=live.LiveAdapter(tmp_path,dict(run_id=RUN,qpc_frequency=f,initial_qpc=p(first-10000)),p(first-9000))
    a.step(p(first-8000),session=proof['session'])
    request=max(first+330*f,last+100)
    a.step(p(request),closed=proof['closed'])
    live.write_json(tmp_path/'remove-ack.json',dict(run_id=RUN,native_session=proof['session'],
                    request_id=a.engine.request_id,qpc=p(request+10),native_closure=False))
    sealed=tuple(archive[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8'))
    a.step(p(request+20),closed=proof['closed'],sealed=sealed)
    assert a.engine.state=='FINAL_CLOCK'
    kw=synthetic_probes(proof,a.engine.closure_qpc)
    # Fixture run identity is retained by the synthetic clock records.
    run=kw['run_id']
    for index,raw in enumerate(kw['measurements']):
        row=live.parse(raw); row['epoch']=RUN; row['sample']['epoch']=RUN
        raw=live.canonical(row); kw['measurements'][index]=raw
        kw['bridges'][index]['measurement_sha256']=live.digest(raw)
    result=a.engine.finish(qpc=request+3000,epoch=RUN,frequency=f,
        measurements=kw['measurements'],bridges=kw['bridges'],references=kw['references'],unchanged_closed=True)
    assert result['state']=='COMPLETE' and result['runtime_admission'] is False


@pytest.mark.parametrize('attack',['none','hash','inventory','raw'])
def test_clock_durable_inventory_revalidation(tmp_path,attack):
    _,proof=recorded(); kw=synthetic_probes(proof,proof['last_emission']['qpc_after']+100)
    (tmp_path/'clock/measurements').mkdir(parents=True)
    attempts=[]
    for i,(raw,bridge) in enumerate(zip(kw['measurements'],kw['bridges'])):
        prefix=tmp_path/'clock/measurements'/f'{i:05d}'
        live.write_new(prefix.with_suffix('.json'),raw)
        live.write_json(prefix.with_suffix('.bridge.json'),bridge)
        attempts.append((i,raw,bridge))
    if attack=='hash': attempts[0][2]['measurement_sha256']='0'*64
    if attack=='inventory': live.write_new(tmp_path/'clock/measurements/extra',b'bad')
    if attack=='raw': (tmp_path/'clock/measurements/00000.json').write_bytes(b'changed')
    if attack=='none': live.validate_clock_artifacts(tmp_path,attempts,kw['run_id'],proof['qpc_frequency'])
    else:
        with pytest.raises(ValueError): live.validate_clock_artifacts(tmp_path,attempts,kw['run_id'],proof['qpc_frequency'])


def test_native_monitor_receipts_seal_and_replacement(tmp_path,monkeypatch):
    archive,proof=recorded()
    (tmp_path/'market/timing').mkdir(parents=True); (tmp_path/'receipts').mkdir()
    session=proof['session']; f=proof['qpc_frequency']
    sealed=tuple(archive[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8'))
    paths=(tmp_path/'market'/f'{session}.jsonl',
           tmp_path/'market/timing'/f'{session}.production-timing.jsonl',
           tmp_path/'market/timing'/f'{session}.production-timing.jsonl.done.json')
    for path,raw in zip(paths,sealed): path.write_bytes(raw)
    # Dependency-injected offline reads, never claiming native exclusive closure.
    q=proof['last_emission']['qpc_after']+100
    counter=iter(range(q,q+1000,2))
    original=live.StableFile
    monkeypatch.setattr(live,'StableFile',lambda path,frequency,**kw:original(path,frequency,
                        sample=lambda:pair(next(counter),f),**kw))
    monkeypatch.setattr(live,'exclusive_bytes',lambda paths:tuple(p.read_bytes() for p in paths))
    monitor=live.NativeMonitor(tmp_path,RUN,f)
    assert monitor.poll()==sealed and monitor.closed==proof['closed']
    before=monitor.ledger.path.read_bytes()
    assert monitor.poll()==sealed and monitor.ledger.path.read_bytes()==before
    assert live.replay(before,*sealed[:2],RUN,f)['records']==proof['records']
    paths[0].rename(tmp_path/'old')
    paths[0].write_bytes(sealed[0])
    with pytest.raises(ValueError,match='REPLACED|SEALED_FILES_CHANGED'): monitor.poll()


def test_private_output_rejects_runtime_and_repository(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(live.ROOT))
    with pytest.raises(ValueError,match='PRIVATE_DIRECTORY'): live.base_directory()
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'commands'))
    with pytest.raises(ValueError,match='FORBIDDEN_OUTPUT'): live.base_directory()


def test_ack_is_explicit_and_does_not_claim_closure(tmp_path,monkeypatch):
    a=adapter(tmp_path); requested(a)
    monkeypatch.setattr(live,'load_run',lambda p:(tmp_path,dict(run_id=RUN,qpc_frequency=10)))
    monkeypatch.setattr(live,'qpc_pair',lambda:pair(3320))
    live.acknowledge(tmp_path)
    row=live.parse((tmp_path/'remove-ack.json').read_bytes())
    assert row['native_closure'] is False
    assert row['statement']=='I received and completed the manual remove request.'
    assert a.engine.state=='REMOVE_REQUESTED'
    a.step(pair(3330),closed=3)
    assert a.engine.state=='WAITING_FOR_CLOSURE'
    with pytest.raises(ValueError): live.acknowledge(tmp_path)


def test_dead_collector_finalizes_fail_manifest_without_network_or_native(tmp_path,monkeypatch):
    import queue
    import threading
    monkeypatch.setattr(live,'base_directory',lambda:tmp_path)
    values=iter(range(10,1000,10))
    monkeypatch.setattr(live,'qpc_pair',lambda:pair(next(values)))
    monkeypatch.setattr(live,'uuid4',lambda:RUN)
    snapshots=[]
    def windows():
        snapshots.append(True)
        return {'status':'SYNTHETIC_UNAVAILABLE','last_sync_mono_us':None}
    monkeypatch.setattr(live.clock,'windows_snapshot',windows)
    class DeadCollector:
        def __init__(self,*args):
            self.stop=threading.Event(); self.items=queue.Queue(); self.error=None; self.thread=self
        def start(self): pass
        def is_alive(self): return False
        def join(self,*args): pass
    monkeypatch.setattr(live,'ClockCollector',DeadCollector)
    folder=live.prepare()
    result=live.run(folder)
    assert result['result']=='FAIL' and result['runtime_admission'] is False
    assert result['absolute_time_authority']=='UNKNOWN' and result['data_freshness']=='NOT_ASSERTED'
    assert len(snapshots)==2
    manifest=live.parse((folder/'final/capture-manifest.json').read_bytes())
    assert manifest['artifacts']==live.inventory(folder)
    assert manifest['repo_head']==live.head() and manifest['source_sha256']==live.source_pins()
    assert not any((folder/'market').iterdir())
    with pytest.raises(FileExistsError): live.run(folder)


def test_worker_retains_every_invalid_attempt(tmp_path,monkeypatch):
    (tmp_path/'clock/measurements').mkdir(parents=True)
    worker=live.ClockCollector(tmp_path,RUN,10)
    calls=[]
    def attempt(ref):
        calls.append(ref)
        raw=live.canonical(dict(reference=ref,epoch=RUN,status='PROBE_INVALID_OR_UNAVAILABLE'))
        q=len(calls)*10
        if len(calls)==3: worker.stop.set()
        return raw,dict(before=pair(q),after=pair(q+2),measurement_sha256=live.digest(raw))
    monkeypatch.setattr(worker,'attempt',attempt)
    worker.work()
    assert calls==list(live.REFERENCES) and worker.items.qsize()==3
    attempts=[worker.items.get_nowait() for _ in range(3)]
    live.validate_clock_artifacts(tmp_path,attempts,RUN,10)
    assert all(live.parse(raw)['status']=='PROBE_INVALID_OR_UNAVAILABLE' for _,raw,_ in attempts)



def test_replace_status_retries_windows_sharing_failure(tmp_path, monkeypatch):
    """A transient Windows reader must not kill status publication."""
    live.write_json(
        tmp_path / "status.json",
        {"state": "OLD"},
    )

    real_replace = live.os.replace
    calls = []

    def flaky_replace(source, target):
        calls.append((source, target))

        if len(calls) == 1:
            error = PermissionError(13, "sharing violation")
            error.winerror = 32
            raise error

        return real_replace(source, target)

    monkeypatch.setattr(live.os, "replace", flaky_replace)
    monkeypatch.setattr(live.os, "name", "nt")
    monkeypatch.setattr(live.time, "sleep", lambda _seconds: None)

    live.replace_status(
        tmp_path,
        {"state": "CAPTURING", "runtime_admission": False},
    )

    status = live.parse(
        (tmp_path / "status.json").read_bytes()
    )

    assert status == {
        "state": "CAPTURING",
        "runtime_admission": False,
    }

    assert len(calls) == 2
    assert not (tmp_path / "status.next").exists()


def test_replace_status_terminal_failure_does_not_leave_status_next(
    tmp_path, monkeypatch
):
    """A permanent publication failure must not poison a later attempt."""
    live.write_json(
        tmp_path / "status.json",
        {"state": "OLD"},
    )

    real_replace = live.os.replace

    def always_locked(_source, _target):
        error = PermissionError(13, "sharing violation")
        error.winerror = 32
        raise error

    monkeypatch.setattr(live.os, "replace", always_locked)
    monkeypatch.setattr(live.os, "name", "nt")
    monkeypatch.setattr(live.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError):
        live.replace_status(
            tmp_path,
            {"state": "CAPTURING"},
        )

    # Critical regression: the failed publication must not leave the exact
    # poison file that killed the physical LONG_A run.
    assert not (tmp_path / "status.next").exists()

    # A later normal publication must still work.
    monkeypatch.setattr(live.os, "replace", real_replace)

    live.replace_status(
        tmp_path,
        {"state": "RECOVERED_FOR_TEST_ONLY"},
    )

    assert not (tmp_path / "status.next").exists()

    status = live.parse(
        (tmp_path / "status.json").read_bytes()
    )

    assert status["state"] == "RECOVERED_FOR_TEST_ONLY"
