"""Offline event traces and recorded archive replay; never starts a watcher."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tools import production_capture_contract_v1 as contract
from tools import production_timing_v1 as production
from backend.tests.test_clock_evidence_sprint15u import packet_case

RUN = '3e821985-2bcd-4ccc-adef-3cb588cbeb61'
SESSION = 'f36aeebc-0ca7-4079-a318-55cce9d38602'
ROOT = Path(__file__).resolve().parents[2]


def engine():
    return contract.Coordinator(run_id=RUN, epoch='synthetic-boot', frequency=10,
                                ready_qpc=0, budget=contract.Budget(600,330,60,30,30))


def tick(c, q, **kw):
    return c.tick(q, epoch='synthetic-boot', frequency=10, **kw)


def requested(c):
    tick(c, 100, session=SESSION)
    assert tick(c, 3400, closed=3)['state'] == 'REMOVE_REQUESTED'
    assert c.request_id == RUN+':remove:1'


def acknowledged(c):
    requested(c)
    assert tick(c, 3500, closed=3, acknowledged_request=c.request_id)['state']=='WAITING_FOR_CLOSURE'


def synthetic_seal(monkeypatch):
    proof = dict(status='PASS',session=SESSION,qpc_frequency=10,
                 first_callback={'qpc_before':101},last_emission={'qpc_after':3600})
    monkeypatch.setattr(production,'adjudicate',lambda *args: proof)
    return (b'synthetic-canonical',b'synthetic-pairs',b'synthetic-seal')


def test_on_time_close_keeps_collector_running(monkeypatch):
    c=engine();acknowledged(c)
    s=tick(c,3650,closed=3,sealed=synthetic_seal(monkeypatch),exclusive_closed=True)
    assert s['state']=='FINAL_CLOCK' and s['collector_must_continue']
    assert s['closure_deadline_qpc']==3800 and s['runtime_admission'] is False
    assert [e['kind'] for e in c.events]==['CAPTURE_COMPLETE_REMOVE_REQUEST','REMOVE_REQUEST_ACKNOWLEDGED','SEALED_WRITERS_OBSERVED']


@pytest.mark.parametrize('case',['late_removal','missing_seal','late_seal','visibility_after_deadline','watcher_timeout'])
def test_deadline_fault_latches_without_retroactive_pass(monkeypatch,case):
    c=engine();acknowledged(c)
    sealed=synthetic_seal(monkeypatch)
    at_timeout=dict(sealed=sealed,exclusive_closed=True) if case in ('late_seal','visibility_after_deadline') else {}
    s=tick(c,3800,closed=3,**at_timeout)
    assert s['reason']=='WRITER_CLOSURE_TIMEOUT' and s['state']=='FAILED'
    assert tick(c,3900,closed=3,sealed=sealed,exclusive_closed=True)==s
    assert s['collector_must_continue'] is False


def test_visibility_delay_inside_allowance_is_valid(monkeypatch):
    c=engine();acknowledged(c)
    assert tick(c,3600,closed=3)['state']=='WAITING_FOR_CLOSURE'
    assert tick(c,3799,closed=3,sealed=synthetic_seal(monkeypatch),exclusive_closed=True)['state']=='FINAL_CLOCK'


@pytest.mark.parametrize('ack',[False,True])
def test_early_and_unacknowledged_close_cannot_complete(ack):
    c=engine();tick(c,100,session=SESSION)
    if ack: tick(c,3400,closed=3)
    assert tick(c,3450 if ack else 200,closed=3,sealed=(b'',b'',b''))['reason']=='EARLY_OR_UNACKNOWLEDGED_CLOSURE'


def test_display_acknowledgement_starts_allowance_not_old_wall_deadline():
    c=engine();requested(c)
    assert tick(c,3790,closed=3)['state']=='REMOVE_REQUESTED'
    s=tick(c,3900,closed=3,acknowledged_request=c.request_id)
    assert s['closure_deadline_qpc']==4200
    assert tick(c,4199,closed=3)['state']=='WAITING_FOR_CLOSURE'
    assert tick(c,4200,closed=3)['reason']=='WRITER_CLOSURE_TIMEOUT'


@pytest.mark.parametrize('wall',['1900-01-01T00:00:00Z','2200-01-01T00:00:00Z',None])
def test_wall_clock_jumps_do_not_change_monotonic_deadlines(wall):
    c=engine();acknowledged(c)
    assert tick(c,3799,closed=3,wall_utc=wall)['state']=='WAITING_FOR_CLOSURE'
    assert tick(c,3800,closed=3,wall_utc=wall)['reason']=='WRITER_CLOSURE_TIMEOUT'


@pytest.mark.parametrize('kw',[{'qpc':99},{'qpc':101,'epoch':'different-boot'},{'qpc':101,'frequency':11}])
def test_monotonic_regression_epoch_or_frequency_change_fail_closed(kw):
    c=engine();tick(c,100,session=SESSION)
    args=dict(qpc=101,epoch='synthetic-boot',frequency=10);args.update(kw)
    assert c.tick(**args)['reason']=='MONOTONIC_CONTINUITY_LOST'


def test_no_ack_and_wrong_ack_are_bounded():
    c=engine();requested(c)
    assert tick(c,4000,closed=3)['reason']=='REMOVE_REQUEST_NOT_ACKNOWLEDGED'
    c=engine();requested(c)
    assert tick(c,3401,closed=3,acknowledged_request='another-run')['reason']=='REQUEST_ACK_IDENTITY'


def test_collector_stopping_early_fails_even_if_seal_present(monkeypatch):
    c=engine();acknowledged(c)
    assert tick(c,3650,closed=3,collector_alive=False,sealed=synthetic_seal(monkeypatch),exclusive_closed=True)['reason']=='CLOCK_COLLECTOR_STOPPED_EARLY'


def test_invalid_or_not_exclusively_closed_seal_is_rejected(monkeypatch):
    c=engine();acknowledged(c)
    assert tick(c,3650,closed=3,sealed=synthetic_seal(monkeypatch))['reason']=='INVALID_SEALED_STREAM'


def test_final_clock_timeout_remains_bounded(monkeypatch):
    c=engine();acknowledged(c)
    tick(c,3650,closed=3,sealed=synthetic_seal(monkeypatch),exclusive_closed=True)
    assert tick(c,3950,closed=3)['reason']=='FINAL_CLOCK_TIMEOUT'


def recorded():
    c=json.loads((ROOT/'backend/tests/production_timing_sprint15w.json').read_text())['native_capture']
    proof=production.adjudicate(*[c[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8')])
    assert proof['status']=='PASS'
    return c,proof


def synthetic_probes(proof,closure):
    """Synthetic bracketing probes, explicitly not new native evidence."""
    raws=[];bridges=[];refs=tuple(contract.clock.REFERENCES)
    for q in (proof['first_callback']['qpc_before']-1000,closure+1000):
        for i,ref in enumerate(refs):
            packet,origin,sent,received=packet_case()
            for stamp in (sent,received):
                for key in ('mono_before_ns','mono_after_ns'):
                    stamp[key]+=len(raws)*1000000000
            row=contract.clock.decode_reply(packet,origin,sent,received,ref,RUN)
            raw=json.dumps(row).encode();raws.append(raw)
            def p(value): return dict(qpc_before=value,qpc_after=value+1,frequency=proof['qpc_frequency'],host_unix_ns=0)
            bridges.append(dict(before=p(q+i*10),after=p(q+i*10+2),measurement_sha256=hashlib.sha256(raw).hexdigest()))
    return dict(run_id=RUN,references=refs,measurements=raws,bridges=bridges,closure_qpc=closure)


def test_recorded_archive_pairing_preserved_but_epoch_fails():
    c,proof=recorded()
    assert proof['pairs']==18 and proof['closed']==8 and proof['production_exporter_emission_binding']=='PASS_STREAM_ONLY'
    with pytest.raises(ValueError,match='EPOCH_DOES_NOT_BRACKET_PRODUCTION'):
        contract.coverage(proof,run_id=RUN,references=tuple(contract.clock.REFERENCES),
                          measurements=[r.encode() for r in c['clock_measurements_utf8']],bridges=c['clock_bridges'],
                          closure_qpc=proof['last_emission']['qpc_after']+1)


def test_clock_collection_brackets_closure_without_granting_authority():
    _,proof=recorded();args=synthetic_probes(proof,proof['last_emission']['qpc_after']+100)
    bound=contract.coverage(proof,**args)
    assert bound['status']=='PASS_COVERAGE_ONLY' and bound['reference_bound'] is None
    assert bound['drift_bound'] is None and bound['runtime_admission'] is False


@pytest.mark.parametrize('case',['event_after_final_sample','closure_after_final_sample','missing_reference','bad_packet','bad_hash','reused_sample'])
def test_incomplete_clock_coverage_rejected(case):
    _,proof=recorded();args=synthetic_probes(proof,proof['last_emission']['qpc_after']+100)
    if case=='event_after_final_sample':
        proof=deepcopy(proof);proof['last_emission']['qpc_after']=args['bridges'][-1]['after']['qpc_after']+100
        args['closure_qpc']=proof['last_emission']['qpc_after']+1
    elif case=='closure_after_final_sample': args['closure_qpc']=args['bridges'][-1]['after']['qpc_after']+100
    elif case=='missing_reference': args['measurements'].pop();args['bridges'].pop()
    elif case=='bad_hash': args['bridges'][-1]['measurement_sha256']='0'*64
    elif case=='reused_sample':
        args['measurements'][-1]=args['measurements'][2]
        args['bridges'][-1]['measurement_sha256']=hashlib.sha256(args['measurements'][-1]).hexdigest()
    else:
        row=json.loads(args['measurements'][-1]);row['packet_hex']='00'*48
        args['measurements'][-1]=json.dumps(row).encode()
        args['bridges'][-1]['measurement_sha256']=hashlib.sha256(args['measurements'][-1]).hexdigest()
    with pytest.raises(ValueError): contract.coverage(proof,**args)


@pytest.mark.parametrize('unchanged',[True,False])
def test_complete_engine_uses_actual_seal_and_validated_final_coverage(unchanged):
    c,proof=recorded();f=proof['qpc_frequency'];start=proof['first_callback']['qpc_before']-10
    # Synthetic policy permits replay of this long recorded stream. It does NOT
    # revise its original failed 330+30 second capture contract.
    engine=contract.Coordinator(run_id=RUN,epoch='synthetic',frequency=f,ready_qpc=start-100,
                                budget=contract.Budget(600,1,60,600,30))
    def step(q,**kw):return engine.tick(q,epoch='synthetic',frequency=f,**kw)
    step(start,session=SESSION)
    step(start+f,closed=3)
    step(start+f+1,closed=3,acknowledged_request=engine.request_id)
    closure=proof['last_emission']['qpc_after']+100
    sealed=tuple(c[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8'))
    assert step(closure,closed=8,sealed=sealed,exclusive_closed=True)['state']=='FINAL_CLOCK'
    args=synthetic_probes(proof,closure)
    result=engine.finish(qpc=args['bridges'][-1]['after']['qpc_after']+1,epoch='synthetic',frequency=f,
                         measurements=args['measurements'],bridges=args['bridges'],references=args['references'],
                         unchanged_closed=unchanged)
    assert result['state']==('COMPLETE' if unchanged else 'FAILED')
    assert result['runtime_admission'] is False and result['reference_bound']=='UNKNOWN'
    assert result['collector_must_continue'] is False


def test_contract_has_no_automatic_activation_or_io():
    import ast
    tree=ast.parse(Path(contract.__file__).read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    assert not names.intersection({'open','subprocess','socket','threading','ctypes','exec','eval'})
