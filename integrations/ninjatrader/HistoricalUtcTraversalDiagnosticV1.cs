// R5.5: isolated observation of the historical UTC traversal; no query repair.
using System;
using System.Collections.Generic;
using System.Globalization;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R55
{
    internal sealed class UtcTraversalTime
    {
        public string clock, kind;
        public long ticks;
        internal static UtcTraversalTime Of(DateTime value)
        {
            return new UtcTraversalTime { clock = value.ToString("yyyy-MM-ddTHH:mm:ss.fffffff", CultureInfo.InvariantCulture),
                ticks = value.Ticks, kind = value.Kind.ToString() };
        }
    }

    internal sealed class UtcTraversalCall
    {
        public int ordinal;
        public UtcTraversalTime query, source_after, begin, end, trading_day;
        public string trading_day_outcome = "NOT_READ";
        public string derivation, exception = "NONE", phase = "QUERY", guard = "NONE";
        public bool include_end_time = true, source_preserved, bounds_valid;
        public bool? returned;
    }

    internal sealed class UtcTraversalResult
    {
        public string constructor_source = "RETURNED_REPOSITORY_BARS", iterator_identity;
        public string outcome, exception = "NONE";
        public int iterator_constructor_attempts, getnextsession_attempts, begin_read_attempts, end_read_attempts;
        public int trading_day_read_attempts;
        public bool observed_false, stopped_by_limit, stopped_by_requested_boundary;
        public int? first_false_ordinal;
        public UtcTraversalTime first_false_query;
        public int successful_calls_before_false;
        public List<UtcTraversalCall> calls = new List<UtcTraversalCall>();
    }

    internal static class HistoricalUtcTraversalDiagnosticV1
    {
        internal const int MaximumCalls = 64;
        internal const string Initial = "CONFIGURED_FROM_MINUS_TWO_DAYS_UTC";
        internal const string Next = "PRIOR_NATIVE_SESSION_END_PLUS_ONE_TICK";

        internal static string Error(Exception error)
        {
            // Never expose provider text, stack traces, paths or arbitrary type names.
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is System.IO.IOException) return "IOException";
            if (error is UnauthorizedAccessException) return "UnauthorizedAccessException";
            return "OTHER";
        }

        internal static bool Same(DateTime a, DateTime b)
        { return a.Ticks == b.Ticks && a.Kind == b.Kind; }

        private static UtcTraversalResult CallFailure(UtcTraversalResult result, UtcTraversalCall call, Exception error)
        { call.exception = Error(error); result.outcome = "CALL_EXCEPTION"; return result; }

        internal static UtcTraversalResult Run(Bars returnedBars, DateTime initial, DateTime through,
            Action checkpoint)
        {
            var result = new UtcTraversalResult();
            if (returnedBars == null || checkpoint == null) throw new ArgumentException();
            if (initial.Kind != DateTimeKind.Utc || through.Kind != DateTimeKind.Utc || initial >= through)
            { result.outcome = "QUERY_REJECTED"; return result; }
            checkpoint();
            SessionIterator iterator;
            result.iterator_constructor_attempts++;
            try { iterator = new SessionIterator(returnedBars); }
            catch (Exception error)
            { result.outcome = "CONSTRUCTOR_EXCEPTION"; result.exception = Error(error); return result; }
            // A run-local identity denotes the single object retained by this method.
            result.iterator_identity = "ITERATOR_1";
            DateTime query = initial, lastEnd = DateTime.MinValue;
            for (int count = 0; count < MaximumCalls; count++)
            {
                checkpoint();
                if (query.Kind != DateTimeKind.Utc) throw new InvalidOperationException();
                DateTime source = query;
                var call = new UtcTraversalCall { ordinal = count, query = UtcTraversalTime.Of(source),
                    derivation = count == 0 ? Initial : Next };
                result.calls.Add(call); // Capture exact source before attempting the native call.
                if (!Same(source, query)) throw new InvalidOperationException();
                call.phase = "ADVANCE";
                result.getnextsession_attempts++;
                try { call.returned = iterator.GetNextSession(query, true); }
                catch (Exception error) { return CallFailure(result, call, error); }
                finally
                {
                    call.source_after = UtcTraversalTime.Of(source);
                    call.source_preserved = Same(source, query);
                }
                if (!call.source_preserved) throw new InvalidOperationException();
                checkpoint(); // Integrity failures propagate to the host; they are not native outcomes.
                if (!call.returned.Value)
                {
                    result.observed_false = true; result.first_false_ordinal = count;
                    result.first_false_query = call.query;
                    result.successful_calls_before_false = count;
                    call.phase = "RETURNED_FALSE"; result.outcome = "FALSE";
                    return result; // In particular, do not read stale bounds.
                }
                DateTime begin, end;
                call.phase = "BEGIN_READ"; result.begin_read_attempts++;
                try { begin = iterator.ActualSessionBegin; call.begin = UtcTraversalTime.Of(begin); }
                catch (Exception error) { return CallFailure(result, call, error); }
                checkpoint();
                call.phase = "END_READ"; result.end_read_attempts++;
                try { end = iterator.ActualSessionEnd; call.end = UtcTraversalTime.Of(end); }
                catch (Exception error) { return CallFailure(result, call, error); }
                checkpoint();
                call.phase = "BOUNDS";
                if (begin >= end || end <= lastEnd) call.guard = "BOUND_ORDER";
                if (call.guard != "NONE") { result.outcome = "BOUND_REJECTED"; return result; }
                // The exporter stops at terminal look-ahead before UTC validation
                // and before reading ActualTradingDayExchange.
                call.bounds_valid = true;
                if (begin >= through)
                { result.stopped_by_requested_boundary = true; result.outcome = "REQUESTED_BOUNDARY"; return result; }
                if (begin.Kind != DateTimeKind.Utc || end.Kind != DateTimeKind.Utc)
                { call.guard = "BOUND_KIND"; call.bounds_valid = false; result.outcome = "BOUND_REJECTED"; return result; }
                call.phase = "TRADING_DAY_READ"; result.trading_day_read_attempts++;
                try
                {
                    DateTime tradingDay = iterator.ActualTradingDayExchange;
                    call.trading_day = UtcTraversalTime.Of(tradingDay);
                    call.trading_day_outcome = "RETURNED";
                }
                catch (Exception error)
                { call.trading_day_outcome = "EXCEPTION"; return CallFailure(result, call, error); }
                checkpoint();
                lastEnd = end;
                call.phase = "QUERY_UPDATE";
                try { query = end.AddTicks(1); }
                catch (Exception error) { return CallFailure(result, call, error); }
                call.phase = "COMPLETE";
                if (query >= through)
                { result.stopped_by_requested_boundary = true; result.outcome = "REQUESTED_BOUNDARY"; return result; }
            }
            result.stopped_by_limit = true; result.outcome = "CALL_LIMIT";
            return result;
        }
    }
}
