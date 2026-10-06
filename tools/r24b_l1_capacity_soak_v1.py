"""Offline-only L1 segmented capacity certification exceeding 256 MiB."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tracemalloc
from uuid import uuid4

from backend.market_data.fresh_native_adapter_v1 import MAX_L1_FILE
from backend.services import sim_native_l1_authority_v1 as l1_module
from backend.services.runtime_admission_v2 import RuntimeAdmissionV2
from backend.services.sim_native_commissioning_policy_v1 import load


def _line(session,sequence,kind,payload,at):
    return (json.dumps({'schema':'arms.nt.l1.v1','session':session,
        'sequence':sequence,'event_time':at,'kind':kind,'payload':payload},
        separators=(',',':'),allow_nan=False)+'\n').encode()


def _write_segment(path, *, session, sequence, first, target, at):
    written=0
    quote={'bid':25000.0,'ask':25000.25,'bid_time':at,'ask_time':at}
    with path.open('xb',buffering=1024*1024) as stream:
        if first:
            raw=_line(session,sequence,'HELLO',dict(l1_module.IDENTITY),at)
            stream.write(raw);written+=len(raw);sequence+=1
        batch=bytearray()
        while True:
            kind='HEARTBEAT' if sequence%10000==0 else 'QUOTE'
            payload={'connected':True} if kind=='HEARTBEAT' else quote
            raw=_line(session,sequence,kind,payload,at)
            if written+len(batch)+len(raw)>target:
                break
            batch.extend(raw);sequence+=1
            if len(batch)>=1024*1024:
                stream.write(batch);written+=len(batch);batch.clear()
        if batch:
            stream.write(batch);written+=len(batch)
        stream.flush();os.fsync(stream.fileno())
    return sequence,written


def _seal(path,index,first_sequence,last_sequence):
    raw_hash=sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            raw_hash.update(block)
    return {'index':index,'file':path.name,'first_sequence':first_sequence,
        'last_sequence':last_sequence,'bytes':path.stat().st_size,
        'sha256':raw_hash.hexdigest(),'sealed':True}


def run_capacity_soak(*,result_path=None):
    started=time.perf_counter()
    now=datetime(2026,10,5,12,tzinfo=timezone.utc)
    at=now.isoformat().replace('+00:00','Z')
    session=str(uuid4())
    with TemporaryDirectory(prefix='arms-r24b-l1-') as temporary:
        directory=Path(temporary).resolve()
        one=directory/(session+'.segment.000001.l1.jsonl')
        two=directory/(session+'.segment.000002.l1.jsonl')
        sequence=0
        sequence,size_one=_write_segment(one,session=session,sequence=sequence,
            first=True,target=MAX_L1_FILE-4096,at=at)
        first_count=sequence
        sequence,size_two=_write_segment(two,session=session,sequence=sequence,
            first=False,target=4*1024*1024,at=at)
        terminal=_line(session,sequence,'TERMINAL',
            {'connected':False,'reason':'SESSION_TERMINATED'},at)
        with two.open('ab',buffering=0) as stream:
            stream.write(terminal);stream.flush();os.fsync(stream.fileno())
        sequence+=1
        segments=[_seal(one,1,0,first_count-1),
            _seal(two,2,first_count,sequence-1)]
        manifest={'schema':'arms.nt.l1.manifest.v1','session':session,
            'provider':'Provider31','instrument':'NQ','contract':'NQ DEC26',
            'segment_capacity_bytes':MAX_L1_FILE,'state':'TERMINATED',
            'terminal_reason':'SESSION_TERMINATED','segments':segments}
        manifest_path=directory/(session+'.l1.manifest.json')
        manifest_path.write_text(json.dumps(manifest,separators=(',',':'))+'\n',
            encoding='utf-8')
        original_private=l1_module.private_path
        l1_module.private_path=lambda path:Path(path)
        admission=RuntimeAdmissionV2(settings=load().api_settings)
        reader=l1_module.SimNativeL1AuthorityV1(admission=admission,
            context=lambda:None,clock=lambda:now,directory=directory,
            elapsed=time.monotonic)
        polls=0
        tracemalloc.start()
        try:
            while reader.status!='REVOKED':
                reader.poll();polls+=1
                if polls>10000:
                    raise RuntimeError('L1_SOAK_POLL_LIMIT')
            current,peak=tracemalloc.get_traced_memory()
            if reader.reason!='L1_STREAM_TERMINATED:SESSION_TERMINATED':
                raise RuntimeError('L1_TERMINAL_REASON_LOST:'+str(reader.reason)+':'
                    +str(reader.validation_error)+':sequence='+str(reader.sequence)
                    +':segment='+str(reader.segment_index))
            if reader.sequence!=sequence-1:
                raise RuntimeError('L1_SEQUENCE_CONTINUITY_FAILED')
            terminal_reason = reader.reason
            last_sequence = reader.sequence
        finally:
            tracemalloc.stop()
            reader.close()
            l1_module.private_path=original_private
        total=size_one+two.stat().st_size
        if total<=268431503 or len(segments)<2:
            raise RuntimeError('L1_PRIOR_FAILURE_VOLUME_NOT_EXCEEDED')
        result={'schema':'arms.r24b.l1-capacity-soak.v1',
            'python':os.sys.version,'total_bytes':total,'segment_count':2,
            'segment_bytes':[item['bytes'] for item in segments],
            'segment_sha256':[item['sha256'] for item in segments],
            'manifest_sha256':sha256(manifest_path.read_bytes()).hexdigest(),
            'records':sequence,'last_sequence':last_sequence,
            'sequence_gaps':0,'duplicate_records':0,'polls':polls,
            'terminal_reason':terminal_reason,
            'peak_tracemalloc_bytes':peak,
            'duration_seconds':time.perf_counter()-started,
            'paper_enabled':False,'live_execution_allowed':False,
            'external_order_authority':False}
    if result_path is not None:
        result_path=Path(result_path)
        result_path.parent.mkdir(parents=True,exist_ok=True)
        result_path.write_text(json.dumps(result,sort_keys=True,indent=2),
            encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run_capacity_soak(result_path=args.result),sort_keys=True))


if __name__=='__main__':
    main()
