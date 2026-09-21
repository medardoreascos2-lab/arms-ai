"""Private bounded diagnostic watcher. Never imports market admission/execution.

PASS means paired provenance for this witness stream, NOT absolute UTC accuracy
or retroactive pairing of ArmsReadOnlyMarketV1 emissions.
"""
import argparse
import ctypes
from datetime import datetime, date, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid
import tempfile

from backend.market_data.loaded_calendar_binding_v1 import verify_loaded_binding, _wall, DAYS

CALENDAR_FIELDS = ('template','template_version','template_timezone','sessions',
                   'holiday_dates','partial_holiday_dates','partial_holidays_2026')
IDENTITY = dict(provider='Provider31',instrument='NQ',contract='NQ DEC26',
                bars_type='Minute',bars_value=1,application_timezone='UTC',
                template='CME US Index Futures ETH',bar_label='CLOSE')
TICKS_UNIX = 621355968000000000
MINUTE = 600000000
MAX_BYTES = 1_000_000
ROOT_FIELDS = set('schema run_id session sequence kind event_time emission callback qpc_frequency start_qpc observation_only runtime_admission payload'.split())
OBS_FIELDS = set('callback callback_index bar_index bars_ago first_tick bars_in_progress state native_label native_kind indexed_label indexed_kind close_label_utc implied_start_utc bar_label calendar_sha256 session_begin_utc session_end_utc session_begin_raw session_begin_kind session_end_raw session_end_kind trading_day provider instrument contract bars_type bars_value application_timezone template'.split())
EVENT_FIELDS = set('event_sequence event_present connection_present same_source event_status event_price_status previous_status previous_price_status source_status source_price_status source_status_after source_price_status_after source_valid samples_agree baseline_established continuity_before continuity_after state bar_evidence_emitted reason'.split())
BASELINE_FIELDS = set('aligned_event_sequence state continuity_before continuity_after source_status source_price_status source_status_after source_price_status_after source_valid samples_agree calendar_sha256'.split())


def connection_reason(p):
    """Independent Sprint 11T predicate replay; no elapsed-time health proof."""
    for bad,reason in ((not p['event_present'],'CONNECTION_EVENT_NULL'),
                      (not p['connection_present'],'CONNECTION_EVENT_SOURCE_NULL')):
        if bad: return reason
    fields=('event_status','event_price_status','previous_status','previous_price_status','source_status','source_price_status')
    if any(p[k] not in ('Connected','Connecting','Disconnected','Disconnecting','ConnectionLost') for k in fields):
        return 'STOP_UNKNOWN_CONNECTION_STATE'
    if not p['same_source']: return 'STOP_CONNECTION_IDENTITY_MISMATCH'
    if not p['samples_agree']: return 'STOP_UNSTABLE_CONNECTION_STATE'
    if not p['source_valid'] or p['source_status']!='Connected' or p['source_price_status']!='Connected':
        return 'STOP_CURRENT_CONNECTION_NOT_READY'
    current=(p['event_status'],p['event_price_status']);previous=(p['previous_status'],p['previous_price_status'])
    ready=p['continuity_before']=='BASELINE_PROVEN'
    if any(v in ('Disconnected','Disconnecting','ConnectionLost') for v in current): return 'STOP_CONNECTION_LOSS_EVENT'
    if any(v in ('Disconnecting','ConnectionLost') for v in previous) or (ready and previous!=('Connected','Connected')):
        return 'STOP_RECONNECT_OR_UNPROVEN_CONTINUITY'
    if current!=('Connected','Connected'):
        if ready or 'Connected' in previous: return 'STOP_CONNECTION_REGRESSION'
        return 'WAIT_STARTUP_ALIGNMENT'
    return 'CONTINUE'


def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result: raise ValueError('DUPLICATE_JSON_KEY')
        result[k]=v
    return result


def parse(raw):
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda s: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def ticks(value, utc=True):
    match=re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\.(\d{7})(Z?)',value)
    if not match or bool(match[3]) != utc: raise ValueError('UTC_ENCODING')
    instant=datetime.fromisoformat(match[1]).replace(tzinfo=timezone.utc)
    delta=instant-datetime(1970,1,1,tzinfo=timezone.utc)
    return TICKS_UNIX+(delta.days*86400+delta.seconds)*10000000+int(match[2])


def check_pair(p):
    if set(p)!=set(('qpc_before','utc_ticks','qpc_after','utc')): raise ValueError('PAIR_FIELDS')
    if any(type(p[k]) is not int for k in ('qpc_before','qpc_after','utc_ticks')): raise ValueError('PAIR_INTEGER')
    if not 0<=p['qpc_before']<=p['qpc_after'] or ticks(p['utc'])!=p['utc_ticks']: raise ValueError('PAIR_ORDER_OR_UTC')


def qpc_pair():
    if os.name!='nt': raise ValueError('WINDOWS_QPC_REQUIRED')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    qpc=kernel.QueryPerformanceCounter
    freq=kernel.QueryPerformanceFrequency
    qpc.argtypes=freq.argtypes=[ctypes.POINTER(ctypes.c_longlong)]
    qpc.restype=freq.restype=ctypes.c_int
    a,b,f=ctypes.c_longlong(),ctypes.c_longlong(),ctypes.c_longlong()
    if not freq(ctypes.byref(f)) or not qpc(ctypes.byref(a)): raise ValueError('QPC_UNAVAILABLE')
    wall=time.time_ns()
    if not qpc(ctypes.byref(b)): raise ValueError('QPC_UNAVAILABLE')
    return dict(qpc_before=a.value,qpc_after=b.value,host_unix_ns=wall,frequency=f.value)


def as_preflight_pair(record):
    """Integer outward QPC bracket, not UTC truth; no cross-epoch relabeling."""
    p=record['emission'];check_pair(p); f=record['qpc_frequency']
    if type(f) is not int or f<=0: raise ValueError('QPC_FREQUENCY')
    return dict(native_epoch=[record['run_id'],record['session']],
                host_utc_us=(p['utc_ticks']-TICKS_UNIX)//10,
                mono_low_us=p['qpc_before']*1000000//f,
                mono_high_us=(p['qpc_after']*1000000+f-1)//f,
                capture_quantization_us=1,reference_bound=None,drift_bound=None,
                clock_preflight='UNKNOWN',runtime_admission=False)


def expected_session(calendar, trading_day):
    d=date.fromisoformat(trading_day)
    if trading_day in calendar['holiday_dates'] or trading_day in calendar['partial_holiday_dates']:
        raise ValueError('UNREVIEWED_EXCEPTION_SESSION')
    rows=[s for s in calendar['sessions'] if s['trading_day']==DAYS[d.weekday()]]
    if len(rows)!=1: raise ValueError('SESSION_AMBIGUOUS')
    s=rows[0];start=d-timedelta(days=(d.weekday()-DAYS.index(s['begin_day']))%7)
    def to_ticks(t):
        delta=t-datetime(1970,1,1,tzinfo=timezone.utc)
        return TICKS_UNIX+(delta.days*86400+delta.seconds)*10000000
    return to_ticks(_wall(start,s['begin_time'])),to_ticks(_wall(d,s['end_time']))


def adjudicate(raw, seal_raw, plan):
    result=dict(status='FAIL',paired_native_timing='NOT_PROVEN',runtime_admission=False,
                clock_preflight='UNKNOWN',broker_order_calls=0,ninjatrader_account_access=False,
                paper_entries='DISABLED',news='UNCERTIFIED',sim_execution='DISABLED',live_authority=False)
    line_number=0
    try:
        if len(raw)>MAX_BYTES or not raw.endswith(b'\n'): raise ValueError('TRUNCATED_OR_OVERSIZE')
        rows=[parse(line) for line in raw.splitlines()]
        if not 3<=len(rows)<=16: raise ValueError('RECORD_COUNT')
        session=rows[0]['session']
        if str(uuid.UUID(session))!=session: raise ValueError('SESSION_UUID')
        last_qpc=plan['reader_start']['qpc_before']
        last_wall=None
        first_index=None;last_index=None;last_label=None;pending=None;closed=0;forming=0;session_identity=None
        realtime=False;continuity='PRE_BASELINE';event_count=0;connection_failure=None
        aligned_event=None;aligned_emission=None;realtime_qpc=None;baseline_emission=None
        for line_number,r in enumerate(rows,1):
            if set(r)!=ROOT_FIELDS or r['schema']!='arms.nt.native-timing.v3': raise ValueError('SCHEMA')
            if r['run_id']!=plan['run_id'] or r['session']!=session: raise ValueError('RESTART_OR_RUN_MISMATCH')
            if type(r['sequence']) is not int or r['sequence']!=line_number-1: raise ValueError('SEQUENCE')
            if r['observation_only'] is not True or r['runtime_admission'] is not False: raise ValueError('AUTHORITY_CLAIM')
            if type(r['qpc_frequency']) is not int or r['qpc_frequency']!=plan['reader_start']['frequency']: raise ValueError('CLOCK_BASIS')
            if type(r['start_qpc']) is not int or not plan['reader_start']['qpc_before']<=r['start_qpc']<=r['emission']['qpc_before']: raise ValueError('OLD_NATIVE_EPOCH')
            if r['start_qpc']!=rows[0]['start_qpc']: raise ValueError('CLOCK_EPOCH_CHANGED')
            check_pair(r['emission']);check_pair(r['callback'])
            if r['callback']['qpc_before']<r['start_qpc']: raise ValueError('CALLBACK_BEFORE_START')
            if r['event_time']!=r['emission']['utc']: raise ValueError('EMISSION_NOT_BOUND')
            if r['callback']['qpc_after']>r['emission']['qpc_before'] or r['emission']['qpc_before']<last_qpc: raise ValueError('MONOTONIC_ORDER')
            if r['emission']['qpc_after']>plan['reader_end']['qpc_after']: raise ValueError('RECEIPT_ORDER')
            if r['kind']!='END' and r['emission']['qpc_after']-r['start_qpc']>=330*r['qpc_frequency']: raise ValueError('NATIVE_WINDOW_EXCEEDED')
            if last_wall is not None and r['emission']['utc_ticks']<last_wall: raise ValueError('HOST_WALL_REGRESSION')
            last_wall=r['emission']['utc_ticks']
            last_qpc=r['emission']['qpc_after']
            p=r['payload'];kind=r['kind']
            if line_number==1:
                if kind!='HELLO' or set(p)!=set(IDENTITY)|{'calendar_json','calendar_sha256','capture_ms','required_closed','continuity_contract'}: raise ValueError('HELLO')
                if p['continuity_contract']!='SPRINT11T_STARTUP_ALIGNMENT_R4': raise ValueError('STALE_WITNESS_REVISION')
                if any(type(p[k]) is not type(v) or p[k]!=v for k,v in IDENTITY.items()): raise ValueError('SOURCE_IDENTITY')
                if parse(p['calendar_json'])!=plan['calendar'] or hashlib.sha256(p['calendar_json'].encode()).hexdigest()!=p['calendar_sha256']: raise ValueError('CALENDAR')
                if p['capture_ms']!=330000 or p['required_closed']!=3: raise ValueError('CAPTURE_LIMITS')
                continue
            if line_number==len(rows):
                if kind!='END' or set(p)!={'reason','closed_count'} or p['closed_count']!=closed or pending: raise ValueError('TERMINAL')
                if connection_failure and p['reason']!=connection_failure: raise ValueError('CONNECTION_END_MISMATCH')
                continue
            if connection_failure: raise ValueError('AFTER_CONTINUITY_FAILURE')
            if kind=='REALTIME':
                if realtime or p!={'state':'Realtime'}: raise ValueError('HISTORICAL_REALTIME_TRANSITION')
                realtime=True
                realtime_qpc=r['callback']['qpc_before'];aligned_event=None;aligned_emission=None
                continue
            if kind=='CONNECTION_EVENT':
                if set(p)!=EVENT_FIELDS or type(p['event_sequence']) is not int or p['event_sequence']!=event_count: raise ValueError('CONNECTION_EVENT_SCHEMA')
                for field in ('event_present','connection_present','same_source','source_valid','samples_agree','baseline_established','bar_evidence_emitted'):
                    if type(p[field]) is not bool: raise ValueError('CONNECTION_BOOLEAN')
                for field in ('event_status','event_price_status','previous_status','previous_price_status','source_status','source_price_status','source_status_after','source_price_status_after'):
                    if type(p[field]) is not str or not re.fullmatch(r'Connected|Connecting|ConnectionLost|Disconnected|Disconnecting|UNAVAILABLE|UNDEFINED_-?\d+',p[field]): raise ValueError('CONNECTION_ENUM')
                if not p['event_present'] and (p['connection_present'] or p['same_source'] or any(p[k]!='UNAVAILABLE' for k in ('event_status','event_price_status','previous_status','previous_price_status'))): raise ValueError('CONNECTION_NULL_EVENT')
                if p['same_source'] and not p['connection_present']: raise ValueError('CONNECTION_IDENTITY')
                if p['samples_agree']!=(p['source_status']==p['source_status_after'] and p['source_price_status']==p['source_price_status_after']): raise ValueError('CONNECTION_SAMPLES')
                if p['state'] not in ('DataLoaded','Historical','Transition','Realtime') or (p['state']=='Realtime')!=realtime: raise ValueError('CONNECTION_LIFECYCLE')
                if p['continuity_before']!=continuity or p['baseline_established']!=(continuity=='BASELINE_PROVEN') or p['bar_evidence_emitted']!=(forming>0): raise ValueError('CONNECTION_BASELINE')
                reason=connection_reason(p)
                if (reason in ('CONTINUE','WAIT_STARTUP_ALIGNMENT') and realtime and continuity!='BASELINE_PROVEN'
                        and (r['callback']['qpc_before']-realtime_qpc>=30*r['qpc_frequency']
                             or (p['reason']=='STOP_STARTUP_TIMEOUT' and r['emission']['qpc_after']-realtime_qpc>=30*r['qpc_frequency']))):
                    reason='STOP_STARTUP_TIMEOUT'
                if p['reason']!=reason: raise ValueError('CONNECTION_REASON')
                if reason not in ('CONTINUE','WAIT_STARTUP_ALIGNMENT'):
                    connection_failure=reason
                    continuity='STOPPED'
                else:
                    if continuity!='BASELINE_PROVEN': continuity='WAIT_ALIGNMENT'
                    aligned_event=event_count if reason=='CONTINUE' and realtime and r['callback']['qpc_before']>=realtime_qpc else None
                    aligned_emission=r['emission']['qpc_after'] if aligned_event is not None else None
                if p['continuity_after']!=continuity: raise ValueError('CONNECTION_TRANSITION')
                event_count+=1
                continue
            if kind=='BASELINE':
                if (not realtime or continuity!='WAIT_ALIGNMENT' or aligned_event is None
                        or set(p)!=BASELINE_FIELDS): raise ValueError('BASELINE_WITHOUT_ALIGNMENT')
                if (type(p['aligned_event_sequence']) is not int or p['aligned_event_sequence']!=aligned_event
                        or p['state']!='Realtime' or p['continuity_before']!=continuity
                        or p['continuity_after']!='BASELINE_PROVEN'): raise ValueError('BASELINE_IDENTITY')
                if (p['source_valid'] is not True or p['samples_agree'] is not True
                        or any(p[k]!='Connected' for k in ('source_status','source_price_status','source_status_after','source_price_status_after'))
                        or p['calendar_sha256']!=rows[0]['payload']['calendar_sha256']): raise ValueError('BASELINE_SOURCE')
                if r['callback']['qpc_before']<aligned_emission: raise ValueError('BASELINE_POLL_NOT_INDEPENDENT')
                if r['emission']['qpc_after']-realtime_qpc>=30*r['qpc_frequency']: raise ValueError('BASELINE_STARTUP_TIMEOUT')
                continuity='BASELINE_PROVEN'
                baseline_emission=r['emission']['qpc_after']
                continue
            if not realtime or continuity!='BASELINE_PROVEN': raise ValueError('BAR_BEFORE_BASELINE')
            if r['callback']['qpc_before']<baseline_emission: raise ValueError('BAR_CALLBACK_BEFORE_BASELINE')
            if kind not in ('FORMING','CLOSED') or set(p)!=OBS_FIELDS: raise ValueError('OBSERVATION_SCHEMA')
            if any(type(p[k]) is not type(v) or p[k]!=v for k,v in IDENTITY.items()): raise ValueError('SOURCE_IDENTITY')
            if p['state']!='Realtime' or p['first_tick'] is not True or p['bars_in_progress']!=0: raise ValueError('CALLBACK_STATE')
            if p['callback']!=r['callback']: raise ValueError('CALLBACK_PAIR_BINDING')
            if p['calendar_sha256']!=rows[0]['payload']['calendar_sha256']: raise ValueError('CALENDAR_CHANGED')
            for k in ('callback_index','bar_index','bars_ago','bars_in_progress'):
                if type(p[k]) is not int or p[k]<0: raise ValueError('BAR_INDEX')
            for raw_key,kind_key,utc_key in [('native_label','native_kind','close_label_utc'),('indexed_label','indexed_kind','close_label_utc'),('session_begin_raw','session_begin_kind','session_begin_utc'),('session_end_raw','session_end_kind','session_end_utc')]:
                if p[kind_key] not in ('Utc','Unspecified') or ticks(p[raw_key],p[kind_key]=='Utc')!=ticks(p[utc_key]): raise ValueError('NATIVE_ZONE_MAPPING')
            label=ticks(p['close_label_utc'])
            if label%MINUTE or ticks(p['implied_start_utc'])!=label-MINUTE: raise ValueError('BAR_LABEL')
            if not ticks(plan['valid_from'])<=label<ticks(plan['valid_until']) or p['trading_day'] not in plan['covered_dates']: raise ValueError('CALENDAR_COVERAGE')
            bounds=expected_session(plan['calendar'],p['trading_day'])
            actual=(ticks(p['session_begin_utc']),ticks(p['session_end_utc']))
            if actual!=bounds or not bounds[0]<=label-MINUTE<label<=bounds[1]: raise ValueError('SESSION_BOUNDARIES')
            identity=(*actual,p['trading_day'])
            if session_identity is not None and identity!=session_identity: raise ValueError('SESSION_TRANSITION')
            session_identity=identity
            index=p['callback_index']
            if kind=='CLOSED':
                if pending or last_index is None or index!=last_index+1 or p['bars_ago']!=1 or p['bar_index']!=index-1 or index-first_index<2 or label!=last_label: raise ValueError('CLOSED_CONTINUITY')
                pending=r;closed+=1
            else:
                if p['bars_ago']!=0 or p['bar_index']!=index: raise ValueError('FORMING_INDEX')
                if first_index is None: first_index=index
                elif index!=last_index+1 or label!=last_label+MINUTE: raise ValueError('DUPLICATE_OUT_OF_ORDER_OR_GAP')
                if (index-first_index>=2)!=(pending is not None): raise ValueError('MISSING_CLOSED')
                if pending and (pending['callback']!=r['callback'] or pending['payload']['callback_index']!=index): raise ValueError('SAME_CALLBACK')
                pending=None;last_index=index;last_label=label;forming+=1
        seal=parse(seal_raw)
        if set(seal)!=set('schema run_id session writer_closed timers_detached records bytes sha256 reason'.split()): raise ValueError('SEAL_FIELDS')
        if (seal['schema']!='arms.nt.native-timing.seal.v1' or seal['run_id']!=plan['run_id'] or seal['session']!=session
                or seal['writer_closed'] is not True or seal['timers_detached'] is not True or seal['records']!=len(rows)
                or seal['bytes']!=len(raw) or seal['sha256']!=hashlib.sha256(raw).hexdigest()
                or seal['reason']!=rows[-1]['payload']['reason']): raise ValueError('WRITER_SEAL')
        reason=seal['reason']
        if reason=='WINDOW_END' and closed<3 and realtime: status='INCONCLUSIVE'
        elif reason=='BOUNDARIES_COMPLETE' and closed==3 and forming==5: status='PASS'
        else: raise ValueError('NATIVE_STOP_'+str(reason))
        result.update(status=status,paired_native_timing='PASS_WITNESS_STREAM_ONLY' if status=='PASS' else 'INSUFFICIENT_BOUNDARIES',
                      native_session=session,forming_count=forming,closed_count=closed,writer_closed=True,
                      source_sha256=seal['sha256'],preflight_pairs=[as_preflight_pair(r) for r in rows if r['kind'] in ('FORMING','CLOSED')])
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError) as error:
        reason=str(error)
        result.update(first_witness_line=line_number,reason=reason if type(error) is ValueError and re.fullmatch('[A-Z0-9_]{1,100}',reason) else 'MALFORMED_EVIDENCE')
    return result


def atomic_publish(source,destination):
    if os.name!='nt':
        source.replace(destination)
        return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    replace=kernel.ReplaceFileW
    replace.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_wchar_p,
                      ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p]
    replace.restype=ctypes.c_int
    if replace(os.path.abspath(destination),os.path.abspath(source),None,0,None,None): return
    error=ctypes.get_last_error()
    if error==2 and not destination.exists():
        # Initial publication has no existing destination/reader handle.
        source.replace(destination)
        return
    raise ctypes.WinError(error)


def write_json(path,value):
    """Publish only closed, flushed JSON; tolerate bounded Windows reader locks."""
    data=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode('utf-8')
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    tmp=Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        for attempt in range(21):
            try:
                atomic_publish(tmp,path)
                return
            except OSError as error:
                if getattr(error,'winerror',None) not in (5,32,33) or attempt==20: raise
                time.sleep(.025)
    finally:
        # Only this invocation's unique temporary file may be cleaned up.
        for attempt in range(21):
            try:
                tmp.unlink(missing_ok=True)
                break
            except OSError:
                if attempt==20: raise
                time.sleep(.025)


def read_status_json(path):
    """Windows readers must share delete access with the atomic publisher."""
    if os.name!='nt': return parse(path.read_bytes())
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,
                     ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    create.restype=ctypes.c_void_p
    # Keep path normalization lexical; open exactly one shared reader handle.
    for attempt in range(21):
        handle=create(os.path.abspath(path),0x80000000,7,None,3,0x80,None)
        if handle!=ctypes.c_void_p(-1).value: break
        error=ctypes.get_last_error()
        # ReplaceFile can briefly make the name unavailable to new opens.
        # Never fall back to an old cached ACTIVE snapshot during this interval.
        if error not in (2,5,32,33) or attempt==20: raise ctypes.WinError(error)
        time.sleep(.01)
    try:
        fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except Exception:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd,'rb') as stream:
        raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise ValueError('STATUS_OVERSIZE')
    return parse(raw)


def live_process_start(pid):
    """Creation FILETIME binds PID reuse; access denial is not evidence of life."""
    if os.name!='nt' or type(pid) is not int or pid<=0: return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    kernel.WaitForSingleObject.restype=ctypes.c_uint32
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    handle=kernel.OpenProcess(0x100000|0x1000,False,pid)
    if not handle: return None
    try:
        if kernel.WaitForSingleObject(handle,0)!=258: return None
        values=[ctypes.c_ulonglong() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]): return None
        return values[0].value
    finally: kernel.CloseHandle(handle)


def begin_status(folder,mode):
    identity=dict(pid=os.getpid(),process_start=live_process_start(os.getpid()),
                  watcher_id=str(uuid.uuid4()),run_id=folder.name,mode=mode)
    if identity['process_start'] is None: raise ValueError('PROCESS_IDENTITY_UNAVAILABLE')
    # Exclusive permanent claim: even a dead process cannot reuse this run.
    with (folder/'claim.json').open('x') as stream:
        json.dump(identity,stream);stream.flush();os.fsync(stream.fileno())
    return dict(identity,watcher_status='STARTING',waiting_for_fresh_native_timing_session=False,
                heartbeat_counter=0,heartbeat_monotonic=time.monotonic(),status_lease_seconds=2,
                clock_authority='UNKNOWN',runtime_admission=False,broker_order_calls=0,
                ninjatrader_account_access=False,paper_entries='DISABLED',news='UNCERTIFIED',
                sim_execution='DISABLED',live_authority=False)


def publish_status(folder,status):
    status.update(heartbeat_counter=status['heartbeat_counter']+1,heartbeat_monotonic=time.monotonic())
    write_json(folder/'status.json',status)


def finish_status(folder,status,result):
    status.update(watcher_status='STOPPED',waiting_for_fresh_native_timing_session=False,
                  terminal_state='FAILED' if result['status']=='FAIL' else 'COMPLETED',
                  reason=result.get('reason',result['status']),heartbeat_monotonic=time.monotonic())
    # Separate terminal publication survives an indefinitely locked status.json.
    write_json(folder/'terminal.json',status)
    try: write_json(folder/'status.json',status)
    except OSError: pass  # terminal.json and process death both veto stale ACTIVE.


def verified_status(folder,samples=3,interval=.3):
    """Only this live observation, never a persisted ACTIVE string, grants waiting."""
    rejected=dict(watcher_status='NOT_ACTIVE',waiting_for_fresh_native_timing_session=False,
                  runtime_admission=False)
    try:
        if type(samples) is not int or samples<2 or not 0<interval<=.5: raise ValueError('PROBE_BOUNDS')
        claim=read_status_json(folder/'claim.json')
        if claim['run_id']!=folder.name: raise ValueError('RUN_IDENTITY')
        prior=None
        for i in range(samples):
            if i: time.sleep(interval)
            if (folder/'terminal.json').exists() or (folder/'result.json').exists(): raise ValueError('TERMINAL_RESULT_PRESENT')
            status=read_status_json(folder/'status.json')
            if any(status[k]!=claim[k] for k in ('pid','process_start','watcher_id','run_id','mode')): raise ValueError('PROCESS_RUN_IDENTITY')
            live_start=live_process_start(status['pid'])
            if live_start is None or live_start!=status['process_start']: raise ValueError('PROCESS_NOT_ALIVE')
            age=time.monotonic()-status['heartbeat_monotonic']
            if not 0<=age<=2 or status['status_lease_seconds']!=2: raise ValueError('HEARTBEAT_STALE')
            if status['watcher_status']!='ACTIVE_AND_WAITING' or status['waiting_for_fresh_native_timing_session'] is not True: raise ValueError('NOT_WAITING')
            if prior is not None and (status['heartbeat_counter']<=prior['heartbeat_counter'] or status['heartbeat_monotonic']<=prior['heartbeat_monotonic']): raise ValueError('HEARTBEAT_NOT_ADVANCING')
            prior=status
        live_start=live_process_start(status['pid'])
        if (folder/'terminal.json').exists() or (folder/'result.json').exists() or live_start is None or live_start!=status['process_start']: raise ValueError('PROCESS_EXIT_OR_TERMINAL')
        return dict(status,process_alive=True,heartbeat_advancing=True,verified_samples=samples,
                    verified_monotonic=time.monotonic(),heartbeat_age_seconds=age)
    except (OSError,ValueError,TypeError,KeyError) as error:
        return dict(rejected,reason=str(error) if type(error) is ValueError else 'STATUS_UNVERIFIABLE')


def prepare(base,spec_path):
    spec=parse(spec_path.read_bytes())
    raw=Path(spec['loaded_calendar_evidence_file']).read_bytes()
    template=Path(spec['calendar_evidence_file']).read_bytes()
    if hashlib.sha256(template).hexdigest()!=spec['calendar_evidence_sha256']: raise ValueError('TEMPLATE_CHANGED')
    verify_loaded_binding(raw,template)
    native=parse(raw);run=str(uuid.uuid4());folder=base/run
    folder.mkdir();(folder/'inbox').mkdir()
    def iso(v): return datetime.fromisoformat(v).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+'.0000000Z'
    plan=dict(schema='arms.native-timing.plan.v1',run_id=run,activation_seconds=600,capture_seconds=330,
              calendar={k:native[k] for k in CALENDAR_FIELDS},covered_dates=spec['covered_dates'],
              valid_from=iso(spec['contract']['valid_from']),valid_until=iso(spec['contract']['valid_until']),
              witness_sha256=hashlib.sha256(Path('integrations/ninjatrader/ArmsNativeTimingWitnessV1.cs').read_bytes()).hexdigest(),
              observation_only=True,runtime_admission=False)
    write_json(folder/'plan.json',plan)
    return folder


def watch(folder):
    plan=parse((folder/'plan.json').read_bytes())
    if plan['schema']!='arms.native-timing.plan.v1' or folder.name!=plan['run_id']: raise ValueError('RUN_IDENTITY')
    if plan['activation_seconds']!=600 or plan['capture_seconds']!=330: raise ValueError('UNREVIEWED_BUDGET')
    if plan['witness_sha256']!=hashlib.sha256(Path('integrations/ninjatrader/ArmsNativeTimingWitnessV1.cs').read_bytes()).hexdigest(): raise ValueError('SOURCE_CHANGED')
    waiting=begin_status(folder,'NATIVE_DIAGNOSTIC')
    if any((folder/'inbox').iterdir()): raise ValueError('OLD_EVIDENCE_PRESENT')
    result=dict(status='FAIL',reason='WATCHER_START_FAILED',runtime_admission=False)
    try:
        publish_status(folder,waiting)
        plan['reader_start']=qpc_pair()
        start=time.monotonic();activation=start+600;capture_end=None
        waiting.update(watcher_status='ACTIVE_AND_WAITING',waiting_for_fresh_native_timing_session=True,
                       activation_deadline_utc=datetime.fromtimestamp(time.time()+600,timezone.utc).isoformat(),
                       activation_deadline_monotonic=activation)
        while True:
            files=list((folder/'inbox').glob('*.timing.jsonl'))
            if len(files)>1: raise ValueError('MULTIPLE_NATIVE_SESSIONS')
            now=time.monotonic()
            if not files and now>=activation: raise ValueError('ACTIVATION_TIMEOUT')
            if files:
                if capture_end is None:
                    if now>=activation: raise ValueError('LATE_ACTIVATION')
                    capture_end=now+345  # Native 330s plus reader/seal delivery budget; no freshness tolerance.
                source=files[0]
                if now>=capture_end: raise ValueError('NATIVE_END_OR_SEAL_MISSING')
                if source.stat().st_size>MAX_BYTES: raise ValueError('OVERSIZE_NATIVE_FILE')
                done=source.with_name(source.name+'.done.json')
                if done.exists():
                    if done.stat().st_size>4096: raise ValueError('OVERSIZE_SEAL')
                    plan['reader_read_begin']=qpc_pair()
                    raw=source.read_bytes();seal=done.read_bytes()
                    plan['reader_end']=qpc_pair()
                    result=adjudicate(raw,seal,plan)
                    write_json(folder/'receipt.json',plan)
                    write_json(folder/'result.json',result)
                    break
            waiting.update(watcher_status='CAPTURING_DIAGNOSTIC' if files else 'ACTIVE_AND_WAITING',
                           waiting_for_fresh_native_timing_session=not bool(files))
            publish_status(folder,waiting)
            time.sleep(.25)
    except Exception as error:
        result=dict(status='FAIL',reason=str(error) if type(error) is ValueError else 'WATCHER_IO_FAILED',
                    runtime_admission=False,windows_error=getattr(error,'winerror',None))
        write_json(folder/'result.json',result)
    finally:
        finish_status(folder,waiting,result)


def dry_run(folder):
    """Five-second non-native status lifecycle; does not read any native inbox."""
    folder.mkdir()
    status=begin_status(folder,'NON_NATIVE_DRY_RUN')
    result=dict(status='FAIL',reason='DRY_RUN_START_FAILED',runtime_admission=False)
    try:
        publish_status(folder,status)
        time.sleep(.3)
        for _ in range(20):
            status.update(watcher_status='ACTIVE_AND_WAITING',waiting_for_fresh_native_timing_session=True)
            publish_status(folder,status)
            time.sleep(.25)
        result=dict(status='PASS',reason='NON_NATIVE_DRY_RUN_COMPLETE',runtime_admission=False)
        write_json(folder/'result.json',result)
    finally: finish_status(folder,status,result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--base',type=Path,required=True);p.add_argument('--spec',type=Path,required=True)
    p=sub.add_parser('watch');p.add_argument('--run-directory',type=Path,required=True)
    p=sub.add_parser('status');p.add_argument('--run-directory',type=Path,required=True)
    p=sub.add_parser('dry-run');p.add_argument('--run-directory',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare': print(prepare(args.base,args.spec))
    elif args.command=='watch': watch(args.run_directory)
    elif args.command=='status': print(json.dumps(verified_status(args.run_directory),indent=2))
    else: dry_run(args.run_directory)
