// R5.3-A tests of the actual pure C# planner. No NinjaTrader doubles or assemblies.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R53;

internal static class PlanHarness
{
    private static readonly string Snapshot = new string('a', 64);
    private static readonly string Template = new string('b', 64);
    private static DateTime Raw(int y, int m, int d, int h, int min)
    { return new DateTime(y, m, d, h, min, 0, DateTimeKind.Unspecified); }
    private static TimeZoneInfo Fixed(int minutes)
    { return TimeZoneInfo.CreateCustomTimeZone("TEST_FIXED_" + minutes, TimeSpan.FromMinutes(minutes), "test", "test"); }
    private static TimeZoneInfo Seasonal()
    {
        var atTwo = new DateTime(1, 1, 1, 2, 0, 0, DateTimeKind.Unspecified);
        var start = TimeZoneInfo.TransitionTime.CreateFloatingDateRule(atTwo, 3, 2, DayOfWeek.Sunday);
        var end = TimeZoneInfo.TransitionTime.CreateFloatingDateRule(atTwo, 11, 1, DayOfWeek.Sunday);
        var rule = TimeZoneInfo.AdjustmentRule.CreateAdjustmentRule(new DateTime(2026, 1, 1),
            new DateTime(2026, 12, 31), TimeSpan.FromHours(1), start, end);
        return TimeZoneInfo.CreateCustomTimeZone("TEST_DST_2026", TimeSpan.FromHours(-6),
            "test", "test standard", "test daylight", new[] { rule });
    }
    private static TimestampQueryPlan Plan(TimeZoneInfo zone)
    { return SessionTimestampPlanV1.Build(Raw(2026, 9, 15, 22, 1), Raw(2026, 9, 21, 21, 0), 5520, Snapshot, Template, zone); }
    private static void Check(bool ok, string id)
    { if (!ok) throw new InvalidOperationException("TEST_" + id); }
    private static void Guard(string expected, Action action)
    {
        try { action(); }
        catch (PlanGuardException e) { Check(e.GuardId == expected && e.Message == expected, "GUARD_" + expected); return; }
        throw new InvalidOperationException("TEST_MISSING_GUARD_" + expected);
    }
    private static Dictionary<string, Action> Tests()
    {
        var t = new Dictionary<string, Action>(StringComparer.Ordinal);
        t.Add("fixed_matrix", () => {
            var p = Plan(Fixed(-300));
            Check(String.Join(",", p.Cases.Select(c => c.CaseId)) ==
                "A_U,A_LUTC,A_THUTC,B_U,B_LUTC,B_THUTC,C_U,C_LUTC,C_THUTC,R0,R1,N", "ORDER");
            Check(p.Cases.Select(c => c.Ordinal).SequenceEqual(Enumerable.Range(1,12)), "ORDINALS");
            Check(String.Join(",", p.Cases.Select(c => c.IteratorId)) ==
                "I01,I02,I03,I04,I05,I06,I07,I08,I09,I10,I10,I11", "ITERATOR_IDS");
            Check(p.Cases.All(c => c.IncludeEndTime && c.ConstructorContext == "Bars"), "CONTEXT");
            Check(p.Cases.Count(c => c.Reuse) == 1 && p.Cases[10].Reuse, "REUSE_ONLY_R1");
        });
        t.Add("limits", () => Check(SessionTimestampPlanV1.MaximumPlannedCalls == 12 &&
            SessionTimestampPlanV1.MaximumIteratorSlots == 11 && SessionTimestampPlanV1.MaximumRows == 10002, "LIMITS"));
        t.Add("source_and_reference_provenance", () => {
            var p = Plan(Fixed(-300));
            foreach (var c in p.Cases.Take(3)) {
                Check(c.SourceIndex == 0 && c.ReferenceUtc == null && c.Time.Raw.Ticks == p.RawFirst.Ticks,
                    "A_SOURCE_BINDING");
                Check(c.Provenance == "CALLER_SUPPLIED_BARS_INDEX_0", "A_PROVENANCE");
            }
            Check(p.Cases.Skip(3).All(c => !c.SourceIndex.HasValue), "NO_FALSE_INDEX");
            Check(!p.NativeProvenanceAttested && !p.TemplateCalendarValidated, "NO_NATIVE_CLAIM");
            Check(p.SnapshotSha256 == Snapshot && p.TemplateSha256 == Template, "DIGESTS");
        });
        t.Add("range_is_raw_only", () => {
            var p=Plan(Fixed(-300));
            Check(p.Cases.Take(3).All(c => c.RawTicksWithinEndpointRange), "A_RANGE");
            Check(p.Cases.Skip(3).All(c => !c.RawTicksWithinEndpointRange), "REFERENCE_OUTSIDE_RANGE");
            Check(p.Cases.All(c => c.RangeInterpretation == "RAW_TICKS_ONLY_NOT_SESSION_MEMBERSHIP"), "RANGE_LABEL");
        });
        for (int g = 0; g < 3; g++) {
            int k = g * 3;
            string family = new[] {"A","B","C"}[g];
            t.Add("kind_only_" + family, () => {
                var p=Plan(Fixed(-300)); var u=p.Cases[k].Time; var l=p.Cases[k+1].Time;
                Check(u.Raw.Kind==DateTimeKind.Unspecified && u.Query.Kind==DateTimeKind.Unspecified, "U_KIND");
                Check(u.Query.Ticks==u.Raw.Ticks && !u.KindChanged && !u.ConversionPerformed, "U_UNTOUCHED");
                Check(l.Query.Kind==DateTimeKind.Utc && l.Raw.Ticks==u.Raw.Ticks && l.Query.Ticks==u.Query.Ticks,
                    "LABEL_SAME_TICKS");
                Check(l.KindChanged && !l.ConversionPerformed && l.TickDelta==0 && l.SourceOffsetTicks==null,
                    "LABEL_NOT_CONVERSION");
            });
            t.Add("explicit_zone_" + family, () => {
                var p=Plan(Fixed(-300)); var l=p.Cases[k+1].Time; var c=p.Cases[k+2].Time;
                Check(c.Query.Kind==DateTimeKind.Utc && l.Query.Kind==DateTimeKind.Utc, "TWO_UTC_LABELS");
                Check(c.Raw.Ticks==l.Raw.Ticks && c.TickDelta==TimeSpan.FromHours(5).Ticks &&
                    c.SourceOffsetTicks==TimeSpan.FromHours(-5).Ticks && c.ConversionPerformed, "EXPLICIT_SHIFT");
                Check(c.SourceZoneId==p.SourceZoneId, "ZONE_ID");
            });
        }
        t.Add("one_tick_precision", () => {
            var p=Plan(Fixed(-300));
            for(int i=0;i<3;i++) {
                Check(p.Cases[6+i].Time.Raw.Ticks-p.Cases[3+i].Time.Raw.Ticks==1, "RAW_ONE_TICK");
                Check(p.Cases[6+i].Time.Query.Ticks-p.Cases[3+i].Time.Query.Ticks==1, "QUERY_ONE_TICK");
                Check(p.Cases[6+i].Time.Query.Ticks % TimeSpan.TicksPerSecond==1, "NO_ROUNDING");
            }
        });
        t.Add("reference_queries", () => {
            var p=Plan(Fixed(-300));
            Check(p.Cases[3].ReferenceUtc.Value==new DateTime(2026,9,14,21,0,0,DateTimeKind.Utc), "B_REF");
            Check(p.Cases[6].ReferenceUtc.Value.Ticks-p.Cases[3].ReferenceUtc.Value.Ticks==1, "C_REF");
            Check(p.Cases[9].Time.Query==new DateTime(2026,9,14,0,0,0,DateTimeKind.Utc), "R0_REF");
            Check(p.Cases[10].Time.Query.Ticks==p.Cases[7].Time.Query.Ticks &&
                p.Cases[10].Time.Query.Kind==p.Cases[7].Time.Query.Kind, "R1_EQUALS_C_LUTC");
            Check(p.Cases[11].Time.Query==new DateTime(2026,9,14,22,1,0,DateTimeKind.Utc) &&
                p.Cases[11].Provenance=="TEMPLATE_EXPECTATION_NOT_OBSERVED_BOUND", "N_REF");
        });
        t.Add("reuse_prerequisite_truth_table", () => {
            foreach(bool? result in new bool?[]{null,false,true})
                foreach(bool readable in new[]{false,true})
                    foreach(bool valid in new[]{false,true})
                        Check(SessionTimestampPlanV1.ReusePrerequisiteSatisfied(result,readable,valid)==
                            (result==true && readable && valid), "R1_PREREQUISITE");
        });
        t.Add("variable_snapshot_count", () => {
            foreach(int rows in new[]{3,4,4503,5520,10002}) {
                var p=SessionTimestampPlanV1.Build(Raw(2026,9,15,22,1),Raw(2026,9,21,21,0),rows,Snapshot,Template,Fixed(-300));
                Check(p.ReturnedRows==rows && p.Cases.Count==12, "NO_FIXED_5520_ASSUMPTION");
            }
        });
        t.Add("bad_row_count", () => {
            foreach(int rows in new[]{-1,0,2,10003,Int32.MaxValue})
                Guard("ROW_COUNT_OUT_OF_RANGE", () => SessionTimestampPlanV1.Build(
                    Raw(2026,9,15,22,1),Raw(2026,9,21,21,0),rows,Snapshot,Template,Fixed(-300)));
        });
        t.Add("reject_utc_or_local_A", () => {
            foreach(var kind in new[]{DateTimeKind.Utc,DateTimeKind.Local})
                Guard("A_NATIVE_KIND_NOT_UNSPECIFIED", () => SessionTimestampPlanV1.Build(
                    DateTime.SpecifyKind(Raw(2026,9,15,22,1),kind),Raw(2026,9,21,21,0),5520,Snapshot,Template,Fixed(-300)));
        });
        t.Add("reject_reversed_raw_endpoints", () => Guard("RAW_ENDPOINT_RANGE_REVERSED", () =>
            SessionTimestampPlanV1.Build(Raw(2026,9,15,22,1),Raw(2026,9,14,22,1),5,Snapshot,Template,Fixed(-300))));
        t.Add("reject_bad_snapshot_digest", () => {
            foreach(string digest in new[]{null,"",new string('A',64),new string('g',64),new string('a',63)})
                Guard("SNAPSHOT_DIGEST_INVALID", () => SessionTimestampPlanV1.Build(
                    Raw(2026,9,15,22,1),Raw(2026,9,21,21,0),5,digest,Template,Fixed(-300)));
        });
        t.Add("reject_bad_template_digest", () => Guard("TEMPLATE_DIGEST_INVALID", () =>
            SessionTimestampPlanV1.Build(Raw(2026,9,15,22,1),Raw(2026,9,21,21,0),5,Snapshot,"bad",Fixed(-300))));
        t.Add("reject_missing_zone", () => Guard("TH_ZONE_MISSING", () => Plan(null)));
        t.Add("reject_invalid_wall_time", () => Guard("TH_INVALID_WALL_TIME", () =>
            SessionTimestampPlanV1.Build(Raw(2026,3,8,2,30),Raw(2026,3,8,3,30),5,Snapshot,Template,Seasonal())));
        t.Add("reject_ambiguous_wall_time", () => Guard("TH_AMBIGUOUS_WALL_TIME", () =>
            SessionTimestampPlanV1.Build(Raw(2026,11,1,1,30),Raw(2026,11,1,3,30),5,Snapshot,Template,Seasonal())));
        t.Add("dst_offset_is_dynamic", () => {
            var zone=Seasonal();
            var summer=SessionTimestampPlanV1.InterpretTradingHoursUtc(Raw(2026,9,14,21,0),zone);
            var winter=SessionTimestampPlanV1.InterpretTradingHoursUtc(Raw(2026,1,14,21,0),zone);
            Check(summer.SourceOffsetTicks==TimeSpan.FromHours(-5).Ticks &&
                winter.SourceOffsetTicks==TimeSpan.FromHours(-6).Ticks, "NOT_CONSTANT_OFFSET");
        });
        t.Add("positive_fractional_offset", () => {
            var v=SessionTimestampPlanV1.InterpretTradingHoursUtc(Raw(2026,9,14,21,0).AddTicks(1),Fixed(330));
            Check(v.TickDelta == -TimeSpan.FromMinutes(330).Ticks && v.Query.Hour==15 &&
                v.Query.Minute==30 && v.Query.Ticks % TimeSpan.TicksPerSecond==1, "FRACTIONAL_OFFSET");
        });
        t.Add("zero_offset_still_explicit_conversion", () => {
            var p=Plan(TimeZoneInfo.Utc);
            Check(p.Cases[0].Time.Query.Ticks==p.Cases[2].Time.Query.Ticks &&
                !p.Cases[0].Time.ConversionPerformed && p.Cases[2].Time.ConversionPerformed, "ZERO_OFFSET_FLAGS");
        });
        t.Add("reject_min_saturation", () => Guard("TH_UTC_OUT_OF_RANGE", () =>
            SessionTimestampPlanV1.InterpretTradingHoursUtc(DateTime.MinValue,Fixed(840))));
        t.Add("reject_max_saturation", () => Guard("TH_UTC_OUT_OF_RANGE", () =>
            SessionTimestampPlanV1.InterpretTradingHoursUtc(DateTime.MaxValue,Fixed(-840))));
        t.Add("exact_datetime_limits", () => {
            var min=SessionTimestampPlanV1.InterpretTradingHoursUtc(DateTime.MinValue.AddHours(14),Fixed(840));
            var max=SessionTimestampPlanV1.InterpretTradingHoursUtc(DateTime.MaxValue.AddHours(-14),Fixed(-840));
            Check(min.Query.Ticks==DateTime.MinValue.Ticks && max.Query.Ticks==DateTime.MaxValue.Ticks, "EXACT_LIMITS");
        });
        t.Add("conversion_requires_unspecified", () => {
            var utc=DateTime.SpecifyKind(Raw(2026,9,14,21,0),DateTimeKind.Utc);
            Guard("RAW_KIND_NOT_UNSPECIFIED", () => SessionTimestampPlanV1.RawUnspecified(utc));
            Guard("LABEL_INPUT_KIND_NOT_UNSPECIFIED", () => SessionTimestampPlanV1.LabelUtc(utc));
            Guard("TH_INPUT_KIND_NOT_UNSPECIFIED", () => SessionTimestampPlanV1.InterpretTradingHoursUtc(utc,Fixed(-300)));
        });
        t.Add("readonly_controls", () => {
            var p=Plan(Fixed(-300)); bool rejected=false;
            try { ((IList<QueryControl>)p.Cases)[0]=p.Cases[1]; }
            catch(NotSupportedException) { rejected=true; }
            Check(rejected, "READONLY_COLLECTION");
            Check(typeof(QueryControl).GetProperties().All(x => x.GetSetMethod()==null), "NO_PUBLIC_SETTERS");
        });
        t.Add("input_not_mutated_and_repeatable", () => {
            DateTime first=Raw(2026,9,15,22,1).AddTicks(1), last=first.AddDays(2);
            var z=Fixed(-300);
            var p=SessionTimestampPlanV1.Build(first,last,4,Snapshot,Template,z);
            var q=SessionTimestampPlanV1.Build(first,last,4,Snapshot,Template,z);
            Check(first.Kind==DateTimeKind.Unspecified && first.Ticks % TimeSpan.TicksPerSecond==1, "INPUT_NOT_MUTATED");
            Check(p.Cases.Select(x => x.Time.Query.Ticks).SequenceEqual(q.Cases.Select(x => x.Time.Query.Ticks)), "REPEATABLE");
        });
        t.Add("no_ninjatrader_assemblies", () => Check(!AppDomain.CurrentDomain.GetAssemblies().Any(
            a => a.GetName().Name.StartsWith("NinjaTrader",StringComparison.OrdinalIgnoreCase)), "NO_NATIVE_ASSEMBLY"));
        return t;
    }
    public static int Main(string[] args)
    {
        var tests=Tests();
        string[] selected;
        if(args.Length==1 && args[0]=="--all") selected=tests.Keys.OrderBy(s=>s,StringComparer.Ordinal).ToArray();
        else if(args.Length==2 && args[0]=="--case" && tests.ContainsKey(args[1])) selected=new[]{args[1]};
        else { Console.Error.WriteLine("TEST_ARGUMENTS_INVALID"); return 2; }
        var results=new List<object>(); int failed=0;
        foreach(string name in selected) {
            try { tests[name](); results.Add(new { name=name, status="PASS", error=(string)null }); }
            catch(Exception e) { failed++; results.Add(new { name=name, status="FAIL", error=e.GetType().Name+":"+e.Message }); }
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            classification="SYNTHETIC_CORE_ONLY_NOT_NATIVE_EVIDENCE", total=selected.Length,
            passed=selected.Length-failed, failed=failed, results=results,
            native_api_calls=0, native_provenance_attested=false
        }));
        return failed==0 ? 0 : 1;
    }
}
