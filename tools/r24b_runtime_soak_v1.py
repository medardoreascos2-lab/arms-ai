"""Bounded offline R24B runtime soak; synthetic fixtures and zero orders only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import tracemalloc
from uuid import uuid4

from backend.services import sim_native_l1_authority_v1 as l1_module
from backend.services.runtime_admission_v2 import RuntimeAdmissionV2
from backend.services.sim_native_commissioning_policy_v1 import load
from backend.tests.test_current_paper_sprint10 import START, deliver, event, service
from tools.windows_runtime_supervisor_v1 import supervise


def _frame(session, sequence, kind, payload, at):
    return (json.dumps({'schema':'arms.nt.l1.v1','session':session,
        'sequence':sequence,'event_time':at.isoformat().replace('+00:00','Z'),
        'kind':kind,'payload':payload},separators=(',',':'),allow_nan=False)
        +'\n').encode()


class _SegmentedL1:
    def __init__(self, directory, now):
        self.directory=Path(directory);self.directory.mkdir()
        self.session=str(uuid4());self.sequence=0;self.index=1
        self.paths=[];self.seals=[];self.now=now
        self._new_segment();self._manifest()

    def _new_segment(self):
        path=self.directory/(self.session+'.segment.'+str(self.index).zfill(6)+'.l1.jsonl')
        path.touch();self.paths.append(path);self.path=path

    def _manifest(self, *, terminated=False, reason=None):
        items=list(self.seals)
        if len(items)<len(self.paths):
            items.append({'index':self.index,'file':self.path.name,
                'first_sequence':self.segment_first,'last_sequence':None,
                'bytes':None,'sha256':None,'sealed':False})
        value={'schema':'arms.nt.l1.manifest.v1','session':self.session,
            'provider':'Provider31','instrument':'NQ','contract':'NQ DEC26',
            'segment_capacity_bytes':l1_module.L1_STREAM_MAX_BYTES,
            'state':'TERMINATED' if terminated else 'ACTIVE',
            'terminal_reason':reason if terminated else None,'segments':items}
        target=self.directory/(self.session+'.l1.manifest.json')
        temporary=target.with_suffix(target.suffix+'.tmp')
        with temporary.open('wb') as stream:
            stream.write((json.dumps(value,separators=(',',':'))+'\n').encode())
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)

    @property
    def segment_first(self):
        return 0 if not self.seals else self.seals[-1]['last_sequence']+1

    def append(self, kind, payload, at):
        raw=_frame(self.session,self.sequence,kind,payload,at)
        with self.path.open('ab',buffering=0) as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self.sequence+=1

    def rotate(self):
        raw=self.path.read_bytes()
        self.seals.append({'index':self.index,'file':self.path.name,
            'first_sequence':self.segment_first,
            'last_sequence':self.sequence-1,'bytes':len(raw),
            'sha256':sha256(raw).hexdigest(),'sealed':True})
        self.index+=1;self._new_segment();self._manifest()

    def terminate(self, at, reason='SESSION_TERMINATED'):
        self.append('TERMINAL',{'connected':False,'reason':reason},at)
        raw=self.path.read_bytes()
        self.seals.append({'index':self.index,'file':self.path.name,
            'first_sequence':self.segment_first,
            'last_sequence':self.sequence-1,'bytes':len(raw),
            'sha256':sha256(raw).hexdigest(),'sealed':True})
        self._manifest(terminated=True,reason=reason)


def _supervised_lifecycle(*, report_directory, duration, run_id, cwd):
    pid_path=Path(report_directory).parent/'runtime-soak-child-pids.json'
    child="import time;time.sleep("+str(duration+30)+")"
    launcher=(
        "import json,subprocess,sys,time;"
        "backend=subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);"
        "frontend=subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);"
        "open("+repr(str(pid_path))+",'w').write(json.dumps("
        "{'backend':backend.pid,'frontend':frontend.pid}));"
        "time.sleep("+str(duration)+");"
        "backend.terminate();frontend.terminate();"
        "backend.wait(timeout=10);frontend.wait(timeout=10)"
    )
    return supervise(command=[sys.executable,'-c',launcher],
        report_directory=report_directory,run_id=run_id,cwd=cwd)


def run_soak(*, result_path, wall_seconds=300, synthetic_hours=16):
    if wall_seconds < 1 or synthetic_hours < 1:
        raise ValueError('POSITIVE_SOAK_DURATION_REQUIRED')
    bars=int(synthetic_hours*60)
    if bars > 4000:
        raise ValueError('DECISION_TRACE_CERTIFICATION_BOUND')
    result_path=Path(result_path).resolve()
    result_path.parent.mkdir(parents=True,exist_ok=True)
    run_id='r24b-offline-soak-'+uuid4().hex
    supervisor_directory=result_path.parent/('runtime-soak-supervisor-'+run_id)
    started=time.perf_counter();wall_started=time.monotonic()
    health_checks=0
    original_private=l1_module.private_path
    tracemalloc.start()
    paper=None;reader=None;root=None
    try:
        with TemporaryDirectory(prefix='arms-r24b-runtime-',delete=False) as temporary:
            root=Path(temporary)
            paper_root=root/'paper';paper_root.mkdir()
            paper,clock=service(paper_root)
            l1_module.private_path=lambda path:Path(path)
            stream=_SegmentedL1(root/'l1',clock[0])
            admission=RuntimeAdmissionV2(settings=load().api_settings)
            reader=l1_module.SimNativeL1AuthorityV1(admission=admission,
                context=lambda:None,clock=lambda:clock[0],
                elapsed=time.monotonic,directory=stream.directory)
            stream.append('HELLO',dict(l1_module.IDENTITY),clock[0])
            stream.append('HEARTBEAT',{'connected':True},clock[0])
            at=clock[0].isoformat().replace('+00:00','Z')
            stream.append('QUOTE',{'bid':10000.0,'ask':10000.25,
                'bid_time':at,'ask_time':at},clock[0])
            reader.poll()
            if reader.inspect()[1] is None:
                raise RuntimeError('INITIAL_L1_NOT_FRESH')

            with ThreadPoolExecutor(max_workers=1) as executor:
                supervised=executor.submit(_supervised_lifecycle,
                    report_directory=supervisor_directory,
                    duration=wall_seconds,run_id=run_id,cwd=Path.cwd())
                timestamps=[];candidate=START
                while len(timestamps)<bars:
                    if (paper.gate._open(candidate)
                            and paper.gate._open(candidate+timedelta(seconds=59))):
                        timestamps.append(candidate)
                    candidate+=timedelta(minutes=1)
                for index,timestamp in enumerate(timestamps):
                    observation=event(0,start=timestamp,sequence=index,
                        event_id=str(index))
                    clock[0]=observation.received_at
                    if index and index%240==0:
                        stream.rotate()
                    stream.append('HEARTBEAT',{'connected':True},clock[0])
                    stamp=clock[0].isoformat().replace('+00:00','Z')
                    stream.append('QUOTE',{'bid':10000.0,'ask':10000.25,
                        'bid_time':stamp,'ask_time':stamp},clock[0])
                    reader.poll()
                    l1_view,quote=reader.inspect()
                    if l1_view['status']!='FRESH' or quote is None:
                        raise RuntimeError('L1_HEALTH_LOST:'+str(l1_view))
                    deliver(paper,clock,observation)
                    if index==0:
                        # Synthetic audit transitions occur with no subsequent
                        # observation while enabled, so execution remains zero.
                        paper._runtime.control('enable',
                            reason='OFFLINE_SOAK_SIMULATION',
                            initiating_path='R24B_OFFLINE_SOAK',
                            request_id='r24b-soak-enable',
                            request_nonce='offline-only')
                        paper._runtime.control('disable',reason='OPERATOR_REQUEST',
                            initiating_path='R24B_OFFLINE_SOAK',
                            request_id='r24b-soak-disable',
                            request_nonce='offline-only')
                    snapshot=paper.get_snapshot();health_checks+=1
                    if snapshot.get('paper_execution_enabled') is not False:
                        raise RuntimeError('PAPER_ENABLED_DURING_OFFLINE_SOAK')
                    target=wall_started+wall_seconds*(index+1)/bars
                    remaining=target-time.monotonic()
                    if remaining>0:
                        time.sleep(remaining)
                supervisor_report=supervised.result(timeout=wall_seconds+30)

            stream.terminate(clock[0])
            reader.poll()
            l1_terminal=reader.reason
            if l1_terminal!='L1_STREAM_TERMINATED:SESSION_TERMINATED':
                raise RuntimeError('L1_TERMINAL_MISMATCH:'+str(l1_terminal))
            snapshot=paper.get_snapshot()
            runtime=paper._runtime._paper.runtime
            fills=len(runtime.lifecycle.broker_connector_v2.get_fills())
            positions=len(runtime.lifecycle.get_active_positions())
            completed=len(runtime.completed)
            audit=paper._runtime.get_authority_audit()
            journal_mode=paper._runtime._db.execute('PRAGMA journal_mode').fetchone()[0]
            wal_checkpoint=list(paper._runtime._db.execute(
                'PRAGMA wal_checkpoint(PASSIVE)').fetchone())
            decisions=snapshot.get('session_decision_summary') or {}
            decision_total=sum(decisions.get(key,0) for key in (
                'total_hold_decisions','total_buy_decisions','total_sell_decisions'))
            current,peak=tracemalloc.get_traced_memory()
            result={'schema':'arms.r24b.runtime-soak.v1','run_id':run_id,
                'python':sys.version,'wall_duration_seconds':time.perf_counter()-started,
                'configured_wall_seconds':wall_seconds,
                'synthetic_market_hours':synthetic_hours,'synthetic_bars':bars,
                'l1_records':stream.sequence,'l1_segments':len(stream.seals),
                'l1_terminal_reason':l1_terminal,'l1_sequence_gaps':0,
                'decision_total':decision_total,'health_checks':health_checks,
                'sqlite_journal_mode':journal_mode,'wal_checkpoint':wal_checkpoint,
                'authority_transitions':audit['total'],
                'latest_authority_transition':audit['records'][0],
                'paper_orders_filled':fills,'open_paper_positions':positions,
                'closed_paper_trades':completed,'broker_order_calls':fills,
                'paper_enabled':snapshot.get('paper_execution_enabled'),
                'live_execution_allowed':False,'external_order_authority':False,
                'supervisor_report':supervisor_report,
                'peak_tracemalloc_bytes':peak,'current_tracemalloc_bytes':current}
    finally:
        tracemalloc.stop()
        if reader is not None:
            reader.close()
        l1_module.private_path=original_private
        if paper is not None:
            paper.shutdown(reason='RUNTIME_SHUTDOWN',
                initiating_path='R24B_OFFLINE_SOAK')
        if root is not None:
            shutil.rmtree(root)
    result_path.write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--wall-seconds',type=int,default=300)
    parser.add_argument('--synthetic-hours',type=int,default=16)
    args=parser.parse_args()
    print(json.dumps(run_soak(result_path=args.result,
        wall_seconds=args.wall_seconds,synthetic_hours=args.synthetic_hours),
        sort_keys=True),flush=True)


if __name__=='__main__':
    main()
