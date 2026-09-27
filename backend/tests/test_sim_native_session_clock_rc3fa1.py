"""Execute extracted production session methods against a declared synthetic SDK.

Only the legacy DateTime.Now seam is frozen in the temporary compilation so the
pre-fix mismatch is reproducible at the same absolute instant as Globals.Now.
The session oracle uses explicit ETH open/end instants, never production files.
"""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"

HARNESS = r'''
using System;
using System.Globalization;
using NinjaTrader.Data;
using NinjaTrader.Cbi;
static class TestClock {
 public static DateTime Instant;
 public static DateTime OsNow {get {return TimeZoneInfo.ConvertTimeFromUtc(Instant,TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"));}}
}
namespace NinjaTrader.Core {
 public class Options {public TimeZoneInfo TimeZoneInfo;}
 public static class Globals {
  public static Options GeneralOptions=new Options();
  public static DateTime Now {get {return TimeZoneInfo.ConvertTimeFromUtc(TestClock.Instant,GeneralOptions.TimeZoneInfo);}}
 }
}
namespace NinjaTrader.Cbi {
 public enum ConnectionStatus { Connected, Disconnected }
 public class Account {public ConnectionStatus ConnectionStatus=ConnectionStatus.Connected;}
 public class Master {public TradingHours TradingHours;}
 public class Instrument {public Master MasterInstrument=new Master();}
}
namespace NinjaTrader.Data {
 public class TradingHours {
  public string Name="CME US Index Futures ETH";
  public TimeZoneInfo TimeZone=TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
  public DateTime Begin,End; public bool Broken;
 }
 public class SessionIterator {
  TradingHours hours;
  public SessionIterator(TradingHours value) {hours=value;}
  public DateTime ActualSessionBegin {get {return TimeZoneInfo.ConvertTimeFromUtc(hours.Begin,NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);}}
  public DateTime ActualSessionEnd {get {return TimeZoneInfo.ConvertTimeFromUtc(hours.End,NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);}}
  public bool IsInSession(DateTime query,bool includeEnd,bool intraday) {
   if(hours.Broken)throw new InvalidOperationException("unknown synthetic session");
   if(includeEnd || !intraday)throw new Exception("session flags weakened");
   Console.WriteLine("IS_QUERY="+query.ToString("o"));
   return query>=ActualSessionBegin && query<ActualSessionEnd;
  }
  public bool GetNextSession(DateTime query,bool includeEnd) {
   if(hours.Broken)throw new InvalidOperationException("unknown synthetic session");
   if(includeEnd)throw new Exception("session flags weakened");
   Console.WriteLine("NEXT_QUERY="+query.ToString("o"));
   return query<ActualSessionEnd;
  }
 }
}
public class Bridge {
 Account selectedAccount=new Account();
 void ValidateSelectedAccount() {}
 void Print(string value) {Console.WriteLine(value);}
 // METHODS
 static DateTime Utc(string value) {return DateTime.Parse(value,CultureInfo.InvariantCulture,DateTimeStyles.AdjustToUniversal|DateTimeStyles.AssumeUniversal);}
 public static void Main(string[] args) {
  TestClock.Instant=Utc(args[1]);
  NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.FindSystemTimeZoneById(args[0]);
  var instrument=new Instrument();
  instrument.MasterInstrument.TradingHours=new TradingHours {Begin=Utc(args[2]),End=Utc(args[3]),Broken=args[4]=="unknown"};
  var bridge=new Bridge();
  if(args[4]=="missing")instrument.MasterInstrument.TradingHours=null;
  if(args[4]=="badzone")NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=null;
  if(args[4]=="disconnected")bridge.selectedAccount.ConnectionStatus=ConnectionStatus.Disconnected;
  Console.WriteLine("OS_NOW="+TestClock.OsNow.ToString("o"));
  Console.WriteLine("RESULT="+bridge.EvaluatePhysicalTestReadiness(instrument));
  Console.WriteLine(bridge.DescribePhysicalTestSessionWindow(instrument));
  if(args[4]=="valid")Console.WriteLine("RESOLVED="+bridge.ResolveNextPhysicalTestSessionWindow(
      instrument.MasterInstrument.TradingHours,NinjaTrader.Core.Globals.Now));
 }
}
'''


@pytest.fixture(scope="module")
def session_binary(tmp_path_factory):
    directory = tmp_path_factory.mktemp("session-clock-sdk")
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("        private string ResolveNextPhysicalTestSessionWindow(")
    # Include the new clock helper when present; the old body still compiles red.
    helper = text.find("        private DateTime PhysicalTestApplicationNow(")
    if helper >= 0:
        start = helper
    methods = text[start:text.index("        private void WriteRuntimeReadinessSnapshot()", start)]
    start = text.index("        private string EvaluatePhysicalTestReadiness(")
    methods += text[start:text.index("        private void AttemptEmergencyFlatten()", start)]
    methods = methods.replace("DateTime.Now", "TestClock.OsNow")
    code = directory / "session.cs"
    code.write_text(HARNESS.replace("// METHODS", methods), encoding="utf-8")
    target = directory / "session.exe"
    compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
    result = subprocess.run([str(compiler), "/nologo", "/langversion:5", "/out:"+str(target), str(code)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    return target


def run(binary, *, zone="UTC", now="2026-09-27T22:30:00Z", begin="2026-09-27T22:00:00Z",
        end="2026-09-28T21:00:00Z", mode="valid"):
    result = subprocess.run([str(binary), zone, now, begin, end, mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout+result.stderr
    return result.stdout


def test_os_eastern_application_utc_same_instant_inside_eth_is_ready(session_binary):
    output = run(session_binary)
    assert "OS_NOW=2026-09-27T18:30:00" in output
    assert "RESULT=PHYSICAL_TEST_READY" in output
    assert "IS_QUERY=2026-09-27T22:30:00" in output
    assert "NEXT_QUERY=2026-09-27T22:30:00" in output
    assert "RESOLVED= next_session_begin=2026-09-27T22:00:00" in output
    assert "application_timezone=UTC" in output and "trading_hours_timezone=" in output


@pytest.mark.parametrize("zone", ["UTC", "Eastern Standard Time", "Central Standard Time", "Tokyo Standard Time"])
@pytest.mark.parametrize("now,expected", [
    ("2026-09-27T21:59:59Z", "MARKET_SESSION_CLOSED"),
    ("2026-09-27T22:00:00Z", "PHYSICAL_TEST_READY"),
    ("2026-09-28T20:59:59Z", "PHYSICAL_TEST_READY"),
    ("2026-09-28T21:00:00Z", "MARKET_SESSION_CLOSED"),
    ("2026-09-28T21:00:01Z", "MARKET_SESSION_CLOSED")])
def test_application_zones_and_session_boundaries(session_binary, zone, now, expected):
    assert "RESULT="+expected in run(session_binary, zone=zone, now=now)


@pytest.mark.parametrize("zone", ["UTC", "Eastern Standard Time"])
@pytest.mark.parametrize("now,begin,end", [
    ("2026-03-08T22:30:00Z", "2026-03-08T22:00:00Z", "2026-03-09T21:00:00Z"),
    ("2026-11-01T23:30:00Z", "2026-11-01T23:00:00Z", "2026-11-02T22:00:00Z")])
def test_dst_aware_session_instants(session_binary, zone, now, begin, end):
    assert "RESULT=PHYSICAL_TEST_READY" in run(session_binary, zone=zone, now=now, begin=begin, end=end)


@pytest.mark.parametrize("mode,expected", [("unknown", "SESSION_STATE_UNKNOWN"), ("missing", "SESSION_STATE_UNKNOWN"),
    ("badzone", "SESSION_STATE_UNKNOWN"), ("disconnected", "CONNECTION_NOT_READY")])
def test_unknown_or_disconnected_fails_closed(session_binary, mode, expected):
    assert "RESULT="+expected in run(session_binary, mode=mode)


def test_no_os_clock_in_session_paths_and_explicit_diagnostics():
    text = SOURCE.read_text(encoding="utf-8")
    assert "DateTime.Now" not in text
    assert "NinjaTrader.Core.Globals.Now" in text
    assert '" application_timezone="' in text
    assert '" trading_hours_timezone="' in text
    assert '" application_now="' in text
    assert '" now_local="' not in text
    assert "NATIVE_SUBMIT_ENABLED = false" in text
    assert "AUTO_RETRY_ALLOWED = false" in text
