// SYNTHETIC SDK doubles only. Does not load or run NinjaTrader.
using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R56;
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
        private readonly int ordinal, row;
        private int calls, readStage;
        private DateTime begin, end;
        private bool returned, prime;
        public SessionIterator(Bars source)
        {
            ordinal = ++Harness.Constructors; row = (ordinal - 1) / 2; bars = source;
            Harness.Check(Object.ReferenceEquals(source, Harness.ExpectedBars), "wrong Bars source");
            if (Harness.Mode == "constructor_throw" || (Harness.Mode == "fresh_constructor_throw" && ordinal == 2)
                || (Harness.Mode == "f_primed_constructor_throw" && ordinal == 11)
                || (Harness.Mode == "f_fresh_constructor_throw" && ordinal == 12))
                throw new InvalidOperationException(Harness.Secret);
        }
        public bool GetNextSession(DateTime query, bool include)
        {
            Harness.Check(calls < (ordinal % 2 == 1 ? 2 : 1), "iterator reused across cases");
            if (calls > 0) Harness.Check(readStage == 3, "case before prime getter order complete");
            prime = ordinal % 2 == 1 && calls == 0; calls++; readStage = 0;
            Harness.Calls++; Harness.Operations.Add("ADVANCE_" + Harness.Calls);
            if (Harness.Mode == "concurrent_traversal") Harness.Pause("TRAVERSAL");
            Harness.Check(query.Kind == DateTimeKind.Utc, "query kind");
            DateTime q0 = new DateTime(Harness.From.AddDays(-2).Ticks, DateTimeKind.Utc);
            DateTime primeBegin = q0.AddHours(-2), primeEnd = q0.AddHours(21);
            if (Harness.Mode == "tick_overflow") primeEnd = new DateTime(DateTime.MaxValue.Ticks, DateTimeKind.Utc);
            if (Harness.Mode.StartsWith("days_overflow"))
            { q0 = Harness.DirectInitial; primeBegin = q0.AddDays(-2); primeEnd = q0.AddDays(-1); }
            DateTime expected = prime ? q0 : row < 2 ? primeEnd : row < 4 ? primeEnd.AddTicks(1) : q0.AddDays(row == 4 ? 1 : 2);
            Harness.Check(query == expected && include == (prime || (row != 1 && row != 3)), "exact matrix query");
            Harness.Queries.Add(query.Ticks);
            Harness.CallFacts.Add(new { iterator = ordinal, prime = prime, query = BoundaryTime.Of(query), include = include });
            if (row == 5 && !prime && ordinal == 11 && Harness.Mode == "f_case_throw_cancel")
            {
                Harness.InCall = true;
                try { Harness.Host.Step(NinjaTrader.NinjaScript.State.Terminated); }
                finally { Harness.InCall = false; }
                throw new InvalidOperationException(Harness.Secret);
            }
            if (row == 5 && ((prime && Harness.Mode == "f_prime_throw")
                || (!prime && ordinal == 11 && Harness.Mode == "f_primed_case_throw")
                || (!prime && ordinal == 12 && Harness.Mode == "f_fresh_case_throw")))
                throw new InvalidOperationException(Harness.Secret);
            if (Harness.Mode == "prime_advance_throw" && prime || Harness.Mode == "advance_throw" && !prime)
                throw new InvalidOperationException(Harness.Secret);
            returned = !(prime && Harness.Mode == "prime_false") && (prime || Harness.Mode != "false");
            if (!prime && Harness.Mode == "mixed") returned = row == 1 || row == 4;
            if (!prime && Harness.Mode == "one_control" && row == 4) returned = ordinal % 2 == 0;
            // Focused F scenarios: E supplies no advancing result in either mode.
            if (Harness.Mode.StartsWith("f_") && row == 4 && !prime) returned = false;
            if (row == 5 && prime && Harness.Mode == "f_prime_false") returned = false;
            if (row == 5 && !prime && (Harness.Mode == "f_both_false"
                || (Harness.Mode == "f_one_false" && ordinal == 11))) returned = false;
            if (Harness.Mode == "mutate_price") bars.Mutation = 1;
            if (Harness.Mode == "mutate_time") bars.Mutation = 2;
            if (Harness.Mode == "mutate_hours") bars.TradingHours.Sessions[0].EndTime++;
            if (Harness.Mode == "replace_hours") bars.TradingHours = new TradingHours();
            if (Harness.Mode == "replace_bars") BarsRequest.Last.Bars = new Bars();
            if (Harness.Mode == "mutate_request") BarsRequest.Last.MergePolicy = MergePolicy.MergeBackAdjusted;
            if (Harness.Mode == "change_properties") Harness.Host.ThroughUtcDate = "2026-09-22";
            if (Harness.Mode == "terminate_during_call")
            { Harness.InCall = true; try { Harness.Host.Step(NinjaTrader.NinjaScript.State.Terminated); } finally { Harness.InCall = false; } }
            if (Harness.Mode == "reentrant") BarsRequest.Last.Fire();
            if (Harness.Mode == "foreign_file") File.WriteAllText(Path.Combine(Harness.Folder, "foreign.txt"), "preserve");
            begin = primeBegin; end = primeEnd;
            if (!prime && row > 0 && Harness.Mode != "tick_overflow" && !Harness.Mode.StartsWith("days_overflow")) { begin = begin.AddDays(1); end = end.AddDays(1); }
            if (!prime && Harness.Mode == "other") { begin = primeBegin.AddDays(-2); end = primeEnd.AddDays(-2); }
            if (!prime && Harness.Mode == "same") { begin = primeBegin; end = primeEnd; }
            if (prime && Harness.Mode == "prime_disagree" && ordinal == 3) begin = begin.AddTicks(1);
            if (row == 5 && prime && Harness.Mode == "f_prime_disagree") begin = begin.AddTicks(1);
            if (row == 5 && prime && Harness.Mode == "f_prime_bad_order") end = begin;
            if (row == 5 && prime && Harness.Mode == "f_prime_kind") begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified);
            if (Harness.Mode == "prime_bad_order" && prime || Harness.Mode == "bad_order" && !prime) end = begin;
            if (Harness.Mode == "prime_unspecified" && prime || Harness.Mode == "begin_unspecified" && !prime)
                begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified);
            if (Harness.Mode == "prime_local" && prime || Harness.Mode == "end_local" && !prime)
                end = DateTime.SpecifyKind(end, DateTimeKind.Local);
            if (Harness.Mode == "prime_boundary" && prime || Harness.Mode == "case_boundary" && !prime)
            { begin = new DateTime(2026,9,29,0,0,0,DateTimeKind.Unspecified); end = begin.AddHours(1); }
            return returned;
        }
        public DateTime ActualSessionBegin { get {
            Harness.BeginReads++; Harness.Check(returned && readStage == 0, "begin getter order"); readStage = 1;
            Harness.Operations.Add("BEGIN_" + Harness.Calls);
            if (Harness.Mode == "terminate_in_begin") Harness.Host.Step(NinjaTrader.NinjaScript.State.Terminated);
            if (Harness.Mode == "begin_throw" && !prime || Harness.Mode == "prime_begin_throw" && prime
                || row == 5 && ((prime && Harness.Mode == "f_prime_begin_throw")
                || (ordinal == 12 && Harness.Mode == "f_fresh_begin_throw")))
                throw new InvalidOperationException(Harness.Secret);
            return begin;
        } }
        public DateTime ActualSessionEnd { get {
            Harness.EndReads++; Harness.Check(returned && readStage == 1, "end getter order"); readStage = 2;
            Harness.Operations.Add("END_" + Harness.Calls);
            if (Harness.Mode == "end_throw" && !prime || Harness.Mode == "prime_end_throw" && prime
                || row == 5 && ((prime && Harness.Mode == "f_prime_end_throw")
                || (ordinal == 12 && Harness.Mode == "f_fresh_end_throw")))
                throw new InvalidOperationException(Harness.Secret);
            return end;
        } }
        public DateTime ActualTradingDayExchange { get {
            Harness.Check(returned && readStage == 2, "trading-day getter order"); readStage = 3;
            Harness.DayReads++; Harness.Operations.Add("TRADING_DAY_" + Harness.Calls);
            if (Harness.Mode == "day_throw" && !prime || Harness.Mode == "prime_day_throw" && prime
                || row == 5 && ((prime && Harness.Mode == "f_prime_day_throw")
                || (ordinal == 12 && Harness.Mode == "f_fresh_day_throw")))
                throw new InvalidOperationException(Harness.Secret);
            var kind = Harness.Mode == "day_local" ? DateTimeKind.Local : Harness.Mode == "day_utc" ? DateTimeKind.Utc : DateTimeKind.Unspecified;
            DateTime value = new DateTime(begin.Date.Ticks + 123, kind);
            if (Harness.Mode == "prime_day_disagree" && prime && ordinal == 3) value = value.AddTicks(1);
            Harness.DayValues.Add(BoundaryTime.Of(value)); return value;
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
    public class Host : ArmsHistoricalUtcBoundaryMatrixProbeV1
    {
        public void Step(NinjaTrader.NinjaScript.State value) { State = value; OnStateChange(); }
        public Host Clone() { return (Host)MemberwiseClone(); }
    }
}
public static class Harness
{
    public static string Mode, Folder;
    public static DateTime From = new DateTime(2026,9,16), Through = new DateTime(2026,9,21);
    public static bool InCall; public static DateTime DirectInitial; public static List<object> CallFacts = new List<object>();
    public const string Secret = "PRIVATE_PROVIDER_SENTINEL";
    public static int Requests, RequestConstructors, Disposes, Constructors, Calls, BeginReads, EndReads, DayReads;
    public static NinjaTrader.Data.Bars ExpectedBars;
    public static NinjaTrader.NinjaScript.Indicators.Host Host;
    public static List<long> Queries = new List<long>(); public static List<string> Prints = new List<string>();
    public static List<string> Operations = new List<string>();
    internal static List<BoundaryTime> DayValues = new List<BoundaryTime>();
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
        bodyAtPause = File.Exists(Path.Combine(Folder, "historical-utc-boundary-matrix.json"));
        sealAtPause = File.Exists(Path.Combine(Folder, "historical-utc-boundary-matrix.done.json"));
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
        if (Mode.StartsWith("query_") || Mode.StartsWith("days_overflow"))
        {
            ExpectedBars = new NinjaTrader.Data.Bars();
            var kind = Mode.StartsWith("query_") ? (DateTimeKind)Enum.Parse(typeof(DateTimeKind), Mode.Substring(6)) : DateTimeKind.Utc;
            var q = Mode.StartsWith("days_overflow") ? new DateTime(9999,12,Mode.EndsWith("two") ? 30 : 31,0,0,0,kind) : new DateTime(2026,9,14,0,0,0,kind); DirectInitial = q;
            direct = HistoricalUtcBoundaryMatrixDiagnosticV1.Run(ExpectedBars, q, Mode.StartsWith("days_overflow") ? new DateTime(DateTime.MaxValue.Ticks, DateTimeKind.Utc) : new DateTime(2026,9,29,0,0,0,DateTimeKind.Utc), delegate { });
            Check(q.Kind == kind && q.Ticks == DirectInitial.Ticks, "source changed");
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
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification = "SYNTHETIC_OFFLINE_R56", requests = Requests,
            request_constructors = RequestConstructors, disposes = Disposes, constructors = Constructors, calls = Calls,
            begins = BeginReads, ends = EndReads, day_reads = DayReads, day_values = DayValues, operations = Operations,
            intent_observed = intentObserved, termination_waited = terminationWaited, pauses = pauses,
            body_at_pause = bodyAtPause, seal_at_pause = sealAtPause,
            queries = Queries, call_facts = CallFacts, prints = Prints, direct = direct }));
        return 0;
    }
}
