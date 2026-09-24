// ARMS AI R5.4-A
// Narrow SessionIterator query-domain adapter.
// Does not mutate Bars, historical data, TradingHours, connections or accounts.

using System;
using System.Security.Cryptography;
using System.Text;
using NinjaTrader.Data;

namespace Arms.AI.Diagnostics.R54
{
    internal sealed class SessionIteratorQueryDomainGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }

        internal SessionIteratorQueryDomainGuardException(string guard)
            : base(guard)
        {
            GuardId = guard;
        }
    }

    internal enum SessionIteratorQueryDomainPolicyV1
    {
        PreserveUtc = 1,
        TradingHoursWallClockToUtc = 2
    }

    internal sealed class SessionIteratorQueryDomainResultV1
    {
        public DateTime Source { get; private set; }
        public DateTime Query { get; private set; }

        public long SourceTicks { get; private set; }
        public long QueryTicks { get; private set; }
        public long SourceOffsetTicks { get; private set; }

        public string SourceKind { get; private set; }
        public string QueryKind { get; private set; }

        public string ZoneId { get; private set; }
        public string ZoneFingerprintSha256 { get; private set; }

        public string Policy { get; private set; }
        public string Provenance { get; private set; }

        public bool ConversionPerformed { get; private set; }

        internal SessionIteratorQueryDomainResultV1(
            DateTime source,
            DateTime query,
            long offsetTicks,
            string zoneId,
            string zoneHash,
            SessionIteratorQueryDomainPolicyV1 policy,
            string provenance,
            bool conversionPerformed)
        {
            Source = source;
            Query = query;

            SourceTicks = source.Ticks;
            QueryTicks = query.Ticks;
            SourceOffsetTicks = offsetTicks;

            SourceKind = source.Kind.ToString();
            QueryKind = query.Kind.ToString();

            ZoneId = zoneId;
            ZoneFingerprintSha256 = zoneHash;

            Policy = policy.ToString();
            Provenance = provenance;

            ConversionPerformed = conversionPerformed;
        }
    }

    internal static class SessionIteratorQueryDomainAdapterV1
    {
        internal const string Version =
            "R5.4-A/session-iterator-query-domain-adapter/1";

        private static void Guard(bool condition, string id)
        {
            if (!condition)
                throw new SessionIteratorQueryDomainGuardException(id);
        }

        private static void ValidateProvenance(string value)
        {
            Guard(!String.IsNullOrWhiteSpace(value), "PROVENANCE_INVALID");
            Guard(value.Length <= 96, "PROVENANCE_INVALID");

            foreach (char c in value)
            {
                bool allowed =
                    (c >= 'A' && c <= 'Z') ||
                    (c >= '0' && c <= '9') ||
                    c == '_';

                Guard(allowed, "PROVENANCE_INVALID");
            }
        }

        private static string ZoneFingerprint(TimeZoneInfo zone)
        {
            Guard(zone != null, "TIMEZONE_MISSING");

            byte[] payload =
                new UTF8Encoding(false, true).GetBytes(
                    zone.ToSerializedString());

            using (SHA256 sha = SHA256.Create())
            {
                return BitConverter
                    .ToString(sha.ComputeHash(payload))
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        internal static SessionIteratorQueryDomainResultV1 Adapt(
            DateTime source,
            TradingHours tradingHours,
            SessionIteratorQueryDomainPolicyV1 policy,
            string provenance)
        {
            ValidateProvenance(provenance);

            Guard(tradingHours != null, "TRADING_HOURS_MISSING");

            TimeZoneInfo zoneBefore = tradingHours.TimeZoneInfo;

            Guard(zoneBefore != null, "TIMEZONE_MISSING");

            string zoneIdBefore = zoneBefore.Id;
            string zoneHashBefore = ZoneFingerprint(zoneBefore);

            long originalTicks = source.Ticks;
            DateTimeKind originalKind = source.Kind;

            Guard(
                source.Kind != DateTimeKind.Local,
                "SOURCE_KIND_LOCAL_REJECTED");

            DateTime query;
            long offsetTicks = 0;
            bool converted = false;

            if (source.Kind == DateTimeKind.Utc)
            {
                Guard(
                    policy == SessionIteratorQueryDomainPolicyV1.PreserveUtc,
                    "POLICY_INPUT_MISMATCH");

                query = source;
            }
            else if (source.Kind == DateTimeKind.Unspecified)
            {
                Guard(
                    policy ==
                    SessionIteratorQueryDomainPolicyV1.TradingHoursWallClockToUtc,
                    "POLICY_INPUT_MISMATCH");

                Guard(
                    !zoneBefore.IsInvalidTime(source),
                    "WALL_CLOCK_INVALID");

                Guard(
                    !zoneBefore.IsAmbiguousTime(source),
                    "WALL_CLOCK_AMBIGUOUS");

                TimeSpan offset = zoneBefore.GetUtcOffset(source);
                offsetTicks = offset.Ticks;

                long candidateTicks = source.Ticks - offsetTicks;

                Guard(
                    candidateTicks >= DateTime.MinValue.Ticks &&
                    candidateTicks <= DateTime.MaxValue.Ticks,
                    "UTC_CONVERSION_RANGE");

                try
                {
                    query = TimeZoneInfo.ConvertTimeToUtc(source, zoneBefore);
                }
                catch (ArgumentException)
                {
                    throw new SessionIteratorQueryDomainGuardException(
                        "UTC_CONVERSION_REJECTED");
                }

                Guard(
                    query.Kind == DateTimeKind.Utc,
                    "QUERY_KIND_NOT_UTC");

                Guard(
                    query.Ticks == candidateTicks,
                    "UTC_CONVERSION_INCONSISTENT");

                converted = true;
            }
            else
            {
                throw new SessionIteratorQueryDomainGuardException(
                    "SOURCE_KIND_UNSUPPORTED");
            }

            TimeZoneInfo zoneAfter = tradingHours.TimeZoneInfo;

            Guard(zoneAfter != null, "TIMEZONE_CHANGED");

            string zoneIdAfter = zoneAfter.Id;
            string zoneHashAfter = ZoneFingerprint(zoneAfter);

            Guard(
                String.Equals(
                    zoneIdBefore,
                    zoneIdAfter,
                    StringComparison.Ordinal) &&
                String.Equals(
                    zoneHashBefore,
                    zoneHashAfter,
                    StringComparison.Ordinal),
                "TIMEZONE_CHANGED");

            Guard(
                source.Ticks == originalTicks &&
                source.Kind == originalKind,
                "SOURCE_MUTATED");

            Guard(
                query.Kind == DateTimeKind.Utc,
                "QUERY_KIND_NOT_UTC");

            return new SessionIteratorQueryDomainResultV1(
                source,
                query,
                offsetTicks,
                zoneIdBefore,
                zoneHashBefore,
                policy,
                provenance,
                converted);
        }
    }
}
