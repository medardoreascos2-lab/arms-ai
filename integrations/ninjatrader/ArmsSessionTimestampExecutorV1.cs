// R5.3-B: bounded diagnostic execution coordinator. Not a NinjaScript component.
// Native adapters, request lifecycle, persisted evidence, and seals are NOT implemented here.
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class MatrixGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        internal MatrixGuardException(string id) : base(id) { GuardId = id; }
    }

    // A future adapter must return the actual underlying iterator object as Identity.
    // The synthetic harness provides doubles. This assembly references no NinjaTrader API.
    internal interface ISessionTimestampCursor
    {
        object Identity { get; }
        bool Advance(DateTime query, bool includeEndTime);
        DateTime ReadBegin();
        DateTime ReadEnd();
    }

    internal sealed class TimestampCaseObservation
    {
        public QueryControl Control { get; private set; }
        public string Outcome { get; private set; }
        public string GuardId { get; private set; }
        public string ExceptionType { get; private set; }
        public bool? Returned { get; private set; }
        public DateTime? Begin { get; private set; }
        public DateTime? End { get; private set; }
        public bool BoundsReadable { get; private set; }
        public bool BoundsValid { get; private set; }
        public int ConstructorAttemptsAfter { get; private set; }
        public int CallAttemptsAfter { get; private set; }
        public bool PrerequisiteSatisfied
        {
            get { return SessionTimestampPlanV1.ReusePrerequisiteSatisfied(Returned, BoundsReadable, BoundsValid); }
        }
        internal TimestampCaseObservation(QueryControl control, string outcome, string guardId,
            string error, bool? returned, DateTime? begin, DateTime? end, bool readable,
            bool valid, int constructors, int calls)
        {
            Control = control; Outcome = outcome; GuardId = guardId; ExceptionType = error;
            Returned = returned; Begin = begin; End = end; BoundsReadable = readable;
            BoundsValid = valid; ConstructorAttemptsAfter = constructors; CallAttemptsAfter = calls;
        }
    }

    internal sealed class TimestampMatrixReport
    {
        public ReadOnlyCollection<TimestampCaseObservation> Observations { get; private set; }
        // MatrixCompleted means all 12 cases have an outcome, not that all calls returned true.
        // It is NOT a persisted-evidence seal or a native-provenance claim.
        public bool MatrixCompleted { get; private set; }
        public string StopGuard { get; private set; }
        public int ConstructorAttempts { get; private set; }
        public int CallAttempts { get; private set; }
        public int BeginReadAttempts { get; private set; }
        public int EndReadAttempts { get; private set; }
        public bool NativeProvenanceAttested { get { return false; } }
        public bool HistoricalAdmission { get { return false; } }
        internal TimestampMatrixReport(List<TimestampCaseObservation> rows, bool complete, string guard,
            int constructors, int calls, int begins, int ends)
        {
            Observations = new List<TimestampCaseObservation>(rows).AsReadOnly();
            MatrixCompleted = complete; StopGuard = guard; ConstructorAttempts = constructors;
            CallAttempts = calls; BeginReadAttempts = begins; EndReadAttempts = ends;
        }
    }

    internal sealed class SessionTimestampExecutorV1
    {
        private readonly object sync = new object();
        private readonly SessionTimestampExecutorV1 instanceOwner;
        private bool started, running, tainted;
        private int constructors, calls, begins, ends;
        private static readonly string[] Ids = {
            "A_U", "A_LUTC", "A_THUTC", "B_U", "B_LUTC", "B_THUTC",
            "C_U", "C_LUTC", "C_THUTC", "R0", "R1", "N" };

        internal SessionTimestampExecutorV1() { instanceOwner = this; }

        private static void Guard(bool ok, string id)
        {
            if (!ok) throw new MatrixGuardException(id);
        }

        private static string SafeError(Exception error)
        {
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is NullReferenceException) return "NullReferenceException";
            if (error is OverflowException) return "OverflowException";
            return "OTHER";
        }

        private void Check(Action<string, QueryControl> check, string phase, QueryControl control)
        {
            Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
            try { check(phase, control); }
            catch (Exception) { throw new MatrixGuardException("CONTEXT_CHECK_FAILED_" + phase); }
            Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
        }

        private static object Identity(ISessionTimestampCursor cursor)
        {
            Guard(cursor != null, "FACTORY_RETURNED_NULL_CURSOR");
            object identity;
            try { identity = cursor.Identity; }
            catch (Exception) { throw new MatrixGuardException("ITERATOR_IDENTITY_ACCESS_FAILED"); }
            Guard(identity != null, "ITERATOR_IDENTITY_MISSING");
            return identity;
        }

        private static bool Same(DateTime a, DateTime b) { return a.Ticks == b.Ticks && a.Kind == b.Kind; }

        private static void ValidatePlan(TimestampQueryPlan plan)
        {
            Guard(plan != null, "PLAN_MISSING");
            Guard(plan.Cases != null && plan.Cases.Count == 12, "PLAN_CASE_COUNT_INVALID");
            for (int i = 0; i < 12; i++)
            {
                QueryControl c = plan.Cases[i];
                Guard(c != null && c.Time != null, "PLAN_CASE_MISSING");
                Guard(c.Ordinal == i + 1 && c.CaseId == Ids[i], "PLAN_ORDER_INVALID");
                string slot = "I" + (i < 10 ? i + 1 : i == 10 ? 10 : 11)
                    .ToString("00", System.Globalization.CultureInfo.InvariantCulture);
                Guard(c.IteratorId == slot && c.Reuse == (i == 10), "PLAN_ISOLATION_INVALID");
                Guard(c.ConstructorContext == "Bars" && c.IncludeEndTime, "PLAN_CONTEXT_INVALID");
                Guard(c.Prerequisite == (i == 10 ? "R0_TRUE_READABLE_VALID_BOUNDS" : "NONE"),
                    "PLAN_PREREQUISITE_INVALID");
                Guard(c.SourceIndex == (i < 3 ? (int?)0 : null), "PLAN_SOURCE_INDEX_INVALID");
                if (i < 3) Guard(Same(c.Time.Raw, plan.RawFirst), "PLAN_SOURCE_TIME_INVALID");
                Guard(c.Time.Query.Kind == (i < 9 && i % 3 == 0 ? DateTimeKind.Unspecified : DateTimeKind.Utc),
                    "PLAN_QUERY_KIND_INVALID");
            }
            Guard(Same(plan.Cases[7].Time.Query, plan.Cases[10].Time.Query), "REUSE_QUERY_MISMATCH");
        }

        private TimestampCaseObservation Observe(QueryControl c, string outcome, string guard,
            string error, bool? result, DateTime? begin, DateTime? end, bool readable, bool valid)
        {
            return new TimestampCaseObservation(c, outcome, guard, error, result, begin, end,
                readable, valid, constructors, calls);
        }

        internal TimestampMatrixReport Execute(TimestampQueryPlan plan,
            Func<QueryControl, ISessionTimestampCursor> factory, Action<string, QueryControl> contextCheck)
        {
            // Reject a shallow clone BEFORE any shared lock/resource access or state mutation.
            Guard(Object.ReferenceEquals(this, instanceOwner), "CLONED_EXECUTOR_NOT_OWNER");
            lock (sync)
            {
                if (started)
                {
                    if (running) tainted = true;
                    throw new MatrixGuardException(running ? "EXECUTION_REENTRANT" : "EXECUTION_ALREADY_USED");
                }
                started = true; running = true;
                var rows = new List<TimestampCaseObservation>();
                var identities = new List<object>();
                ISessionTimestampCursor reuseCursor = null;
                object reuseIdentity = null;
                TimestampCaseObservation r0 = null;
                bool complete = false;
                string stop = "NONE";
                try
                {
                    ValidatePlan(plan);
                    Guard(factory != null, "FACTORY_MISSING");
                    Guard(contextCheck != null, "CONTEXT_CHECK_MISSING");
                    Check(contextCheck, "BEFORE_MATRIX", null);
                    foreach (QueryControl c in plan.Cases)
                    {
                        Check(contextCheck, "BEFORE_CASE", c);
                        if (c.Reuse && (r0 == null || !r0.PrerequisiteSatisfied))
                        {
                            rows.Add(Observe(c, "SKIPPED", "R0_TRUE_READABLE_VALID_BOUNDS_NOT_MET",
                                "NONE", null, null, null, false, false));
                            Check(contextCheck, "AFTER_CASE", c);
                            continue;
                        }
                        ISessionTimestampCursor cursor;
                        object id;
                        if (c.Reuse)
                        {
                            Guard(reuseCursor != null && reuseIdentity != null, "REUSE_IDENTITY_MISSING");
                            cursor = reuseCursor; id = reuseIdentity;
                            Guard(Object.ReferenceEquals(Identity(cursor), id), "REUSE_IDENTITY_CHANGED");
                        }
                        else
                        {
                            Check(contextCheck, "BEFORE_CREATE", c);
                            Guard(constructors < SessionTimestampPlanV1.MaximumIteratorSlots, "CONSTRUCTOR_BUDGET_EXCEEDED");
                            constructors++; // Charge attempts even if the adapter constructor throws.
                            try { cursor = factory(c); }
                            catch (Exception error)
                            {
                                rows.Add(Observe(c, "CONSTRUCTOR_EXCEPTION", "NONE", SafeError(error),
                                    null, null, null, false, false));
                                if (c.CaseId == "R0") r0 = rows[rows.Count - 1];
                                Check(contextCheck, "AFTER_CASE", c);
                                continue;
                            }
                            Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
                            id = Identity(cursor);
                            foreach (object prior in identities)
                                Guard(!Object.ReferenceEquals(id, prior), "FRESH_ITERATOR_IDENTITY_REUSED");
                            identities.Add(id);
                            if (c.CaseId == "R0") { reuseCursor = cursor; reuseIdentity = id; }
                        }
                        Check(contextCheck, "BEFORE_ADVANCE", c);
                        Guard(Object.ReferenceEquals(Identity(cursor), id), "ITERATOR_IDENTITY_CHANGED");
                        Guard(calls < SessionTimestampPlanV1.MaximumPlannedCalls, "CALL_BUDGET_EXCEEDED");
                        calls++;
                        bool value;
                        try { value = cursor.Advance(c.Time.Query, c.IncludeEndTime); }
                        catch (Exception error)
                        {
                            rows.Add(Observe(c, "ADVANCE_EXCEPTION", "NONE", SafeError(error),
                                null, null, null, false, false));
                            if (c.CaseId == "R0") r0 = rows[rows.Count - 1];
                            Check(contextCheck, "AFTER_CASE", c);
                            continue;
                        }
                        Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
                        if (!value)
                        {
                            rows.Add(Observe(c, "RETURNED_FALSE", "NONE", "NONE", false, null, null, false, false));
                        }
                        else
                        {
                            DateTime? begin = null, end = null;
                            string errorType = "NONE", outcome = "RETURNED_TRUE", guardId = "NONE";
                            Check(contextCheck, "BEFORE_BEGIN", c);
                            Guard(Object.ReferenceEquals(Identity(cursor), id), "ITERATOR_IDENTITY_CHANGED");
                            begins++;
                            try { begin = cursor.ReadBegin(); }
                            catch (Exception error) { outcome = "BEGIN_READ_EXCEPTION"; errorType = SafeError(error); }
                            Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
                            if (begin.HasValue)
                            {
                                Check(contextCheck, "BEFORE_END", c);
                                Guard(Object.ReferenceEquals(Identity(cursor), id), "ITERATOR_IDENTITY_CHANGED");
                                ends++;
                                try { end = cursor.ReadEnd(); }
                                catch (Exception error) { outcome = "END_READ_EXCEPTION"; errorType = SafeError(error); }
                                Guard(!tainted, "REENTRANT_EXECUTION_REJECTED");
                            }
                            bool readable = begin.HasValue && end.HasValue;
                            // Same-Kind raw bound ordering only; never infer timezone meaning or query containment.
                            bool valid = readable && begin.Value.Kind == end.Value.Kind && begin.Value.Ticks < end.Value.Ticks;
                            if (readable && !valid)
                            {
                                outcome = "BOUNDS_INVALID";
                                guardId = begin.Value.Kind != end.Value.Kind ? "BOUNDS_KIND_MISMATCH" : "BOUNDS_NON_POSITIVE";
                            }
                            rows.Add(Observe(c, outcome, guardId, errorType, true, begin, end, readable, valid));
                        }
                        if (c.CaseId == "R0") r0 = rows[rows.Count - 1];
                        Check(contextCheck, "AFTER_CASE", c);
                    }
                    Check(contextCheck, "BEFORE_COMPLETE", null);
                    Guard(rows.Count == 12 && constructors <= 11 && calls <= 12, "FINAL_BUDGET_INVALID");
                    complete = true;
                }
                catch (MatrixGuardException error) { stop = error.GuardId; }
                catch (Exception) { stop = "INTERNAL_EXECUTOR_ERROR"; }
                finally { running = false; }
                return new TimestampMatrixReport(rows, complete, stop, constructors, calls, begins, ends);
            }
        }
    }
}
