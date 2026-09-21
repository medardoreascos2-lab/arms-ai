"""Synthetic whole-exporter equivalence, adverse evidence, and installed SDK audit.

No real NinjaTrader instance, provider, account, or watcher is started.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import uuid

import pytest

from tools import production_timing_v1 as timing

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'integrations/ninjatrader/ArmsReadOnlyMarketV1.cs'
BASELINE = ROOT/'backend/tests/fixtures/ArmsReadOnlyMarketV1.sprint13.cs'
FW = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
SDK = Path('C:/Program Files/NinjaTrader 8/bin')


def literal_script(path, marker):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant)
                and isinstance(n.value,str) and marker in n.value)


@pytest.fixture(scope='module')
def binaries(tmp_path_factory):
    folder = tmp_path_factory.mktemp('production_pairing')
    host = literal_script(ROOT/'backend/tests/test_ninjatrader_exporter_startup_sprint11t.py', 'class Harness')
    host = host.replace('namespace Doubles {', '''namespace Doubles {
 public static class Wall {public static DateTime UtcNow=new DateTime(2026,9,21,14,0,0,DateTimeKind.Utc);}
 public static class Identity {public static Guid Session=new Guid("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee");public static Guid NewGuid(){return Session;}}
''')
    host = host.replace('string c=args[0];', 'if(args.Length>2)Doubles.Identity.Session=new Guid(args[2]);string c=args[0];')
    host = host.replace('public void Bar(int n){CurrentBar=n;OnBarUpdate();}', '''public void Bar(int n){
      CurrentBar=n;Doubles.Wall.UtcNow=new DateTime(2026,9,21,14,0,1,DateTimeKind.Utc).AddMinutes(n-10);
      Time[0]=new DateTime(2026,9,21,14,1,0,DateTimeKind.Utc).AddMinutes(n-10);Time[1]=Time[0].AddMinutes(-1);
      OnBarUpdate();}''')
    host = host.replace('if(c=="bars") {h.Bar(10);h.Bar(11);h.Bar(12);}', '''
   if(c=="bars" || c.StartsWith("pair_")) {
    if(c=="pair_open_failure")File.WriteAllText(Path.Combine(args[1],"timing"),"synthetic obstacle");
    var watch=System.Diagnostics.Stopwatch.StartNew();
    int count=c=="pair_benchmark"?1000:5;
    for(int n=10;n<10+count;n++) {
     h.Bar(n);
     if(n==10 && c=="pair_canonical_failure") {
      var canonical=typeof(NinjaTrader.NinjaScript.Indicators.ArmsReadOnlyMarketV1).GetField("writer",BindingFlags.Instance|BindingFlags.NonPublic);
      ((StreamWriter)canonical.GetValue(h)).Dispose();
     }
     if(n==10 && (c=="pair_write_failure" || c=="pair_close_failure")) {
      var field=typeof(NinjaTrader.NinjaScript.Indicators.ArmsReadOnlyMarketV1).GetField("timing",BindingFlags.Instance|BindingFlags.NonPublic);
      if(field!=null) {
       var evidence=field.GetValue(h);
       var output=evidence.GetType().GetField("output",BindingFlags.Instance|BindingFlags.NonPublic);
       ((StreamWriter)output.GetValue(evidence)).Dispose();
       output.SetValue(evidence,new FaultWriter(c=="pair_close_failure"));
      }
     }
    }
    watch.Stop(); File.WriteAllText(Path.Combine(args[1],"elapsed.txt"),watch.Elapsed.TotalMilliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture));
    if(c=="pair_connection_stop") {
     e.PreviousStatus=e.PreviousPriceStatus=ConnectionStatus.Connected;
     e.Status=e.PriceStatus=ConnectionStatus.Disconnected;h.Send(e);
    }
   }''')
    host += '''
class FaultWriter:StreamWriter {
 bool closing; public FaultWriter(bool c):base(new MemoryStream()){closing=c;}
 public override void WriteLine(string s){if(!closing)throw new IOException("SYNTHETIC_WRITE_FAILURE");base.WriteLine(s);}
 protected override void Dispose(bool b){if(closing)throw new IOException("SYNTHETIC_CLOSE_FAILURE");base.Dispose(b);}
}
'''
    (folder/'Host.cs').write_text(host)
    outputs = {}
    for name, source in (('baseline',BASELINE),('paired',SOURCE)):
        text = source.read_text().replace('using System.Diagnostics;', 'using Stopwatch = Doubles.Clock;')
        text = text.replace('System.Threading.Timer','Doubles.Deadline')
        text = text.replace('DateTime.UtcNow','Doubles.Wall.UtcNow').replace('Guid.NewGuid()','Doubles.Identity.NewGuid()')
        cs = folder/(name+'.cs'); cs.write_text(text)
        exe = folder/(name+'.exe')
        process = subprocess.run([str(FW/'csc.exe'),'/nologo','/out:'+str(exe),
                '/r:'+str(FW/'System.Web.Extensions.dll'),'/r:'+str(FW/'System.ComponentModel.DataAnnotations.dll'),
                str(cs),str(folder/'Host.cs')],capture_output=True,text=True)
        assert process.returncode == 0, process.stdout
        outputs[name] = exe
    return outputs


def run(exe, folder, case='bars', session=None):
    folder.mkdir()
    proc = subprocess.run([str(exe),case,str(folder),*([session] if session else [])],capture_output=True,text=True)
    assert proc.returncode == 0, proc.stdout+proc.stderr
    assert 'PRIVATE_SENTINEL' not in proc.stdout
    return next(p for p in folder.glob('*.jsonl') if not p.name.endswith('.connection.jsonl')).read_bytes()


def evidence(folder):
    canonical = next(p for p in folder.glob('*.jsonl') if not p.name.endswith('.connection.jsonl'))
    sidecar, = (folder/'timing').glob('*.production-timing.jsonl')
    return canonical.read_bytes(),sidecar.read_bytes(),Path(str(sidecar)+'.done.json').read_bytes()


@pytest.mark.parametrize('case', ['bars','pair_connection_stop','pair_open_failure','pair_write_failure',
    'pair_close_failure','pair_canonical_failure','timeout','deadline_without_heartbeat','late_heartbeat','source_mismatch',
    'provider_mismatch','unknown','unstable','price_loss','connection_loss','null','reconnect','rapid_ordering',
    'heartbeat_loss','bar_loss','source_removed','second_source','realtime_reentry','late_transition_duplicate',
    'recovery_callback','historical_reentry','no_callback_timeout','startup_duplicates','registry_busy','duplicates','closed_connected'])
def test_canonical_bytes_and_connection_diagnostics_unchanged(binaries,tmp_path,case):
    old = run(binaries['baseline'],tmp_path/'old',case)
    new = run(binaries['paired'],tmp_path/'new',case)
    assert old == new  # Includes original schemas, payloads, values, sequence, errors, HELLO/heartbeat/stop.
    assert next((tmp_path/'old').glob('*.connection.jsonl')).read_bytes() == next((tmp_path/'new').glob('*.connection.jsonl')).read_bytes()
    if case in ('bars','pair_connection_stop'):
        result = timing.adjudicate(*evidence(tmp_path/'new'))
        assert result['status'] == 'PASS', result
        assert (result['forming'],result['closed']) == (5,3)
        assert result['clock_preflight'] == result['reference_bound'] == result['drift_bound'] == 'UNKNOWN'
    else:
        assert not list((tmp_path/'new'/'timing').glob('*.done.json'))


@pytest.fixture
def valid(binaries,tmp_path):
    run(binaries['paired'],tmp_path/'valid')
    return evidence(tmp_path/'valid')


def encode(rows):
    return b''.join(json.dumps(r,separators=(',',':')).encode()+b'\n' for r in rows)


def reseal(rows, seal):
    raw = encode(rows); seal = deepcopy(seal)
    seal.update(records=len(rows),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return raw,json.dumps(seal).encode()


@pytest.mark.parametrize('mutation', ['missing','duplicate','order','sequence','session','row_hash','utc','qpc',
    'utc_regression','qpc_regression','frequency','label','index','historical','series','first_tick','provider',
    'template','bar_type','same_callback','closed_before_label','closure','unsealed','truncated','malformed',
    'duplicate_key','canonical_missing','canonical_duplicate','canonical_modified','bool_integer'])
def test_adverse_pairs_fail_closed(valid,mutation):
    canonical,raw,sealraw = valid
    pairs = [timing.parse(v) for v in raw.splitlines()]; seal = timing.parse(sealraw)
    p = pairs[2]
    if mutation == 'missing': pairs.pop(2)
    elif mutation == 'duplicate': pairs.insert(2,deepcopy(p))
    elif mutation == 'order': pairs[1],pairs[2] = pairs[2],pairs[1]
    elif mutation == 'sequence': p['canonical_sequence'] += 1
    elif mutation == 'session': p['session'] = str(uuid.uuid4())
    elif mutation == 'row_hash': p['canonical_sha256'] = '0'*64
    elif mutation == 'utc': p['emission']['utc_ticks'] += 1
    elif mutation == 'qpc': p['callback']['qpc_before'] = p['callback']['qpc_after']+1
    elif mutation == 'utc_regression': p['emission'] = deepcopy(pairs[0]['emission'])
    elif mutation == 'qpc_regression': p['emission']['qpc_before'] = p['emission']['qpc_after'] = 0
    elif mutation == 'frequency': p['qpc_frequency'] += 1
    elif mutation == 'label': p['source_bar_label'] = pairs[0]['source_bar_label']
    elif mutation == 'index': p['bar_index'] += 1
    elif mutation == 'historical': p['state'] = 'Historical'
    elif mutation == 'series': p['bars_in_progress'] = 1
    elif mutation == 'first_tick': p['first_tick'] = False
    elif mutation == 'provider': p['provider'] = 'Other'
    elif mutation == 'template': p['template'] = 'Other'
    elif mutation == 'bar_type': p['bars_type'] = 'Second'
    elif mutation == 'same_callback': pairs[3]['callback']['qpc_before'] += 1
    elif mutation == 'closed_before_label': p['callback'] = deepcopy(pairs[0]['callback'])
    elif mutation == 'closure': seal['canonical_writer_closed'] = False
    elif mutation == 'bool_integer': p['pair_sequence'] = True
    raw,sealraw = reseal(pairs,seal)
    if mutation == 'unsealed': sealraw = b'{}'
    elif mutation == 'truncated': raw = raw[:-1]
    elif mutation == 'malformed': raw = b'not JSON\n'
    elif mutation == 'duplicate_key': raw = raw.replace(b'"pair_sequence":0',b'"pair_sequence":0,"pair_sequence":0')
    elif mutation == 'canonical_missing': canonical = b'\n'.join(canonical.splitlines()[1:])+b'\n'
    elif mutation == 'canonical_duplicate': canonical += canonical.splitlines()[2]+b'\n'
    elif mutation == 'canonical_modified': canonical = canonical.replace(b'"open":100',b'"open":101')
    result = timing.adjudicate(canonical,raw,sealraw)
    assert result['status'] == 'FAIL', mutation
    assert result['runtime_admission'] is False and result['clock_preflight'] == 'UNKNOWN'


def test_old_seal_and_restart_stream_cannot_be_mixed(valid):
    canonical,raw,seal = valid
    new_session = str(uuid.uuid4()).encode()
    old_session = timing.parse(raw.splitlines()[0])['session'].encode()
    assert timing.adjudicate(canonical.replace(old_session,new_session),raw,seal)['status'] == 'FAIL'
    assert timing.adjudicate(canonical,raw+raw,seal)['status'] == 'FAIL'


def test_two_fresh_exporter_processes_are_isolated(binaries,tmp_path):
    for name in ('one','two'):
        run(binaries['paired'],tmp_path/name,session=str(uuid.uuid4()))
    one,two = evidence(tmp_path/'one'),evidence(tmp_path/'two')
    a,b = timing.adjudicate(*one),timing.adjudicate(*two)
    assert a['status'] == b['status'] == 'PASS' and a['session'] != b['session']
    assert timing.adjudicate(one[0],two[1],two[2])['status'] == 'FAIL'
    assert timing.adjudicate(two[0],two[1],one[2])['status'] == 'FAIL'


def clock_inputs(result):
    epoch = str(uuid.uuid4()); f = result['qpc_frequency']
    start = result['first_callback']['qpc_before']; end = result['last_emission']['qpc_after']
    raw = json.dumps(dict(epoch=epoch,status='MEASURED_NOT_ATTESTED',reviewed_reference_error_us=None,
                         reviewed_rate_error_ppb=None)).encode()
    def p(q): return dict(qpc_before=q,qpc_after=q+1,frequency=f,host_unix_ns=0)
    bridges = [dict(before=p(start-100),after=p(start-50),measurement_sha256=hashlib.sha256(raw).hexdigest()),
               dict(before=p(end+50),after=p(end+100),measurement_sha256=hashlib.sha256(raw).hexdigest())]
    return dict(run_id=epoch,epoch=epoch,bridges=bridges,measurements=[raw,raw])


def test_clock_binding_keeps_unknown_authority(valid):
    from tools.clock_preflight_v1 import assess
    result = timing.adjudicate(*valid)
    bound = timing.clock_epoch_binding(result,**clock_inputs(result))
    assert bound['reference_bound'] is None and bound['drift_bound'] is None
    assert bound['exporter_session'] == result['session'] and bound['runtime_admission'] is False
    assert len(bound['production_emission_windows']) == 8
    for window in bound['production_emission_windows']:
        assert window['host_utc_low_us'] <= window['host_utc_high_us']
        assert window['mono_low_us'] <= window['mono_high_us']
    proof = assess(samples=[],bounds=None,windows=[],windows_state=None,epoch=bound['epoch'],host_now_us=0,mono_now_us=0)
    assert proof['status'] == 'UNKNOWN' and not any(proof['clock_ready'].values())


@pytest.mark.parametrize('mutation',['epoch','hash','frequency','order','span'])
def test_clock_binding_rejects_mixed_epochs_or_unbracketed_evidence(valid,mutation):
    result = timing.adjudicate(*valid); args = clock_inputs(result)
    if mutation == 'epoch': args['epoch'] = str(uuid.uuid4())
    elif mutation == 'hash': args['bridges'][0]['measurement_sha256'] = '0'*64
    elif mutation == 'frequency': args['bridges'][0]['before']['frequency'] += 1
    elif mutation == 'order': args['bridges'].reverse()
    else: args['bridges'][0] = deepcopy(args['bridges'][1])
    with pytest.raises(ValueError): timing.clock_epoch_binding(result,**args)


def test_clock_probe_is_explicit_bracketed_and_bounded(monkeypatch):
    from tools import clock_evidence_v1, native_timing_witness_v1
    calls = []; epoch = str(uuid.uuid4())
    monkeypatch.setattr(native_timing_witness_v1,'qpc_pair',lambda:calls.append('pair') or {'fixture':True})
    def probe(ref,address,run,timeout):
        calls.append('probe'); assert timeout == 2 and run == epoch
        return dict(epoch=run,status='PROBE_INVALID_OR_UNAVAILABLE')
    monkeypatch.setattr(clock_evidence_v1,'probe',probe)
    raw,bridge = timing.acquire_clock_measurement(next(iter(clock_evidence_v1.REFERENCES)),'192.0.2.1',epoch)
    assert calls == ['pair','probe','pair']
    assert bridge['measurement_sha256'] == hashlib.sha256(raw).hexdigest()


def test_installed_sdk_compile_and_read_only_il(tmp_path):
    shim = tmp_path/'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    dll = tmp_path/'ProductionTiming.dll'
    refs = ['System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Xaml.dll',
            str(FW/'WPF/WindowsBase.dll'),str(FW/'WPF/PresentationCore.dll'),str(FW/'WPF/PresentationFramework.dll'),
            str(SDK/'NinjaTrader.Core.dll'),str(SDK/'NinjaTrader.Gui.dll')]
    proc = subprocess.run([str(FW/'csc.exe'),'/nologo','/target:library','/out:'+str(dll),
                          *['/r:'+r for r in refs],str(shim),str(SOURCE)],capture_output=True,text=True)
    assert proc.returncode == 0, proc.stdout
    inspector = tmp_path/'Inspect.ps1'
    inspector.write_text(literal_script(ROOT/'backend/tests/test_sim101_witness_sprint14r.py','ReflectionOnlyAssemblyResolve'))
    proc = subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(inspector),str(dll)],capture_output=True,text=True)
    assert proc.returncode == 0,proc.stderr
    allowed = {'Connection':{'Connections','InstrumentTypes','Options','PlaybackConnection','PriceStatus','Status'},
        'ConnectionStatusEventArgs':{'Connection','PreviousPriceStatus','PreviousStatus','PriceStatus','Status'},
        'ConnectOptions':{'Provider'},'Instrument':{'FullName','MasterInstrument','Expiry'},
        'MasterInstrument':{'Name','PointValue','TickSize'}}
    assert set(json.loads(proc.stdout)) == {f'NinjaTrader.Cbi.{t}::get_{m}' for t,ms in allowed.items() for m in ms}
    for word in ('Account','Order','Submit','Cancel','Flatten','Position','Reflection','DllImport','Activator','dynamic','Sleep','Socket','HttpClient'):
        assert not re.search(r'\b'+word+r'\b',SOURCE.read_text().replace('Order =','')),word


def test_offline_overhead_is_small_relative_to_minute_cadence(binaries,tmp_path,record_property):
    measured = {}
    for name,exe in binaries.items():
        values = []
        for n in range(3):
            folder = tmp_path/(name+str(n));run(exe,folder,'pair_benchmark')
            values.append(float((folder/'elapsed.txt').read_text())/1998)
        measured[name] = statistics.median(values)
    added = measured['paired']-measured['baseline']
    record_property('synthetic_median_ms_per_bar_record',json.dumps(measured))
    record_property('synthetic_added_ms_per_bar_record',added)
    # Broad local regression ceiling, not a real provider latency guarantee.
    assert added < 20, measured


def test_frozen_admission_methods_and_historical_certificate():
    from backend.tests.test_ninjatrader_stop_diagnostics_sprint11 import _method
    current = SOURCE.read_text(); old = BASELINE.read_text()
    for signature in ('private sealed class ReadinessGate','private bool SafeSource(',
                      'private void Heartbeat(', 'private object Candle(', 'private void Emit(',
                      'protected override void OnConnectionStatusUpdate(', 'protected override void OnStateChange('):
        assert _method(current,signature) == _method(old,signature),signature
    certificate = json.loads((ROOT/'backend/tests/market_open_native_certification_sprint13.json').read_text())
    assert hashlib.sha256(BASELINE.read_bytes().replace(b'\r\n',b'\n')).hexdigest() == certificate['reviewed_source_sha256']['integrations/ninjatrader/ArmsReadOnlyMarketV1.cs']


def test_offline_certificate_never_promotes_native_or_clock_authority():
    cert = json.loads((ROOT/'backend/tests/production_timing_sprint15w.json').read_text())
    assert cert['evidence_kind'] == 'OFFLINE_VALIDATION_WITH_RECORDED_PRODUCTION_CAPTURE'
    assert cert['fresh_production_capture_acquired'] is True
    assert cert['native_capture']['capture_status'] == 'INCOMPLETE_COORDINATED_CAPTURE_VALID_SEALED_STREAM'
    assert cert['reference_bound_status'] == cert['drift_bound_status'] == 'UNKNOWN'
    assert cert['runtime_admission'] is False and cert['live_authority'] is False
    for name,digest in cert['reviewed_source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == digest,name


@pytest.fixture(scope='module')
def recorded_production_capture():
    """Actual immutable recorded evidence, never injected into a fresh inbox."""
    return json.loads((ROOT/'backend/tests/production_timing_sprint15w.json').read_text())['native_capture']


def test_recorded_production_pairs_match_every_native_bar_and_seal(recorded_production_capture):
    c = recorded_production_capture
    raw,paired,seal = [c[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8')]
    result = timing.adjudicate(raw,paired,seal)
    assert result['status'] == 'PASS' and result['production_exporter_emission_binding'] == 'PASS_STREAM_ONLY'
    assert (result['records'],result['forming'],result['closed'],result['pairs']) == (134,10,8,18)
    session = c['exporter_session']
    assert session == 'f36aeebc-0ca7-4079-a318-55cce9d38602' == result['session']
    for suffix,data in ((f'inbox/{session}.jsonl',raw),
                        (f'inbox/timing/{session}.production-timing.jsonl',paired),
                        (f'inbox/timing/{session}.production-timing.jsonl.done.json',seal)):
        assert hashlib.sha256(data).hexdigest() == c['archive_file_sha256'][suffix]
    assert result['reference_bound'] == result['drift_bound'] == 'UNKNOWN'


def test_late_native_closure_cannot_retroactively_pass_failed_watcher(recorded_production_capture):
    c = recorded_production_capture
    assert c['watcher_terminal']['terminal_state'] == 'FAILED'
    assert c['watcher_terminal']['reason'] == 'WRITER_CLOSURE_TIMEOUT'
    assert c['watcher_terminal']['capture_elapsed_seconds'] >= 360
    assert 'reader_end' not in c['watcher_receipt']
    assert c['first_seen_to_end_seconds'] > 572 and c['closure_lateness_seconds'] > 212
    pairs = [timing.parse(line) for line in c['native_timing_utf8'].splitlines()]
    first = c['watcher_receipt']['first_seen_qpc']['qpc_before'];frequency = pairs[0]['qpc_frequency']
    inside = [p for p in pairs if p['emission']['qpc_after'] <= first+330*frequency]
    assert len(inside) == 10 and sum(p['kind']=='CLOSED' for p in inside) == 4
    assert len(pairs)-len(inside) == 8
    assert pairs[-1]['emission']['qpc_before']/frequency > c['watcher_terminal']['heartbeat_monotonic']+190
    assert c['capture_status'] != 'PASS' and c['runtime_admission'] is False


def test_all_recorded_clock_packets_redecode_and_remain_unattested(recorded_production_capture):
    from tools import clock_evidence_v1 as clock
    c = recorded_production_capture;records = []
    previous = -1
    for text,bridge in zip(c['clock_measurements_utf8'],c['clock_bridges']):
        raw = text.encode();r = timing.parse(raw)
        assert hashlib.sha256(raw).hexdigest() == bridge['measurement_sha256']
        assert r == clock.decode_reply(bytes.fromhex(r['packet_hex']),clock.encode_time(r['sent']['host_ns']),
                                       r['sent'],r['received'],r['reference'],c['run_id'])
        a,b = bridge['before'],bridge['after']
        assert a['frequency'] == b['frequency'] == 10000000
        assert previous <= a['qpc_before'] <= a['qpc_after'] <= b['qpc_before'] <= b['qpc_after']
        previous = b['qpc_after'];records.append(r)
        assert r['authenticated'] is False and r['reviewed_reference_error_us'] is None
        assert r['reviewed_rate_error_ppb'] is None
    assert len(records) == len(c['clock_bridges']) == 387
    summary = clock.summarize(records,{'mono_before_ns':max(r['received']['mono_after_ns'] for r in records)})
    assert summary == c['clock_summary']
    for ref in clock.REFERENCES:
        matching = [r for r in records if r['reference']==ref]
        assert len(matching) == 129
        assert statistics.median(r['midpoint_offset_ns'] for r in matching) == c['reference_groups'][ref]['all_sample_median_offset_ns']


def test_recorded_clock_epoch_does_not_cover_late_production_emissions(recorded_production_capture):
    from tools.clock_preflight_v1 import Sample,assess
    c = recorded_production_capture
    proof = timing.adjudicate(*[c[k].encode() for k in ('native_canonical_utf8','native_timing_utf8','native_seal_utf8')])
    with pytest.raises(ValueError,match='EPOCH_DOES_NOT_BRACKET_PRODUCTION'):
        timing.clock_epoch_binding(proof,run_id=c['run_id'],epoch=c['run_id'],bridges=c['clock_bridges'],
                                   measurements=[r.encode() for r in c['clock_measurements_utf8']])
    gap = (proof['last_emission']['qpc_after']-c['clock_bridges'][-1]['after']['qpc_after'])/proof['qpc_frequency']
    assert gap == pytest.approx(196.7828204)
    records = [timing.parse(r) for r in c['clock_measurements_utf8']]
    assessment = assess(samples=[Sample(**r['sample']) for r in records],bounds=None,windows=[],windows_state=None,
                        epoch=c['run_id'],host_now_us=records[-1]['received']['host_ns']//1000,
                        mono_now_us=records[-1]['received']['mono_after_ns']//1000)
    assert assessment == c['preflight']
    assert assessment['status'] == 'UNKNOWN' and not any(assessment['clock_ready'].values())
    for name in ('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs','tools/production_timing_v1.py',
                 'tools/clock_preflight_v1.py','tools/clock_evidence_v1.py'):
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == c['source_hashes_at_capture'][name]


def test_recorded_canonical_frames_use_unchanged_reader_with_inert_sink(recorded_production_capture):
    """Historical parser replay under an explicit test clock, never runtime admission."""
    from datetime import datetime
    from types import SimpleNamespace
    from math import isfinite
    from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1
    rows = recorded_production_capture['native_canonical_utf8'].splitlines()
    now = [None]; received = []; connected = []
    contract = SimpleNamespace(provider='NINJATRADER:Provider31',contract='NQ DEC26',trading_hours_template='CME US Index Futures ETH')
    sink = SimpleNamespace(gate=SimpleNamespace(contract=contract,clock=lambda:now[0]),_runtime=None,
                           connection=connected.append,ingest=received.append)
    reader = object.__new__(NinjaTraderMarketReaderV1)  # No CurrentPaperService, account, database or executor.
    reader.service=sink;reader.provider='Provider31';reader.expiry='2026-12-01';reader.deadline=15
    reader.session=None;reader.sequence=-1;reader.last_event=None;reader.candle_sequence=0
    for raw in rows[:-1]:
        row=timing.parse(raw);now[0]=datetime.fromisoformat(row['event_time'].replace('Z','+00:00'))
        reader._frame(raw.encode())
        if row['kind'] in ('FORMING','CLOSED'):
            p=row['payload'];assert set(p)==set('bar_time open high low close volume'.split())
            assert all(isfinite(p[k]) and p[k]*4==int(p[k]*4) for k in ('open','high','low','close'))
            assert p['low']<=p['open']<=p['high'] and p['low']<=p['close']<=p['high']
            assert type(p['volume']) is int and p['volume']>=0
    assert connected==[True] and len(received)==18 and sink._runtime is None
    now[0]=datetime.fromisoformat(timing.parse(rows[-1])['event_time'].replace('Z','+00:00'))
    with pytest.raises(ValueError,match='disconnect'): reader._frame(rows[-1].encode())
    assert len(received)==18  # Termination does not synthesize a candle or fill.
