// SYNTHETIC EXECUTOR TESTS ONLY. No NinjaTrader assembly or broker APIs.
using System;
using System.Collections.Generic;
using System.Reflection;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;

internal static class ExecutorHarness
{
    private const string Secret = "PRIVATE_NATIVE_MESSAGE_SENTINEL";
    private static readonly DateTime First = new DateTime(2026, 9, 15, 22, 1, 0, DateTimeKind.Unspecified);
    private static readonly DateTime Last = new DateTime(2026, 9, 21, 21, 0, 0, DateTimeKind.Unspecified);
    private static readonly TimeZoneInfo Zone = TimeZoneInfo.CreateCustomTimeZone("Synthetic_Central_Offset", TimeSpan.FromHours(-5), "Synthetic", "Synthetic");
    private static TimestampQueryPlan Plan()
    {
        return SessionTimestampPlanV1.Build(First, Last, 5520, new string('a', 64), new string('b', 64), Zone);
    }
    private static void Assert(bool ok, string id) { if (!ok) throw new Exception(id); }
    private static void Guarded(Action action, string id)
    {
        try { action(); }
        catch (MatrixGuardException e) { Assert(e.GuardId == id, "WRONG_GUARD:" + e.GuardId); return; }
        throw new Exception("EXPECTED_GUARD:" + id);
    }

    private sealed class Call
    {
        public QueryControl Case;
        public Cursor Cursor;
        public DateTime Query;
        public bool Inclusion;
    }

    private sealed class FakeEnvironment
    {
        public string Fault = "NONE", Target = "A_U", FailPhase = "NONE";
        public int Mask = 4095, Constructors, Calls, Begins, Ends;
        public QueryControl Current;
        public SessionTimestampExecutorV1 Executor;
        public TimestampQueryPlan QueryPlan;
        public bool ReentryCaught;
        public object SharedIdentity = new object();
        public List<Call> Log = new List<Call>();
        public void Check(string phase, QueryControl c)
        {
            Current = c;
            if (phase == FailPhase) throw new Exception(Secret);
        }
        public ISessionTimestampCursor Create(QueryControl c)
        {
            Constructors++;
            if (Fault == "reentrant_factory" && c.CaseId == Target)
            {
                try { Executor.Execute(QueryPlan, Create, Check); }
                catch (MatrixGuardException) { ReentryCaught = true; }
            }
            if (c.CaseId == Target && Fault == "constructor") throw new InvalidOperationException(Secret);
            if (c.CaseId == Target && Fault == "null_cursor") return null;
            return new Cursor(this, c.CaseId);
        }
        public TimestampMatrixReport Run(TimestampQueryPlan plan = null)
        {
            QueryPlan = plan ?? Plan(); Executor = new SessionTimestampExecutorV1();
            return Executor.Execute(QueryPlan, Create, Check);
        }
    }
    private sealed class Cursor : ISessionTimestampCursor
    {
        private readonly FakeEnvironment env;
        private readonly string createdFor;
        private readonly object identity = new object();
        private int identityReads;
        private bool? lastReturn;
        internal Cursor(FakeEnvironment e, string c) { env = e; createdFor = c; }
        public object Identity
        {
            get
            {
                identityReads++;
                if (createdFor == env.Target && env.Fault == "identity_throw") throw new Exception(Secret);
                if (createdFor == env.Target && env.Fault == "null_identity") return null;
                if (createdFor == env.Target && env.Fault == "identity_flip" && identityReads > 1) return new object();
                if (env.Fault == "shared_identity") return env.SharedIdentity;
                if (env.Fault == "reuse_identity_flip" && env.Current.CaseId == "R1") return new object();
                return identity;
            }
        }
        public bool Advance(DateTime query, bool includeEndTime)
        {
            env.Calls++;
            QueryControl c = env.Current;
            env.Log.Add(new Call { Case = c, Cursor = this, Query = query, Inclusion = includeEndTime });
            if (env.Fault == "advance" && c.CaseId == env.Target) throw new InvalidOperationException(Secret);
            bool result = (env.Mask & (1 << (c.Ordinal - 1))) != 0;
            lastReturn = result;
            return result;
        }
        public DateTime ReadBegin()
        {
            env.Begins++;
            Assert(lastReturn == true, "BEGIN_READ_AFTER_FALSE");
            if (env.Fault == "begin" && env.Current.CaseId == env.Target) throw new ArgumentException(Secret);
            DateTimeKind k = env.Fault == "unspecified_bounds" ? DateTimeKind.Unspecified : DateTimeKind.Utc;
            return new DateTime(2026, 9, 13, 22, 0, 0, k);
        }
        public DateTime ReadEnd()
        {
            env.Ends++;
            Assert(lastReturn == true, "END_READ_AFTER_FALSE");
            if (env.Fault == "end" && env.Current.CaseId == env.Target) throw new NullReferenceException(Secret);
            if (env.Fault == "invalid_bounds" && env.Current.CaseId == env.Target)
                return new DateTime(2026, 9, 13, 22, 0, 0, DateTimeKind.Utc);
            DateTimeKind k = env.Fault == "unspecified_bounds" || env.Fault == "mixed_bounds" && env.Current.CaseId == env.Target
                ? DateTimeKind.Unspecified : DateTimeKind.Utc;
            return new DateTime(2026, 9, 14, 21, 0, 0, k);
        }
    }
    private static TimestampCaseObservation Find(TimestampMatrixReport r, string id)
    {
        foreach (var c in r.Observations) if (c.Control.CaseId == id) return c;
        throw new Exception("MISSING_CASE:" + id);
    }
    private static void Counters(FakeEnvironment e, TimestampMatrixReport r)
    {
        Assert(r.ConstructorAttempts == e.Constructors && r.CallAttempts == e.Calls, "ATTEMPT_COUNTS");
        Assert(r.BeginReadAttempts == e.Begins && r.EndReadAttempts == e.Ends, "READ_COUNTS");
        Assert(r.ConstructorAttempts <= 11 && r.CallAttempts <= 12, "LIMIT_EXCEEDED");
        Assert(!r.NativeProvenanceAttested && !r.HistoricalAdmission, "AUTHORITY");
    }
    private static void Complete(FakeEnvironment e, TimestampMatrixReport r)
    {
        Counters(e, r);
        Assert(r.MatrixCompleted && r.StopGuard == "NONE" && r.Observations.Count == 12, "INCOMPLETE");
    }
    private static void R0Failure(string fault, string outcome)
    {
        var e = new FakeEnvironment { Fault = fault, Target = "R0" };
        var r = e.Run(); Complete(e, r);
        Assert(Find(r, "R0").Outcome == outcome, "R0_OUTCOME");
        Assert(Find(r, "R1").Outcome == "SKIPPED", "R1_NOT_SKIPPED");
        Assert(Find(r, "N").Returned == true, "N_DID_NOT_RUN");
        Assert(e.Calls == (fault == "constructor" ? 10 : 11), "SKIP_CALL_COUNT");
    }

    private static void AllTrue()
    {
        var e = new FakeEnvironment(); var r = e.Run(); Complete(e, r);
        Assert(e.Calls == 12 && e.Constructors == 11 && e.Begins == 12 && e.Ends == 12, "TRUE_COUNTS");
        foreach (var row in r.Observations) Assert(row.PrerequisiteSatisfied && row.Outcome == "RETURNED_TRUE", "TRUE_OUTCOME");
    }
    private static void AllFalse()
    {
        var e = new FakeEnvironment { Mask = 0 }; var r = e.Run(); Complete(e, r);
        Assert(e.Calls == 11 && e.Constructors == 11 && e.Begins == 0 && e.Ends == 0, "FALSE_COUNTS");
        foreach (var row in r.Observations)
            Assert(row.Control.CaseId == "R1" ? row.Outcome == "SKIPPED" : row.Returned == false && !row.Begin.HasValue && !row.End.HasValue, "FALSE_BOUNDS");
    }
    private static void R0False()
    {
        var e = new FakeEnvironment { Mask = 4095 & ~(1 << 9) }; var r = e.Run(); Complete(e, r);
        Assert(e.Calls == 11 && Find(r, "R1").Outcome == "SKIPPED" && Find(r, "N").Returned == true, "FALSE_SKIP");
    }
    private static void FaultEveryCase(string fault)
    {
        foreach (var c in Plan().Cases)
        {
            if (fault == "constructor" && c.Reuse) continue;
            var e = new FakeEnvironment { Fault = fault, Target = c.CaseId }; var r = e.Run(); Complete(e, r);
            string expected = fault == "constructor" ? "CONSTRUCTOR_EXCEPTION" : fault == "advance" ? "ADVANCE_EXCEPTION" : fault == "begin" ? "BEGIN_READ_EXCEPTION" : "END_READ_EXCEPTION";
            Assert(Find(r, c.CaseId).Outcome == expected, "WRONG_FAULT_CLASS");
            if (fault == "constructor") Assert(!Find(r, c.CaseId).Returned.HasValue, "CTOR_HAS_RETURN");
            if (fault == "begin") Assert(!Find(r, c.CaseId).End.HasValue, "END_AFTER_BEGIN_EXCEPTION");
        }
    }
    private static void ReuseIdentity()
    {
        var e = new FakeEnvironment(); var r = e.Run(); Complete(e, r);
        Assert(Object.ReferenceEquals(e.Log[9].Cursor, e.Log[10].Cursor), "REUSE_NOT_SAME");
        Assert(e.Log[7].Query.Ticks == e.Log[10].Query.Ticks && e.Log[7].Query.Kind == e.Log[10].Query.Kind, "QUERY_DIFFERENT");
        Assert(!Object.ReferenceEquals(e.Log[7].Cursor, e.Log[10].Cursor), "FRESH_NOT_DISTINCT");
    }
    private static void IdentityFailure(string fault, string guard, int constructors, int calls)
    {
        var e = new FakeEnvironment { Fault = fault }; var r = e.Run(); Counters(e, r);
        Assert(!r.MatrixCompleted && r.StopGuard == guard && e.Constructors == constructors && e.Calls == calls, "IDENTITY_FAILURE");
    }
    private static void NullPlan()
    {
        var e = new FakeEnvironment(); var engine = new SessionTimestampExecutorV1();
        var r = engine.Execute(null, e.Create, e.Check); Counters(e, r);
        Assert(!r.MatrixCompleted && r.StopGuard == "PLAN_MISSING" && e.Calls == 0, "NULL_PLAN");
    }
    private static void MalformedPlan(bool order)
    {
        var plan = Plan(); var cases = new List<QueryControl>(plan.Cases);
        if (order) { var tmp = cases[0]; cases[0] = cases[1]; cases[1] = tmp; } else cases.RemoveAt(11);
        var bad = new TimestampQueryPlan(cases, First, Last, 5520, new string('a',64), new string('b',64), Zone.Id);
        var e = new FakeEnvironment(); var r = e.Run(bad); Counters(e, r);
        Assert(!r.MatrixCompleted && e.Constructors == 0 && e.Calls == 0, "BAD_PLAN_CALLED");
    }
    private static void MissingDependency(bool factory)
    {
        var e = new FakeEnvironment(); var engine = new SessionTimestampExecutorV1();
        var r = engine.Execute(Plan(), factory ? null : (Func<QueryControl, ISessionTimestampCursor>)e.Create,
            factory ? (Action<string,QueryControl>)e.Check : null);
        Counters(e, r); Assert(!r.MatrixCompleted && e.Calls == 0 && r.StopGuard == (factory ? "FACTORY_MISSING" : "CONTEXT_CHECK_MISSING"), "DEPENDENCY");
    }
    private static void ContextFailure(string phase, int constructors, int calls, int begins, int ends)
    {
        var e = new FakeEnvironment { FailPhase = phase }; var r = e.Run(); Counters(e, r);
        Assert(!r.MatrixCompleted && r.StopGuard == "CONTEXT_CHECK_FAILED_" + phase, "CONTEXT_GUARD");
        Assert(e.Constructors == constructors && e.Calls == calls && e.Begins == begins && e.Ends == ends, "CONTEXT_COUNTS");
    }
    private static void Reentry()
    {
        var e = new FakeEnvironment { Fault = "reentrant_factory" }; var r = e.Run(); Counters(e, r);
        Assert(e.ReentryCaught && !r.MatrixCompleted && r.StopGuard == "REENTRANT_EXECUTION_REJECTED" && e.Constructors == 1 && e.Calls == 0, "REENTRY");
    }
    private static void Repeat()
    {
        var e = new FakeEnvironment(); var r = e.Run(); Complete(e, r);
        Guarded(() => e.Executor.Execute(e.QueryPlan, e.Create, e.Check), "EXECUTION_ALREADY_USED");
        Counters(e, r); Assert(e.Calls == 12, "REPEATED_NATIVE_CALLS");
    }
    private static void Clone()
    {
        var e = new FakeEnvironment(); e.QueryPlan = Plan(); e.Executor = new SessionTimestampExecutorV1();
        var clone = (SessionTimestampExecutorV1)typeof(object).GetMethod("MemberwiseClone", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(e.Executor, null);
        Guarded(() => clone.Execute(e.QueryPlan, e.Create, e.Check), "CLONED_EXECUTOR_NOT_OWNER");
        Assert(e.Calls == 0 && e.Constructors == 0, "CLONE_SIDE_EFFECT");
        var r = e.Executor.Execute(e.QueryPlan, e.Create, e.Check); Complete(e, r);
        Guarded(() => clone.Execute(e.QueryPlan, e.Create, e.Check), "CLONED_EXECUTOR_NOT_OWNER");
        Counters(e, r); Assert(e.Calls == 12, "OWNER_DAMAGED");
    }
    private static void BooleanMatrix()
    {
        for (int mask = 0; mask < 4096; mask++)
        {
            var e = new FakeEnvironment { Mask = mask }; var r = e.Run(); Complete(e, r);
            bool r0 = (mask & (1 << 9)) != 0;
            Assert(e.Calls == (r0 ? 12 : 11) && e.Constructors == 11, "MASK_COUNTS");
            foreach (var row in r.Observations)
            {
                if (row.Control.CaseId == "R1" && !r0) Assert(row.Outcome == "SKIPPED", "MASK_SKIP");
                else
                {
                    bool expected = (mask & (1 << (row.Control.Ordinal - 1))) != 0;
                    Assert(row.Returned == expected && row.BoundsReadable == expected && row.BoundsValid == expected, "MASK_RESULT");
                }
            }
        }
    }
    private static void QueryPreservation()
    {
        var e = new FakeEnvironment(); var r = e.Run(); Complete(e, r);
        for (int i = 0; i < 12; i++)
        {
            var c = e.QueryPlan.Cases[i]; var called = e.Log[i];
            Assert(called.Case.CaseId == c.CaseId && called.Query.Ticks == c.Time.Query.Ticks && called.Query.Kind == c.Time.Query.Kind && called.Inclusion, "QUERY_MUTATED");
        }
    }
    private static void Redaction()
    {
        var e = new FakeEnvironment { Fault = "advance" }; var r = e.Run(); Complete(e, r);
        string output = new JavaScriptSerializer().Serialize(r);
        Assert(!output.Contains(Secret) && output.Contains("ADVANCE_EXCEPTION"), "MESSAGE_LEAK");
    }
    private static void ReadonlyReport()
    {
        var e = new FakeEnvironment(); var r = e.Run(); Complete(e, r);
        try { ((IList<TimestampCaseObservation>)r.Observations).Clear(); }
        catch (NotSupportedException) { Assert(r.Observations.Count == 12, "MUTATED"); return; }
        throw new Exception("MUTABLE_REPORT");
    }
    private static void CountersBeforeInvocation()
    {
        var e = new FakeEnvironment(); var plan = Plan(); var engine = new SessionTimestampExecutorV1();
        Func<QueryControl, ISessionTimestampCursor> create = c =>
        {
            int charged = (int)typeof(SessionTimestampExecutorV1).GetField("constructors", BindingFlags.Instance|BindingFlags.NonPublic).GetValue(engine);
            Assert(charged == e.Constructors + 1, "CTOR_NOT_CHARGED_FIRST");
            return e.Create(c);
        };
        var r = engine.Execute(plan, create, e.Check); Complete(e, r);
    }

    private sealed class Test
    {
        public string Name; public Action Run;
        public Test(string name, Action run) { Name = name; Run = run; }
    }
    private static List<Test> Tests()
    {
        return new List<Test> {
            new Test("all_true_budget", AllTrue),
            new Test("all_false_no_bounds", AllFalse),
            new Test("r0_false_skips_r1_only", R0False),
            new Test("r0_constructor_exception", () => R0Failure("constructor", "CONSTRUCTOR_EXCEPTION")),
            new Test("r0_advance_exception", () => R0Failure("advance", "ADVANCE_EXCEPTION")),
            new Test("r0_begin_exception", () => R0Failure("begin", "BEGIN_READ_EXCEPTION")),
            new Test("r0_end_exception", () => R0Failure("end", "END_READ_EXCEPTION")),
            new Test("r0_invalid_bounds", () => R0Failure("invalid_bounds", "BOUNDS_INVALID")),
            new Test("r0_mixed_bound_kinds", () => R0Failure("mixed_bounds", "BOUNDS_INVALID")),
            new Test("matching_unspecified_bounds", () => { var e = new FakeEnvironment { Fault="unspecified_bounds" }; var r=e.Run(); Complete(e,r); Assert(e.Calls==12, "UNSPECIFIED_REJECTED"); }),
            new Test("constructor_fault_every_fresh_case", () => FaultEveryCase("constructor")),
            new Test("advance_fault_every_case", () => FaultEveryCase("advance")),
            new Test("begin_fault_every_case", () => FaultEveryCase("begin")),
            new Test("end_fault_every_case", () => FaultEveryCase("end")),
            new Test("r1_reuses_r0_only", ReuseIdentity),
            new Test("fresh_identity_reuse_rejected", () => IdentityFailure("shared_identity", "FRESH_ITERATOR_IDENTITY_REUSED", 2, 1)),
            new Test("null_cursor_rejected", () => IdentityFailure("null_cursor", "FACTORY_RETURNED_NULL_CURSOR", 1, 0)),
            new Test("null_identity_rejected", () => IdentityFailure("null_identity", "ITERATOR_IDENTITY_MISSING", 1, 0)),
            new Test("identity_change_rejected", () => IdentityFailure("identity_flip", "ITERATOR_IDENTITY_CHANGED", 1, 0)),
            new Test("identity_getter_exception", () => IdentityFailure("identity_throw", "ITERATOR_IDENTITY_ACCESS_FAILED", 1, 0)),
            new Test("reuse_identity_change_rejected", () => IdentityFailure("reuse_identity_flip", "REUSE_IDENTITY_CHANGED", 10, 10)),
            new Test("null_plan_rejected", NullPlan),
            new Test("bad_case_count_rejected", () => MalformedPlan(false)),
            new Test("bad_order_rejected", () => MalformedPlan(true)),
            new Test("missing_factory_rejected", () => MissingDependency(true)),
            new Test("missing_context_check_rejected", () => MissingDependency(false)),
            new Test("context_before_create", () => ContextFailure("BEFORE_CREATE",0,0,0,0)),
            new Test("context_before_advance", () => ContextFailure("BEFORE_ADVANCE",1,0,0,0)),
            new Test("context_before_begin", () => ContextFailure("BEFORE_BEGIN",1,1,0,0)),
            new Test("context_before_end", () => ContextFailure("BEFORE_END",1,1,1,0)),
            new Test("context_before_complete", () => ContextFailure("BEFORE_COMPLETE",11,12,12,12)),
            new Test("reentrant_executor_cannot_complete", Reentry),
            new Test("repeated_executor_no_more_calls", Repeat),
            new Test("shallow_clone_preserves_owner", Clone),
            new Test("all_4096_boolean_patterns", BooleanMatrix),
            new Test("query_ticks_kind_inclusion_unchanged", QueryPreservation),
            new Test("exception_messages_not_persisted", Redaction),
            new Test("immutable_observation_collection", ReadonlyReport),
            new Test("constructor_attempt_charged_first", CountersBeforeInvocation)
        };
    }
    public static int Main(string[] args)
    {
        if (args.Length != 1 && args.Length != 2) return 2;
        bool all = args.Length == 1 && args[0] == "--all";
        if (!all && !(args.Length == 2 && args[0] == "--case")) return 2;
        var results = new List<object>(); int passed = 0, failed = 0;
        foreach (var test in Tests())
        {
            if (!all && test.Name != args[1]) continue;
            try { test.Run(); results.Add(new { name=test.Name, status="PASS", detail="NONE" }); passed++; }
            catch (Exception error) { results.Add(new { name=test.Name, status="FAIL", detail=error.GetType().Name+":"+error.Message }); failed++; }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            classification="SYNTHETIC_EXECUTOR_ONLY_NOT_NATIVE_EVIDENCE", total=passed+failed, passed=passed, failed=failed,
            real_native_api_calls=0, native_provenance_attested=false,
            loaded_ninjatrader_assemblies=Array.FindAll(AppDomain.CurrentDomain.GetAssemblies(), a => a.GetName().Name.StartsWith("NinjaTrader", StringComparison.Ordinal)).Length, results=results }));
        return failed == 0 && passed > 0 ? 0 : 1;
    }
}
