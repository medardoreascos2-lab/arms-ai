// SYNTHETIC OFFLINE SDK doubles. Compiles the actual exporter, never loads NinjaTrader.
using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
[assembly: System.Reflection.AssemblyVersion("8.1.8.2")]
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
            if (value != "NQ DEC26") throw new Exception("wrong requested instrument");
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
        public string Name = "CME US Index Futures ETH";
        public int Version = 1;
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public static TradingHours Get(string name) {
            if (name != "CME US Index Futures ETH") throw new Exception("wrong template");
            return new TradingHours();
        }
    }
    public class Bars {
        public Instrument Instrument; public BarsPeriod BarsPeriod; public TradingHours TradingHours;
        public int Count = 5;
        public DateTime GetTime(int i) {
            return DateTime.SpecifyKind(new DateTime(2026,9,16,12,0,0).AddMinutes(i),
                Harness.Mode == "bar_kind" ? DateTimeKind.Unspecified : DateTimeKind.Utc);
        }
        public double GetOpen(int i) { return Harness.Mode == "bad_price" ? Double.NaN : 20000; }
        public double GetHigh(int i) { return 20001; }
        public double GetLow(int i) { return 19999; }
        public double GetClose(int i) { return 20000.25; }
        public long GetVolume(int i) { return 0; }
    }
    public class SessionIterator {
        private DateTime begin, end;
        private int calls;
        public DateTime ActualSessionBegin { get {
            if (Harness.Mode == "begin_throw") throw new InvalidOperationException(Harness.Secret);
            return begin;
        } }
        public DateTime ActualSessionEnd { get {
            if (Harness.Mode == "end_throw") throw new InvalidOperationException(Harness.Secret);
            return end;
        } }
        public DateTime ActualTradingDayExchange { get { return begin.Date; } }
        public SessionIterator(Bars bars) {
            if (Harness.Mode == "iterator_create_throw") throw new InvalidOperationException(Harness.Secret);
        }
        public bool GetNextSession(DateTime query, bool include) {
            calls++;
            if (!include) throw new Exception("end inclusion changed");
            if (Harness.Mode == "iterator_throw" || (Harness.Mode == "late_throw" && calls == 3))
                throw new InvalidOperationException(Harness.Secret + " C:\\private\\secret.txt\n" + new string('x',10000));
            if (Harness.Mode == "iterator_false") return false;
            if (Harness.Mode == "late_false" && calls == 3) return false;
            if (Harness.Mode == "repeated" && calls > 1) return true;
            if (Harness.Mode == "nonadvancing" && calls > 1) { begin=begin.AddHours(-1); return true; }
            if (Harness.Mode == "tiny_sessions") {
                begin = query; end = query.AddTicks(1); return true;
            }
            if (Harness.Mode == "session_boundaries" || Harness.Mode.StartsWith("query_")) {
                // Synthetic September 2026 ETH geometry only; not native calendar evidence.
                var start = query.Date.AddHours(22);
                if (query.Hour < 21 || (query.Hour == 21 && query.TimeOfDay == TimeSpan.FromHours(21)))
                    start = start.AddDays(-1);
                while (start.DayOfWeek == DayOfWeek.Friday || start.DayOfWeek == DayOfWeek.Saturday)
                    start = start.AddDays(1);
                begin = DateTime.SpecifyKind(start, DateTimeKind.Utc);
                end = begin.AddHours(23); return true;
            }
            begin = DateTime.SpecifyKind(query.Date.AddDays(query.TimeOfDay > TimeSpan.Zero ? 1 : 0),
                Harness.Mode == "calendar_kind" ? DateTimeKind.Unspecified : DateTimeKind.Utc);
            end = begin.AddHours(23);
            if (Harness.Mode == "end_before_begin") end=begin.AddTicks(-1);
            return true;
        }
    }
    public class BarsRequest : IDisposable {
        public static BarsRequest Last;
        public static int Creates, Invokes, Disposes;
        public Instrument Instrument; public DateTime FromLocal, ToLocal;
        public BarsPeriod BarsPeriod; public TradingHours TradingHours;
        public MergePolicy MergePolicy; public LookupPolicies LookupPolicy;
        public bool IsResetOnNewTradingDay, IsDividendAdjusted, IsSplitAdjusted;
        public Bars Bars; private Action<BarsRequest,ErrorCode,string> callback;
        private bool disposed;
        public BarsRequest(Instrument instrument, DateTime from, DateTime through) {
            Creates++;
            if (Harness.Mode == "create_throw") throw new InvalidOperationException(Harness.Secret);
            Last = this; Instrument = instrument; FromLocal = from; ToLocal = through;
        }
        public void Request(Action<BarsRequest,ErrorCode,string> action) {
            Invokes++; callback = action;
            string trace;
            using (var input = new StreamReader(new FileStream(Path.Combine(Harness.DirectoryPath,
                "historical-diagnostic.jsonl"), FileMode.Open, FileAccess.Read, FileShare.ReadWrite)))
                trace = input.ReadToEnd();
            if (!trace.Contains("CONFIG_VALIDATED") || !trace.Contains("REQUEST_SUBMITTING"))
                throw new Exception("directory probe not flushed before request");
            if (LookupPolicy != LookupPolicies.Repository || MergePolicy != MergePolicy.DoNotMerge
                || !IsResetOnNewTradingDay || IsDividendAdjusted || IsSplitAdjusted
                || BarsPeriod.Value != 1 || FromLocal != new DateTime(2026,9,16)
                || ToLocal != new DateTime(2026,9,21)) throw new Exception("request contract");
            if (Harness.Mode == "request_throw") throw new IOException(Harness.Secret);
            Bars = new Bars { Instrument=Instrument, BarsPeriod=BarsPeriod, TradingHours=TradingHours };
            if (Harness.Mode == "empty" || Harness.Mode == "inline_empty") Bars.Count = 0;
            if (Harness.Mode == "inline_success" || Harness.Mode == "inline_empty") Fire();
        }
        public void Fire() {
            callback(Harness.Mode == "wrong_callback" ? null : this,
                Harness.Mode == "callback_error" ? ErrorCode.Failed : ErrorCode.NoError, Harness.Secret);
        }
        public void Dispose() { if (!disposed) { Disposes++; disposed = true; } }
    }
}
namespace NinjaTrader.NinjaScript {
    public enum State { SetDefaults, Configure, DataLoaded, Historical, Transition, Realtime, Terminated }
    [AttributeUsage(AttributeTargets.Property)] public class NinjaScriptPropertyAttribute : Attribute { }
}
namespace NinjaTrader.NinjaScript.Indicators {
    public class Indicator {
        public NinjaTrader.NinjaScript.State State;
        public string Name, Description; public bool IsOverlay, IsChartOnly;
        protected virtual void OnStateChange() { }
        protected void Print(string text) {
            if (Harness.Mode == "print_unavailable") throw new IOException(Harness.Secret);
            Harness.Prints.Add(text);
        }
    }
    public class Host : ArmsHistoricalBootstrapV1 {
        public void Step(NinjaTrader.NinjaScript.State state) { State=state; OnStateChange(); }
        public Host Clone() { return (Host)MemberwiseClone(); }
        public void QueryKind(DateTimeKind kind) {
            // Exercise the real private traversal with alternate input Kind; never change production defaults.
            var type = typeof(ArmsHistoricalBootstrapV1);
            var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
            type.GetMethod("CalendarIntervals",flags).Invoke(this,new object[] {
                new NinjaTrader.Data.Bars(), DateTime.SpecifyKind(new DateTime(2026,9,16),kind),
                DateTime.SpecifyKind(new DateTime(2026,9,17),kind) });
        }
    }
}
public static class Harness {
    public static string Mode, DirectoryPath;
    public const string Secret = "PRIVATE_PROVIDER_SENTINEL_DO_NOT_LOG";
    public static List<string> Prints = new List<string>();
    public static int Main(string[] args) {
        Mode=args[0]; DirectoryPath=args[1];
        var h = new NinjaTrader.NinjaScript.Indicators.Host();
        h.Step(NinjaTrader.NinjaScript.State.SetDefaults);
        if (Mode == "defaults") {
            h.Step(NinjaTrader.NinjaScript.State.Configure);
            h.Step(NinjaTrader.NinjaScript.State.DataLoaded);
        } else {
            if (Mode == "late_properties") h.Step(NinjaTrader.NinjaScript.State.Configure);
            h.CaptureEnabled=true; h.OutputDirectory=DirectoryPath;
            h.FromUtcDate=Mode == "bad_date" ? Secret : "2026-09-16";
            h.ThroughUtcDate="2026-09-21";
            if (Mode != "late_properties") h.Step(NinjaTrader.NinjaScript.State.Configure);
            if (Mode.StartsWith("query_")) {
                h.QueryKind((DateTimeKind)Enum.Parse(typeof(DateTimeKind),Mode.Substring(6)));
                h.Step(NinjaTrader.NinjaScript.State.Terminated);
                Console.WriteLine("{\"creates\":0,\"invokes\":0,\"disposes\":0}"); return 0;
            }
            if (Mode == "changed_properties") h.ThroughUtcDate="2026-09-22";
            if (Mode == "terminate_before_request") h.Step(NinjaTrader.NinjaScript.State.Terminated);
            h.Step(NinjaTrader.NinjaScript.State.DataLoaded);
            var request = NinjaTrader.Data.BarsRequest.Last;
            if (Mode == "clone") {
                var clone = h.Clone();
                clone.Step(NinjaTrader.NinjaScript.State.Terminated);
                if (NinjaTrader.Data.BarsRequest.Disposes != 0) throw new Exception("clone disposed owner");
            }
            for (int i=0;i<100;i++) {
                h.Step(NinjaTrader.NinjaScript.State.DataLoaded);
                h.Step(NinjaTrader.NinjaScript.State.Historical);
                h.Step(NinjaTrader.NinjaScript.State.Transition);
                h.Step(NinjaTrader.NinjaScript.State.Realtime);
            }
            if (Mode == "terminated") h.Step(NinjaTrader.NinjaScript.State.Terminated);
            if (Mode == "foreign_file") File.WriteAllText(Path.Combine(DirectoryPath,"foreign.txt"),"untouched");
            if (Mode == "callback_properties") h.CaptureEnabled=false;
            if (request != null && NinjaTrader.Data.BarsRequest.Invokes == 1
                && Mode != "request_throw" && Mode != "pending" && Mode != "terminate_before_request") {
                if (Mode == "async") {
                    var t = new System.Threading.Thread(request.Fire); t.Start(); t.Join();
                } else request.Fire();
                request.Fire(); // duplicate callback cannot emit another dataset
            }
            if (Mode != "pending") h.Step(NinjaTrader.NinjaScript.State.Terminated);
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            creates=NinjaTrader.Data.BarsRequest.Creates, invokes=NinjaTrader.Data.BarsRequest.Invokes,
            disposes=NinjaTrader.Data.BarsRequest.Disposes, prints=Prints }));
        return 0;
    }
}
