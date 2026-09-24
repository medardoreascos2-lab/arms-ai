// ARMS AI R5.4-B
// Bounded comparison of RAW / same-ticks UTC label / R5.4 adapter query.
// Diagnostic core only. No accounts, orders, ATM, connection mutation or files.

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R54
{
    internal sealed class QueryDomainNativeComparisonGuardException
        : InvalidOperationException
    {
        public string GuardId { get; private set; }

        internal QueryDomainNativeComparisonGuardException(string id)
            : base(id)
        {
            GuardId = id;
        }
    }

    internal sealed class QueryDomainNativeObservationV1
    {
        public string CaseId { get; private set; }
        public DateTime Query { get; private set; }
        public bool Returned { get; private set; }
        public DateTime? Begin { get; private set; }
        public DateTime? End { get; private set; }
        public bool BoundsReadable { get; private set; }
        public bool BoundsValid { get; private set; }
        public int ConstructorAttemptsAfter { get; private set; }
        public int CallAttemptsAfter { get; private set; }

        internal QueryDomainNativeObservationV1(
            string caseId,
            DateTime query,
            bool returned,
            DateTime? begin,
            DateTime? end,
            bool readable,
            bool valid,
            int constructors,
            int calls)
        {
            CaseId = caseId;
            Query = query;
            Returned = returned;
            Begin = begin;
            End = end;
            BoundsReadable = readable;
            BoundsValid = valid;
            ConstructorAttemptsAfter = constructors;
            CallAttemptsAfter = calls;
        }
    }

    internal sealed class QueryDomainNativeComparisonResultV1
    {
        public DateTime SourceBefore { get; private set; }
        public DateTime SourceAfter { get; private set; }

        public long SourceTicksBefore { get; private set; }
        public long SourceTicksAfter { get; private set; }

        public string SourceKindBefore { get; private set; }
        public string SourceKindAfter { get; private set; }

        public SessionIteratorQueryDomainResultV1 AdapterResult
        {
            get;
            private set;
        }

        public ReadOnlyCollection<QueryDomainNativeObservationV1>
            Observations
        {
            get;
            private set;
        }

        public int IteratorConstructorAttempts { get; private set; }
        public int GetNextSessionAttempts { get; private set; }

        public bool SourcePreserved { get; private set; }

        internal QueryDomainNativeComparisonResultV1(
            DateTime sourceBefore,
            DateTime sourceAfter,
            SessionIteratorQueryDomainResultV1 adapter,
            IList<QueryDomainNativeObservationV1> observations,
            int constructors,
            int calls)
        {
            SourceBefore = sourceBefore;
            SourceAfter = sourceAfter;

            SourceTicksBefore = sourceBefore.Ticks;
            SourceTicksAfter = sourceAfter.Ticks;

            SourceKindBefore = sourceBefore.Kind.ToString();
            SourceKindAfter = sourceAfter.Kind.ToString();

            AdapterResult = adapter;

            Observations =
                new ReadOnlyCollection<QueryDomainNativeObservationV1>(
                    new List<QueryDomainNativeObservationV1>(observations));

            IteratorConstructorAttempts = constructors;
            GetNextSessionAttempts = calls;

            SourcePreserved =
                sourceBefore.Ticks == sourceAfter.Ticks &&
                sourceBefore.Kind == sourceAfter.Kind;
        }
    }

    internal static class SessionIteratorQueryDomainNativeComparisonV1
    {
        internal const string Version =
            "R5.4-B/native-query-domain-comparison/1";

        private static void Guard(bool value, string id)
        {
            if (!value)
                throw new QueryDomainNativeComparisonGuardException(id);
        }

        private static QueryDomainNativeObservationV1 RunCase(
            Bars bars,
            string caseId,
            DateTime query,
            Action checkpoint,
            ref int constructors,
            ref int calls)
        {
            checkpoint();

            constructors++;

            SessionIterator iterator;

            try
            {
                iterator = new SessionIterator(bars);
            }
            catch
            {
                throw new QueryDomainNativeComparisonGuardException(
                    "SESSION_ITERATOR_CONSTRUCTOR_" + caseId);
            }

            checkpoint();

            calls++;

            bool returned;

            try
            {
                returned =
                    iterator.GetNextSession(query, true);
            }
            catch
            {
                throw new QueryDomainNativeComparisonGuardException(
                    "GETNEXTSESSION_" + caseId);
            }

            DateTime? begin = null;
            DateTime? end = null;

            bool readable = false;
            bool valid = false;

            if (returned)
            {
                checkpoint();

                DateTime b;

                try
                {
                    b = iterator.ActualSessionBegin;
                }
                catch
                {
                    throw new QueryDomainNativeComparisonGuardException(
                        "SESSION_BEGIN_" + caseId);
                }

                checkpoint();

                DateTime e;

                try
                {
                    e = iterator.ActualSessionEnd;
                }
                catch
                {
                    throw new QueryDomainNativeComparisonGuardException(
                        "SESSION_END_" + caseId);
                }

                begin = b;
                end = e;
                readable = true;
                valid = e > b;

                Guard(
                    valid,
                    "SESSION_BOUNDS_INVALID_" + caseId);
            }

            return new QueryDomainNativeObservationV1(
                caseId,
                query,
                returned,
                begin,
                end,
                readable,
                valid,
                constructors,
                calls);
        }

        internal static QueryDomainNativeComparisonResultV1 Compare(
            DateTime source,
            Bars bars,
            string provenance,
            Action checkpoint)
        {
            Guard(bars != null, "BARS_MISSING");
            Guard(checkpoint != null, "CHECKPOINT_MISSING");

            Guard(
                bars.TradingHours != null,
                "TRADING_HOURS_MISSING");

            Guard(
                source.Kind == DateTimeKind.Unspecified,
                "SOURCE_KIND_NOT_UNSPECIFIED");

            DateTime sourceBefore = source;

            long originalTicks = source.Ticks;
            DateTimeKind originalKind = source.Kind;

            DateTime rawQuery = source;

            DateTime sameTicksUtc =
                new DateTime(
                    source.Ticks,
                    DateTimeKind.Utc);

            SessionIteratorQueryDomainResultV1 adapter =
                SessionIteratorQueryDomainAdapterV1.Adapt(
                    source,
                    bars.TradingHours,
                    SessionIteratorQueryDomainPolicyV1
                        .TradingHoursWallClockToUtc,
                    provenance);

            Guard(
                adapter.SourceTicks == originalTicks &&
                adapter.SourceKind ==
                    DateTimeKind.Unspecified.ToString(),
                "ADAPTER_SOURCE_MISMATCH");

            Guard(
                adapter.Query.Kind == DateTimeKind.Utc,
                "ADAPTER_QUERY_NOT_UTC");

            Guard(
                adapter.ConversionPerformed,
                "ADAPTER_CONVERSION_NOT_RECORDED");

            Guard(
                sameTicksUtc.Ticks == originalTicks,
                "SAME_TICKS_QUERY_CHANGED_TICKS");

            Guard(
                adapter.Query.Ticks != sameTicksUtc.Ticks,
                "ADAPTER_NOT_DISTINCT_FROM_RELABEL");

            var observations =
                new List<QueryDomainNativeObservationV1>();

            int constructors = 0;
            int calls = 0;

            observations.Add(
                RunCase(
                    bars,
                    "C_RAW",
                    rawQuery,
                    checkpoint,
                    ref constructors,
                    ref calls));

            observations.Add(
                RunCase(
                    bars,
                    "C_SAME_TICKS",
                    sameTicksUtc,
                    checkpoint,
                    ref constructors,
                    ref calls));

            observations.Add(
                RunCase(
                    bars,
                    "C_ADAPTER",
                    adapter.Query,
                    checkpoint,
                    ref constructors,
                    ref calls));

            Guard(
                constructors == 3,
                "ITERATOR_CONSTRUCTOR_BUDGET");

            Guard(
                calls == 3,
                "GETNEXTSESSION_CALL_BUDGET");

            Guard(
                source.Ticks == originalTicks &&
                source.Kind == originalKind,
                "SOURCE_MUTATED");

            return new QueryDomainNativeComparisonResultV1(
                sourceBefore,
                source,
                adapter,
                observations,
                constructors,
                calls);
        }
    }
}
