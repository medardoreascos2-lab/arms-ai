using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R54;

namespace NinjaTrader.Data
{
    public class TradingHours
    {
        public TimeZoneInfo TimeZoneInfo { get; set; }
    }

    public class Bars
    {
        public TradingHours TradingHours { get; set; }
    }

    public class SessionIterator
    {
        public static int Constructors;
        public static int Calls;
        public static int SourceCallTicks;
        public static long RawTicks;
        public static long AdapterTicks;
        public static string Mode = "normal";

        public static readonly List<DateTime> Queries =
            new List<DateTime>();

        private DateTime begin;
        private DateTime end;

        public SessionIterator(Bars bars)
        {
            Constructors++;

            if (Mode == "constructor_second" &&
                Constructors == 2)
                throw new InvalidOperationException(
                    "PRIVATE_CONSTRUCTOR_SENTINEL");
        }

        public bool GetNextSession(
            DateTime query,
            bool includeEndTime)
        {
            Calls++;
            Queries.Add(query);

            if (Mode == "advance_second" &&
                Calls == 2)
                throw new InvalidOperationException(
                    "PRIVATE_ADVANCE_SENTINEL");

            if (query.Ticks == RawTicks)
                return false;

            if (query.Ticks == AdapterTicks &&
                query.Kind == DateTimeKind.Utc)
            {
                begin =
                    new DateTime(
                        2026, 9, 14, 22, 0, 0,
                        DateTimeKind.Utc);

                end =
                    new DateTime(
                        2026, 9, 15, 21, 0, 0,
                        DateTimeKind.Utc);

                if (Mode == "invalid_bounds")
                    end = begin;

                return true;
            }

            return false;
        }

        public DateTime ActualSessionBegin
        {
            get { return begin; }
        }

        public DateTime ActualSessionEnd
        {
            get { return end; }
        }

        public static void Reset()
        {
            Constructors = 0;
            Calls = 0;
            SourceCallTicks = 0;
            Queries.Clear();
            Mode = "normal";
        }
    }
}

internal static class R54NativeComparisonHarness
{
    private const string Provenance =
        "R53_NATIVE_REGRESSION";

    private sealed class Test
    {
        internal string Name;
        internal Action Body;

        internal Test(string name, Action body)
        {
            Name = name;
            Body = body;
        }
    }

    private static void Check(bool value, string id)
    {
        if (!value)
            throw new Exception(id);
    }

    private static TimeZoneInfo Central()
    {
        return TimeZoneInfo.FindSystemTimeZoneById(
            "Central Standard Time");
    }

    private static NinjaTrader.Data.Bars Bars()
    {
        return new NinjaTrader.Data.Bars
        {
            TradingHours =
                new NinjaTrader.Data.TradingHours
                {
                    TimeZoneInfo = Central()
                }
        };
    }

    private static DateTime Source()
    {
        DateTime boundary =
            new DateTime(
                2026, 9, 14, 21, 0, 0,
                DateTimeKind.Unspecified);

        return new DateTime(
            boundary.Ticks + 1,
            DateTimeKind.Unspecified);
    }

    private static DateTime Adapted()
    {
        DateTime boundary =
            new DateTime(
                2026, 9, 15, 2, 0, 0,
                DateTimeKind.Utc);

        return new DateTime(
            boundary.Ticks + 1,
            DateTimeKind.Utc);
    }

    private static void Reset(string mode)
    {
        NinjaTrader.Data.SessionIterator.Reset();
        NinjaTrader.Data.SessionIterator.Mode = mode;

        NinjaTrader.Data.SessionIterator.RawTicks =
            Source().Ticks;

        NinjaTrader.Data.SessionIterator.AdapterTicks =
            Adapted().Ticks;
    }

    private static QueryDomainNativeComparisonResultV1 Run(
        string mode,
        Action checkpoint)
    {
        Reset(mode);

        return
            SessionIteratorQueryDomainNativeComparisonV1.Compare(
                Source(),
                Bars(),
                Provenance,
                checkpoint);
    }

    private static void ExpectGuard(
        Action action,
        string expected)
    {
        try
        {
            action();
        }
        catch (QueryDomainNativeComparisonGuardException error)
        {
            Check(
                error.GuardId == expected,
                "WRONG_GUARD_" + error.GuardId);

            return;
        }

        throw new Exception(
            "EXPECTED_GUARD_" + expected);
    }

    private static void Normal()
    {
        int checkpoints = 0;

        var result =
            Run(
                "normal",
                delegate { checkpoints++; });

        Check(
            result.SourcePreserved,
            "SOURCE_NOT_PRESERVED");

        Check(
            result.SourceTicksBefore ==
            result.SourceTicksAfter,
            "SOURCE_TICKS_CHANGED");

        Check(
            result.IteratorConstructorAttempts == 3,
            "CONSTRUCTOR_COUNT");

        Check(
            result.GetNextSessionAttempts == 3,
            "CALL_COUNT");

        Check(
            result.Observations.Count == 3,
            "OBSERVATION_COUNT");

        Check(
            result.Observations[0].CaseId == "C_RAW" &&
            !result.Observations[0].Returned,
            "RAW_RESULT");

        Check(
            result.Observations[1].CaseId == "C_SAME_TICKS" &&
            !result.Observations[1].Returned,
            "SAME_TICKS_RESULT");

        Check(
            result.Observations[2].CaseId == "C_ADAPTER" &&
            result.Observations[2].Returned,
            "ADAPTER_RESULT");

        Check(
            result.Observations[2].BoundsReadable &&
            result.Observations[2].BoundsValid,
            "ADAPTER_BOUNDS");

        Check(
            result.Observations[0].Query.Ticks ==
            result.Observations[1].Query.Ticks,
            "RAW_RELABEL_TICKS_DIFFER");

        Check(
            result.Observations[0].Query.Kind ==
                DateTimeKind.Unspecified &&
            result.Observations[1].Query.Kind ==
                DateTimeKind.Utc,
            "RAW_RELABEL_KIND");

        Check(
            result.Observations[2].Query ==
            Adapted(),
            "ADAPTER_QUERY");

        Check(
            NinjaTrader.Data.SessionIterator.Constructors == 3 &&
            NinjaTrader.Data.SessionIterator.Calls == 3,
            "NATIVE_BUDGET");

        Check(
            NinjaTrader.Data.SessionIterator.Queries.Count == 3,
            "QUERY_TRACE_COUNT");

        Check(
            checkpoints == 8,
            "CHECKPOINT_COUNT");
    }

    private static void NullBars()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainNativeComparisonV1.Compare(
                    Source(),
                    null,
                    Provenance,
                    delegate { });
            },
            "BARS_MISSING");
    }

    private static void NullTradingHours()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainNativeComparisonV1.Compare(
                    Source(),
                    new NinjaTrader.Data.Bars(),
                    Provenance,
                    delegate { });
            },
            "TRADING_HOURS_MISSING");
    }

    private static void WrongKind()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainNativeComparisonV1.Compare(
                    new DateTime(
                        Source().Ticks,
                        DateTimeKind.Utc),
                    Bars(),
                    Provenance,
                    delegate { });
            },
            "SOURCE_KIND_NOT_UNSPECIFIED");
    }

    private static void MissingCheckpoint()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainNativeComparisonV1.Compare(
                    Source(),
                    Bars(),
                    Provenance,
                    null);
            },
            "CHECKPOINT_MISSING");
    }

    private static void ConstructorFailure()
    {
        ExpectGuard(
            delegate
            {
                Run(
                    "constructor_second",
                    delegate { });
            },
            "SESSION_ITERATOR_CONSTRUCTOR_C_SAME_TICKS");
    }

    private static void AdvanceFailure()
    {
        ExpectGuard(
            delegate
            {
                Run(
                    "advance_second",
                    delegate { });
            },
            "GETNEXTSESSION_C_SAME_TICKS");
    }

    private static void InvalidBounds()
    {
        ExpectGuard(
            delegate
            {
                Run(
                    "invalid_bounds",
                    delegate { });
            },
            "SESSION_BOUNDS_INVALID_C_ADAPTER");
    }

    private static Test[] Tests()
    {
        return new[]
        {
            new Test("normal_c_matrix", Normal),
            new Test("null_bars", NullBars),
            new Test("null_trading_hours", NullTradingHours),
            new Test("wrong_source_kind", WrongKind),
            new Test("missing_checkpoint", MissingCheckpoint),
            new Test("constructor_failure", ConstructorFailure),
            new Test("advance_failure", AdvanceFailure),
            new Test("invalid_bounds", InvalidBounds)
        };
    }

    public static int Main(string[] args)
    {
        bool all =
            args.Length == 1 &&
            args[0] == "--all";

        bool one =
            args.Length == 2 &&
            args[0] == "--case";

        if (!all && !one)
            return 2;

        int passed = 0;
        int failed = 0;

        var results = new List<object>();

        foreach (Test test in Tests())
        {
            if (one && test.Name != args[1])
                continue;

            try
            {
                test.Body();

                results.Add(
                    new
                    {
                        name = test.Name,
                        status = "PASS",
                        detail = "NONE"
                    });

                passed++;
            }
            catch (Exception error)
            {
                results.Add(
                    new
                    {
                        name = test.Name,
                        status = "FAIL",
                        detail =
                            error.GetType().Name +
                            ":" +
                            error.Message
                    });

                failed++;
            }
        }

        int loaded =
            Array.FindAll(
                AppDomain.CurrentDomain.GetAssemblies(),
                delegate(System.Reflection.Assembly assembly)
                {
                    return assembly.GetName().Name.StartsWith(
                        "NinjaTrader",
                        StringComparison.Ordinal);
                }).Length;

        Console.WriteLine(
            new JavaScriptSerializer().Serialize(
                new
                {
                    classification =
                        "SYNTHETIC_R54_NATIVE_COMPARISON_ONLY",
                    total = passed + failed,
                    passed = passed,
                    failed = failed,
                    native_ninjatrader_assemblies_loaded = loaded,
                    account_api_calls = 0,
                    order_api_calls = 0,
                    execution_authority = false,
                    results = results
                }));

        return failed == 0 && passed > 0 ? 0 : 1;
    }
}
