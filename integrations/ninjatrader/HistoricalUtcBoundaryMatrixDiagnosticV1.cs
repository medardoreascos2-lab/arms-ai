// R5.6 diagnostic observations only. No production strategy is selected.
using System;
using System.Collections.Generic;
using System.Globalization;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R56
{
    internal sealed class BoundaryTime
    {
        public string clock, kind;
        public long ticks;
        internal DateTime raw;
        internal static BoundaryTime Of(DateTime value)
        { return new BoundaryTime { clock = value.ToString("yyyy-MM-ddTHH:mm:ss.fffffff", CultureInfo.InvariantCulture), ticks = value.Ticks, kind = value.Kind.ToString(), raw = value }; }
    }
    internal sealed class BoundaryCall
    {
        public BoundaryTime query, source_after, begin, end, trading_day;
        public string derivation, phase = "ADVANCE", exception = "NONE", guard = "NONE";
        public string classification = "EXCEPTION", trading_day_outcome = "NOT_READ";
        public bool include_end_time, source_preserved, bounds_valid;
        public bool? returned;
        public int getnextsession_attempts = 1, begin_read_attempts, end_read_attempts, trading_day_read_attempts;
    }
    internal sealed class BoundaryObservation
    {
        public string case_id, mode, iterator_identity, source_bars_identity = "RETURNED_BARS_1";
        public string exception = "NONE", phase = "CONSTRUCTOR";
        public int constructor_ordinal;
        public bool priming_occurred;
        public BoundaryCall prime, observation;
    }
    internal sealed class BoundaryMatrixResult
    {
        public string constructor_source = "RETURNED_REPOSITORY_BARS", outcome;
        public bool interpretation_allowed;
        public bool? conditional_required;
        public int iterator_constructor_attempts, getnextsession_attempts, begin_read_attempts, end_read_attempts, trading_day_read_attempts;
        public List<BoundaryObservation> observations = new List<BoundaryObservation>();
    }
    internal static class HistoricalUtcBoundaryMatrixDiagnosticV1
    {
        internal static readonly string[] Cases = { "END_INCLUDE_TRUE", "END_INCLUDE_FALSE",
            "END_PLUS_ONE_TICK_INCLUDE_TRUE", "END_PLUS_ONE_TICK_INCLUDE_FALSE",
            "NEXT_DAY_INTERIOR_CONTROL", "LATER_DATE_CONTROL" };
        internal static readonly string[] Derivations = { "NATIVE_PRIME_END", "NATIVE_PRIME_END",
            "NATIVE_PRIME_END_PLUS_ONE_TICK", "NATIVE_PRIME_END_PLUS_ONE_TICK", "INITIAL_PLUS_ONE_DAY", "INITIAL_PLUS_TWO_DAYS" };
        internal const string Initial = "CONFIGURED_FROM_MINUS_TWO_DAYS_UTC";
        internal static string Error(Exception error)
        {
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is System.IO.IOException) return "IOException";
            if (error is UnauthorizedAccessException) return "UnauthorizedAccessException";
            return "OTHER";
        }
        private static bool Same(BoundaryTime a, BoundaryTime b)
        { return a != null && b != null && a.ticks == b.ticks && a.kind == b.kind; }
        private static bool Agrees(BoundaryCall a, BoundaryCall b)
        { return Same(a.begin, b.begin) && Same(a.end, b.end) && Same(a.trading_day, b.trading_day); }

        private static BoundaryCall Observe(SessionIterator iterator, DateTime query, bool include, string derivation,
            DateTime through, BoundaryCall anchor, BoundaryMatrixResult result, Action checkpoint)
        {
            if (query.Kind != DateTimeKind.Utc) throw new InvalidOperationException();
            DateTime source = query;
            var call = new BoundaryCall { query = BoundaryTime.Of(source), include_end_time = include, derivation = derivation };
            checkpoint(); result.getnextsession_attempts++;
            try { call.returned = iterator.GetNextSession(query, include); }
            catch (Exception error) { call.exception = Error(error); return call; }
            finally
            {
                call.source_after = BoundaryTime.Of(source);
                call.source_preserved = source.Ticks == query.Ticks && source.Kind == query.Kind;
            }
            checkpoint();
            if (!call.returned.Value) { call.phase = call.classification = "RETURNED_FALSE"; return call; }
            DateTime begin, end;
            call.phase = "BEGIN_READ"; call.begin_read_attempts++; result.begin_read_attempts++;
            try { begin = iterator.ActualSessionBegin; call.begin = BoundaryTime.Of(begin); }
            catch (Exception error) { call.exception = Error(error); return call; }
            checkpoint();
            call.phase = "END_READ"; call.end_read_attempts++; result.end_read_attempts++;
            try { end = iterator.ActualSessionEnd; call.end = BoundaryTime.Of(end); }
            catch (Exception error) { call.exception = Error(error); return call; }
            checkpoint(); call.phase = "BOUNDS";
            // Same prime order/terminal-lookahead/UTC/day getter order as the exporter.
            // Case comparisons intentionally allow the same or earlier valid session.
            if (begin >= end || end.Ticks <= 0) call.guard = "BOUND_ORDER";
            else if (begin >= through) { call.classification = "REQUESTED_BOUNDARY"; return call; }
            else if (begin.Kind != DateTimeKind.Utc || end.Kind != DateTimeKind.Utc) call.guard = "BOUND_KIND";
            if (call.guard != "NONE") { call.classification = "BOUND_REJECTED"; return call; }
            call.bounds_valid = true;
            call.phase = "TRADING_DAY_READ"; call.trading_day_read_attempts++; result.trading_day_read_attempts++;
            try { call.trading_day = BoundaryTime.Of(iterator.ActualTradingDayExchange); call.trading_day_outcome = "RETURNED"; }
            catch (Exception error) { call.trading_day_outcome = "EXCEPTION"; call.exception = Error(error); return call; }
            checkpoint(); call.phase = "COMPLETE";
            call.classification = anchor == null ? "PRIME" :
                Same(call.begin, anchor.begin) && Same(call.end, anchor.end) ? "SAME_AS_PRIME" :
                call.end.ticks > anchor.end.ticks ? "ADVANCING_AFTER_PRIME" : "OTHER_VALID_SESSION";
            return call;
        }
        internal static BoundaryMatrixResult Run(Bars returnedBars, DateTime initial, DateTime through, Action checkpoint)
        {
            if (returnedBars == null || checkpoint == null) throw new ArgumentException();
            var result = new BoundaryMatrixResult();
            if (initial.Kind != DateTimeKind.Utc || through.Kind != DateTimeKind.Utc || initial >= through)
            { result.outcome = "QUERY_REJECTED"; return result; }
            BoundaryCall canonical = null;
            for (int row = 0; row < Cases.Length; row++)
            {
                if (row == 5 && result.conditional_required != true) break;
                DateTime caseQuery = initial;
                bool advancingControl = false;
                for (int mode = 0; mode < 2; mode++)
                {
                    checkpoint();
                    var item = new BoundaryObservation { case_id = Cases[row], mode = mode == 0 ? "PRIMED_REUSED" : "FRESH_DIRECT",
                        constructor_ordinal = ++result.iterator_constructor_attempts };
                    result.observations.Add(item);
                    SessionIterator iterator;
                    try { iterator = new SessionIterator(returnedBars); }
                    catch (Exception error)
                    { item.exception = Error(error); result.outcome = "CONSTRUCTOR_EXCEPTION"; return result; }
                    item.iterator_identity = "ITERATOR_" + item.constructor_ordinal.ToString(CultureInfo.InvariantCulture);
                    if (mode == 0)
                    {
                        item.phase = "PRIME"; item.priming_occurred = true;
                        item.prime = Observe(iterator, initial, true, Initial, through, null, result, checkpoint);
                        if (item.prime.phase != "COMPLETE") { result.outcome = "PRIME_REJECTED"; return result; }
                        if (canonical == null) canonical = item.prime;
                        else if (!Agrees(canonical, item.prime)) { result.outcome = "PRIME_DISAGREEMENT"; return result; }
                        item.phase = "DERIVATION";
                        try
                        {
                            // E comes from THIS pair's prime, never a fixture or calendar offset.
                            DateTime end = item.prime.end.raw;
                            caseQuery = row < 2 ? end : row < 4 ? end.AddTicks(1) : initial.AddDays(row == 4 ? 1 : 2);
                        }
                        catch (Exception error)
                        { item.exception = Error(error); result.outcome = "DERIVATION_EXCEPTION"; return result; }
                    }
                    item.phase = "CASE";
                    item.observation = Observe(iterator, caseQuery, row != 1 && row != 3, Derivations[row], through, canonical, result, checkpoint);
                    item.phase = "COMPLETE"; // A native case failure ends this iterator, not its independent peers.
                    if (item.observation.classification == "ADVANCING_AFTER_PRIME") advancingControl = true;
                }
                if (row == 4) result.conditional_required = !advancingControl;
            }
            result.outcome = "COMPLETE"; result.interpretation_allowed = true;
            return result;
        }
    }
}
