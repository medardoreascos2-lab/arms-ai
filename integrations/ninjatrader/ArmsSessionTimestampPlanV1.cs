// ARMS AI R5.3-A: pure diagnostic query planning. No native adapter or execution.
// Do not install this helper in NinjaTrader independently.
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;

namespace Arms.AI.Diagnostics.R53
{
    internal sealed class PlanGuardException : InvalidOperationException
    {
        public string GuardId { get; private set; }
        public PlanGuardException(string guardId) : base(guardId) { GuardId = guardId; }
    }

    internal sealed class TimeInterpretation
    {
        public DateTime Raw { get; private set; }
        public DateTime Query { get; private set; }
        public string Variant { get; private set; }
        public string Method { get; private set; }
        public string SourceZoneId { get; private set; }
        public long? SourceOffsetTicks { get; private set; }
        public bool ConversionPerformed { get; private set; }
        public bool KindChanged { get { return Raw.Kind != Query.Kind; } }
        public long TickDelta { get { return Query.Ticks - Raw.Ticks; } }
        internal TimeInterpretation(DateTime raw, DateTime query, string variant,
            string method, string zoneId, long? offsetTicks, bool converted)
        {
            Raw = raw; Query = query; Variant = variant; Method = method;
            SourceZoneId = zoneId; SourceOffsetTicks = offsetTicks;
            ConversionPerformed = converted;
        }
    }

    internal sealed class QueryControl
    {
        public int Ordinal { get; private set; }
        public string CaseId { get; private set; }
        public string Family { get; private set; }
        public string IteratorId { get; private set; }
        public bool Reuse { get; private set; }
        public string Prerequisite { get; private set; }
        public int? SourceIndex { get; private set; }
        public string Provenance { get; private set; }
        public DateTime? ReferenceUtc { get; private set; }
        public TimeInterpretation Time { get; private set; }
        public bool RawTicksWithinEndpointRange { get; private set; }
        public bool IncludeEndTime { get { return true; } }
        public string ConstructorContext { get { return "Bars"; } }
        public string RangeInterpretation { get { return "RAW_TICKS_ONLY_NOT_SESSION_MEMBERSHIP"; } }
        internal QueryControl(int ordinal, string id, string family, string iterator,
            bool reuse, string prerequisite, int? sourceIndex, string provenance,
            DateTime? referenceUtc, TimeInterpretation time, DateTime first, DateTime last)
        {
            Ordinal = ordinal; CaseId = id; Family = family; IteratorId = iterator;
            Reuse = reuse; Prerequisite = prerequisite; SourceIndex = sourceIndex;
            Provenance = provenance; ReferenceUtc = referenceUtc; Time = time;
            RawTicksWithinEndpointRange = time.Raw.Ticks >= first.Ticks && time.Raw.Ticks <= last.Ticks;
        }
    }

    internal sealed class TimestampQueryPlan
    {
        public ReadOnlyCollection<QueryControl> Cases { get; private set; }
        public DateTime RawFirst { get; private set; }
        public DateTime RawLast { get; private set; }
        public int ReturnedRows { get; private set; }
        public string SnapshotSha256 { get; private set; }
        public string TemplateSha256 { get; private set; }
        public string SourceZoneId { get; private set; }
        // These hashes are supplied by the caller. This pure helper does not attest them.
        public bool NativeProvenanceAttested { get { return false; } }
        public bool TemplateCalendarValidated { get { return false; } }
        internal TimestampQueryPlan(List<QueryControl> cases, DateTime first, DateTime last,
            int rows, string snapshotHash, string templateHash, string zoneId)
        {
            Cases = new List<QueryControl>(cases).AsReadOnly();
            RawFirst = first; RawLast = last; ReturnedRows = rows;
            SnapshotSha256 = snapshotHash; TemplateSha256 = templateHash; SourceZoneId = zoneId;
        }
    }

    internal static class SessionTimestampPlanV1
    {
        public const int MaximumPlannedCalls = 12;
        public const int MaximumIteratorSlots = 11;
        public const int MaximumRows = 10002;
        public const string Version = "R5.3-A/query-plan/1";
        private static readonly DateTime ReferenceInitialUtc =
            new DateTime(2026, 9, 14, 0, 0, 0, DateTimeKind.Utc);
        private static readonly DateTime ReferenceEndUtc =
            new DateTime(2026, 9, 14, 21, 0, 0, DateTimeKind.Utc);
        private static readonly DateTime ReferenceInteriorUtc =
            new DateTime(2026, 9, 14, 22, 1, 0, DateTimeKind.Utc);

        private static void Guard(bool ok, string id)
        {
            if (!ok) throw new PlanGuardException(id);
        }

        private static bool IsDigest(string value)
        {
            if (value == null || value.Length != 64) return false;
            foreach (char c in value)
                if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
            return true;
        }

        internal static TimeInterpretation RawUnspecified(DateTime raw)
        {
            Guard(raw.Kind == DateTimeKind.Unspecified, "RAW_KIND_NOT_UNSPECIFIED");
            return new TimeInterpretation(raw, raw, "U", "IDENTITY_RAW_CLOCK",
                null, null, false);
        }

        internal static TimeInterpretation LabelUtc(DateTime raw)
        {
            Guard(raw.Kind == DateTimeKind.Unspecified, "LABEL_INPUT_KIND_NOT_UNSPECIFIED");
            DateTime query = DateTime.SpecifyKind(raw, DateTimeKind.Utc);
            Guard(query.Ticks == raw.Ticks, "LABEL_CHANGED_TICKS");
            return new TimeInterpretation(raw, query, "LUTC", "SPECIFY_KIND_UTC_SAME_TICKS",
                null, null, false);
        }

        internal static TimeInterpretation InterpretTradingHoursUtc(DateTime raw, TimeZoneInfo zone)
        {
            Guard(raw.Kind == DateTimeKind.Unspecified, "TH_INPUT_KIND_NOT_UNSPECIFIED");
            Guard(zone != null, "TH_ZONE_MISSING");
            Guard(!String.IsNullOrWhiteSpace(zone.Id), "TH_ZONE_ID_MISSING");
            try
            {
                Guard(!zone.IsInvalidTime(raw), "TH_INVALID_WALL_TIME");
                Guard(!zone.IsAmbiguousTime(raw), "TH_AMBIGUOUS_WALL_TIME");
                TimeSpan offset = zone.GetUtcOffset(raw);
                long expectedTicks = checked(raw.Ticks - offset.Ticks);
                Guard(expectedTicks >= DateTime.MinValue.Ticks && expectedTicks <= DateTime.MaxValue.Ticks,
                    "TH_UTC_OUT_OF_RANGE");
                // Explicit source-zone overload only; never infer the machine's local zone.
                DateTime query = TimeZoneInfo.ConvertTimeToUtc(raw, zone);
                Guard(query.Kind == DateTimeKind.Utc && query.Ticks == expectedTicks,
                    "TH_CONVERSION_INCONSISTENT");
                return new TimeInterpretation(raw, query, "THUTC", "EXPLICIT_SOURCE_ZONE_TO_UTC",
                    zone.Id, offset.Ticks, true);
            }
            catch (PlanGuardException) { throw; }
            catch (OverflowException) { throw new PlanGuardException("TH_UTC_OUT_OF_RANGE"); }
            catch (ArgumentException) { throw new PlanGuardException("TH_CONVERSION_ARGUMENT_ERROR"); }
            catch (InvalidTimeZoneException) { throw new PlanGuardException("TH_ZONE_INVALID"); }
        }

        private static TimeInterpretation DirectReference(DateTime utc)
        {
            Guard(utc.Kind == DateTimeKind.Utc, "REFERENCE_KIND_NOT_UTC");
            return new TimeInterpretation(utc, utc, "REFERENCE_UTC", "PRESERVED_REFERENCE_UTC",
                null, null, false);
        }

        private static void AddFamily(List<QueryControl> cases, string family, DateTime raw,
            int? sourceIndex, string provenance, DateTime? referenceUtc,
            DateTime first, DateTime last, TimeZoneInfo zone)
        {
            // Finish all transforms before publishing any result to a caller.
            TimeInterpretation[] variants = { RawUnspecified(raw), LabelUtc(raw),
                InterpretTradingHoursUtc(raw, zone) };
            foreach (TimeInterpretation value in variants)
            {
                int ordinal = cases.Count + 1;
                cases.Add(new QueryControl(ordinal, family + "_" + value.Variant, family,
                    "I" + ordinal.ToString("00", System.Globalization.CultureInfo.InvariantCulture),
                    false, "NONE", sourceIndex, provenance, referenceUtc, value, first, last));
            }
        }

        internal static TimestampQueryPlan Build(DateTime actualFirst, DateTime actualLast,
            int returnedRows, string snapshotSha256, string templateSha256, TimeZoneInfo loadedZone)
        {
            Guard(returnedRows >= 3 && returnedRows <= MaximumRows, "ROW_COUNT_OUT_OF_RANGE");
            Guard(IsDigest(snapshotSha256), "SNAPSHOT_DIGEST_INVALID");
            Guard(IsDigest(templateSha256), "TEMPLATE_DIGEST_INVALID");
            Guard(actualFirst.Kind == DateTimeKind.Unspecified, "A_NATIVE_KIND_NOT_UNSPECIFIED");
            Guard(actualLast.Ticks >= actualFirst.Ticks, "RAW_ENDPOINT_RANGE_REVERSED");
            Guard(loadedZone != null, "TH_ZONE_MISSING");

            DateTime referenceAfterUtc = ReferenceEndUtc.AddTicks(1);
            DateTime rawB = new DateTime(ReferenceEndUtc.Ticks, DateTimeKind.Unspecified);
            DateTime rawC = new DateTime(referenceAfterUtc.Ticks, DateTimeKind.Unspecified);
            var cases = new List<QueryControl>();
            AddFamily(cases, "A", actualFirst, 0, "CALLER_SUPPLIED_BARS_INDEX_0",
                null, actualFirst, actualLast, loadedZone);
            AddFamily(cases, "B", rawB, null, "CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE",
                ReferenceEndUtc, actualFirst, actualLast, loadedZone);
            AddFamily(cases, "C", rawC, null, "CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE_PLUS_ONE_TICK",
                referenceAfterUtc, actualFirst, actualLast, loadedZone);
            cases.Add(new QueryControl(10, "R0", "R", "I10", false, "NONE", null,
                "R2_R4_REFERENCE_UTC", ReferenceInitialUtc, DirectReference(ReferenceInitialUtc),
                actualFirst, actualLast));
            cases.Add(new QueryControl(11, "R1", "R", "I10", true, "R0_TRUE_READABLE_VALID_BOUNDS", null,
                "CONSTRUCTED_CLOCK_FROM_R2_R4_REFERENCE_PLUS_ONE_TICK", referenceAfterUtc,
                LabelUtc(rawC), actualFirst, actualLast));
            cases.Add(new QueryControl(12, "N", "N", "I11", false, "NONE", null,
                "TEMPLATE_EXPECTATION_NOT_OBSERVED_BOUND", ReferenceInteriorUtc,
                DirectReference(ReferenceInteriorUtc), actualFirst, actualLast));
            Guard(cases.Count == MaximumPlannedCalls, "PLAN_CALL_COUNT_MISMATCH");
            Guard(new HashSet<string>(cases.ConvertAll(c => c.IteratorId)).Count == MaximumIteratorSlots,
                "PLAN_ITERATOR_SLOT_COUNT_MISMATCH");
            return new TimestampQueryPlan(cases, actualFirst, actualLast, returnedRows,
                snapshotSha256, templateSha256, loadedZone.Id);
        }

        // The future native adapter must supply measured facts, not assumptions.
        internal static bool ReusePrerequisiteSatisfied(bool? r0Result, bool boundsReadable, bool boundsValid)
        {
            return r0Result == true && boundsReadable && boundsValid;
        }
    }
}
