// Opt-in R5 diagnostic only. One repository request, seven iterators, eight calls maximum.
// No account/order APIs, connection mutations, realtime subscription or history admission.
using System;
using System.Collections.Generic;
using System.Linq;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSessionDomainProbeV1 : Indicator
    {
        private const string Version = "ArmsSessionDomainProbeV1/1";
        private const string Template = "CME US Index Futures ETH";
        private const int MaximumCalls = 8, MaximumRecords = 96, MaximumBytes = 262144;
        private readonly object sync = new object();
        private ArmsSessionDomainProbeV1 owner;
        private BarsRequest request;
        private FileStream stream;
        private StreamWriter diagnostic;
        private bool attempted, submitted, submitting, callbackEntered, callbackFinished, terminal, terminated;
        private string directory, outputProperty, probeId, snapshotId, snapshotHash;
        private string stage = "NOT_STARTED", outcome = "UNRESOLVED", sdkVersion, applicationTimezone;
        private int records, bytes, calls, iterators, returnedRows = -1;
        private object coverage;
        private string templatePayload, templateHash;
        private DateTime? coveredQuery;
        private int coveredIndex = -1, coveredSession = -1, nextSessionCount, postCount;
        private readonly Dictionary<string, Observation> observations = new Dictionary<string, Observation>();
        private string[] findings = new string[0];
        private static readonly int[] SessionOffsets = { 0, 1, 2, 3, 4, 7 };
        private object templateVersion;
        private static readonly DateTime Initial = new DateTime(2026, 9, 14, 0, 0, 0, DateTimeKind.Utc);
        private static readonly DateTime FirstBegin = Initial.AddHours(-2), FirstEnd = Initial.AddHours(21);

        [NinjaScriptProperty]
        [Display(Name = "Probe enabled", Order = 1, GroupName = "ARMS diagnostic only")]
        public bool ProbeEnabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Fresh private output directory", Order = 2, GroupName = "ARMS diagnostic only")]
        public string OutputDirectory { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Operator confirms market reopened", Order = 3, GroupName = "ARMS diagnostic only")]
        public bool MarketReopenConfirmed { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Operator confirms NQ data flow", Order = 4, GroupName = "ARMS diagnostic only")]
        public bool NqDataFlowConfirmed { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Operator confirms stable connection", Order = 5, GroupName = "ARMS diagnostic only")]
        public bool ConnectionStableConfirmed { get; set; }

        private sealed class Observation
        {
            public string Case, Iterator, Constructor, Mode, Phase = "NOT_CALLED", Error = "NONE", Guard = "NONE";
            public int Index, SourceIndex = -1;
            public bool Include;
            public DateTime Query;
            public bool? Result;
            public DateTime? Begin, End;
            public bool Valid;
        }

        protected override void OnStateChange()
        {
            // Do not let a UI clone reset or close the running owner's resources.
            if (owner != null && !Object.ReferenceEquals(owner, this)) return;
            if (State == State.SetDefaults)
            {
                Name = "ArmsSessionDomainProbeV1";
                Description = "Diagnostic repository-only SessionIterator domain matrix; no historical or execution authority.";
                IsOverlay = true; IsChartOnly = true;
                ProbeEnabled = MarketReopenConfirmed = NqDataFlowConfirmed = ConnectionStableConfirmed = false;
                OutputDirectory = "";
            }
            else if (State == State.DataLoaded)
            {
                lock (sync)
                {
                    if (!ProbeEnabled || attempted || terminated) return;
                    owner = this; attempted = true; outputProperty = OutputDirectory;
                    probeId = Guid.NewGuid().ToString(); snapshotId = Guid.NewGuid().ToString();
                    try
                    {
                        stage = "OUTPUT_OPEN";
                        directory = LocalDirectory(outputProperty);
                        Require(Directory.GetFileSystemEntries(directory).Length == 0);
                        stream = new FileStream(Path.Combine(directory, "session-domain-probe.jsonl"),
                            FileMode.CreateNew, FileAccess.ReadWrite, FileShare.Read, 4096, FileOptions.WriteThrough);
                        diagnostic = new StreamWriter(stream, new UTF8Encoding(false));
                        diagnostic.NewLine = "\n"; diagnostic.AutoFlush = true;
                        Trace("ATTEMPT_STARTED", null);
                        ValidateEnvironment();
                        stage = "INSTRUMENT";
                        var instrument = Instrument.GetInstrument("NQ DEC26");
                        ValidateInstrument(instrument);
                        stage = "REQUEST_CREATE";
                        request = new BarsRequest(instrument, new DateTime(2026, 9, 16), new DateTime(2026, 9, 21));
                        request.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute,
                            Value = 1, MarketDataType = MarketDataType.Last };
                        request.TradingHours = TradingHours.Get(Template);
                        request.LookupPolicy = LookupPolicies.Repository;
                        request.MergePolicy = MergePolicy.DoNotMerge;
                        request.IsResetOnNewTradingDay = true;
                        request.IsDividendAdjusted = request.IsSplitAdjusted = false;
                        stage = "REQUEST_INVOKE"; submitted = true; submitting = true;
                        Trace("REQUEST_SUBMITTING", null);
                        request.Request(Completed);
                        Trace("REQUEST_RETURNED", null);
                    }
                    catch (Exception error) { Fail(error); }
                    finally
                    {
                        submitting = false;
                        if (terminal) Release();
                        else if (callbackFinished) Finish();
                    }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                {
                    terminated = true;
                    if (attempted && !terminal) { stage = "TERMINATED_INCOMPLETE"; Fail(new InvalidOperationException()); }
                    if (!submitting) Release();
                }
            }
        }

        private static void Require(bool condition) { if (!condition) throw new InvalidOperationException(); }

        private void ValidateEnvironment()
        {
            stage = "OPERATOR_GATES";
            Require(!terminated && ProbeEnabled && OutputDirectory == outputProperty && MarketReopenConfirmed
                && NqDataFlowConfirmed && ConnectionStableConfirmed);
            stage = "SDK_VERSION";
            sdkVersion = typeof(BarsRequest).Assembly.GetName().Version.ToString();
            Require(sdkVersion == "8.1.8.2");
            stage = "TIMEZONE_PLAYBACK";
            applicationTimezone = Core.Globals.GeneralOptions.TimeZoneInfo.Id;
            Require(applicationTimezone == "UTC" && Connection.PlaybackConnection == null);
        }

        private static void ValidateInstrument(Instrument value)
        {
            Require(value != null && value.FullName == "NQ DEC26" && value.MasterInstrument.Name == "NQ"
                && value.Expiry.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) == "2026-12-01"
                && value.MasterInstrument.TickSize == .25 && value.MasterInstrument.PointValue == 20);
        }

        private static void ValidatePeriod(BarsPeriod value)
        { Require(value != null && value.BarsPeriodType == BarsPeriodType.Minute && value.Value == 1 && value.MarketDataType == MarketDataType.Last); }

        private void ValidateSnapshot(BarsRequest value)
        {
            ValidateEnvironment(); stage = "SNAPSHOT_IDENTITY";
            ValidateInstrument(value.Instrument); ValidatePeriod(value.BarsPeriod);
            Require(value.LookupPolicy == LookupPolicies.Repository && value.MergePolicy == MergePolicy.DoNotMerge
                && value.IsResetOnNewTradingDay && !value.IsDividendAdjusted && !value.IsSplitAdjusted);
            var bars = value.Bars;
            Require(bars != null); ValidateInstrument(bars.Instrument); ValidatePeriod(bars.BarsPeriod);
            var hours = bars.TradingHours;
            Require(hours != null && value.TradingHours != null && hours.Name == Template
                && hours.TimeZoneInfo.Id == "Central Standard Time" && value.TradingHours.Name == hours.Name
                && value.TradingHours.TimeZoneInfo.Id == hours.TimeZoneInfo.Id && value.TradingHours.Version == hours.Version);
            if (templateVersion != null) Require(Object.Equals(templateVersion, hours.Version));
            Require(hours.Version > 0);
            templateVersion = hours.Version;
            var payload = TemplateText(hours);
            if (templatePayload != null) Require(payload == templatePayload);
            templatePayload = payload; templateHash = Hash(Encoding.UTF8.GetBytes(payload));
            Require(bars.Count >= 3 && bars.Count <= 10002);
        }

        private void Completed(BarsRequest received, ErrorCode error, string ignoredProviderMessage)
        {
            lock (sync)
            {
                if (terminal || terminated || callbackEntered) return;
                callbackEntered = true; // Also reject a same-thread reentrant duplicate callback.
                try
                {
                    stage = "CALLBACK_IDENTITY"; Require(submitted && Object.ReferenceEquals(received, request));
                    stage = "CALLBACK_ERROR"; Require(error == ErrorCode.NoError);
                    ValidateSnapshot(received);
                    returnedRows = received.Bars.Count;
                    stage = "SNAPSHOT_FINGERPRINT"; snapshotHash = Fingerprint(received.Bars);
                    Trace("SNAPSHOT_VERIFIED", null);
                    stage = "COVERAGE";
                    coverage = Measure(received.Bars);
                    Trace("COVERAGE_VERIFIED", null);
                    Matrix(received.Bars);
                    ValidateSnapshot(received);
                    stage = "SNAPSHOT_STABILITY";
                    Require(received.Bars.Count == returnedRows && Fingerprint(received.Bars) == snapshotHash);
                    findings = Findings(); outcome = "OBSERVATIONS_ONLY";
                    callbackFinished = true;
                    if (!submitting) Finish();
                }
                catch (Exception failure) { Fail(failure); }
            }
        }

        private SessionIterator NewIterator(Bars bars, bool template)
        {
            stage = "ITERATOR_CREATE"; Require(iterators < 7); iterators++;
            return template ? new SessionIterator(bars.TradingHours) : new SessionIterator(bars);
        }

        private void Matrix(Bars bars)
        {
            var r = NewIterator(bars, false);
            var r0 = Observe(r, "R0", "R", Initial, true, "Bars", "FRESH", -1);
            if (r0.Valid) Observe(r, "R1", "R", r0.End.Value.AddSeconds(1), true, "Bars", "REUSED", -1);
            else Skip("R1", "ANCHOR_INVALID");
            var g = Observe(NewIterator(bars, false), "G", "G", FirstEnd.AddSeconds(1), true, "Bars", "FRESH", -1);
            var n = Observe(NewIterator(bars, false), "N", "N", FirstBegin.AddDays(1).AddSeconds(1), true, "Bars", "FRESH", -1);
            Observation c = null;
            if (coveredQuery.HasValue)
                c = Observe(NewIterator(bars, false), "C", "C", coveredQuery.Value, true, "Bars", "FRESH", coveredIndex);
            else Skip("C", "NO_COVERED_INTERIOR_TIMESTAMP");
            bool endpoint = g.Result == false && n.Valid;
            foreach (var id in new[] { "E_TRUE", "E_FALSE" })
                if (endpoint) Observe(NewIterator(bars, false), id, id, FirstEnd, id == "E_TRUE", "Bars", "FRESH", -1);
                else Skip(id, "PREDICATE_FALSE");
            if (nextSessionCount == 0 || (n.Result == false && c != null && c.Valid))
                Observe(NewIterator(bars, true), "T_NEXT", "T_NEXT", FirstBegin.AddDays(1).AddSeconds(1), true, "TradingHours", "FRESH", -1);
            else Skip("T_NEXT", "PREDICATE_FALSE");
        }

        private void Skip(string id, string reason)
        { Trace("CASE_SKIPPED", new Observation { Case = id, Index = -1, Guard = reason }); }

        private Observation Observe(SessionIterator iterator, string id, string identity, DateTime query,
            bool include, string constructor, string mode, int sourceIndex)
        {
            ValidateSnapshot(request);
            Require(!observations.ContainsKey(id) && calls < MaximumCalls);
            var value = new Observation { Case = id, Iterator = identity, Index = calls, Query = query,
                Include = include, Constructor = constructor, Mode = mode, SourceIndex = sourceIndex };
            observations.Add(id, value);
            Trace("CALL_BEGIN", value);
            calls++;
            try
            {
                value.Phase = "GET_NEXT_SESSION";
                value.Result = iterator.GetNextSession(query, include);
                if (value.Result.Value)
                {
                    value.Phase = "BEGIN_READ"; value.Begin = iterator.ActualSessionBegin;
                    value.Phase = "END_READ"; value.End = iterator.ActualSessionEnd;
                    value.Phase = "BOUNDS_GUARD";
                    if (value.Begin.Value.Kind != DateTimeKind.Utc || value.End.Value.Kind != DateTimeKind.Utc)
                        value.Guard = "UTC_KIND_REQUIRED";
                    else if (value.Begin >= value.End) value.Guard = "REVERSED_OR_EMPTY_BOUNDS";
                    else
                    {
                        int expected = id == "R0" || id == "E_TRUE" ? 0 : id == "C" ? coveredSession : 1;
                        // E_FALSE may select either adjacent session; record that observation without assuming which.
                        bool match = value.Begin == FirstBegin.AddDays(SessionOffsets[expected])
                            && value.End == FirstEnd.AddDays(SessionOffsets[expected]);
                        if (id == "E_FALSE") match = match || (value.Begin == FirstBegin && value.End == FirstEnd);
                        if (!match) value.Guard = "TEMPLATE_BOUNDS_MISMATCH";
                        else value.Valid = true;
                    }
                }
                value.Phase = "RETURNED";
            }
            catch (Exception error) { value.Error = SafeError(error); }
            Trace("CALL_RESULT", value);
            // Preserve the observation, but never seal a comparison after an exception or invalid successful bounds.
            Require(value.Error == "NONE" && value.Guard == "NONE");
            return value;
        }

        private string[] Findings()
        {
            var result = new List<string>();
            if (postCount == 0 || !coveredQuery.HasValue) result.Add("SNAPSHOT_COVERAGE_FAILURE");
            var g = observations["G"]; var n = observations["N"];
            if (g.Result == false) result.Add("MAINTENANCE_GAP_QUERY_FALSE");
            if (n.Result == false) result.Add("DIRECT_NEXT_SESSION_QUERY_FALSE");
            Observation r, t;
            if (observations.TryGetValue("R1", out r)) result.Add(r.Result == g.Result && r.Begin == g.Begin && r.End == g.End
                ? "FRESH_ITERATOR_SAME_RESULT" : "ITERATOR_REUSE_DIFFERENCE");
            if (observations.TryGetValue("T_NEXT", out t) && (t.Result != n.Result || t.Begin != n.Begin || t.End != n.End))
                result.Add("CONSTRUCTOR_CONTEXT_DIFFERENCE");
            if (result.Count == 0 || observations["R0"].Result == false || !coveredQuery.HasValue) result.Add("UNRESOLVED");
            return result.ToArray(); // Descriptive observations, never a root cause or repair authorization.
        }

        private sealed class Bucket
        {
            public int count, first_index = -1, last_index = -1, candidate_index = -1;
            public string first, last, candidate;
            public void Add(int index, DateTime time)
            {
                if (count++ == 0) { first_index = index; first = Stamp(time); }
                last_index = index; last = Stamp(time);
            }
        }

        private object Measure(Bars bars)
        {
            var bins = new Bucket[6]; for (int j = 0; j < 6; j++) bins[j] = new Bucket();
            var dates = new SortedDictionary<string, Bucket>(StringComparer.Ordinal);
            var post = new Bucket(); var gaps = new Bucket[4];
            for (int j = 0; j < 4; j++) gaps[j] = new Bucket();
            var boundaries = new List<object>();
            int maintenance = 0, outside = 0, boundary = 0;
            DateTime previous = DateTime.MinValue, first = bars.GetTime(0), last = bars.GetTime(returnedRows - 1);
            for (int i = 0; i < returnedRows; i++)
            {
                var time = bars.GetTime(i);
                Require(time.Kind == DateTimeKind.Utc && time > previous && time.Ticks % TimeSpan.TicksPerMinute == 0);
                previous = time;
                string day = time.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                if (!dates.ContainsKey(day)) { Require(dates.Count < 32); dates.Add(day, new Bucket()); }
                dates[day].Add(i, time);
                if (time > FirstEnd) { postCount++; post.Add(i, time); }
                bool member = false, gap = false;
                for (int j = 0; j < 6; j++)
                {
                    var begin = FirstBegin.AddDays(SessionOffsets[j]); var end = FirstEnd.AddDays(SessionOffsets[j]);
                    if (time == begin || time == end) { boundary++; boundaries.Add(new { index = i, time = Stamp(time) }); }
                    if (time > begin && time <= end)
                    {
                        member = true; bins[j].Add(i, time);
                        if (i > 0 && i < returnedRows - 1 && time < end && bins[j].candidate_index < 0)
                        { bins[j].candidate_index = i; bins[j].candidate = Stamp(time); }
                        if (j > 0 && !coveredQuery.HasValue && bins[j].candidate_index == i)
                        { coveredQuery = time; coveredIndex = i; coveredSession = j; }
                    }
                    if (j < 4 && time > end && time <= end.AddHours(1)) { gap = true; gaps[j].Add(i, time); }
                }
                if (!member) { if (gap) maintenance++; else outside++; }
            }
            Require(bars.Count == returnedRows);
            nextSessionCount = bins[1].count;
            return new { returned_rows = returnedRows, first = Stamp(first), first_kind = first.Kind.ToString(),
                last = Stamp(last), last_kind = last.Kind.ToString(), strictly_ordered = true,
                first_last_may_be_partial = true, after_first_session_count = postCount,
                session_bins = bins, utc_dates = dates, post_first = post, maintenance_bins = gaps, boundary_points = boundaries,
                maintenance_count = maintenance, outside_count = outside,
                exact_boundary_count = boundary, covered_source_index = coveredIndex, covered_query = Stamp(coveredQuery),
                covered_session = coveredSession, membership = "TEMPLATE_EXPECTATION_MINUTE_CLOSE_BEGIN_EXCLUSIVE_END_INCLUSIVE" };
        }

        private static string SessionText(Session s)
        { return String.Join(",", new[] { ((int)s.BeginDay).ToString(CultureInfo.InvariantCulture), s.BeginTime.ToString(CultureInfo.InvariantCulture),
            ((int)s.EndDay).ToString(CultureInfo.InvariantCulture), s.EndTime.ToString(CultureInfo.InvariantCulture), ((int)s.TradingDay).ToString(CultureInfo.InvariantCulture) }); }

        private static string TemplateText(TradingHours hours)
        {
            Require(hours.Sessions.Count <= 64 && hours.Holidays.Count <= 512 && hours.PartialHolidays.Count <= 512);
            foreach (var offset in SessionOffsets)
            {
                Require(hours.TimeZoneInfo.GetUtcOffset(FirstBegin.AddDays(offset)) == TimeSpan.FromHours(-5));
                Require(hours.TimeZoneInfo.GetUtcOffset(FirstEnd.AddDays(offset)) == TimeSpan.FromHours(-5));
            }
            var sessions = hours.Sessions.Select(SessionText).ToArray();
            var holidays = hours.Holidays.Keys.Select(d => d.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)).OrderBy(d => d, StringComparer.Ordinal).ToArray();
            var partials = new List<string>();
            foreach (var pair in hours.PartialHolidays.OrderBy(p => p.Key))
            {
                var h = pair.Value; Require(h.Sessions.Count <= 64);
                partials.Add(pair.Key.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) + "|" + (h.IsEarlyEnd ? "1" : "0") + "|"
                    + (h.IsLateBegin ? "1" : "0") + "|" + (h.Constraint == null ? "NONE" : SessionText(h.Constraint)) + "|"
                    + String.Join(";", h.Sessions.Select(SessionText).ToArray()));
            }
            // Bind the reviewed calendar expectation to the actual returned template, not a second disk lookup.
            Require(sessions.SequenceEqual(new[] { "0,1700,1,1600,1", "1,1700,2,1600,2", "2,1700,3,1600,3",
                "3,1700,4,1600,4", "4,1700,5,1600,5" }));
            foreach (var date in holidays.Concat(partials.Select(p => p.Substring(0, 10))))
                Require(String.CompareOrdinal(date, "2026-09-13") < 0 || String.CompareOrdinal(date, "2026-09-21") > 0);
            var value = new JavaScriptSerializer().Serialize(new { sessions = sessions, holidays = holidays, partials = partials });
            Require(Encoding.UTF8.GetByteCount(value) <= 10000);
            return value;
        }

        private static string Stamp(DateTime? value)
        { return value.HasValue ? value.Value.ToString("o", CultureInfo.InvariantCulture) : null; }
        private static string Kind(DateTime? value) { return value.HasValue ? value.Value.Kind.ToString() : "NONE"; }
        private static string Hash(byte[] raw)
        { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(raw)).Replace("-", "").ToLowerInvariant(); }

        private string Fingerprint(Bars bars)
        {
            Require(bars.Count == returnedRows && returnedRows >= 3 && returnedRows <= 10002);
            var text = new StringBuilder();
            for (int i = 0; i < returnedRows; i++)
            {
                text.Append(bars.GetTime(i).ToString("o", CultureInfo.InvariantCulture)).Append('|');
                text.Append(bars.GetTime(i).Kind).Append('|');
                text.Append(bars.GetOpen(i).ToString("R", CultureInfo.InvariantCulture)).Append('|');
                text.Append(bars.GetHigh(i).ToString("R", CultureInfo.InvariantCulture)).Append('|');
                text.Append(bars.GetLow(i).ToString("R", CultureInfo.InvariantCulture)).Append('|');
                text.Append(bars.GetClose(i).ToString("R", CultureInfo.InvariantCulture)).Append('|');
                text.Append(bars.GetVolume(i).ToString(CultureInfo.InvariantCulture)).Append('\n');
                Require(text.Length <= 4 * 1024 * 1024);
            }
            Require(bars.Count == returnedRows);
            return Hash(Encoding.UTF8.GetBytes(text.ToString()));
        }

        private void Trace(string eventName, Observation value, string error = "NONE")
        {
            Require(diagnostic != null && records < MaximumRecords);
            bool isCall = eventName == "CALL_BEGIN" || eventName == "CALL_RESULT";
            var row = new {
                schema = "arms.nt.session-domain-probe.record.v1", classification = "DIAGNOSTIC_ONLY",
                certification_evidence = false, runtime_admission = false, probe_uuid = probeId, probe_version = Version,
                sequence = records, stage = eventName, operation = stage, state = State.ToString(),
                component_assembly_mvid = typeof(ArmsSessionDomainProbeV1).Assembly.ManifestModule.ModuleVersionId.ToString(),
                request_id = snapshotId, sdk_version = sdkVersion, application_timezone = applicationTimezone,
                config = new { instrument = "NQ", contract = "NQ DEC26", bars_type = "Minute", bars_value = 1, market_data_type = "Last",
                    trading_hours = Template, trading_hours_timezone = "Central Standard Time", requested_from = "2026-09-16", requested_through = "2026-09-21",
                    request_date_kind = "Unspecified", lookup_policy = "Repository", merge_policy = "DoNotMerge", reset = true,
                    split_adjusted = false, dividend_adjusted = false, market_reopen = MarketReopenConfirmed,
                    nq_flow = NqDataFlowConfirmed, connection_stable = ConnectionStableConfirmed },
                snapshot_sha256 = snapshotHash, returned_rows = returnedRows, template_version = templateVersion, template_sha256 = templateHash,
                template_payload = eventName == "SNAPSHOT_VERIFIED" ? templatePayload : null,
                coverage = eventName == "COVERAGE_VERIFIED" ? coverage : null,
                case_id = value == null ? null : value.Case, iterator_id = isCall ? value.Iterator : null,
                constructor = isCall ? value.Constructor : null, mode = isCall ? value.Mode : null,
                call_index = isCall ? value.Index : -1, source_index = isCall ? value.SourceIndex : -1,
                query = isCall ? Stamp(value.Query) : null, query_kind = isCall ? value.Query.Kind.ToString() : "NONE",
                include_end_time = isCall ? (bool?)value.Include : null,
                boolean_result = isCall ? value.Result : null,
                session_begin = isCall ? Stamp(value.Begin) : null, session_end = isCall ? Stamp(value.End) : null,
                session_begin_kind = isCall ? Kind(value.Begin) : "NONE", session_end_kind = isCall ? Kind(value.End) : "NONE",
                bounds_valid = isCall && value.Valid, guard = value == null ? "NONE" : value.Guard,
                phase = isCall ? value.Phase : "NONE", exception_type = isCall ? value.Error : error,
                exception_message = (isCall ? value.Error : error) == "NONE" ? "NONE" : "REDACTED_NATIVE_OR_GUARD_MESSAGE",
                native_calls = calls, maximum_native_calls = MaximumCalls, iterator_count = iterators, maximum_iterators = 7,
                request_count = submitted ? 1 : 0, maximum_requests = 1,
                findings = eventName == "EXPERIMENT_COMPLETE" ? findings : new string[0],
                adjudication = eventName == "EXPERIMENT_COMPLETE" ? outcome : "UNRESOLVED", root_cause = "UNRESOLVED"
            };
            string line = new JavaScriptSerializer().Serialize(row);
            int size = Encoding.UTF8.GetByteCount(line) + 1;
            Require(size <= 16384 && bytes + size <= MaximumBytes);
            diagnostic.WriteLine(line); records++; bytes += size;
        }

        private void Finish()
        {
            if (terminal || submitting || !callbackFinished) return;
            try
            {
                ValidateSnapshot(request);
                Require(Fingerprint(request.Bars) == snapshotHash);
                stage = "OUTPUT_OWNERSHIP";
                Require(LocalDirectory(directory) == directory);
                var entries = Directory.GetFileSystemEntries(directory);
                Require(entries.Length == 1 && Path.GetFullPath(entries[0]) == Path.Combine(directory, "session-domain-probe.jsonl"));
                Trace("EXPERIMENT_COMPLETE", null);
                stage = "DIAGNOSTIC_CLOSE";
                diagnostic.Flush(); stream.Flush(true); stream.Position = 0;
                string hash;
                using (var h = SHA256.Create()) hash = BitConverter.ToString(h.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                diagnostic.Dispose(); diagnostic = null; stream = null;
                stage = "DIAGNOSTIC_SEAL";
                string path = Path.Combine(directory, "session-domain-probe.done");
                using (var seal = new StreamWriter(new FileStream(path + ".tmp", FileMode.CreateNew, FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                    seal.Write(new JavaScriptSerializer().Serialize(new {
                        schema = "arms.nt.session-domain-probe.seal.v1", classification = "DIAGNOSTIC_ONLY",
                        probe_uuid = probeId, probe_version = Version, sha256 = hash, records = records, bytes = bytes,
                        native_calls = calls, iterator_count = iterators, request_count = 1, diagnostic_complete = true, writer_closed = true,
                        adjudication = outcome, findings = findings, root_cause = "UNRESOLVED", certification_evidence = false, runtime_admission = false }));
                File.Move(path + ".tmp", path + ".json");
                terminal = true;
            }
            catch (Exception error) { Fail(error); }
            finally { if (!submitting) Release(); }
        }

        private void Fail(Exception error)
        {
            if (terminal) return;
            terminal = true; outcome = "UNRESOLVED";
            try { Trace("ATTEMPT_FAILED", null, SafeError(error)); } catch { }
            if (!submitting) Release();
        }

        private static string SafeError(Exception error)
        {
            if (error is UnauthorizedAccessException) return "UnauthorizedAccessException";
            if (error is IOException) return "IOException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is InvalidOperationException) return "InvalidOperationException";
            if (error is NullReferenceException) return "NullReferenceException";
            return "OTHER";
        }

        private static string LocalDirectory(string value)
        {
            Require(!String.IsNullOrWhiteSpace(value) && Path.IsPathRooted(value)
                && !Path.GetPathRoot(value).StartsWith(@"\\") && Directory.Exists(value));
            string full = Path.GetFullPath(value);
            Require(new DriveInfo(Path.GetPathRoot(full)).DriveType == DriveType.Fixed);
            for (var d = new DirectoryInfo(full); d != null; d = d.Parent)
                Require((d.Attributes & FileAttributes.ReparsePoint) == 0);
            return full;
        }

        private void Release()
        {
            var prior = request; request = null;
            if (prior != null) try { prior.Dispose(); } catch { }
            try { if (diagnostic != null) diagnostic.Dispose(); else if (stream != null) stream.Dispose(); } catch { }
            diagnostic = null; stream = null;
        }
    }
}
