"""Synthetic callback execution of the actual witness; installed SDK IL audit.

The executable harness links ONLY fake SDK types. Real SDK is compiled/inspected
as metadata, never instantiated and never connected to NinjaTrader.
"""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess
import uuid
import os
import sys
import time
import threading
import ctypes
from contextlib import contextmanager

import pytest

from tools import native_timing_witness_v1 as timing

SOURCE=Path('integrations/ninjatrader/ArmsNativeTimingWitnessV1.cs')
FRAMEWORK=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
SDK=Path('C:/Program Files/NinjaTrader 8/bin')

def recorded_r4_capture():
    """Hash-bound historical trace, never injected into a fresh watcher inbox."""
    cert=json.loads(Path('backend/tests/native_timing_sprint15v.json').read_text(encoding='utf-8'))
    c=cert['native_capture_r4_adjudication']
    return c,c['native_jsonl'].encode('utf-8'),c['seal_json'].encode('utf-8'),deepcopy(c['receipt'])


def test_actual_r4_capture_replay_preserves_startup_and_three_closed_boundaries():
    capture,raw,seal,receipt=recorded_r4_capture()
    result=timing.adjudicate(raw,seal,receipt)
    assert result==capture['watcher_result'] and result['status']=='PASS'
    assert hashlib.sha256(raw).hexdigest()=='1c4d563074886224dda99f156c2352c3eec3d5b87d6bfcf8b6962c4a0629e4bb'
    assert result['native_session']=='ca149956-c358-4d85-b5b2-c7a2961e0afd'
    rows=[timing.parse(line) for line in raw.splitlines()]
    assert [r['sequence'] for r in rows]==list(range(14))
    assert [rows[i]['payload']['reason'] for i in (2,3)]==['WAIT_STARTUP_ALIGNMENT','CONTINUE']
    assert rows[4]['kind']=='BASELINE' and rows[4]['payload']['aligned_event_sequence']==1
    assert rows[4]['callback']['qpc_before']>rows[3]['emission']['qpc_after']
    bars=[r for r in rows if r['kind'] in ('FORMING','CLOSED')]
    assert all(r['callback']['qpc_before']>rows[4]['emission']['qpc_after'] for r in bars)
    closed=[r for r in bars if r['kind']=='CLOSED']
    assert [r['payload']['bar_index'] for r in closed]==[5089,5090,5091]
    assert [r['payload']['close_label_utc'] for r in closed]==[
        '2026-09-21T13:50:00.0000000Z','2026-09-21T13:51:00.0000000Z','2026-09-21T13:52:00.0000000Z']
    for index in (7,9,11):
        assert rows[index]['callback']==rows[index+1]['callback']
        assert rows[index]['emission']['qpc_after']<rows[index+1]['emission']['qpc_before']
    assert (result['forming_count'],result['closed_count'])==(5,3)
    assert rows[-1]['payload']==dict(reason='BOUNDARIES_COMPLETE',closed_count=3)
    assert not result['runtime_admission'] and result['clock_preflight']=='UNKNOWN'


@pytest.mark.parametrize('attack',['missing_baseline','unaligned_event','callback_before_baseline','bad_pair','duplicate_closed','foreign_run','unclosed_writer'])
def test_actual_r4_evidence_mutations_cannot_retain_diagnostic_pass(attack):
    capture,raw,seal,receipt=recorded_r4_capture()
    rows=[timing.parse(line) for line in raw.splitlines()]
    if attack=='missing_baseline': del rows[4]
    if attack=='unaligned_event': rows[4]['payload']['aligned_event_sequence']=0
    if attack=='callback_before_baseline': rows[5]['callback']=rows[3]['callback'];rows[5]['payload']['callback']=rows[3]['callback']
    if attack=='bad_pair': rows[7]['emission']['utc_ticks']+=1
    if attack=='duplicate_closed': rows[9]['payload']=deepcopy(rows[7]['payload'])
    if attack=='foreign_run': receipt['run_id']=str(uuid.uuid4())
    s=timing.parse(seal)
    if attack=='unclosed_writer': s['writer_closed']=False
    for index,r in enumerate(rows): r['sequence']=index
    s['records']=len(rows)
    raw,seal=repack(rows,json.dumps(s).encode())
    result=timing.adjudicate(raw,seal,receipt)
    assert result['status']=='FAIL' and result['paired_native_timing']=='NOT_PROVEN'
    assert not result['runtime_admission']


def test_actual_r4_pairs_supply_neither_absolute_bounds_nor_production_emission_binding():
    from tools.clock_preflight_v1 import assess
    from tools.clock_evidence_v1 import native_candidate_proof
    capture,raw,seal,receipt=recorded_r4_capture()
    rows=[timing.parse(line) for line in raw.splitlines()]
    for row in (r for r in rows if r['kind'] in ('FORMING','CLOSED')):
        pair=timing.as_preflight_pair(row)
        assert pair['reference_bound'] is None and pair['drift_bound'] is None
        result=assess(samples=[],bounds=None,windows=[],windows_state=None,epoch=row['run_id'],
            host_now_us=pair['host_utc_us'],mono_now_us=pair['mono_high_us'])
        assert result==capture['summary']['clock_preflight']
        assert not any(result['clock_ready'].values()) and not result['runtime_readiness_granted']
        candidate=dict(epoch=row['run_id'],native_session=row['session'],calendar_sha256=row['payload']['calendar_sha256'],
            state='Realtime',connection_continuity=True,callback_bound_to_exporter_record=False,
            source=['Provider31','NQ DEC26','Minute',1,'UTC','CME US Index Futures ETH'],kind=row['kind'])
        assert native_candidate_proof(candidate,epoch=row['run_id'],native_session=row['session'],
            calendar_hash=row['payload']['calendar_sha256'],window=None,event_utc=None,receipt_utc=None,
            now_utc=None,maximum_age_us=None)=='UNKNOWN'


HARNESS=r'''
using System; using System.IO; using System.Linq; using System.Collections.Generic;
using System.Reflection; using System.Threading; using System.Web.Script.Serialization;
namespace Doubles {
 public class Dispatcher { public void InvokeAsync(Action a){a();} }
 public class Chart { public Dispatcher Dispatcher=new Dispatcher(); }
}
namespace System.Windows.Threading {
 public class DispatcherTimer {
  public bool Running; public TimeSpan Interval; public event EventHandler Tick;
  public void Start(){Running=true;} public void Stop(){Running=false;}
  public void Fire(){if(Running && Tick!=null)Tick(this,EventArgs.Empty);}
 }
}
namespace NinjaTrader.Core { public static class Globals { public static Options GeneralOptions=new Options(); }
public class Options { public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.Utc; } }
namespace NinjaTrader.Cbi {
 public enum ConnectionStatus { Connected, Disconnected, Connecting, ConnectionLost, Disconnecting } public enum Provider { Provider31, Other }
 public enum InstrumentType { Future }
 public class ConnectOptions { public Provider Provider=Provider.Provider31; }
 public class Connection {
  public static Connection PlaybackConnection=null; public static List<Connection> Connections=new List<Connection>{new Connection()};
  public InstrumentType[] InstrumentTypes=new[]{InstrumentType.Future}; public ConnectOptions Options=new ConnectOptions();
  public ConnectionStatus Status=ConnectionStatus.Connected;
  private ConnectionStatus price=ConnectionStatus.Connected; public bool Flip,FlipOuter;private int reads;
  public ConnectionStatus PriceStatus {get{if(Flip || FlipOuter)reads++;return (Flip && reads%2==0) || (FlipOuter && reads>=4) ? ConnectionStatus.Connecting : price;}set{price=value;}}
 }
 public class ConnectionStatusEventArgs { public Connection Connection=Connection.Connections[0];
  public ConnectionStatus Status=ConnectionStatus.Connected,PriceStatus=ConnectionStatus.Connected,
   PreviousStatus=ConnectionStatus.Connected,PreviousPriceStatus=ConnectionStatus.Connected; }
 public class Instrument { public string FullName="NQ DEC26"; public MasterInstrument MasterInstrument=new MasterInstrument(); }
 public class MasterInstrument { public string Name="NQ"; public double TickSize=.25,PointValue=20; }
}
namespace NinjaTrader.Data {
 public enum BarsPeriodType { Minute } public class BarsPeriod { public BarsPeriodType BarsPeriodType=BarsPeriodType.Minute;public int Value=1; }
 public class Session { public DayOfWeek BeginDay,EndDay,TradingDay;public int BeginTime=1700,EndTime=1600; }
 public class Partial { public bool IsEarlyEnd,IsLateBegin;public Session Constraint;public List<Session> Sessions=new List<Session>(); }
 public class Hours { public string Name="CME US Index Futures ETH";public int Version=1;
  public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
  public List<Session> Sessions=Enumerable.Range(1,5).Select(i=>new Session{BeginDay=(DayOfWeek)(i-1),EndDay=(DayOfWeek)i,TradingDay=(DayOfWeek)i}).ToList();
  public Dictionary<DateTime,string> Holidays=new Dictionary<DateTime,string>();
  public Dictionary<DateTime,Partial> PartialHolidays=new Dictionary<DateTime,Partial>(); }
 public class Bars { public Hours TradingHours=new Hours();public DateTime Zero;public int Current;
  public DateTime GetTime(int index){return Zero.AddMinutes(index-Current);} }
 public class SessionIterator { public SessionIterator(Bars b){}
  public DateTime ActualSessionBegin=DateTime.Parse("2026-09-20T22:00:00Z").ToUniversalTime();
  public DateTime ActualSessionEnd=DateTime.Parse("2026-09-21T21:00:00Z").ToUniversalTime();
  public DateTime ActualTradingDayExchange=new DateTime(2026,9,21);
  public void GetNextSession(DateTime d,bool inclusive){} }
}
namespace NinjaTrader.NinjaScript {
 public enum State { SetDefaults,DataLoaded,Historical,Realtime,Terminated }
 public enum Calculate { OnEachTick }
 [AttributeUsage(AttributeTargets.Property)] public class NinjaScriptPropertyAttribute:Attribute{}
 public class Series { public NinjaTrader.Data.Bars Bars;public DateTime this[int ago]{get{return Bars.Zero.AddMinutes(-ago);}} }
}
namespace NinjaTrader.NinjaScript.Indicators {
 public class Indicator {
  public State State;public string Name,Description;public Calculate Calculate; public bool IsOverlay,IsChartOnly,IsSuspendedWhileInactive;
  public NinjaTrader.Cbi.Instrument Instrument=new NinjaTrader.Cbi.Instrument();
  public NinjaTrader.Data.BarsPeriod BarsPeriod=new NinjaTrader.Data.BarsPeriod();
  public NinjaTrader.Data.Bars Bars=new NinjaTrader.Data.Bars();public Series Time;
  public int CurrentBar,BarsInProgress;public bool IsFirstTickOfBar=true;
  public Doubles.Chart ChartControl=new Doubles.Chart();
  public Indicator(){Time=new Series{Bars=Bars};}
  protected virtual void OnStateChange(){} protected virtual void OnBarUpdate(){}
  protected virtual void OnConnectionStatusUpdate(NinjaTrader.Cbi.ConnectionStatusEventArgs e){}
  public void Print(string s){}
 }
 public class Driver:ArmsNativeTimingWitnessV1 {
  public void StateTo(State s){State=s;OnStateChange();}
  public void Bar(int index,DateTime label){CurrentBar=index;Bars.Current=index;Bars.Zero=label;OnBarUpdate();}
  public void Disconnect(){OnConnectionStatusUpdate(new NinjaTrader.Cbi.ConnectionStatusEventArgs{Status=NinjaTrader.Cbi.ConnectionStatus.Disconnected});}
  public void EarlyConnection(string mode){
   var e=new NinjaTrader.Cbi.ConnectionStatusEventArgs();
   if(mode=="early_other")e.Connection=new NinjaTrader.Cbi.Connection();
   if(mode=="early_source_null")e.Connection=null;
   if(mode=="early_previous")e.PreviousStatus=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
   if(mode=="early_disconnected")e.Status=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
   if(mode=="early_price")e.PriceStatus=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
   if(mode=="early_price_connecting")e.PriceStatus=NinjaTrader.Cbi.ConnectionStatus.Connecting;
   if(mode=="early_lost")e.Status=NinjaTrader.Cbi.ConnectionStatus.ConnectionLost;
   if(mode=="early_connecting")e.Status=NinjaTrader.Cbi.ConnectionStatus.Connecting;
   if(mode=="early_unknown")e.Status=(NinjaTrader.Cbi.ConnectionStatus)999;
   if(mode=="early_previous_price")e.PreviousPriceStatus=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
   if(mode=="aligned")e.PreviousStatus=e.PreviousPriceStatus=NinjaTrader.Cbi.ConnectionStatus.Connecting;
   if(mode=="ambiguous")e.PreviousStatus=NinjaTrader.Cbi.ConnectionStatus.ConnectionLost;
   if(mode=="early_bootstrap"){
    e.Status=e.PriceStatus=NinjaTrader.Cbi.ConnectionStatus.Connecting;
    e.PreviousStatus=e.PreviousPriceStatus=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
   }
   OnConnectionStatusUpdate(mode=="early_null"?null:e);
  }
 }
}
class Program {
 static object Field(object x,string name){return typeof(NinjaTrader.NinjaScript.Indicators.ArmsNativeTimingWitnessV1).GetField(name,BindingFlags.NonPublic|BindingFlags.Instance).GetValue(x);}
 public static int Main(string[] args){
  var d=new NinjaTrader.NinjaScript.Indicators.Driver();d.StateTo(NinjaTrader.NinjaScript.State.SetDefaults);
  string attack=args[2];
  if(attack=="prebaseline")d.Disconnect();
  if(attack=="snapshot_unavailable")NinjaTrader.Cbi.Connection.Connections.Clear();
  if(attack=="snapshot_disconnected")NinjaTrader.Cbi.Connection.Connections[0].Status=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
  d.OutputDirectory=args[0];d.CaptureRunId=args[1];d.StateTo(NinjaTrader.NinjaScript.State.DataLoaded);
  if(attack=="before_realtime")d.Disconnect();
  if(attack=="healthy_before_realtime")d.EarlyConnection("healthy");
  var at=DateTime.Parse("2026-09-21T07:01:00Z").ToUniversalTime();
  d.StateTo(NinjaTrader.NinjaScript.State.Historical);d.Bar(99,at.AddMinutes(-1));
  if(attack=="queued_realtime_event"){
   var gate=Field(d,"sync");Monitor.Enter(gate);
   var queued=new Thread(()=>d.EarlyConnection("healthy"));queued.Start();
   if(!SpinWait.SpinUntil(()=>(queued.ThreadState & ThreadState.WaitSleepJoin)!=0,3000))throw new Exception("No blocked event");
   d.StateTo(NinjaTrader.NinjaScript.State.Realtime);Monitor.Exit(gate);queued.Join();
  }else d.StateTo(NinjaTrader.NinjaScript.State.Realtime);
  if(attack.StartsWith("early_"))d.EarlyConnection(attack);
  if(attack=="before_baseline_bar")d.Bar(90,at.AddMinutes(-10));
  if(attack=="source_snapshot_bad")NinjaTrader.Cbi.Connection.Connections[0].PriceStatus=NinjaTrader.Cbi.ConnectionStatus.Connecting;
  if(attack=="source_connecting")NinjaTrader.Cbi.Connection.Connections[0].Status=NinjaTrader.Cbi.ConnectionStatus.Connecting;
  if(attack=="source_disconnected")NinjaTrader.Cbi.Connection.Connections[0].Status=NinjaTrader.Cbi.ConnectionStatus.Disconnected;
  if(attack=="provider")NinjaTrader.Cbi.Connection.Connections[0].Options.Provider=NinjaTrader.Cbi.Provider.Other;
  if(attack=="unstable")NinjaTrader.Cbi.Connection.Connections[0].Flip=true;
  if(attack=="unstable_outer")NinjaTrader.Cbi.Connection.Connections[0].FlipOuter=true;
  bool r4=attack.StartsWith("r4_");
  if(r4){d.EarlyConnection("early_bootstrap");d.Bar(80,at.AddMinutes(-20));
   if(attack=="r4_duplicates")d.EarlyConnection("early_bootstrap");
   ((System.Windows.Threading.DispatcherTimer)Field(d,"alignmentTimer")).Fire();d.Bar(81,at.AddMinutes(-19));
   if(attack!="r4_connecting_only")d.EarlyConnection("aligned");
   if(attack=="r4_duplicates")d.EarlyConnection("aligned");
  }
  if(!r4 && !attack.StartsWith("snapshot_") && attack!="no_baseline" && attack!="healthy_before_realtime" && attack!="queued_poll" && attack!="queued_realtime_event")d.EarlyConnection("healthy");
  if(attack=="duplicates"){d.EarlyConnection("healthy");d.EarlyConnection("healthy");}
  d.Bar(95,at.AddMinutes(-5)); // Aligned EVENT still cannot grant baseline.
  if(attack=="poll_source_bad")NinjaTrader.Cbi.Connection.Connections[0].PriceStatus=NinjaTrader.Cbi.ConnectionStatus.Connecting;
  if(attack=="poll_calendar_bad")d.Bars.TradingHours.Version++;
  var poll=(System.Windows.Threading.DispatcherTimer)Field(d,"alignmentTimer");
  if(attack=="startup_timeout_poll")typeof(NinjaTrader.NinjaScript.Indicators.ArmsNativeTimingWitnessV1).GetField("realtimeQpc",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(d,System.Diagnostics.Stopwatch.GetTimestamp()-31*System.Diagnostics.Stopwatch.Frequency);
  if(attack=="queued_poll"){
   var gate=Field(d,"sync");Monitor.Enter(gate);
   var queued=new Thread(()=>poll.Fire());queued.Start();
   if(!SpinWait.SpinUntil(()=>(queued.ThreadState & ThreadState.WaitSleepJoin)!=0,3000))throw new Exception("No blocked poll");
   d.EarlyConnection("healthy");Monitor.Exit(gate);queued.Join();
   if(Field(d,"continuity").ToString()=="BASELINE_PROVEN")throw new Exception("Queued poll granted baseline");
   poll.Fire();
  }else if(attack=="queued_bar"){
   var gate=Field(d,"sync");Monitor.Enter(gate);
   var queued=new Thread(()=>d.Bar(96,at.AddMinutes(-4)));queued.Start();
   if(!SpinWait.SpinUntil(()=>(queued.ThreadState & ThreadState.WaitSleepJoin)!=0,3000))throw new Exception("No blocked callback");
   poll.Fire();Monitor.Exit(gate);queued.Join();
  }else if(poll!=null && attack!="aligned_no_poll")poll.Fire();
  for(int i=0;i<5;i++){
   if(attack=="post_price" && i==1)d.EarlyConnection("early_price");
   if(attack=="post_previous" && i==1)d.EarlyConnection("early_previous");
   if(attack=="post_aligned_duplicate" && i==1)d.EarlyConnection("aligned");
   if(attack=="post_ambiguous" && i==1)d.EarlyConnection("ambiguous");
   if(attack=="post_connecting" && i==1)d.EarlyConnection("early_bootstrap");
   if(attack=="restart" && i==1)d.StateTo(NinjaTrader.NinjaScript.State.Realtime);
   if(attack=="reconnect" && i==1){d.Disconnect();d.EarlyConnection("healthy");}
   if(attack=="calendar" && i==1)d.Bars.TradingHours.Version++;
   if(attack=="timezone" && i==1)NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
   if((attack=="timer" || attack=="no_baseline" || attack=="healthy_before_realtime" || attack=="aligned_no_poll" || attack=="queued_realtime_event") && i==1){((Timer)Field(d,"deadline")).Change(1,Timeout.Infinite);SpinWait.SpinUntil(()=>Field(d,"writer")==null && Directory.GetFiles(args[0],"*.done.json").Length==1,3000);break;}
   if(attack=="r4_connecting_only" && i==1){((Timer)Field(d,"startupDeadline")).Change(1,Timeout.Infinite);SpinWait.SpinUntil(()=>Field(d,"writer")==null && Directory.GetFiles(args[0],"*.done.json").Length==1,3000);break;}
   int j=i;
   if(attack=="duplicate" && i==1)j=0;
   if(attack=="out_of_order" && i==1)j=-1;
   if(attack=="gap" && i>=1)j=i+1;
   d.Bar(100+j,at.AddMinutes(j));
  }
  bool closed=Field(d,"writer")==null && Field(d,"deadline")==null && Field(d,"source")==null && Field(d,"startupDeadline")==null && Field(d,"alignmentTimer")==null;
  d.StateTo(NinjaTrader.NinjaScript.State.Terminated);
  var files=Directory.GetFiles(args[0],"*.timing.jsonl");
  bool exclusive=false;
  if(files.Length==1){using(var f=new FileStream(files[0],FileMode.Open,FileAccess.ReadWrite,FileShare.None)){exclusive=true;}}
  Console.WriteLine(new JavaScriptSerializer().Serialize(new{closed=closed,exclusive=exclusive}));return 0;
 }
}
'''


@pytest.fixture(scope='module')
def compiled_harness(tmp_path_factory):
    p=tmp_path_factory.mktemp('native_timing_harness');stub=p/'Harness.cs';stub.write_text(HARNESS)
    exe=p/'Harness.exe'
    result=subprocess.run([str(FRAMEWORK/'csc.exe'),'/nologo','/out:'+str(exe),
                           '/r:System.Web.Extensions.dll','/r:System.ComponentModel.DataAnnotations.dll',
                           str(stub),str(SOURCE.resolve())],capture_output=True,text=True)
    assert result.returncode==0,result.stdout
    return exe


def run_case(exe,tmp_path,attack='none'):
    run=str(uuid.uuid4());before=timing.qpc_pair()
    process=subprocess.run([str(exe),str(tmp_path),run,attack],capture_output=True,text=True,timeout=8)
    after=timing.qpc_pair()
    assert process.returncode==0,process.stdout+process.stderr
    assert json.loads(process.stdout)=={'closed':True,'exclusive':True}
    path=next(tmp_path.glob('*.timing.jsonl'));raw=path.read_bytes();rows=[timing.parse(s) for s in raw.splitlines()]
    seal=path.with_name(path.name+'.done.json').read_bytes()
    plan=dict(run_id=run,reader_start=before,reader_end=after,calendar=timing.parse(rows[0]['payload']['calendar_json']),
              valid_from='2026-09-21T00:00:00.0000000Z',valid_until='2026-09-28T00:00:00.0000000Z',
              covered_dates=['2026-09-21'])
    return raw,seal,plan,rows


def test_actual_csharp_same_callback_pairs_sequence_and_closure(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path)
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='PASS',result
    assert result['closed_count']==3 and result['forming_count']==5 and result['writer_closed']
    assert result['paired_native_timing']=='PASS_WITNESS_STREAM_ONLY'
    assert not result['runtime_admission'] and result['clock_preflight']=='UNKNOWN'
    assert result['broker_order_calls']==0 and result['ninjatrader_account_access'] is False
    assert [r['kind'] for r in rows]==['HELLO','REALTIME','CONNECTION_EVENT','BASELINE','FORMING','FORMING','CLOSED','FORMING','CLOSED','FORMING','CLOSED','FORMING','END']
    for i in (6,8,10):
        assert rows[i]['callback']==rows[i+1]['callback']
        assert rows[i]['emission']['qpc_after']<=rows[i+1]['emission']['qpc_before']
    for r in rows:
        assert r['event_time']==r['emission']['utc']
        assert r['emission']['utc_ticks']==timing.ticks(r['event_time'])


@pytest.mark.parametrize('attack',['duplicate','out_of_order','gap','restart','reconnect','calendar','timezone','timer'])
def test_native_errors_auto_close_and_never_grant_market_authority(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']==('INCONCLUSIVE' if attack=='timer' else 'FAIL'),result
    assert not result['runtime_admission'] and result['clock_preflight']=='UNKNOWN'
    assert rows[-1]['kind']=='END'
    assert len(rows)<12


def repack(rows,seal):
    raw=('\n'.join(json.dumps(r,separators=(',',':')) for r in rows)+'\n').encode()
    seal=timing.parse(seal);seal.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return raw,json.dumps(seal).encode()


@pytest.mark.parametrize('attack,reason',[
    ('early_null','CONNECTION_EVENT_NULL'),
    ('early_source_null','CONNECTION_EVENT_SOURCE_NULL'),
    ('early_other','STOP_CONNECTION_IDENTITY_MISMATCH'),
    ('early_disconnected','STOP_CONNECTION_LOSS_EVENT'),
    ('early_price','STOP_CONNECTION_LOSS_EVENT'),
    ('early_connecting','STOP_CONNECTION_REGRESSION'),
    ('early_lost','STOP_CONNECTION_LOSS_EVENT'),
    ('early_unknown','STOP_UNKNOWN_CONNECTION_STATE'),
    ('early_price_connecting','STOP_CONNECTION_REGRESSION'),
])
def test_pre_bar_connection_abort_is_failure_not_paired_bar_proof(compiled_harness,tmp_path,attack,reason):
    # Synthetic alternatives reproduce the observed HELLO/REALTIME/END shape.
    # The real END reason cannot identify which of these event conditions occurred.
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    assert [r['kind'] for r in rows]==['HELLO','REALTIME','CONNECTION_EVENT','END']
    assert rows[-1]['payload']=={'reason':reason,'closed_count':0}
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='FAIL'
    assert result['first_witness_line']==4
    assert result['reason']=='NATIVE_STOP_'+reason
    assert result['paired_native_timing']=='NOT_PROVEN'
    assert result['runtime_admission'] is False
    assert result['clock_preflight']=='UNKNOWN'
    assert result['broker_order_calls']==0 and result['ninjatrader_account_access'] is False
    assert timing.parse(seal)['writer_closed'] is True


@pytest.mark.parametrize('attack',['prebaseline','duplicates','before_baseline_bar','early_previous','early_previous_price','early_bootstrap','r4_startup','r4_duplicates','queued_bar','queued_poll'])
def test_prebaseline_event_is_not_continuity_proof_and_healthy_duplicates_are_allowed(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    assert rows[0]['kind']=='HELLO' and rows[1]['kind']=='REALTIME'
    bars=[r for r in rows if r['kind'] in ('FORMING','CLOSED')]
    assert bars[0]['kind']=='FORMING' and bars[2]['kind']=='CLOSED'
    assert bars[0]['payload']['bar_index']==100
    assert timing.adjudicate(raw,seal,plan)['status']=='PASS'
    # Diagnostic-only pass, never a claim about events before the DataLoaded snapshot.
    assert all(r['runtime_admission'] is False for r in rows)


def test_post_baseline_event_before_realtime_is_terminal(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'before_realtime')
    assert [r['kind'] for r in rows]==['HELLO','CONNECTION_EVENT','END']
    assert rows[-1]['payload']['reason']=='STOP_CONNECTION_LOSS_EVENT'
    assert timing.adjudicate(raw,seal,plan)['status']=='FAIL'


@pytest.mark.parametrize('attack',['snapshot_unavailable','snapshot_disconnected'])
def test_unavailable_or_disconnected_initial_snapshot_emits_no_evidence(compiled_harness,tmp_path,attack):
    result=subprocess.run([str(compiled_harness),str(tmp_path),str(uuid.uuid4()),attack],capture_output=True,text=True,timeout=8)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'closed':True,'exclusive':False}
    assert not list(tmp_path.glob('*.timing.jsonl'))


def test_legacy_ambiguous_failure_remains_failed_not_relabelled(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'early_previous')
    rows[-1]['payload']['reason']='CONNECTION_CONTINUITY_UNPROVEN'
    for row in rows: row['schema']='arms.nt.native-timing.v1'
    s=timing.parse(seal);s['reason']='CONNECTION_CONTINUITY_UNPROVEN'
    raw,seal=repack(rows,json.dumps(s).encode())
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='FAIL' and result['reason']=='SCHEMA'
    assert result['first_witness_line']==1 and not result['runtime_admission']


def test_control_pair_adapter_cannot_supply_missing_clock_authority(compiled_harness,tmp_path):
    from tools.clock_preflight_v1 import assess
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'early_previous')
    pair=timing.as_preflight_pair(rows[-1])
    assert pair['reference_bound'] is None and pair['drift_bound'] is None
    result=assess(samples=[],bounds=None,windows=[],windows_state=None,
                  epoch=plan['run_id'],host_now_us=pair['host_utc_us'],mono_now_us=pair['mono_high_us'])
    assert result['status']=='UNKNOWN'
    assert result['reasons']==['REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING']
    assert not any(result['clock_ready'].values())
    assert result['runtime_readiness_granted'] is False


def test_r3_observation_is_quarantined_until_new_positive_proof(compiled_harness,tmp_path):
    certificate=json.loads(Path('backend/tests/native_timing_sprint15v.json').read_text())
    capture=certificate['native_capture_r3_adjudication']
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'r4_connecting_only')
    event=rows[2]['payload']
    for field in ('event_status','event_price_status','previous_status','previous_price_status',
                  'source_status','source_price_status','source_status_after','source_price_status_after'):
        assert event[field]==capture['event'][field]
    assert event['reason']=='WAIT_STARTUP_ALIGNMENT'
    assert event['continuity_after']=='WAIT_ALIGNMENT'
    assert rows[-1]['payload']=={'reason':'STOP_STARTUP_TIMEOUT','closed_count':0}
    assert not any(r['kind'] in ('FORMING','CLOSED','BASELINE') for r in rows)
    assert timing.adjudicate(raw,seal,plan)['reason']=='NATIVE_STOP_STOP_STARTUP_TIMEOUT'
    # Prior R3 capture is an immutable historical rejection, never fresh R4 proof.
    assert capture['event']['reason']=='CONNECTION_STATUS_NOT_CONNECTED'


@pytest.mark.parametrize('attack',['session','run','sequence','duplicate_key','truncated','timezone','calendar',
                                  'session_end','label','implied_start','utc_pair','qpc_pair','callback_pair',
                                  'historical','first_tick','bar_index','clock_epoch','receipt_order',
                                  'frequency','unknown_field','unclosed','bad_seal','out_of_order','missing_record'])
def test_malformed_or_unbound_output_fails_closed(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path)
    r=rows[5];p=r['payload']
    if attack=='session': r['session']=str(uuid.uuid4())
    if attack=='run': r['run_id']=str(uuid.uuid4())
    if attack=='sequence': r['sequence']+=1
    if attack=='timezone': p['application_timezone']='Eastern Standard Time'
    if attack=='calendar': p['calendar_sha256']='0'*64
    if attack=='session_end': p['session_end_utc']='2026-09-21T20:00:00.0000000Z'
    if attack=='label': p['native_label']='2026-09-21T07:03:00.0000000Z'
    if attack=='implied_start': p['implied_start_utc']=p['close_label_utc']
    if attack=='utc_pair': r['event_time']=rows[0]['event_time']
    if attack=='qpc_pair': r['emission']['qpc_after']=r['emission']['qpc_before']-1
    if attack=='callback_pair': p['callback']=rows[0]['callback']
    if attack=='historical': p['state']='Historical'
    if attack=='first_tick': p['first_tick']=False
    if attack=='bar_index': p['bar_index']+=1
    if attack=='clock_epoch': r['start_qpc']+=1
    if attack=='receipt_order': plan['reader_end']=plan['reader_start']
    if attack=='frequency': r['qpc_frequency']+=1
    if attack=='unknown_field': p['unreviewed_private_field']='forbidden'
    if attack=='out_of_order': rows[4],rows[5]=rows[5],rows[4]
    if attack=='missing_record': del rows[4]
    raw,seal=repack(rows,seal)
    if attack=='duplicate_key': raw=raw.replace(b'"sequence":4',b'"sequence":4,"sequence":4')
    if attack=='truncated': raw=raw[:-1]
    if attack=='unclosed': s=timing.parse(seal);s['writer_closed']=False;seal=json.dumps(s).encode()
    if attack=='bad_seal': s=timing.parse(seal);s['sha256']='0'*64;seal=json.dumps(s).encode()
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='FAIL',result
    assert result['paired_native_timing']=='NOT_PROVEN' and not result['runtime_admission']


def test_pair_adapter_preserves_quantization_and_separate_epoch(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path)
    p=timing.as_preflight_pair(rows[4]);r=rows[4]
    assert p['mono_low_us']<=r['emission']['qpc_before']*1000000/r['qpc_frequency']
    assert p['mono_high_us']>=r['emission']['qpc_after']*1000000/r['qpc_frequency']
    assert p['native_epoch']==[r['run_id'],r['session']]
    assert p['reference_bound'] is None and p['drift_bound'] is None
    assert p['clock_preflight']=='UNKNOWN' and p['runtime_admission'] is False


@pytest.mark.parametrize('attack,field,value',[
    ('early_connecting','event_status','Connecting'),
    ('early_lost','event_status','ConnectionLost'),
    ('early_disconnected','event_status','Disconnected'),
    ('early_unknown','event_status','UNDEFINED_999'),
    ('early_price_connecting','event_price_status','Connecting'),
    ('early_previous','previous_status','Disconnected'),
    ('early_previous_price','previous_price_status','Disconnected'),
    ('early_bootstrap','previous_price_status','Disconnected'),
])
def test_exact_event_enums_and_prebaseline_failure_are_retained(compiled_harness,tmp_path,attack,field,value):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    event=rows[2];p=event['payload']
    assert p[field]==value and p['event_sequence']==0
    assert p['continuity_before']=='PRE_BASELINE'
    assert p['continuity_after'] in ('WAIT_ALIGNMENT','STOPPED')
    assert not p['baseline_established'] and not p['bar_evidence_emitted']
    assert p['source_status']==p['source_status_after']=='Connected'
    assert event['callback']['qpc_after']<=event['emission']['qpc_before']
    assert p['reason'] in ('CONTINUE','WAIT_STARTUP_ALIGNMENT') or p['reason']==rows[-1]['payload']['reason']


@pytest.mark.parametrize('attack',['no_baseline','healthy_before_realtime','aligned_no_poll','queued_realtime_event'])
def test_no_realtime_baseline_never_emits_bar_evidence(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    assert not any(r['kind'] in ('FORMING','CLOSED') for r in rows)
    assert rows[-1]['payload']==dict(reason='WINDOW_END',closed_count=0)
    assert timing.adjudicate(raw,seal,plan)['status']=='INCONCLUSIVE'
    if attack=='healthy_before_realtime':
        assert rows[1]['payload']['continuity_after']=='WAIT_ALIGNMENT'


def test_loss_after_baseline_is_terminal_even_if_reconnected(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'reconnect')
    events=[r['payload'] for r in rows if r['kind']=='CONNECTION_EVENT']
    assert [p['event_sequence'] for p in events]==[0,1]
    assert events[0]['continuity_after']=='WAIT_ALIGNMENT'
    assert events[1]['continuity_before']=='BASELINE_PROVEN'
    assert events[1]['continuity_after']=='STOPPED'
    assert events[1]['baseline_established'] and events[1]['bar_evidence_emitted']
    assert len([r for r in rows if r['kind']=='FORMING'])==1
    assert timing.adjudicate(raw,seal,plan)['reason']=='NATIVE_STOP_STOP_CONNECTION_LOSS_EVENT'


def test_healthy_event_cannot_override_bad_current_source(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'source_snapshot_bad')
    assert rows[2]['payload']['event_status']=='Connected'
    assert rows[2]['payload']['source_price_status']=='Connecting'
    assert rows[-1]['payload']['reason']=='STOP_CURRENT_CONNECTION_NOT_READY'
    assert timing.adjudicate(raw,seal,plan)['status']=='FAIL'


@pytest.mark.parametrize('attack',['enum','reason','before','after','sequence','private','missing','revision'])
def test_reader_independently_rejects_connection_contract_tampering(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path)
    p=rows[2]['payload']
    if attack=='enum': p['event_status']='Connecting'
    if attack=='reason': p['reason']='CONNECTION_STATUS_NOT_CONNECTED'
    if attack=='before': p['baseline_established']=True
    if attack=='after': p['continuity_after']='PRE_BASELINE'
    if attack=='sequence': p['event_sequence']=1
    if attack=='private': p['connection_name']='forbidden'
    if attack=='revision': rows[0]['payload']['continuity_contract']='OLD'
    if attack=='missing':
        del rows[2]
        for i,row in enumerate(rows): row['sequence']=i
    raw,seal=repack(rows,seal)
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='FAIL' and not result['runtime_admission']
    if attack=='missing': assert result['reason']=='BASELINE_WITHOUT_ALIGNMENT'


@pytest.mark.parametrize('attack,reason',[
    ('source_connecting','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('source_snapshot_bad','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('source_disconnected','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('provider','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('poll_source_bad','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('poll_calendar_bad','SOURCE_OR_CALENDAR_CHANGED'),
    ('unstable','STOP_CURRENT_CONNECTION_NOT_READY'),
    ('unstable_outer','STOP_UNSTABLE_CONNECTION_STATE'),
    ('startup_timeout_poll','STOP_STARTUP_TIMEOUT'),
    ('post_price','STOP_CONNECTION_LOSS_EVENT'),
    ('post_previous','STOP_RECONNECT_OR_UNPROVEN_CONTINUITY'),
    ('post_aligned_duplicate','STOP_RECONNECT_OR_UNPROVEN_CONTINUITY'),
    ('post_ambiguous','STOP_RECONNECT_OR_UNPROVEN_CONTINUITY'),
    ('post_connecting','STOP_RECONNECT_OR_UNPROVEN_CONTINUITY'),
])
def test_r4_failed_alignment_or_continuity_is_terminal(compiled_harness,tmp_path,attack,reason):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,attack)
    assert rows[-1]['payload']['reason']==reason
    bars=[r for r in rows if r['kind'] in ('FORMING','CLOSED')]
    assert len(bars)==(1 if attack.startswith('post_') else 0)
    assert timing.adjudicate(raw,seal,plan)['reason']=='NATIVE_STOP_'+reason
    assert timing.parse(seal)['timers_detached'] is True


def test_r4_event_then_independent_poll_then_first_bar(compiled_harness,tmp_path):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path,'r4_startup')
    assert [r['kind'] for r in rows[:6]]==['HELLO','REALTIME','CONNECTION_EVENT','CONNECTION_EVENT','BASELINE','FORMING']
    assert rows[2]['payload']['reason']=='WAIT_STARTUP_ALIGNMENT'
    assert rows[3]['payload']['reason']=='CONTINUE'
    assert rows[3]['payload']['continuity_after']=='WAIT_ALIGNMENT'
    assert rows[4]['payload']['aligned_event_sequence']==1
    assert rows[4]['callback']['qpc_before']>=rows[3]['emission']['qpc_after']
    assert rows[5]['payload']['bar_index']==100 # All pre-poll calls discarded, never anchored.
    assert timing.adjudicate(raw,seal,plan)['status']=='PASS'


@pytest.mark.parametrize('attack',['missing_poll','bad_source','bad_calendar','bad_event','early_poll','late_poll','old_schema','false_bool','duplicate_poll'])
def test_r4_reader_requires_separate_positive_poll_proof(compiled_harness,tmp_path,attack):
    raw,seal,plan,rows=run_case(compiled_harness,tmp_path)
    r=rows[3];p=r['payload']
    if attack=='missing_poll': del rows[3]
    if attack=='bad_source': p['source_price_status_after']='Connecting'
    if attack=='bad_calendar': p['calendar_sha256']='0'*64
    if attack=='bad_event': p['aligned_event_sequence']=9
    if attack=='early_poll': r['callback']=deepcopy(rows[2]['callback'])
    if attack=='late_poll':
        delta=31*r['qpc_frequency']
        for row in rows[3:]:
            for k in ('callback','emission'):
                row[k]=deepcopy(row[k]);row[k]['qpc_before']+=delta;row[k]['qpc_after']+=delta
            if 'callback' in row['payload']: row['payload']['callback']=row['callback']
        plan['reader_end']['qpc_after']+=delta
    if attack=='old_schema':
        for row in rows: row['schema']='arms.nt.native-timing.v2'
    if attack=='false_bool': p['samples_agree']=1
    if attack=='duplicate_poll': rows.insert(4,deepcopy(rows[3]))
    for i,row in enumerate(rows): row['sequence']=i
    seal_obj=timing.parse(seal);seal_obj['records']=len(rows)
    raw,seal=repack(rows,json.dumps(seal_obj).encode())
    result=timing.adjudicate(raw,seal,plan)
    assert result['status']=='FAIL' and result['runtime_admission'] is False


def test_installed_sdk_compilation_and_no_account_order_api_reachability(tmp_path):
    shim=tmp_path/'IndicatorShim.cs'
    # Installed bin/Custom/Backup/NinjaTrader.Vendor.cs uses this actual GUI base.
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    dll=tmp_path/'Timing.dll'
    refs=['System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Xaml.dll',
          str(FRAMEWORK/'WPF/WindowsBase.dll'),str(FRAMEWORK/'WPF/PresentationCore.dll'),str(FRAMEWORK/'WPF/PresentationFramework.dll'),
          str(SDK/'NinjaTrader.Core.dll'),str(SDK/'NinjaTrader.Gui.dll')]
    result=subprocess.run([str(FRAMEWORK/'csc.exe'),'/nologo','/target:library','/out:'+str(dll),
                           *['/r:'+r for r in refs],str(shim),str(SOURCE.resolve())],capture_output=True,text=True)
    assert result.returncode==0,result.stdout
    # Reuse the previously reviewed IL instruction decoder as DATA, not executable test imports.
    tree=ast.parse(Path('backend/tests/test_sim101_witness_sprint14r.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='test_installed_sdk_compilation_and_cbi_call_allowlist')
    script=next(n.args[0].value for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                and n.func.attr=='write_text' and isinstance(n.args[0],ast.Constant) and 'ReflectionOnlyAssemblyResolve' in str(n.args[0].value))
    inspector=tmp_path/'Inspect.ps1';inspector.write_text(script)
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(inspector),str(dll)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    calls=set(json.loads(result.stdout))
    allowed={
        'Connection':{'Connections','InstrumentTypes','Options','PlaybackConnection','PriceStatus','Status'},
        'ConnectionStatusEventArgs':{'Connection','PreviousPriceStatus','PreviousStatus','PriceStatus','Status'},
        'ConnectOptions':{'Provider'},'Instrument':{'FullName','MasterInstrument'},
        'MasterInstrument':{'Name','PointValue','TickSize'}}
    assert calls=={f'NinjaTrader.Cbi.{t}::get_{m}' for t,methods in allowed.items() for m in methods}
    source=SOURCE.read_text()
    for forbidden in ('Account','Order','Submit','Cancel','Flatten','Position','Reflection','DllImport','Activator','dynamic'):
        assert not re.search(r'\b'+forbidden+r'\b',source.replace('Order =','')),forbidden


def test_no_runtime_consumer_imports_or_authority_in_watcher():
    tree=ast.parse(Path('tools/native_timing_witness_v1.py').read_text())
    imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert [v for v in imports if v.startswith('backend.')]==['backend.market_data.loaded_calendar_binding_v1']
    model=ast.parse(Path('backend/market_data/loaded_calendar_binding_v1.py').read_text())
    assert not any(isinstance(n,ast.ImportFrom) and (n.module or '').startswith('backend.') for n in ast.walk(model))


@pytest.mark.parametrize('scenario',['complete','activation_timeout','late_activation','missing_seal','multiple_sessions','atomic_seal','late_seal'])
def test_watcher_waits_first_and_finishes_bounded_without_authority(compiled_harness,tmp_path,monkeypatch,scenario):
    fixture=tmp_path/'synthetic';fixture.mkdir()
    raw,seal,plan,rows=run_case(compiled_harness,fixture)
    folder=tmp_path/plan['run_id'];folder.mkdir();inbox=folder/'inbox';inbox.mkdir()
    plan.update(schema='arms.native-timing.plan.v1',activation_seconds=600,capture_seconds=330,
                witness_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())
    timing.write_json(folder/'plan.json',plan)
    clock=[0.0];calls=[]
    monkeypatch.setattr(timing.time,'monotonic',lambda:clock[0])
    snapshots=iter([plan['reader_start'],plan['reader_start'],plan['reader_end']])
    monkeypatch.setattr(timing,'qpc_pair',lambda:next(snapshots))
    def sleep(seconds):
        status=timing.parse((folder/'status.json').read_bytes());calls.append(status)
        if len(calls)==1:
            assert status['watcher_status']=='ACTIVE_AND_WAITING'
            assert status['waiting_for_fresh_native_timing_session'] is True
            if scenario!='activation_timeout':
                p=inbox/(rows[0]['session']+'.timing.jsonl');p.write_bytes(raw)
                if scenario in ('complete','late_activation'): p.with_name(p.name+'.done.json').write_bytes(seal)
                if scenario in ('atomic_seal','late_seal'): p.with_name(p.name+'.done.tmp').write_bytes(seal[:10])
                if scenario=='multiple_sessions':(inbox/(str(uuid.uuid4())+'.timing.jsonl')).write_bytes(raw)
        if len(calls)==2 and scenario in ('atomic_seal','late_seal'):
            assert status['watcher_status']=='CAPTURING_DIAGNOSTIC'
            p=next(inbox.glob('*.timing.jsonl'))
            temp=p.with_name(p.name+'.done.tmp');temp.write_bytes(seal)
            temp.rename(p.with_name(p.name+'.done.json'))
        clock[0]+=601 if scenario in ('activation_timeout','late_activation') else 1 if len(calls)==1 or scenario=='atomic_seal' else 346
    monkeypatch.setattr(timing.time,'sleep',sleep)
    timing.watch(folder)
    result=timing.parse((folder/'result.json').read_bytes())
    assert result['status']==('PASS' if scenario in ('complete','atomic_seal') else 'FAIL')
    assert result['runtime_admission'] is False
    assert timing.parse((folder/'status.json').read_bytes())['watcher_status']=='STOPPED'
    assert timing.parse((folder/'claim.json').read_bytes())['run_id']==plan['run_id']
    if scenario in ('activation_timeout','late_activation'):
        assert result['reason']==('ACTIVATION_TIMEOUT' if scenario=='activation_timeout' else 'LATE_ACTIVATION')
        assert not (folder/'receipt.json').exists()
        saved=(folder/'result.json').read_bytes()
        if scenario=='activation_timeout':
            # A native producer can still write after the reader exited. Its
            # sealed output must not become a retroactive watcher acceptance.
            p=inbox/(rows[0]['session']+'.timing.jsonl');p.write_bytes(raw)
            p.with_name(p.name+'.done.json').write_bytes(seal)
        assert (folder/'result.json').read_bytes()==saved
        assert timing.parse((folder/'status.json').read_bytes())['waiting_for_fresh_native_timing_session'] is False
    with pytest.raises(FileExistsError): timing.watch(folder)


def test_watcher_refuses_old_evidence_before_reporting_waiting(tmp_path):
    run=str(uuid.uuid4());folder=tmp_path/run;folder.mkdir();(folder/'inbox').mkdir()
    (folder/'inbox'/'old.timing.jsonl').write_text('not fresh')
    timing.write_json(folder/'plan.json',dict(schema='arms.native-timing.plan.v1',run_id=run,
        activation_seconds=600,capture_seconds=330,witness_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest()))
    with pytest.raises(ValueError,match='OLD_EVIDENCE'):timing.watch(folder)
    assert not (folder/'status.json').exists()


@contextmanager
def deny_delete(path):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,
                                ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    kernel.CreateFileW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateFileW(str(path.resolve()),0x80000000,3,None,3,0x80,None)
    assert handle!=ctypes.c_void_p(-1).value
    try: yield
    finally: kernel.CloseHandle(handle)


def test_windows_non_delete_shared_reader_reproduces_failed_replace(tmp_path):
    destination=tmp_path/'status.json';source=tmp_path/'status.json.tmp'
    destination.write_text('{}');source.write_text('{"new":true}')
    with deny_delete(destination):
        with pytest.raises(PermissionError) as failure: source.replace(destination)
        assert failure.value.winerror==5
    source.replace(destination)
    assert timing.read_status_json(destination)=={'new':True}


def test_status_atomic_io_stress_2000_writes_three_concurrent_readers(tmp_path):
    path=tmp_path/'status.json';timing.write_json(path,dict(sequence=0,padding='x'*512))
    stop=threading.Event();errors=[];reads=[0,0,0]
    def reader(i):
        last=-1
        try:
            while not stop.is_set():
                value=timing.read_status_json(path)
                assert value['sequence']>=last and value['padding']=='x'*512
                last=value['sequence'];reads[i]+=1
        except BaseException as error: errors.append(error)
    threads=[threading.Thread(target=reader,args=(i,)) for i in range(3)]
    for thread in threads: thread.start()
    try:
        for i in range(1,2001): timing.write_json(path,dict(sequence=i,padding='x'*512))
    finally:
        stop.set()
        for thread in threads: thread.join(timeout=5)
    assert not errors and all(n>0 for n in reads) and all(not t.is_alive() for t in threads)
    assert timing.read_status_json(path)['sequence']==2000
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('which',['destination','temporary'])
def test_status_transient_locks_retry_and_cleanup(tmp_path,which,monkeypatch):
    path=tmp_path/'status.json';timing.write_json(path,{'old':True})
    original=timing.atomic_publish;attempts=[];holder=[]
    def replace(source,destination):
        if not attempts:
            held=deny_delete(path if which=='destination' else source)
            held.__enter__();holder.append(held)
            threading.Timer(.1,lambda:held.__exit__(None,None,None)).start()
        attempts.append(source.name)
        return original(source,destination)
    monkeypatch.setattr(timing,'atomic_publish',replace)
    timing.write_json(path,{'new':True})
    assert len(attempts)>1 and len(set(attempts))==1
    assert timing.read_status_json(path)=={'new':True}
    assert not list(tmp_path.glob('*.tmp'))


def test_locked_destination_has_bounded_failure_and_durable_terminal(tmp_path):
    folder=tmp_path/str(uuid.uuid4());folder.mkdir()
    status=timing.begin_status(folder,'TEST_ONLY')
    status.update(watcher_status='ACTIVE_AND_WAITING',waiting_for_fresh_native_timing_session=True)
    timing.publish_status(folder,status)
    with deny_delete(folder/'status.json'):
        begin=time.monotonic()
        with pytest.raises(PermissionError): timing.publish_status(folder,status)
        assert time.monotonic()-begin<2
        timing.finish_status(folder,status,{'status':'FAIL','reason':'LOCK_TEST'})
        assert timing.read_status_json(folder/'status.json')['watcher_status']=='ACTIVE_AND_WAITING'
        assert timing.read_status_json(folder/'terminal.json')['terminal_state']=='FAILED'
        assert timing.verified_status(folder)['watcher_status']=='NOT_ACTIVE'
    assert not list(folder.glob('*.tmp'))


def test_unique_temporaries_do_not_touch_locked_legacy_temp(tmp_path):
    legacy=tmp_path/'status.json.tmp';legacy.write_text('preserve unrelated temp')
    with deny_delete(legacy):
        for i in range(25): timing.write_json(tmp_path/'status.json',{'sequence':i})
    assert legacy.read_text()=='preserve unrelated temp'
    assert list(tmp_path.glob('*.tmp'))==[legacy]


@pytest.mark.parametrize('attack',['pid_reuse','stale','no_advance','wrong_run','dead','missing_identity'])
def test_active_status_requires_live_matching_identity_and_fresh_advancing_heartbeat(tmp_path,monkeypatch,attack):
    folder=tmp_path/str(uuid.uuid4());folder.mkdir()
    status=timing.begin_status(folder,'TEST_ONLY')
    status.update(watcher_status='ACTIVE_AND_WAITING',waiting_for_fresh_native_timing_session=True)
    timing.publish_status(folder,status)
    if attack=='pid_reuse': status['process_start']+=1
    if attack=='stale': status['heartbeat_monotonic']-=3
    if attack=='wrong_run': status['run_id']=str(uuid.uuid4())
    if attack=='dead': monkeypatch.setattr(timing,'live_process_start',lambda pid:None)
    if attack=='missing_identity':
        status.update(pid=-1,process_start=None)
        claim=timing.read_status_json(folder/'claim.json');claim.update(pid=-1,process_start=None)
        timing.write_json(folder/'claim.json',claim)
    timing.write_json(folder/'status.json',status)
    result=timing.verified_status(folder)
    assert result['watcher_status']=='NOT_ACTIVE' and not result['waiting_for_fresh_native_timing_session']


def test_duplicate_claim_and_fresh_run_after_failure(tmp_path):
    first=tmp_path/str(uuid.uuid4());first.mkdir()
    state=timing.begin_status(first,'TEST_ONLY')
    timing.finish_status(first,state,{'status':'FAIL'})
    with pytest.raises(FileExistsError): timing.begin_status(first,'TEST_ONLY')
    second=tmp_path/str(uuid.uuid4());second.mkdir()
    second_state=timing.begin_status(second,'TEST_ONLY')
    assert first!=second and state['watcher_id']!=second_state['watcher_id']
    timing.finish_status(second,second_state,{'status':'PASS'})


@pytest.mark.parametrize('crash',[False,True])
def test_non_native_process_exit_and_crash_never_leave_active_interpretation(tmp_path,crash):
    folder=tmp_path/str(uuid.uuid4())
    process=subprocess.Popen([sys.executable,'-B','-m','tools.native_timing_witness_v1','dry-run','--run-directory',str(folder)],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        limit=time.monotonic()+8
        while time.monotonic()<limit:
            observed=timing.verified_status(folder)
            if observed['watcher_status']=='ACTIVE_AND_WAITING': break
            time.sleep(.02)
        assert observed['watcher_status']=='ACTIVE_AND_WAITING'
        assert observed['pid']==process.pid and observed['mode']=='NON_NATIVE_DRY_RUN'
        if crash: process.kill()
        out,err=process.communicate(timeout=8)
        assert not err
        if crash:
            assert timing.read_status_json(folder/'status.json')['watcher_status']=='ACTIVE_AND_WAITING'
            assert not (folder/'terminal.json').exists()
        else:
            assert process.returncode==0
            assert timing.read_status_json(folder/'terminal.json')['terminal_state']=='COMPLETED'
        assert timing.verified_status(folder)['watcher_status']=='NOT_ACTIVE'
        assert timing.live_process_start(process.pid) is None
    finally:
        if process.poll() is None: process.kill();process.wait(timeout=5)
