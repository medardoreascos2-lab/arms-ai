using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R54;

namespace NinjaTrader.Data
{
    public class TradingHours
    {
        public string Name { get; set; }

        public Func<int, System.TimeZoneInfo> ZoneProvider { get; set; }

        private int reads;

        public System.TimeZoneInfo TimeZoneInfo
        {
            get
            {
                reads++;

                if (ZoneProvider == null)
                    return null;

                return ZoneProvider(reads);
            }
        }
    }
}

internal static class R54QueryDomainHarness
{
    private const string Provenance = "R53_NATIVE_REGRESSION";

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

    private static void Check(bool condition, string id)
    {
        if (!condition)
            throw new Exception(id);
    }

    private static NinjaTrader.Data.TradingHours Hours(
        TimeZoneInfo zone)
    {
        return new NinjaTrader.Data.TradingHours
        {
            Name = "CME US Index Futures ETH",
            ZoneProvider = delegate(int read) { return zone; }
        };
    }

    private static TimeZoneInfo Central()
    {
        return TimeZoneInfo.FindSystemTimeZoneById(
            "Central Standard Time");
    }

    private static SessionIteratorQueryDomainResultV1 Convert(
        DateTime source)
    {
        return SessionIteratorQueryDomainAdapterV1.Adapt(
            source,
            Hours(Central()),
            SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
            Provenance);
    }

    private static void ExpectGuard(Action action, string expected)
    {
        try
        {
            action();
        }
        catch (SessionIteratorQueryDomainGuardException error)
        {
            Check(error.GuardId == expected,
                "WRONG_GUARD_" + error.GuardId);

            return;
        }

        throw new Exception("EXPECTED_GUARD_" + expected);
    }

    private static DateTime U(
        int year,
        int month,
        int day,
        int hour,
        int minute,
        int second)
    {
        return new DateTime(
            year, month, day, hour, minute, second,
            DateTimeKind.Unspecified);
    }

    private static DateTime Z(
        int year,
        int month,
        int day,
        int hour,
        int minute,
        int second)
    {
        return new DateTime(
            year, month, day, hour, minute, second,
            DateTimeKind.Utc);
    }

    private static void UtcIdentity()
    {
        DateTime source = Z(2026, 9, 14, 22, 1, 0);

        var result =
            SessionIteratorQueryDomainAdapterV1.Adapt(
                source,
                Hours(Central()),
                SessionIteratorQueryDomainPolicyV1.PreserveUtc,
                Provenance);

        Check(result.Query == source, "UTC_CHANGED");
        Check(result.SourceTicks == result.QueryTicks, "UTC_TICKS_CHANGED");
        Check(!result.ConversionPerformed, "UTC_CONVERTED");
    }

    private static void CentralBasic()
    {
        DateTime source = U(2026, 9, 15, 12, 0, 0);
        var result = Convert(source);

        Check(
            result.Query ==
            Z(2026, 9, 15, 17, 0, 0),
            "CENTRAL_BASIC_WRONG");

        Check(result.ConversionPerformed, "NOT_CONVERTED");
    }

    private static void R53A()
    {
        DateTime source = U(2026, 9, 15, 22, 1, 0);
        var result = Convert(source);

        Check(
            result.Query ==
            Z(2026, 9, 16, 3, 1, 0),
            "R53_A_WRONG");
    }

    private static void R53B()
    {
        DateTime source = U(2026, 9, 14, 21, 0, 0);
        var result = Convert(source);

        Check(
            result.Query ==
            Z(2026, 9, 15, 2, 0, 0),
            "R53_B_WRONG");
    }

    private static void R53C()
    {
        DateTime baseValue = U(2026, 9, 14, 21, 0, 0);

        DateTime source =
            new DateTime(
                baseValue.Ticks + 1,
                DateTimeKind.Unspecified);

        DateTime expected =
            new DateTime(
                Z(2026, 9, 15, 2, 0, 0).Ticks + 1,
                DateTimeKind.Utc);

        var result = Convert(source);

        Check(result.Query == expected, "R53_C_WRONG");
        Check(
            result.QueryTicks - result.SourceTicks ==
            TimeSpan.FromHours(5).Ticks,
            "R53_C_DELTA_WRONG");
    }

    private static void R53N()
    {
        DateTime source = Z(2026, 9, 14, 22, 1, 0);

        var result =
            SessionIteratorQueryDomainAdapterV1.Adapt(
                source,
                Hours(Central()),
                SessionIteratorQueryDomainPolicyV1.PreserveUtc,
                Provenance);

        Check(result.Query == source, "R53_N_CHANGED");
    }

    private static void InvalidDst()
    {
        DateTime source = U(2026, 3, 8, 2, 30, 0);

        ExpectGuard(
            delegate { Convert(source); },
            "WALL_CLOCK_INVALID");
    }

    private static void AmbiguousDst()
    {
        DateTime source = U(2026, 11, 1, 1, 30, 0);

        ExpectGuard(
            delegate { Convert(source); },
            "WALL_CLOCK_AMBIGUOUS");
    }

    private static void LocalRejected()
    {
        DateTime source =
            new DateTime(
                2026, 9, 15, 12, 0, 0,
                DateTimeKind.Local);

        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    source,
                    Hours(Central()),
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    Provenance);
            },
            "SOURCE_KIND_LOCAL_REJECTED");
    }

    private static void NullTradingHours()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    U(2026, 9, 15, 12, 0, 0),
                    null,
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    Provenance);
            },
            "TRADING_HOURS_MISSING");
    }

    private static void NullTimezone()
    {
        var hours = new NinjaTrader.Data.TradingHours
        {
            Name = "CME US Index Futures ETH",
            ZoneProvider = delegate(int read) { return null; }
        };

        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    U(2026, 9, 15, 12, 0, 0),
                    hours,
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    Provenance);
            },
            "TIMEZONE_MISSING");
    }

    private static void TimezoneMutation()
    {
        TimeZoneInfo first = Central();

        TimeZoneInfo changed =
            TimeZoneInfo.CreateCustomTimeZone(
                "Central Standard Time",
                TimeSpan.FromHours(-6),
                "Changed",
                "Changed");

        var hours = new NinjaTrader.Data.TradingHours
        {
            Name = "CME US Index Futures ETH",

            ZoneProvider = delegate(int read)
            {
                return read == 1 ? first : changed;
            }
        };

        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    U(2026, 9, 15, 12, 0, 0),
                    hours,
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    Provenance);
            },
            "TIMEZONE_CHANGED");
    }

    private static void RangeRejected()
    {
        DateTime source =
            new DateTime(
                DateTime.MaxValue.Ticks,
                DateTimeKind.Unspecified);

        ExpectGuard(
            delegate { Convert(source); },
            "UTC_CONVERSION_RANGE");
    }

    private static void SourceUnchanged()
    {
        DateTime source =
            new DateTime(
                U(2026, 9, 14, 21, 0, 0).Ticks + 1,
                DateTimeKind.Unspecified);

        long ticks = source.Ticks;
        DateTimeKind kind = source.Kind;

        var result = Convert(source);

        Check(source.Ticks == ticks, "SOURCE_TICKS_CHANGED");
        Check(source.Kind == kind, "SOURCE_KIND_CHANGED");
        Check(result.SourceTicks == ticks, "RESULT_SOURCE_CHANGED");
    }

    private static void SameTicksUtcRelabelNotRepair()
    {
        DateTime raw =
            new DateTime(
                U(2026, 9, 14, 21, 0, 0).Ticks + 1,
                DateTimeKind.Unspecified);

        DateTime relabeled =
            new DateTime(
                raw.Ticks,
                DateTimeKind.Utc);

        var identity =
            SessionIteratorQueryDomainAdapterV1.Adapt(
                relabeled,
                Hours(Central()),
                SessionIteratorQueryDomainPolicyV1.PreserveUtc,
                Provenance);

        var converted = Convert(raw);

        Check(
            identity.QueryTicks == raw.Ticks,
            "RELABEL_TICKS_CHANGED");

        Check(
            converted.QueryTicks != identity.QueryTicks,
            "REAL_CONVERSION_NOT_DISTINCT");

        Check(
            converted.QueryTicks - identity.QueryTicks ==
            TimeSpan.FromHours(5).Ticks,
            "EXPECTED_R53_DELTA_MISSING");
    }

    private static void InvalidProvenance()
    {
        ExpectGuard(
            delegate
            {
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    U(2026, 9, 15, 12, 0, 0),
                    Hours(Central()),
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    "bad provenance");
            },
            "PROVENANCE_INVALID");
    }

    private static Test[] Tests()
    {
        return new[]
        {
            new Test("utc_identity", UtcIdentity),
            new Test("central_unspecified", CentralBasic),
            new Test("r53_a", R53A),
            new Test("r53_b", R53B),
            new Test("r53_c", R53C),
            new Test("r53_n", R53N),
            new Test("invalid_dst", InvalidDst),
            new Test("ambiguous_dst", AmbiguousDst),
            new Test("local_rejected", LocalRejected),
            new Test("null_trading_hours", NullTradingHours),
            new Test("null_timezone", NullTimezone),
            new Test("timezone_mutation", TimezoneMutation),
            new Test("range_rejected", RangeRejected),
            new Test("source_unchanged", SourceUnchanged),
            new Test("same_ticks_utc_relabel_not_repair", SameTicksUtcRelabelNotRepair),
            new Test("invalid_provenance", InvalidProvenance)
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

        var rows = new List<object>();

        foreach (Test test in Tests())
        {
            if (one && test.Name != args[1])
                continue;

            try
            {
                test.Body();

                rows.Add(new
                {
                    name = test.Name,
                    status = "PASS",
                    detail = "NONE"
                });

                passed++;
            }
            catch (Exception error)
            {
                rows.Add(new
                {
                    name = test.Name,
                    status = "FAIL",
                    detail =
                        error.GetType().Name + ":" +
                        error.Message
                });

                failed++;
            }
        }

        int loadedNative =
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
                        "SYNTHETIC_R54_QUERY_DOMAIN_ONLY",
                    total = passed + failed,
                    passed = passed,
                    failed = failed,
                    native_ninjatrader_assemblies_loaded =
                        loadedNative,
                    account_api_calls = 0,
                    order_api_calls = 0,
                    execution_authority = false,
                    results = rows
                }));

        return failed == 0 && passed > 0 ? 0 : 1;
    }
}
