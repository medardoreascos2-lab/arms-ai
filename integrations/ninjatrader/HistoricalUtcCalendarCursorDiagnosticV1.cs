// R5.7: bounded raw observations only; no production traversal or execution authority.
using System;
using System.Collections.Generic;
using System.Globalization;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R57
{
    internal sealed class CursorTime
    {
        public string clock, kind;
        public long ticks;
        internal static CursorTime Of(DateTime value)
        { return new CursorTime { clock = value.ToString("yyyy-MM-ddTHH:mm:ss.fffffff", CultureInfo.InvariantCulture), ticks = value.Ticks, kind = value.Kind.ToString() }; }
    }
    internal sealed class CursorConstructor
    {
        public int ordinal;
        public string identity, exception = "NONE", source = "RETURNED_REPOSITORY_BARS", bars_identity = "RETURNED_BARS_1";
        public bool completed;
    }
    internal sealed class CursorCall
    {
        public int ordinal, constructor_ordinal;
        public string path, iterator_identity, derivation = "UTC_CALENDAR_DATE_CURSOR", phase = "ADVANCE", exception = "NONE", guard = "NONE";
        public CursorTime query, source_before, source_after, begin, end, trading_day;
        public bool include_end_time = true, source_preserved;
        public bool? returned;
        public int getnextsession_attempts = 1, getnextsession_completed, begin_read_attempts, end_read_attempts, trading_day_read_attempts;
    }
    internal sealed class CursorPath
    {
        public string path, outcome = "PARTIAL";
        public List<CursorConstructor> constructors = new List<CursorConstructor>();
        public List<CursorCall> calls = new List<CursorCall>();
    }
    internal sealed class CursorResult
    {
        public string analysis_location = "INDEPENDENT_OFFLINE_VERIFIER";
        public bool traversal_complete;
        public List<CursorTime> schedule = new List<CursorTime>();
        public List<CursorPath> paths = new List<CursorPath>();
    }
    internal static class HistoricalUtcCalendarCursorDiagnosticV1
    {
        internal const int MaxConfiguredRangeDays = 14;
        // Historical contract: 14 + 2 lookback + 8 lookahead + inclusive endpoint.
        internal const int MaxScheduledQueries = MaxConfiguredRangeDays + 2 + 8 + 1;
        internal static string Error(Exception error)
        {
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is System.IO.IOException) return "IOException";
            if (error is UnauthorizedAccessException) return "UnauthorizedAccessException";
            return "OTHER";
        }
        internal static List<DateTime> ConfiguredSchedule(DateTime from, DateTime through)
        {
            if (from.Kind != DateTimeKind.Unspecified || through.Kind != DateTimeKind.Unspecified
                || from.TimeOfDay != TimeSpan.Zero || through.TimeOfDay != TimeSpan.Zero
                || through < from || (through - from).TotalDays > MaxConfiguredRangeDays) throw new ArgumentException();
            return Schedule(DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc),
                DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc));
        }
        internal static List<DateTime> Schedule(DateTime initial, DateTime limit)
        {
            if (initial.Kind != DateTimeKind.Utc || limit.Kind != DateTimeKind.Utc
                || initial.TimeOfDay != TimeSpan.Zero || limit.TimeOfDay != TimeSpan.Zero || initial > limit
                || (limit - initial).TotalDays + 1 > MaxScheduledQueries) throw new ArgumentException();
            var values = new List<DateTime>();
            for (DateTime cursor = initial; ; cursor = cursor.AddDays(1))
            { values.Add(cursor); if (cursor == limit) break; }
            return values;
        }
        private static CursorCall Observe(SessionIterator iterator, DateTime query, CursorPath path,
            CursorConstructor constructor, int ordinal, Action checkpoint)
        {
            if (query.Kind != DateTimeKind.Utc) throw new ArgumentException();
            DateTime source = query;
            var call = new CursorCall { path = path.path, ordinal = ordinal, constructor_ordinal = constructor.ordinal,
                iterator_identity = constructor.identity, query = CursorTime.Of(query), source_before = CursorTime.Of(source) };
            checkpoint(); path.calls.Add(call);
            try { call.returned = iterator.GetNextSession(query, true); call.getnextsession_completed = 1; }
            catch (Exception error) { call.exception = Error(error); return call; }
            finally { call.source_after = CursorTime.Of(source); call.source_preserved = source.Ticks == query.Ticks && source.Kind == query.Kind; }
            checkpoint();
            if (!call.returned.Value) { call.phase = "RETURNED_FALSE"; return call; }
            call.phase = "BEGIN_READ"; call.begin_read_attempts++;
            DateTime begin, end;
            try { begin = iterator.ActualSessionBegin; call.begin = CursorTime.Of(begin); }
            catch (Exception error) { call.exception = Error(error); return call; }
            checkpoint(); call.phase = "END_READ"; call.end_read_attempts++;
            try { end = iterator.ActualSessionEnd; call.end = CursorTime.Of(end); }
            catch (Exception error) { call.exception = Error(error); return call; }
            checkpoint(); call.phase = "BOUNDS";
            if (begin >= end) { call.guard = "BOUND_ORDER"; return call; }
            if (begin.Kind != DateTimeKind.Utc || end.Kind != DateTimeKind.Utc) { call.guard = "BOUND_KIND"; return call; }
            // No production terminal shortcut: observe the inclusive last query too.
            // Getter ordering remains begin -> end -> ordering -> UTC -> exchange date.
            call.phase = "TRADING_DAY_READ"; call.trading_day_read_attempts++;
            try { call.trading_day = CursorTime.Of(iterator.ActualTradingDayExchange); }
            catch (Exception error) { call.exception = Error(error); return call; }
            checkpoint(); call.phase = "COMPLETE"; return call;
        }
        internal static CursorResult Run(Bars returnedBars, DateTime from, DateTime through, Action checkpoint)
        {
            if (returnedBars == null || checkpoint == null) throw new ArgumentException();
            var schedule = ConfiguredSchedule(from, through); // All arithmetic/budget checks precede constructors.
            var result = new CursorResult();
            foreach (DateTime q in schedule) result.schedule.Add(CursorTime.Of(q));
            int ordinal = 0;
            for (int lane = 0; lane < 2; lane++)
            {
                var path = new CursorPath { path = lane == 0 ? "REUSED" : "FRESH" }; result.paths.Add(path);
                SessionIterator iterator = null; CursorConstructor constructor = null;
                for (int i = 0; i < schedule.Count; i++)
                {
                    checkpoint();
                    if (lane == 1 || iterator == null)
                    {
                        constructor = new CursorConstructor { ordinal = ++ordinal, identity = "ITERATOR_" + ordinal.ToString(CultureInfo.InvariantCulture) };
                        path.constructors.Add(constructor);
                        try { iterator = new SessionIterator(returnedBars); constructor.completed = true; }
                        catch (Exception error) { constructor.exception = Error(error); path.outcome = "CONSTRUCTOR_EXCEPTION"; break; }
                    }
                    var call = Observe(iterator, schedule[i], path, constructor, i, checkpoint);
                    if (call.exception != "NONE") { path.outcome = "NATIVE_EXCEPTION"; break; }
                    if (call.guard != "NONE") { path.outcome = "BOUND_REJECTED"; break; }
                    // False advances only to the next predeclared diagnostic query. Never a retry.
                    if (i == schedule.Count - 1) path.outcome = "COMPLETE";
                }
            }
            result.traversal_complete = result.paths.TrueForAll(p => p.outcome == "COMPLETE");
            return result;
        }
    }
}
