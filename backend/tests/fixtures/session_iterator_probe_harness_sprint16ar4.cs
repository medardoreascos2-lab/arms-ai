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
    public class TradingHours {
        public string Name = "CME US Index Futures ETH"; public int Version = 1;
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public static TradingHours Get(string name) { if (name != "CME US Index Futures ETH") throw new Exception(); return new TradingHours(); }
    }
    public class Bars {
        public Instrument Instrument; public BarsPeriod BarsPeriod; public TradingHours TradingHours; public int Count = 5;
        public DateTime GetTime(int i) { return new DateTime(2026,9,16,12,0,0,DateTimeKind.Utc).AddMinutes(i); }
        public double GetOpen(int i) { return Harness.Mode == "snapshot_mutated" && SessionIterator.TotalCalls >= 4 ? 20002 : 20000; }
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
        public SessionIterator(Bars value) {
            id = ++Creates; bars = value;
            if (Harness.Mode == "constructor_throw" || (Harness.Mode == "b_constructor_throw" && id == 2))
                throw new InvalidOperationException(Harness.Secret);
        }
        public DateTime ActualSessionBegin { get {
            BeginReads++;
            if (!returned || (Harness.Mode == "begin_throw" && count == 2)) throw new InvalidOperationException(Harness.Secret);
            return begin;
        } }
        public DateTime ActualSessionEnd { get {
            EndReads++;
            if (!returned || (Harness.Mode == "end_throw" && count == 2)) throw new InvalidOperationException(Harness.Secret);
            return end;
        } }
        public bool GetNextSession(DateTime query, bool include) {
            count++; TotalCalls++;
            if (Harness.Mode == "reentrant" && TotalCalls == 1) BarsRequest.Last.Fire();
            Observations.Add(new { iterator = id, call = count, query = query.ToString("o"), kind = query.Kind.ToString(),
                include = include, same_snapshot = Object.ReferenceEquals(bars, BarsRequest.Last.Bars) });
            if (count > 2 || TotalCalls > 4 || !include) throw new Exception("call contract");
            var initial = new DateTime(2026,9,14,0,0,0,DateTimeKind.Utc);
            var expected = count == 1 ? initial : initial.AddHours(21).AddTicks(id == 1 ? 1 : TimeSpan.TicksPerSecond);
            if (query != expected || query.Kind != DateTimeKind.Utc) throw new Exception("query or state isolation contract");
            if (Harness.Mode == "advance_throw" && count == 2) throw new InvalidOperationException(Harness.Secret + new string('x',10000));
            if (Harness.Mode == "other_exception" && count == 2) throw new SecretException(Harness.Secret);
            if (count == 1 && (Harness.Mode == "first_false" || (Harness.Mode == "b_first_false" && id == 2))) return false;
            if (count == 2) {
                bool a = id == 1;
                if (Harness.Mode == "both_false" || (Harness.Mode == "pass" && a) ||
                    (Harness.Mode == "reverse" && !a)) return false;
            }
            begin = initial.AddHours(-2).AddDays(count - 1); end = initial.AddHours(21).AddDays(count - 1);
            if (Harness.Mode == "anchor_mismatch" && id == 2 && count == 1) begin = begin.AddHours(1);
            if (Harness.Mode == "repeat_bounds" && count == 2) { begin = begin.AddDays(-1); end = end.AddDays(-1); }
            if (Harness.Mode == "reversed_bounds" && count == 2) end = begin.AddHours(-1);
            if (Harness.Mode == "unspecified" && count == 2) begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified);
            if (Harness.Mode == "local" && count == 2) end = DateTime.SpecifyKind(end, DateTimeKind.Local);
            if (Harness.Mode == "environment_changed" && TotalCalls == 1) Harness.Host.MarketReopenConfirmed = false;
            if (Harness.Mode == "foreign_file" && TotalCalls == 4) File.WriteAllText(Path.Combine(Harness.Output, "foreign.txt"), "untouched");
            if (Harness.Mode == "template_mutated" && TotalCalls == 1) bars.TradingHours.Version++;
            returned = true; return true;
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
            using (var f = new StreamReader(new FileStream(Path.Combine(Harness.Output,"session-iterator-probe.jsonl"),FileMode.Open,FileAccess.Read,FileShare.ReadWrite)))
                if (!f.ReadToEnd().Contains("REQUEST_SUBMITTING")) throw new Exception("unflushed trace");
            Bars=new Bars { Instrument=Instrument, BarsPeriod=BarsPeriod, TradingHours=TradingHours };
            if (Harness.Mode == "empty") Bars.Count=0;
            if (Harness.Mode == "too_many") Bars.Count=10003;
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
    public class ProbeHost : ArmsSessionIteratorProbeV1 {
        public void Step(State value) { State=value; OnStateChange(); }
        public ProbeHost Clone() { return (ProbeHost)MemberwiseClone(); }
        public void SetPrivate(string name, object value) {
            typeof(ArmsSessionIteratorProbeV1).GetField(name,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(this,value);
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
        if (Mode == "call_cap") Host.SetPrivate("calls",4);
        if (Mode == "record_cap") Host.SetPrivate("records",64);
        if (Mode == "byte_cap") Host.SetPrivate("bytes",131072);
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
            assemblies_loaded_for_execution=AppDomain.CurrentDomain.GetAssemblies().Length }));
        return 0;
    }
}
