"""Whole exporter under deterministic native doubles, without a provider process."""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_production_certified_outcome_v17 import api_settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def exporter_harness(tmp_path_factory):
    folder = tmp_path_factory.mktemp("whole_exporter")
    source = (ROOT / "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    source = source.replace("using System.Diagnostics;", "using Stopwatch = Doubles.Clock;")
    source = source.replace("System.Threading.Timer", "Doubles.Deadline")
    cs = folder / "Exporter.cs"
    cs.write_text(source)
    harness = folder / "Host.cs"
    harness.write_text(r'''
using System; using System.IO; using System.Linq; using System.Collections.Generic;
using System.Reflection; using System.Web.Script.Serialization;
using NinjaTrader.Cbi; using NinjaTrader.NinjaScript;
namespace Doubles {
 public class Clock { public static long Now; public long ElapsedMilliseconds { get { return Now; } } public void Start() {} }
 public class Deadline : IDisposable {
  public static Deadline Last; public bool Disposed; private Action<object> action;
  public Deadline(Action<object> a, object s, int due, int period) { Last=this; action=a; }
  public void Dispose() { Disposed=true; } public void Fire() { action(null); }
 }
 public class Dispatcher { Action pending; public void InvokeAsync(Action a) {pending=a;} public void Drain(){if(pending!=null)pending();pending=null;} }
 public class Chart {public Dispatcher Dispatcher=new Dispatcher();}
}
namespace System.Windows.Threading {
 public class DispatcherTimer {
  public static DispatcherTimer Last; public bool Running; public TimeSpan Interval; public event EventHandler Tick;
  public DispatcherTimer(){Last=this;} public void Start(){Running=true;} public void Stop(){Running=false;}
  public void Fire(){if(Running && Tick!=null)Tick(this,EventArgs.Empty);}
 }
}
namespace NinjaTrader.Cbi {
 public enum ConnectionStatus {Disconnected,Connecting,Connected,Disconnecting,ConnectionLost}
 public enum Provider {Provider31,Other} public enum InstrumentType {Future}
 public class Options {public Provider Provider=Provider.Provider31; public string Name {get{throw new Exception("PRIVATE_SENTINEL");}}}
 public class Connection {
  public static Connection PlaybackConnection; public static List<Connection> Connections=new List<Connection>();
  public Options Options=new Options(); public InstrumentType[] InstrumentTypes={InstrumentType.Future};
  public ConnectionStatus price=ConnectionStatus.Connected,status=ConnectionStatus.Connected;
  public bool Flip; int reads;
  public ConnectionStatus PriceStatus {get{return Flip && ++reads%2==0 ? ConnectionStatus.Connecting : price;}}
  public ConnectionStatus Status {get{return status;}}
 }
 public class ConnectionStatusEventArgs {
  public Connection Connection; public ConnectionStatus PriceStatus,Status,PreviousPriceStatus,PreviousStatus;
  public string NativeError {get{throw new Exception("PRIVATE_SENTINEL");}}
 }
}
namespace NinjaTrader.Data {public enum BarsPeriodType {Minute} public class Period {public BarsPeriodType BarsPeriodType;public int Value=1;}}
namespace NinjaTrader.Core {public static class Globals {public static Settings GeneralOptions=new Settings();} public class Settings {public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.Utc;}}
namespace NinjaTrader.NinjaScript {
 public enum State {SetDefaults,Realtime,Terminated,Historical} public enum Calculate {OnEachTick}
 public class NinjaScriptPropertyAttribute:Attribute {}
 public class Master {public string Name="NQ"; public double TickSize=.25,PointValue=20;}
 public class InstrumentInfo {public string FullName="NQ DEC26"; public DateTime Expiry=new DateTime(2026,12,1); public Master MasterInstrument=new Master();}
 public class Hours {public string Name="CME US Index Futures ETH";} public class BarInfo {public Hours TradingHours=new Hours();}
 public class Indicator {
  public string Name,Description; public Calculate Calculate; public bool IsOverlay,IsChartOnly,IsSuspendedWhileInactive;
  public State State;public InstrumentInfo Instrument=new InstrumentInfo();public BarInfo Bars=new BarInfo();
  public NinjaTrader.Data.Period BarsPeriod=new NinjaTrader.Data.Period(); public Doubles.Chart ChartControl=new Doubles.Chart();
  public int BarsInProgress,CurrentBar;public bool IsFirstTickOfBar=true;
  // Explicit synthetic fixture data, never read from a native feed.
  public double[] Open={100,100},High={101,101},Low={99,99},Close={100,100},Volume={1,1};
  public DateTime[] Time={DateTime.UtcNow,DateTime.UtcNow.AddMinutes(-1)};
  protected virtual void OnStateChange(){} protected virtual void OnBarUpdate(){} protected virtual void OnConnectionStatusUpdate(ConnectionStatusEventArgs e){}
  protected void Print(string text){if(text.Contains("PRIVATE_SENTINEL"))throw new Exception("Leak");}
 }
}
class Host:NinjaTrader.NinjaScript.Indicators.ArmsReadOnlyMarketV1 {
 public void Step(State s){State=s;OnStateChange();} public void Send(ConnectionStatusEventArgs e){OnConnectionStatusUpdate(e);}
 public void Bar(int n){CurrentBar=n;OnBarUpdate();}
}
class Harness {
 static string Read(string path){using(var f=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))using(var r=new StreamReader(f))return r.ReadToEnd();}
 static void Check(bool ok){if(!ok)throw new Exception("Exporter invariant failed");}
 public static void Main(string[] args){
  string c=args[0]; var s=new Connection(); Connection.Connections.Add(s);
  var h=new Host(); h.Step(State.SetDefaults); h.OutputDirectory=args[1]; h.ExpectedProvider="Provider31";
  h.Step(State.Realtime); h.ChartControl.Dispatcher.Drain();
  var timer=System.Windows.Threading.DispatcherTimer.Last; var deadline=Doubles.Deadline.Last;
  h.Bar(0); h.Bar(1); h.Bar(2); // No candle admission during startup.
  var path=Directory.GetFiles(args[1],"*.jsonl").Single(p=>!p.EndsWith(".connection.jsonl"));
  Check(Read(path)=="");
  var e=new ConnectionStatusEventArgs{Connection=s,PriceStatus=ConnectionStatus.Connecting,Status=ConnectionStatus.Connecting,
     PreviousPriceStatus=ConnectionStatus.Disconnected,PreviousStatus=ConnectionStatus.Disconnected};
  if(c!="no_callback_timeout")h.Send(e);
  if(c=="startup_duplicates")h.Send(e);
  Doubles.Clock.Now=100; timer.Fire(); h.Bar(3); Check(Read(path)=="");
  if(c=="timeout" || c=="deadline_without_heartbeat" || c=="no_callback_timeout"){
   Doubles.Clock.Now=30000; if(c=="timeout")timer.Fire();else deadline.Fire();
  } else {
   e.PreviousPriceStatus=e.PreviousStatus=ConnectionStatus.Connecting;e.PriceStatus=e.Status=ConnectionStatus.Connected;
   if(c=="source_mismatch")e.Connection=new Connection();
   if(c=="provider_mismatch")s.Options.Provider=Provider.Other;
   if(c=="unknown")s.price=(ConnectionStatus)999;
   if(c=="unstable")s.Flip=true;
   if(c=="price_loss")s.price=ConnectionStatus.ConnectionLost;
   if(c=="connection_loss")s.status=ConnectionStatus.Disconnected;
   if(c=="null")e=null;
   h.Send(e); if(c=="startup_duplicates")h.Send(e); Check(Read(path).IndexOf("HELLO")<0);
   Doubles.Clock.Now=c=="late_heartbeat"?30000:5000;timer.Fire();
   if(c=="bars") {h.Bar(10);h.Bar(11);h.Bar(12);}
   if(c=="duplicates") {e.PreviousPriceStatus=e.PreviousStatus=ConnectionStatus.Connected;h.Send(e);h.Send(e);timer.Fire();}
   if(c=="late_transition_duplicate" || c=="recovery_callback") {
    if(c=="recovery_callback")e.PreviousPriceStatus=e.PreviousStatus=ConnectionStatus.ConnectionLost;
    h.Send(e);timer.Fire();h.Bar(20);
   }
   if(c=="reconnect" || c=="rapid_ordering") {
    e.PreviousPriceStatus=e.PreviousStatus=ConnectionStatus.Connected;e.PriceStatus=e.Status=ConnectionStatus.Connecting;
    h.Send(e);e.PriceStatus=e.Status=ConnectionStatus.Connected;h.Send(e);timer.Fire();h.Bar(20);
   }
   if(c=="heartbeat_loss") {s.price=ConnectionStatus.Disconnected;timer.Fire();s.price=ConnectionStatus.Connected;timer.Fire();h.Bar(20);}
   if(c=="bar_loss") {s.status=ConnectionStatus.Disconnected;h.Bar(20);s.status=ConnectionStatus.Connected;h.Bar(21);}
   if(c=="source_removed") {Connection.Connections.Clear();h.Bar(20);}
   if(c=="second_source") {Connection.Connections.Add(new Connection());h.Bar(20);}
   if(c=="registry_busy") {
    var held=new System.Threading.ManualResetEventSlim(); var release=new System.Threading.ManualResetEventSlim();
    var thread=new System.Threading.Thread(()=>{lock(Connection.Connections){held.Set();release.Wait();}});
    thread.Start();Check(held.Wait(3000));
    try {h.Bar(20);} finally {release.Set();thread.Join();}
   }
   if(c=="realtime_reentry")h.Step(State.Realtime);
   if(c=="historical_reentry")h.Step(State.Historical);
   if(c=="closed_connected") {for(int i=2;i<=4;i++){Doubles.Clock.Now=i*5000;timer.Fire();}}
  }
  var before=Read(path);h.Step(State.Terminated);timer.Fire();deadline.Fire();
  Check(!timer.Running && deadline.Disposed);
  using(var f=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.None)){}
  Console.WriteLine(new JavaScriptSerializer().Serialize(new{market=before,final=Read(path)}));
 }
}''')
    fw = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    exe = folder / "Host.exe"
    result = subprocess.run([str(fw/"csc.exe"), "/nologo", "/out:"+str(exe),
        "/reference:"+str(fw/"System.Web.Extensions.dll"),
        "/reference:"+str(fw/"System.ComponentModel.DataAnnotations.dll"), str(cs), str(harness)], capture_output=True,text=True)
    assert result.returncode == 0, result.stdout
    return exe


@pytest.mark.parametrize("case,hello,closed,stop", [
    ("bars",1,1,False), ("closed_connected",1,0,False), ("duplicates",1,0,False),
    ("timeout",0,0,True), ("deadline_without_heartbeat",0,0,True), ("late_heartbeat",0,0,True),
    ("source_mismatch",0,0,True), ("provider_mismatch",0,0,True), ("unknown",0,0,True),
    ("unstable",0,0,True), ("price_loss",0,0,True), ("connection_loss",0,0,True), ("null",0,0,True),
    ("reconnect",1,0,True), ("rapid_ordering",1,0,True), ("heartbeat_loss",1,0,True),
    ("bar_loss",1,0,True), ("source_removed",1,0,True), ("second_source",1,0,True),
    ("realtime_reentry",1,0,True),
    ("late_transition_duplicate",1,0,True), ("recovery_callback",1,0,True),
    ("historical_reentry",1,0,True), ("no_callback_timeout",0,0,True), ("startup_duplicates",1,0,False),
    ("registry_busy",1,0,True),
])
def test_whole_exporter_admission(exporter_harness,tmp_path,case,hello,closed,stop):
    result = subprocess.run([str(exporter_harness),case,str(tmp_path)],capture_output=True,text=True)
    assert result.returncode == 0, "Whole exporter invariant failed"
    assert "PRIVATE_SENTINEL" not in result.stdout
    data=json.loads(result.stdout)
    rows=[json.loads(line) for line in data["market"].splitlines()]
    kinds=[row["kind"] for row in rows]
    assert kinds.count("HELLO")==hello
    assert kinds.count("CLOSED")==closed
    assert kinds.count("DISCONNECTED")==int(stop)
    assert kinds.count("FORMING")== (3 if case=="bars" else 0)
    assert [r["sequence"] for r in rows]==list(range(len(rows)))
    if stop: assert kinds[-1]=="DISCONNECTED" and data["market"]==data["final"]
    if case=="closed_connected": assert kinds==["HELLO"]+["HEARTBEAT"]*4
    if case=="startup_duplicates":
        sidecar=next(tmp_path.glob("*.connection.jsonl"))
        callbacks=[json.loads(line) for line in sidecar.read_text().splitlines()]
        assert [r["sequence"] for r in callbacks]==[0,1,2,3]
        assert [r["payload"]["decision"] for r in callbacks]==["WAIT_STARTUP_ALIGNMENT"]*2+["CONTINUE"]*2
    if "timeout" in case or case=="deadline_without_heartbeat" or case=="late_heartbeat":
        assert rows[-1]["payload"]["reason"]=="STOP_STARTUP_TIMEOUT"


@pytest.mark.parametrize("case", ["closed_connected", "timeout"])
def test_native_wire_to_canonical_reader_has_no_execution(exporter_harness, tmp_path, api_settings, case):
    from dataclasses import replace
    from datetime import datetime
    from backend.tests.test_current_paper_sprint10 import gate, config
    from backend.config.api_settings import APISettings
    from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
    from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1

    native = tmp_path / "synthetic_native"
    native.mkdir()
    result = subprocess.run([str(exporter_harness), case, str(native)], capture_output=True, text=True)
    assert result.returncode == 0
    raw = json.loads(result.stdout)["market"]
    rows = [json.loads(line) for line in raw.splitlines()]
    now = datetime.fromisoformat(rows[-1]["event_time"].replace("Z", "+00:00"))
    g, clock = gate(start=now, label="CLOSE")
    clock[0] = now
    g = type(g)(contract=replace(g.contract, provider="NINJATRADER:Provider31", contract="NQ DEC26",
        trading_hours_template="CME US Index Futures ETH"), market_hours=g.market_hours,
        maximum_age_seconds=g.maximum_age, clock=g.clock)
    service = CurrentPaperServiceV1(gate=g, config=config(), settings=APISettings(),
        state_path=tmp_path/"paper.sqlite", initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
    wire = tmp_path/"reader.jsonl"
    wire.write_text(raw)
    reader = NinjaTraderMarketReaderV1(service=service, path=wire, provider="Provider31", expiry="2026-12-01")
    try:
        if case == "timeout":
            with pytest.raises(ValueError): reader.poll()
            assert reader.fault
        else:
            snap = reader.poll()
            assert snap["provider_transport"]["connected"]
            assert not snap["paper_ready"] and not snap["external_order_authority"]
        assert g.closed_count == 0 and g.last_sequence is None
        assert service._runtime is None  # No strategy, position, PnL or executor instantiated.
    finally:
        reader.close()
