// SYNTHETIC SDK doubles only. Does not load or run NinjaTrader.
using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R55;
[assembly: System.Reflection.AssemblyVersion("8.1.8.2")]
namespace NinjaTrader.Core
{
    public static class Globals { public static Options GeneralOptions = new Options(); }
    public class Options { public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc; }
}
namespace NinjaTrader.Cbi
{
    public enum ErrorCode { NoError, Failed }
    public enum MergePolicy { DoNotMerge, MergeBackAdjusted }
    public enum LookupPolicies { Repository, Provider }
    public class Connection { public static Connection PlaybackConnection; }
    public class MasterInstrument { public string Name = "NQ"; public double TickSize = .25, PointValue = 20; }
    public class Instrument
    {
        public string FullName = "NQ DEC26"; public MasterInstrument MasterInstrument = new MasterInstrument();
        public DateTime Expiry = new DateTime(2026,12,1);
        public static Instrument GetInstrument(string name)
        { Harness.Check(name == "NQ DEC26", "instrument"); return new Instrument(); }
    }
}
namespace NinjaTrader.Data
{
    using NinjaTrader.Cbi;
    public enum BarsPeriodType { Minute }
    public enum MarketDataType { Last }
    public class BarsPeriod { public BarsPeriodType BarsPeriodType; public int Value = 1; public MarketDataType MarketDataType; }
    public class Session
    { public DayOfWeek BeginDay, EndDay, TradingDay; public int BeginTime = 1700, EndTime = 1600; }
    public class PartialHoliday
    { public bool IsEarlyEnd, IsLateBegin; public Session Constraint; public List<Session> Sessions = new List<Session>(); }
    public class TradingHours
    {
        public string Name = "CME US Index Futures ETH"; public int Version = 1;
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public List<Session> Sessions = new List<Session> { new Session() };
        public Dictionary<DateTime,string> Holidays = new Dictionary<DateTime,string>();
        public Dictionary<DateTime,PartialHoliday> PartialHolidays = new Dictionary<DateTime,PartialHoliday>();
        public static TradingHours Get(string name)
        { Harness.Check(name == "CME US Index Futures ETH", "hours"); return new TradingHours(); }
    }
    public class Bars
    {
        public Instrument Instrument = new Instrument(); public BarsPeriod BarsPeriod = new BarsPeriod();
        public TradingHours TradingHours = new TradingHours(); public int Count = 5;
        public int Mutation;
        public DateTime GetTime(int i)
        { return new DateTime(2026,9,16,12,0,0,DateTimeKind.Unspecified).AddMinutes(i + (Mutation == 2 ? 1 : 0)); }
        public double GetOpen(int i) { return 20000 + (Mutation == 1 ? 1 : 0); }
        public double GetHigh(int i) { return 20002; }
        public double GetLow(int i) { return 19999; }
        public double GetClose(int i) { return 20000.25; }
        public long GetVolume(int i) { return 10; }
    }
    public class SessionIterator
    {
        private readonly Bars bars;
        private DateTime begin, end;
        private bool returned;
        public SessionIterator(Bars source)
        {
            Harness.Constructors++; bars = source;
            Harness.Check(Object.ReferenceEquals(source, Harness.ExpectedBars), "wrong Bars source");
            if (Harness.Mode == "constructor_throw") throw new InvalidOperationException(Harness.Secret);
        }
        public bool GetNextSession(DateTime query, bool include)
        {
            if (Harness.Calls > 0) Harness.Check(Harness.DayReads == Harness.Calls, "advance before trading-day getter");
            Harness.Calls++;
            Harness.Operations.Add("ADVANCE_" + Harness.Calls);
            if (Harness.Mode == "concurrent_traversal") Harness.Pause("TRAVERSAL");
            Harness.Check(include && query.Kind == DateTimeKind.Utc, "query contract");
            if (Harness.Queries.Count == 0) Harness.Check(query.Ticks == Harness.From.AddDays(-2).Ticks, "initial ticks");
            else Harness.Check(query.Ticks == end.Ticks + 1, "advancement");
            Harness.Queries.Add(query.Ticks);
            if (Harness.Mode == "advance_throw" || (Harness.Mode == "late_throw" && Harness.Calls == 3))
                throw new InvalidOperationException(Harness.Secret);
            returned = Harness.Mode != "false" && !(Harness.Mode == "late_false" && Harness.Calls == 3);
            if (Harness.Mode == "mutate_price") bars.Mutation = 1;
            if (Harness.Mode == "mutate_time") bars.Mutation = 2;
            if (Harness.Mode == "mutate_hours") bars.TradingHours.Sessions[0].EndTime++;
            if (Harness.Mode == "replace_hours") bars.TradingHours = new TradingHours();
            if (Harness.Mode == "replace_bars") BarsRequest.Last.Bars = new Bars();
            if (Harness.Mode == "mutate_request") BarsRequest.Last.MergePolicy = MergePolicy.MergeBackAdjusted;
            if (Harness.Mode == "change_properties") Harness.Host.ThroughUtcDate = "2026-09-22";
            if (Harness.Mode == "terminate_during_call")
            {
                Harness.InCall = true;
                try { Harness.Host.Step(NinjaTrader.NinjaScript.State.Terminated); }
                finally { Harness.InCall = false; }
            }
            if (Harness.Mode == "reentrant") BarsRequest.Last.Fire();
            if (Harness.Mode == "foreign_file") File.WriteAllText(Path.Combine(Harness.Folder, "foreign.txt"), "preserve");
            if (Harness.Mode == "limit") { begin = query; end = query.AddTicks(1); return returned; }
            if (Harness.Mode == "repeated" && Harness.Calls > 1) return returned;
            begin = query.Date.AddDays(query.TimeOfDay > TimeSpan.Zero ? 1 : 0);
            end = begin.AddHours(23);
            if (Harness.Mode == "begin_boundary" || Harness.Mode == "begin_boundary_non_utc")
            {
                begin = new DateTime(2026,9,29,0,0,0,DateTimeKind.Utc); end = begin.AddHours(1);
                if (Harness.Mode == "begin_boundary_non_utc")
                { begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified); end = DateTime.SpecifyKind(end, DateTimeKind.Local); }
            }
            if (Harness.Mode == "end_boundary") end = new DateTime(2026,9,29,0,0,0,DateTimeKind.Utc).AddTicks(-1);
            if (Harness.Mode == "bad_order") end = begin;
            if (Harness.Mode == "begin_unspecified") begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified);
            if (Harness.Mode == "end_local") end = DateTime.SpecifyKind(end, DateTimeKind.Local);
            if (Harness.Mode == "overflow") end = DateTime.SpecifyKind(DateTime.MaxValue, DateTimeKind.Utc);
            return returned;
        }
        public DateTime ActualSessionBegin { get {
            Harness.BeginReads++; Harness.Check(returned, "begin read after false");
            Harness.Operations.Add("BEGIN_" + Harness.Calls);
            if (Harness.Mode == "terminate_in_begin") Harness.Host.Step(NinjaTrader.NinjaScript.State.Terminated);
            if (Harness.Mode == "begin_throw") throw new InvalidOperationException(Harness.Secret);
            return begin;
        } }
        public DateTime ActualSessionEnd { get {
            Harness.EndReads++; Harness.Check(returned, "end read after false");
            Harness.Operations.Add("END_" + Harness.Calls);
            if (Harness.Mode == "end_throw") throw new InvalidOperationException(Harness.Secret);
            return end;
        } }
        public DateTime ActualTradingDayExchange { get {
            Harness.Check(returned && Harness.Operations[Harness.Operations.Count - 1] == "END_" + Harness.Calls,
                "trading-day getter order");
            Harness.DayReads++;
            Harness.Operations.Add("TRADING_DAY_" + Harness.Calls);
            if (Harness.Mode == "day_throw" || (Harness.Mode == "late_day_throw" && Harness.Calls == 3))
                throw new InvalidOperationException(Harness.Secret);
            var kind = Harness.Mode == "day_local" ? DateTimeKind.Local :
                Harness.Mode == "day_utc" ? DateTimeKind.Utc : DateTimeKind.Unspecified;
            DateTime value = new DateTime(begin.Date.Ticks + 123, kind);
            Harness.DayValues.Add(UtcTraversalTime.Of(value));
            return value;
        } }
    }
    public class BarsRequest : IDisposable
    {
        public static BarsRequest Last;
        public Instrument Instrument; public DateTime FromLocal, ToLocal;
        public BarsPeriod BarsPeriod; public TradingHours TradingHours;
        public MergePolicy MergePolicy; public LookupPolicies LookupPolicy;
        public bool IsResetOnNewTradingDay, IsDividendAdjusted, IsSplitAdjusted;
        public Bars Bars; private Action<BarsRequest, ErrorCode, string> callback;
        public BarsRequest(Instrument instrument, DateTime from, DateTime through)
        {
            Harness.RequestConstructors++; Last = this; Instrument = instrument; FromLocal = from; ToLocal = through;
            Harness.Check(from == Harness.From && through == Harness.Through
                && from.Kind == DateTimeKind.Unspecified && through.Kind == DateTimeKind.Unspecified, "date contract");
            if (Harness.Mode == "request_create_throw") throw new InvalidOperationException(Harness.Secret);
        }
        public void Request(Action<BarsRequest, ErrorCode, string> delivery)
        {
            Harness.Requests++; callback = delivery;
            Harness.Check(BarsPeriod.Value == 1 && BarsPeriod.BarsPeriodType == BarsPeriodType.Minute && BarsPeriod.MarketDataType == MarketDataType.Last
                && TradingHours.Name == "CME US Index Futures ETH" && LookupPolicy == LookupPolicies.Repository && MergePolicy == MergePolicy.DoNotMerge
                && IsResetOnNewTradingDay && !IsDividendAdjusted && !IsSplitAdjusted, "request contract");
            Bars = new Bars { Instrument = Instrument, BarsPeriod = BarsPeriod, TradingHours = TradingHours };
            Harness.ExpectedBars = Bars;
            if (Harness.Mode == "wrong_returned_hours") Bars.TradingHours = new TradingHours { Version = 2 };
            if (Harness.Mode == "bad_count") Bars.Count = 2;
            if (Harness.Mode == "request_throw") throw new InvalidOperationException(Harness.Secret);
            if (Harness.Mode == "inline" || Harness.Mode == "inline_then_throw") Fire();
            if (Harness.Mode == "inline_then_throw") throw new InvalidOperationException(Harness.Secret);
        }
        public void Fire()
        { callback(Harness.Mode == "wrong_callback" ? null : this, Harness.Mode == "callback_error" ? ErrorCode.Failed : ErrorCode.NoError, Harness.Secret); }
        public void Dispose()
        {
            Harness.Disposes++;
            Harness.Check(!Harness.InCall, "disposed during native call");
            if (Harness.Mode == "dispose_throw") throw new InvalidOperationException(Harness.Secret);
        }
    }
}
namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Configure, DataLoaded, Historical, Terminated }
    [AttributeUsage(AttributeTargets.Property)] public class NinjaScriptPropertyAttribute : Attribute { }
}
namespace NinjaTrader.NinjaScript.Indicators
{
    public class Indicator
    {
        public NinjaTrader.NinjaScript.State State;
        public string Name, Description; public bool IsOverlay, IsChartOnly;
        protected virtual void OnStateChange() { }
        protected void Print(string value) { Harness.Prints.Add(value); }
    }
    public class Host : ArmsHistoricalUtcTraversalProbeV1
    {
        public void Step(NinjaTrader.NinjaScript.State value) { State = value; OnStateChange(); }
        public Host Clone() { return (Host)MemberwiseClone(); }
    }
}
public static class Harness
{
    public static string Mode, Folder;
    public static DateTime From = new DateTime(2026,9,16), Through = new DateTime(2026,9,21);
    public static bool InCall;
    public const string Secret = "PRIVATE_PROVIDER_SENTINEL";
    public static int Requests, RequestConstructors, Disposes, Constructors, Calls, BeginReads, EndReads, DayReads;
    public static NinjaTrader.Data.Bars ExpectedBars;
    public static NinjaTrader.NinjaScript.Indicators.Host Host;
    public static List<long> Queries = new List<long>(); public static List<string> Prints = new List<string>();
    public static List<string> Operations = new List<string>();
    internal static List<UtcTraversalTime> DayValues = new List<UtcTraversalTime>();
    private static readonly ManualResetEvent Paused = new ManualResetEvent(false), Release = new ManualResetEvent(false),
        Intent = new ManualResetEvent(false), TerminationFinished = new ManualResetEvent(false);
    private static bool intentObserved, terminationWaited, bodyAtPause, sealAtPause;
    private static int pauses;
    public static void Pause(string point)
    {
        bool matches = (Mode == "concurrent_traversal" && point == "TRAVERSAL") ||
            (Mode == "concurrent_body" && point == "BODY_PUBLISHED") ||
            (Mode == "concurrent_seal" && point == "BEFORE_SEAL_COMMIT");
        if (!matches) return;
        Check(++pauses == 1, "second controlled pause");
        bodyAtPause = File.Exists(Path.Combine(Folder, "historical-utc-traversal.json"));
        sealAtPause = File.Exists(Path.Combine(Folder, "historical-utc-traversal.done.json"));
        Paused.Set(); Check(Release.WaitOne(10000), "release timeout");
    }
    private static void Observe(string point)
    {
        if (point == "TERMINATION_INTENT")
        { Check(Host.OfflineTerminationIntent, "termination not visible"); intentObserved = true; Intent.Set(); }
        else Pause(point);
    }
    private static void ConcurrentCallback(NinjaTrader.Data.BarsRequest request)
    {
        Exception callbackError = null, terminationError = null;
        var callback = new Thread(delegate() { try { request.Fire(); } catch (Exception e) { callbackError = e; } });
        var termination = new Thread(delegate() {
            try { Host.Step(NinjaTrader.NinjaScript.State.Terminated); }
            catch (Exception e) { terminationError = e; }
            finally { TerminationFinished.Set(); }
        });
        callback.Start();
        try
        {
            Check(Paused.WaitOne(10000), "callback pause timeout");
            termination.Start();
            Check(Intent.WaitOne(10000), "termination intent blocked behind callback");
            terminationWaited = !TerminationFinished.WaitOne(0);
            Check(terminationWaited && Host.OfflineTerminationIntent, "termination ordering");
        }
        finally { Release.Set(); }
        Check(callback.Join(10000) && termination.Join(10000), "thread completion timeout");
        Check(callbackError == null && terminationError == null, "thread exception");
    }
    public static void Check(bool value, string reason) { if (!value) throw new Exception("HARNESS_" + reason); }
    public static int Main(string[] args)
    {
        Mode = args[0]; Folder = args[1];
        if (Mode == "other_dates") { From = new DateTime(2026,11,25); Through = new DateTime(2026,11,27); }
        object direct = null;
        if (Mode.StartsWith("query_"))
        {
            ExpectedBars = new NinjaTrader.Data.Bars();
            var kind = (DateTimeKind)Enum.Parse(typeof(DateTimeKind), Mode.Substring(6));
            var q = new DateTime(2026,9,14,0,0,0,kind);
            direct = HistoricalUtcTraversalDiagnosticV1.Run(ExpectedBars, q, new DateTime(2026,9,29,0,0,0,DateTimeKind.Utc), delegate { });
            Check(q.Kind == kind && q.Ticks == new DateTime(2026,9,14).Ticks, "source changed");
        }
        else
        {
            Host = new NinjaTrader.NinjaScript.Indicators.Host(); Host.Step(NinjaTrader.NinjaScript.State.SetDefaults);
            Host.OfflineCheckpoint = Observe;
            Check(!Host.ProbeEnabled && !Host.RepositoryPrerequisitesConfirmed && Host.OutputDirectory == ""
                && Host.FromUtcDate == "" && Host.ThroughUtcDate == "", "defaults");
            if (Mode == "disabled_rearm") Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
            if (Mode != "disabled")
            {
                Host.ProbeEnabled = true; Host.RepositoryPrerequisitesConfirmed = Mode != "unconfirmed";
                Host.OutputDirectory = Folder; Host.FromUtcDate = Mode == "bad_date" ? "" : From.ToString("yyyy-MM-dd");
                Host.ThroughUtcDate = Through.ToString("yyyy-MM-dd");
            }
            if (Mode == "wrong_zone") NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
            if (Mode == "playback") NinjaTrader.Cbi.Connection.PlaybackConnection = new NinjaTrader.Cbi.Connection();
            Host.Step(NinjaTrader.NinjaScript.State.Configure); Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
            if (Mode == "clone") Host.Clone().Step(NinjaTrader.NinjaScript.State.Terminated);
            var request = NinjaTrader.Data.BarsRequest.Last;
            if (request != null && Mode != "pending" && Mode != "request_create_throw")
            {
                if (Mode.StartsWith("concurrent_")) ConcurrentCallback(request);
                else if (Mode == "async") { var thread = new System.Threading.Thread(request.Fire); thread.Start(); thread.Join(); }
                else request.Fire();
                request.Fire(); // duplicate callbacks must be ignored
            }
            for (int i = 0; i < 10; i++) Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
            Host.ProbeEnabled = false; Host.ProbeEnabled = true;
            Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
            Host.Step(NinjaTrader.NinjaScript.State.Terminated);
            Host.Step(NinjaTrader.NinjaScript.State.DataLoaded);
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification = "SYNTHETIC_OFFLINE_R55", requests = Requests,
            request_constructors = RequestConstructors, disposes = Disposes, constructors = Constructors, calls = Calls,
            begins = BeginReads, ends = EndReads, day_reads = DayReads, day_values = DayValues, operations = Operations,
            intent_observed = intentObserved, termination_waited = terminationWaited, pauses = pauses,
            body_at_pause = bodyAtPause, seal_at_pause = sealAtPause,
            queries = Queries, prints = Prints, direct = direct }));
        return 0;
    }
}
