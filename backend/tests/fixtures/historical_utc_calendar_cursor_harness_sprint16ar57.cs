// SYNTHETIC SDK doubles only. Does not load or run NinjaTrader.
using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R57;
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
        public string Name = "CME US Index Futures ETH"; public int Version = 5119;
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.FindSystemTimeZoneById("Central Standard Time");
        public List<Session> Sessions = new List<Session>();
        public Dictionary<DateTime,string> Holidays = new Dictionary<DateTime,string>();
        public Dictionary<DateTime,PartialHoliday> PartialHolidays = new Dictionary<DateTime,PartialHoliday>();
        public TradingHours()
        {
            for (int i = 1; i <= 5; i++) Sessions.Add(new Session { BeginDay = (DayOfWeek)(i-1), EndDay = (DayOfWeek)i, TradingDay = (DayOfWeek)i });
            Holidays.Add(new DateTime(2026,1,1), "Synthetic closure"); Holidays.Add(new DateTime(2026,12,25), "Synthetic closure");
            foreach (DateTime d in new[] { new DateTime(2026,9,7), new DateTime(2026,11,26), new DateTime(2026,11,27) })
                PartialHolidays.Add(d, new PartialHoliday { IsEarlyEnd = true, Constraint = new Session { EndDay = d.DayOfWeek, TradingDay = d.DayOfWeek, EndTime = 1200 } });
        }
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
        private readonly Bars bars; private readonly int ordinal;
        private int calls, readStage; private DateTime begin, end, day; private bool returned;
        public SessionIterator(Bars source)
        {
            ordinal = ++Harness.Constructors; bars = source;
            Harness.Check(Object.ReferenceEquals(source, Harness.ExpectedBars), "wrong Bars source");
            if (Harness.Mode == "constructor_throw" || Harness.Mode == "fresh_constructor_throw" && ordinal == 2)
                throw new InvalidOperationException(Harness.Secret);
        }
        public bool GetNextSession(DateTime query, bool include)
        {
            Harness.Check(ordinal == 1 || calls == 0, "fresh iterator reused");
            int i = (int)(query.Date - Harness.From.AddDays(-2)).TotalDays;
            Harness.Check(i == (ordinal == 1 ? calls : ordinal - 2) || Harness.Mode.EndsWith("throw"), "schedule order");
            calls++; readStage = 0; Harness.Calls++; Harness.Operations.Add("ADVANCE_" + Harness.Calls);
            Harness.Check(query.Kind == DateTimeKind.Utc && include, "query contract");
            Harness.Queries.Add(query.Ticks);
            Harness.CallFacts.Add(new { iterator = ordinal, query = CursorTime.Of(query), include = include });
            if (Harness.Mode == "concurrent_traversal") Harness.Pause("TRAVERSAL");
            if (Harness.Mode == "advance_throw" && ordinal == 1 && i == 2) throw new InvalidOperationException(Harness.Secret);
            day = DateTime.SpecifyKind(query.Date, DateTimeKind.Unspecified);
            returned = day.DayOfWeek != DayOfWeek.Saturday && day.DayOfWeek != DayOfWeek.Sunday && !bars.TradingHours.Holidays.ContainsKey(day);
            if (Harness.Mode == "false") returned = false;
            if (Harness.Mode == "reused_false" && ordinal == 1 && i == 1 || Harness.Mode == "fresh_false" && ordinal != 1 && i == 1
                || Harness.Mode == "missing" && i == 1) returned = false;
            if (Harness.Mode == "extra" && day.DayOfWeek == DayOfWeek.Saturday) returned = true;
            if (Harness.Mode == "duplicate" && (day.DayOfWeek == DayOfWeek.Saturday || day.DayOfWeek == DayOfWeek.Sunday))
            { day = day.AddDays(day.DayOfWeek == DayOfWeek.Saturday ? -1 : -2); returned = true; }
            if (Harness.Mode == "backward" && i == 1) day = day.AddDays(-2);
            if (Harness.Mode == "contradictory" && i == 1) day = day.AddDays(-1);
            var zone = bars.TradingHours.TimeZoneInfo;
            begin = TimeZoneInfo.ConvertTimeToUtc(day.AddDays(-1).AddHours(17), zone);
            int endTime = bars.TradingHours.PartialHolidays.ContainsKey(day) ? bars.TradingHours.PartialHolidays[day].Constraint.EndTime : 1600;
            end = TimeZoneInfo.ConvertTimeToUtc(day.AddHours(endTime / 100).AddMinutes(endTime % 100), zone);
            if (Harness.Mode == "different" && ordinal != 1 && i == 1 || Harness.Mode == "bounds_difference" && i == 1) begin = begin.AddMinutes(1);
            if (Harness.Mode == "overlap" && i == 1) begin = begin.AddHours(-2);
            if (Harness.Mode == "contradictory" && i == 1) day = day.AddDays(1);
            if (Harness.Mode == "bad_order") end = begin;
            if (Harness.Mode == "begin_unspecified") begin = DateTime.SpecifyKind(begin, DateTimeKind.Unspecified);
            if (Harness.Mode == "end_local") end = DateTime.SpecifyKind(end, DateTimeKind.Local);
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
            return returned;
        }
        public DateTime ActualSessionBegin { get {
            Harness.BeginReads++; Harness.Check(returned && readStage == 0, "begin getter order"); readStage = 1;
            if (Harness.Mode == "begin_throw" && ordinal == 1 && calls == 3) throw new InvalidOperationException(Harness.Secret);
            return begin;
        } }
        public DateTime ActualSessionEnd { get {
            Harness.EndReads++; Harness.Check(returned && readStage == 1, "end getter order"); readStage = 2;
            if (Harness.Mode == "end_throw" && ordinal == 1 && calls == 3) throw new InvalidOperationException(Harness.Secret);
            return end;
        } }
        public DateTime ActualTradingDayExchange { get {
            Harness.DayReads++; Harness.Check(returned && readStage == 2, "day getter order"); readStage = 3;
            if (Harness.Mode == "day_throw" && ordinal == 1 && calls == 3) throw new InvalidOperationException(Harness.Secret);
            var value = DateTime.SpecifyKind(day, Harness.Mode == "day_local" ? DateTimeKind.Local : Harness.Mode == "day_utc" ? DateTimeKind.Utc : DateTimeKind.Unspecified);
            Harness.DayValues.Add(CursorTime.Of(value)); return value;
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
    public class Host : ArmsHistoricalUtcCalendarCursorProbeV1
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
    internal static List<CursorTime> DayValues = new List<CursorTime>();
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
        bodyAtPause = File.Exists(Path.Combine(Folder, "historical-utc-calendar-cursor.json"));
        sealAtPause = File.Exists(Path.Combine(Folder, "historical-utc-calendar-cursor.done.json"));
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
        if (Mode == "max_range") Through = From.AddDays(14);
        if (Mode == "min_range") Through = From;
        if (Mode == "holiday") { From = new DateTime(2026,1,3); Through = new DateTime(2026,1,7); }
        if (Mode == "early_close") { From = new DateTime(2026,9,7); Through = new DateTime(2026,9,9); }
        if (Mode == "spring_dst") { From = new DateTime(2026,3,7); Through = new DateTime(2026,3,10); }
        if (Mode == "fall_dst") { From = new DateTime(2026,10,31); Through = new DateTime(2026,11,3); }
        if (Mode == "year_start") { From = new DateTime(2026,1,1); Through = From; }
        if (Mode == "year_end") { From = new DateTime(2026,12,31); Through = From; }
        object direct = null;
        if (Mode.StartsWith("query_") || Mode == "overflow_low" || Mode == "overflow_high" || Mode == "over_bound")
        {
            string error = "NONE";
            try {
                if (Mode.StartsWith("query_")) {
                    var kind = (DateTimeKind)Enum.Parse(typeof(DateTimeKind), Mode.Substring(6));
                    HistoricalUtcCalendarCursorDiagnosticV1.Schedule(new DateTime(2026,9,14,0,0,0,kind), new DateTime(2026,9,29,0,0,0,DateTimeKind.Utc));
                } else if (Mode == "over_bound") HistoricalUtcCalendarCursorDiagnosticV1.ConfiguredSchedule(From, From.AddDays(15));
                else HistoricalUtcCalendarCursorDiagnosticV1.ConfiguredSchedule(Mode == "overflow_low" ? DateTime.MinValue : DateTime.MaxValue.Date, Mode == "overflow_low" ? DateTime.MinValue : DateTime.MaxValue.Date);
            } catch (Exception e) { error = HistoricalUtcCalendarCursorDiagnosticV1.Error(e); }
            direct = new { exception = error };
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
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { classification = "SYNTHETIC_OFFLINE_R57", requests = Requests,
            request_constructors = RequestConstructors, disposes = Disposes, constructors = Constructors, calls = Calls,
            begins = BeginReads, ends = EndReads, day_reads = DayReads, day_values = DayValues, operations = Operations,
            intent_observed = intentObserved, termination_waited = terminationWaited, pauses = pauses,
            body_at_pause = bodyAtPause, seal_at_pause = sealAtPause,
            queries = Queries, call_facts = CallFacts, prints = Prints, direct = direct }));
        return 0;
    }
}
