"""Native collector with deterministic doubles; produces ONLY synthetic evidence."""
from pathlib import Path
import subprocess
import json

import pytest


@pytest.fixture(scope='module')
def collector(tmp_path_factory):
    folder=tmp_path_factory.mktemp('synthetic_calendar')
    host=folder/'Host.cs'
    host.write_text(r'''
using System; using System.Collections.Generic;
namespace NinjaTrader.Core {
 public static class Globals {public static Options GeneralOptions=new Options();}
 public class Options {public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.Utc;}
}
namespace NinjaTrader.Data {
 public enum BarsPeriodType {Minute}
 public class Session {public DayOfWeek BeginDay=DayOfWeek.Sunday,EndDay=DayOfWeek.Monday,TradingDay=DayOfWeek.Monday;public int BeginTime=1700,EndTime=1600;}
 public class PartialHoliday {public Session Constraint=new Session();public bool IsEarlyEnd=true,IsLateBegin=false;public List<Session> Sessions=new List<Session>();}
 public class TradingHours {public string Name="CME US Index Futures ETH"; public int Version=1;public TimeZoneInfo TimeZoneInfo=TimeZoneInfo.Utc;
 public List<Session> Sessions=new List<Session>{new Session()};public Dictionary<DateTime,string> Holidays=new Dictionary<DateTime,string>();
 public Dictionary<DateTime,PartialHoliday> PartialHolidays=new Dictionary<DateTime,PartialHoliday>();}
 public class Bars {public TradingHours TradingHours=new TradingHours();}
 public class SessionIterator {public static int Calls;public DateTime ActualSessionBegin,ActualSessionEnd,ActualTradingDayExchange;
 public SessionIterator(Bars b){} public void GetNextSession(DateTime q,bool end){Calls++;ActualSessionBegin=q;ActualSessionEnd=q.AddHours(1);ActualTradingDayExchange=q.Date;}}
}
namespace NinjaTrader.NinjaScript {
 public enum State {SetDefaults,DataLoaded,Historical,Terminated}
 public class NinjaScriptPropertyAttribute:Attribute {}
 public class Master {public string Name="NQ";public double TickSize=.25,PointValue=20;}
 public class InstrumentInfo {public string FullName="NQ DEC26";public DateTime Expiry=new DateTime(2026,12,1);public Master MasterInstrument=new Master();}
 public class Period {public NinjaTrader.Data.BarsPeriodType BarsPeriodType=NinjaTrader.Data.BarsPeriodType.Minute;public int Value=1;}
 public class Indicator {public string Name,Description;public bool IsOverlay,IsChartOnly;public State State;
 public InstrumentInfo Instrument=new InstrumentInfo();public Period BarsPeriod=new Period();public NinjaTrader.Data.Bars Bars=new NinjaTrader.Data.Bars();
 protected virtual void OnStateChange(){} protected void Print(string value){Console.WriteLine(value);}}
}
class Host:NinjaTrader.NinjaScript.Indicators.ArmsCalendarEvidenceV1 {
 public void Step(NinjaTrader.NinjaScript.State s){State=s;OnStateChange();}
 public static void Main(string[] args){var h=new Host();h.Step(NinjaTrader.NinjaScript.State.SetDefaults);h.OutputDirectory=args[0];
 if(args[1]=="wrong_contract")h.Instrument.FullName="SYNTHETIC_OTHER";
 if(args[1]=="wrong_timezone")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.CreateCustomTimeZone("FIXTURE",TimeSpan.FromHours(1),"FIXTURE","FIXTURE");
 if(args[1]=="wrong_bars")h.BarsPeriod.Value=5;
 h.Step(NinjaTrader.NinjaScript.State.DataLoaded);h.Step(NinjaTrader.NinjaScript.State.DataLoaded);h.Step(NinjaTrader.NinjaScript.State.Terminated);
 Console.WriteLine("iterator_calls="+NinjaTrader.Data.SessionIterator.Calls);}
}
''')
    exe=folder/'Host.exe'; fw=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319')
    result=subprocess.run([str(fw/'csc.exe'),'/nologo','/out:'+str(exe),'/r:System.ComponentModel.DataAnnotations.dll',
        '/r:System.Web.Extensions.dll',str(Path('integrations/ninjatrader/ArmsCalendarEvidenceV1.cs').resolve()),str(host)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout
    return exe


@pytest.mark.parametrize('case',['valid','wrong_contract','wrong_timezone','wrong_bars'])
def test_one_shot_private_capture_is_bounded_and_closed(collector,tmp_path,case):
    result=subprocess.run([str(collector),str(tmp_path),case],capture_output=True,text=True)
    assert result.returncode==0
    files=list(tmp_path.glob('*.calendar.jsonl'))
    if case!='valid':
        assert files==[] and 'iterator_calls=0' in result.stdout
        return
    assert len(files)==1 and 'iterator_calls=13' in result.stdout
    raw=files[0].read_bytes(); assert raw.endswith(b'\n')
    evidence=json.loads(raw)
    assert evidence['completion']=='COMPLETE_METADATA_ONLY' and evidence['native_certification']=='PENDING_REVIEW'
    assert evidence['observation_only'] is True and len(evidence['samples'])==13
    assert not any(k in evidence for k in ('account','account_id','password','connection_name','open','high','low','close','volume'))
    # Disposed using-block output is immediately available after capture.
    with files[0].open('rb') as f: assert f.read()==raw
