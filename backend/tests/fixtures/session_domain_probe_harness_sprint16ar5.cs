// SYNTHETIC OFFLINE doubles: actual probe code runs; no NinjaTrader assembly is loaded.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;
[assembly: AssemblyVersion("8.1.8.2")]
namespace NinjaTrader.Core {
    public static class Globals { public static Options GeneralOptions = new Options(); }
    public class Options { public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc; }
}
namespace NinjaTrader.Cbi {
    public enum ErrorCode { NoError, Failed }
    public enum MergePolicy { DoNotMerge, MergeBackAdjusted }
    public enum LookupPolicies { Repository, Provider }
    public class Connection { public static Connection PlaybackConnection; }
    public class MasterInstrument { public string Name = "NQ"; public double TickSize = .25, PointValue = 20; }
    public class Instrument {
        public string FullName = "NQ DEC26";
        public MasterInstrument MasterInstrument = new MasterInstrument();
        public DateTime Expiry = new DateTime(2026,12,1);
        public static Instrument GetInstrument(string value) {
            if (value != "NQ DEC26") throw new Exception(Harness.Secret);
            return new Instrument();
        }
    }
}
namespace NinjaTrader.Data {
    using NinjaTrader.Cbi;
    public enum BarsPeriodType { Minute }
    public enum MarketDataType { Last }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType; public int Value; public MarketDataType MarketDataType; }
    public class Session {
        public DayOfWeek BeginDay, EndDay, TradingDay; public int BeginTime = 1700, EndTime = 1600;
    }
    public class PartialHoliday {
        public bool IsEarlyEnd, IsLateBegin; public Session Constraint;
        public List<Session> Sessions = new List<Session>();
    }
    public class TradingHours {
        public List<Session> Sessions = new List<Session>();
        public Dictionary<DateTime,string> Holidays = new Dictionary<DateTime,string>();
        public Dictionary<DateTime,PartialHoliday> PartialHolidays = new Dictionary<DateTime,PartialHoliday>();
        public TradingHours() { for(int i=0;i<5;i++) Sessions.Add(new Session { BeginDay=(DayOfWeek)i,EndDay=(DayOfWeek)(i+1),TradingDay=(DayOfWeek)(i+1) }); }

        public string Name = "CME US Index Futures ETH"; public int Version = 1;
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public static TradingHours Get(string name) { if (name != "CME US Index Futures ETH") throw new Exception(); return new TradingHours(); }
    }
    public class Bars {
        public Instrument Instrument; public BarsPeriod BarsPeriod; public TradingHours TradingHours; public int Count = 5;
        public DateTime GetTime(int i) {
            var t = new DateTime(2026,9,16,12,0,0,DateTimeKind.Utc).AddMinutes(i);
            if (Harness.Mode == "before_only" || (Harness.Mode.StartsWith("matrix_") && (int.Parse(Harness.Mode.Substring(7)) & 32) != 0)) t = t.AddDays(-2);
            if (Harness.Mode == "with_next") t = t.AddDays(-1);
            if (Harness.Mode == "noncontiguous") t = new DateTime(2026,9,14,20,58,0,DateTimeKind.Utc).AddDays(i*2);
            if (Harness.Mode == "gap_coverage") t = new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc).AddMinutes(i*15);
            if (Harness.Mode == "boundary_coverage") t = new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc).AddDays(i);
            if (Harness.Mode == "bad_order" && i == 2) t = t.AddMinutes(-3);
            if (Harness.Mode == "bad_time_kind") t = DateTime.SpecifyKind(t,DateTimeKind.Unspecified);
            if (Harness.Mode == "too_many_dates") t = t.AddDays(i);
            return t;
        }
        public double GetOpen(int i) { return Harness.Mode == "snapshot_mutated" && SessionIterator.TotalCalls >= 1 ? 20002 : 20000; }
        public double GetHigh(int i) { return 20003; }
        public double GetLow(int i) { return 19999; }
        public double GetClose(int i) { return 20000.25; }
        public long GetVolume(int i) { return 10; }
    }
    public class SessionIterator {
        public static int Creates, TotalCalls, BeginReads, EndReads;
        public static List<object> Observations = new List<object>();
        private readonly int id; private readonly Bars bars; private int count;
        private DateTime begin, end; private bool returned;
        private bool isTemplate;
        public SessionIterator(Bars value) { id = ++Creates; bars = value; if(Harness.Mode=="constructor_throw") throw new InvalidOperationException(Harness.Secret); }
        public SessionIterator(TradingHours value) { id=++Creates; isTemplate=true;
            if (!Object.ReferenceEquals(value,BarsRequest.Last.Bars.TradingHours)) throw new Exception("different template"); }
        public DateTime ActualSessionBegin { get { BeginReads++; if(!returned || Harness.Mode=="begin_throw") throw new InvalidOperationException(Harness.Secret); return begin; } }
        public DateTime ActualSessionEnd { get { EndReads++; if(!returned || Harness.Mode=="end_throw") throw new InvalidOperationException(Harness.Secret); return end; } }
        public bool GetNextSession(DateTime query, bool include) {
            count++; TotalCalls++;
            if (Harness.Mode == "reentrant" && TotalCalls == 1) BarsRequest.Last.Fire();
            Observations.Add(new { iterator=id, call=count, query=query.ToString("o"), kind=query.Kind.ToString(), include=include,
                same_snapshot=isTemplate || Object.ReferenceEquals(bars,BarsRequest.Last.Bars), constructor=isTemplate?"TradingHours":"Bars" });
            if(TotalCalls>8 || Creates>7) throw new Exception("budget");
            if(Harness.Mode=="advance_throw") throw new InvalidOperationException(Harness.Secret);
            var initial = new DateTime(2026,9,14,0,0,0,DateTimeKind.Utc);
            var firstBegin=initial.AddHours(-2); var firstEnd=initial.AddHours(21);
            bool result=true;
            string mode=Harness.Mode;
            if(query==initial) result=mode!="first_false";
            else if(query==firstEnd.AddSeconds(1)) result=mode=="both_true" || (mode=="reuse_difference" && count==1);
            else if(query==firstBegin.AddDays(1).AddSeconds(1)) result=isTemplate ? mode!="constructor_same" : mode!="direct_false" && mode!="constructor_same";
            if(mode.StartsWith("matrix_")) {
                int mask=int.Parse(mode.Substring(7));
                if(query==initial) result=(mask&16)==0;
                if(query==firstEnd.AddSeconds(1)) result=(mask & (count==2 ? 1:2))!=0;
                if(query==firstBegin.AddDays(1).AddSeconds(1)) result=(mask & (isTemplate?8:4))!=0;
            }
            returned=result;
            if (!result) return false;
            int offset=1;
            if(query==initial || query==firstEnd && include) offset=0;
            else if(query>firstEnd.AddDays(1)) offset=(query.Date-initial.Date).Days;
            begin=firstBegin.AddDays(offset); end=firstEnd.AddDays(offset);
            if(Harness.Mode=="reversed_bounds") end=begin;
            if(Harness.Mode=="unspecified") begin=DateTime.SpecifyKind(begin,DateTimeKind.Unspecified);
            if(Harness.Mode=="anchor_mismatch") begin=begin.AddHours(1);
            if(Harness.Mode=="environment_changed") Harness.Host.MarketReopenConfirmed=false;
            if(Harness.Mode=="template_mutated") bars.TradingHours.Version++;
            if(Harness.Mode=="foreign_file") File.WriteAllText(Path.Combine(Harness.Output,"foreign.txt"),"untouched");
            return true;
        }
    }
    public class SecretException : Exception { public SecretException(string value) : base(value) {} }
    public class BarsRequest : IDisposable {
        public static int Creates, Invokes, Disposes; public static BarsRequest Last;
        public Instrument Instrument; public BarsPeriod BarsPeriod; public TradingHours TradingHours;
        public MergePolicy MergePolicy; public LookupPolicies LookupPolicy;
        public bool IsResetOnNewTradingDay, IsDividendAdjusted, IsSplitAdjusted;
        public Bars Bars; private Action<BarsRequest,ErrorCode,string> callback;
        public BarsRequest(Instrument instrument, DateTime from, DateTime through) {
            Creates++; Last=this; Instrument=instrument;
            if (from != new DateTime(2026,9,16) || through != new DateTime(2026,9,21) || from.Kind != DateTimeKind.Unspecified)
                throw new Exception("request date contract");
        }
        public void Request(Action<BarsRequest,ErrorCode,string> value) {
            Invokes++; callback=value;
            if (LookupPolicy != LookupPolicies.Repository || MergePolicy != MergePolicy.DoNotMerge || !IsResetOnNewTradingDay
                || IsDividendAdjusted || IsSplitAdjusted || BarsPeriod.Value != 1) throw new Exception("request contract");
            using (var f = new StreamReader(new FileStream(Path.Combine(Harness.Output,"session-domain-probe.jsonl"),FileMode.Open,FileAccess.Read,FileShare.ReadWrite)))
                if (!f.ReadToEnd().Contains("REQUEST_SUBMITTING")) throw new Exception("unflushed trace");
            Bars=new Bars { Instrument=Instrument, BarsPeriod=BarsPeriod, TradingHours=TradingHours };
            if (Harness.Mode == "empty") Bars.Count=0;
            if (Harness.Mode == "too_many") Bars.Count=10003;
            if (Harness.Mode == "too_many_dates") Bars.Count=33;
            if (Harness.Mode == "large") Bars.Count=4503;
            if (Harness.Mode == "template_exception") TradingHours.Holidays.Add(new DateTime(2026,9,15),"holiday");
            if (Harness.Mode == "wrong_schedule") TradingHours.Sessions[0].BeginTime=180000;
            if (Harness.Mode == "wrong_instrument") Instrument.FullName="OTHER";
            if (Harness.Mode == "wrong_period") BarsPeriod.Value=2;
            if (Harness.Mode == "provider_policy") LookupPolicy=LookupPolicies.Provider;
            if (Harness.Mode == "wrong_template") TradingHours.Name="OTHER";
            if (Harness.Mode.StartsWith("inline")) Fire();
            if (Harness.Mode == "request_throw" || Harness.Mode == "inline_then_throw") throw new IOException(Harness.Secret);
        }
        public void Fire() { callback(Harness.Mode == "wrong_callback" ? null : this,
            Harness.Mode == "callback_error" ? ErrorCode.Failed : ErrorCode.NoError,Harness.Secret); }
        public void Dispose() { Disposes++; }
    }
}
namespace NinjaTrader.NinjaScript {
    public enum State { SetDefaults, Configure, DataLoaded, Historical, Transition, Realtime, Terminated }
    [AttributeUsage(AttributeTargets.Property)] public class NinjaScriptPropertyAttribute : Attribute {}
}
namespace NinjaTrader.NinjaScript.Indicators {
    public class Indicator {
        public State State; public string Name, Description; public bool IsOverlay, IsChartOnly;
        protected virtual void OnStateChange() {}
    }
    public class ProbeHost : ArmsSessionDomainProbeV1 {
        public void Step(State value) { State=value; OnStateChange(); }
        public ProbeHost Clone() { return (ProbeHost)MemberwiseClone(); }
        public void SetPrivate(string name, object value) {
            typeof(ArmsSessionDomainProbeV1).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(this,value);
        }
    }
}
public static class Harness {
    public const string Secret="PRIVATE_PROVIDER_SENTINEL";
    public static string Mode, Output;
    public static NinjaTrader.NinjaScript.Indicators.ProbeHost Host;
    public static int Main(string[] args) {
        Mode=args[0]; Output=args[1]; Host=new NinjaTrader.NinjaScript.Indicators.ProbeHost();
        Host.Step(NinjaTrader.NinjaScript.State.SetDefaults);
        if (Mode != "defaults") {
            Host.ProbeEnabled=true; Host.OutputDirectory=Output;
            Host.MarketReopenConfirmed=Mode != "closed";
            Host.NqDataFlowConfirmed=Mode != "no_flow";
            Host.ConnectionStableConfirmed=Mode != "unstable";
        }
        if (Mode == "playback") NinjaTrader.Cbi.Connection.PlaybackConnection=new NinjaTrader.Cbi.Connection();
        if (Mode == "timezone") NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo=TimeZoneInfo.Local;
        Host.Step(NinjaTrader.NinjaScript.State.Configure);
        Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
        if (Mode == "clone") { var clone=Host.Clone(); clone.Step(NinjaTrader.NinjaScript.State.SetDefaults); clone.Step(NinjaTrader.NinjaScript.State.Terminated); }
        if (Mode == "iterator_cap") Host.SetPrivate("iterators",7);
        if (Mode == "call_cap") Host.SetPrivate("calls",8);
        if (Mode == "record_cap") Host.SetPrivate("records",96);
        if (Mode == "byte_cap") Host.SetPrivate("bytes",262144);
        if (Mode == "changed_properties") Host.OutputDirectory=Secret;
        if (Mode == "terminated") Host.Step(NinjaTrader.NinjaScript.State.Terminated);
        var request=NinjaTrader.Data.BarsRequest.Last;
        if (request != null && Mode != "pending" && Mode != "request_throw") {
            if (Mode == "async") { var t=new System.Threading.Thread(request.Fire);t.Start();t.Join(); }
            else request.Fire();
            request.Fire();
        }
        for (int i=0;i<100;i++) Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
        if (Mode != "pending") Host.Step(NinjaTrader.NinjaScript.State.Terminated);
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            request_creates=NinjaTrader.Data.BarsRequest.Creates,request_invokes=NinjaTrader.Data.BarsRequest.Invokes,
            request_disposes=NinjaTrader.Data.BarsRequest.Disposes,iterator_creates=NinjaTrader.Data.SessionIterator.Creates,
            native_calls=NinjaTrader.Data.SessionIterator.TotalCalls,begin_reads=NinjaTrader.Data.SessionIterator.BeginReads,
            end_reads=NinjaTrader.Data.SessionIterator.EndReads,observations=NinjaTrader.Data.SessionIterator.Observations,
            ninjatrader_assemblies_loaded=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(), a=>a.GetName().Name.StartsWith("NinjaTrader")).Length }));
        return 0;
    }
}
