// R5.7 offline-authored diagnostic host. Installation/native use requires a later gate.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using Arms.AI.Diagnostics.R57;

namespace NinjaTrader.NinjaScript.Indicators
{
    public enum ArmsHistoricalUtcCalendarCursorProfileV1 { NQ_DEC26, NQ_MAR26_DST }

    public class ArmsHistoricalUtcCalendarCursorProbeV1 : Indicator
    {
        private sealed class ProfileContract
        {
            internal readonly ArmsHistoricalUtcCalendarCursorProfileV1 Id;
            internal readonly string InstrumentName, Master, Expiry, RequiredDate;
            internal ProfileContract(ArmsHistoricalUtcCalendarCursorProfileV1 id, string instrument, string expiry, string date)
            { Id = id; InstrumentName = instrument; Master = "NQ"; Expiry = expiry; RequiredDate = date; }
        }
        private static readonly ProfileContract Dec26 = new ProfileContract(
            ArmsHistoricalUtcCalendarCursorProfileV1.NQ_DEC26, "NQ DEC26", "2026-12-01", null);
        private static readonly ProfileContract Mar26 = new ProfileContract(
            ArmsHistoricalUtcCalendarCursorProfileV1.NQ_MAR26_DST, "NQ MAR26", "2026-03-01", "2026-03-06");
        private ProfileContract profile;

        private static ProfileContract ResolveProfile(ArmsHistoricalUtcCalendarCursorProfileV1 selected)
        {
            switch (selected)
            {
                case ArmsHistoricalUtcCalendarCursorProfileV1.NQ_DEC26: return Dec26;
                case ArmsHistoricalUtcCalendarCursorProfileV1.NQ_MAR26_DST: return Mar26;
                default: throw new InvalidOperationException();
            }
        }
        private readonly object sync = new object();
        // This gate covers only cancellation admission / the final rename, never
        // cursor, hashing, writes, flushes or the ordinary state lock.
        private readonly object sealPublication = new object();
        private int terminationIntent;
        private ArmsHistoricalUtcCalendarCursorProbeV1 owner;
        private bool opportunity, terminal, terminated, submitting, traversing, callbackEntered, ready;
        private BarsRequest request;
        private Bars returnedBars;
        private TradingHours requestedHours, returnedHours;
        private int requestAttempts, constructorAttempts, cursorAttempts;
        private string output, fromText, throughText, runId, requestJson, calendarJson;
        private DateTime from, through;
        private FileStream reservation;
        private Dictionary<string, object> requestFact, before;
        private CursorResult cursor;
        private const int MaximumEvidenceBytes = 1048576;
        private const string EvidenceName = "historical-utc-calendar-cursor.json";
        private const string SealName = "historical-utc-calendar-cursor.done.json";

        [NinjaScriptProperty]
        [Display(Name = "Diagnostic profile", Order = 0, GroupName = "ARMS UTC diagnostic")]
        public ArmsHistoricalUtcCalendarCursorProfileV1 DiagnosticProfile { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Probe enabled", Order = 1, GroupName = "ARMS UTC diagnostic")]
        public bool ProbeEnabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Fresh private output directory", Order = 2, GroupName = "ARMS UTC diagnostic")]
        public string OutputDirectory { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "From UTC date yyyy-MM-dd", Order = 3, GroupName = "ARMS UTC diagnostic")]
        public string FromUtcDate { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Through UTC date yyyy-MM-dd", Order = 4, GroupName = "ARMS UTC diagnostic")]
        public string ThroughUtcDate { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "Operator confirms repository data ready and connection stable", Order = 5, GroupName = "ARMS UTC diagnostic")]
        public bool RepositoryPrerequisitesConfirmed { get; set; }

        protected override void OnStateChange()
        {
            if (owner != null && !Object.ReferenceEquals(owner, this)) return;
            State observedState = State;
            if (observedState == State.Terminated)
            {
                lock (sealPublication) Interlocked.Exchange(ref terminationIntent, 1);
                OfflinePoint("TERMINATION_INTENT");
            }
            lock (sync)
            {
                if (observedState == State.SetDefaults)
                {
                    Name = "ArmsHistoricalUtcCalendarCursorProbeV1";
                    Description = "Bounded historical UTC diagnostic; no execution authority.";
                    IsOverlay = true; IsChartOnly = true;
                    ProbeEnabled = RepositoryPrerequisitesConfirmed = false;
                    DiagnosticProfile = ArmsHistoricalUtcCalendarCursorProfileV1.NQ_DEC26;
                    OutputDirectory = FromUtcDate = ThroughUtcDate = "";
                }
                else if (observedState == State.Terminated)
                { terminated = true; terminal = true; Close(); }
                else if (observedState == State.DataLoaded && !opportunity && !terminated && !CancellationRequested)
                {
                    opportunity = true; owner = this; // Disabled opportunity cannot later rearm.
                    if (!ProbeEnabled) { terminal = true; return; }
                    try { Start(); }
                    catch (Exception error) { Fail(error); }
                }
            }
        }

        private bool CancellationRequested { get { return Interlocked.CompareExchange(ref terminationIntent, 0, 0) != 0; } }

        // Deterministic observation points exist only in synthetic test builds.
        // Installed-SDK compilation omits both the field and all calls.
#if R57_OFFLINE_TESTS
        internal Action<string> OfflineCheckpoint;
        internal bool OfflineTerminationIntent { get { return CancellationRequested; } }
#endif
        [System.Diagnostics.Conditional("R57_OFFLINE_TESTS")]
        private void OfflinePoint(string point)
        {
#if R57_OFFLINE_TESTS
            if (OfflineCheckpoint != null) OfflineCheckpoint(point);
#endif
        }

        private static void Need(bool value) { if (!value) throw new InvalidOperationException(); }
        private static Dictionary<string, object> Map(params object[] pairs)
        {
            var value = new Dictionary<string, object>();
            for (int i = 0; i < pairs.Length; i += 2) value.Add((string)pairs[i], pairs[i + 1]);
            return value;
        }
        private static string Json(object value)
        { return new JavaScriptSerializer { MaxJsonLength = MaximumEvidenceBytes }.Serialize(value); }
        private static string Hash(byte[] bytes)
        { using (var hash = SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        private static string HashText(string value) { return Hash(Encoding.UTF8.GetBytes(value)); }
        private static string Number(long value) { return value.ToString(CultureInfo.InvariantCulture); }
        private static object SessionFact(Session value)
        {
            Need(value != null);
            return Map("begin_day", (int)value.BeginDay, "begin_time", value.BeginTime,
                "end_day", (int)value.EndDay, "end_time", value.EndTime, "trading_day", (int)value.TradingDay);
        }
        private static object Transition(TimeZoneInfo.TransitionTime value)
        {
            return Map("fixed", value.IsFixedDateRule, "month", value.Month, "day", value.Day,
                "week", value.Week, "day_of_week", (int)value.DayOfWeek, "time_ticks", value.TimeOfDay.TimeOfDay.Ticks);
        }
        private static Dictionary<string, object> Calendar(TradingHours hours)
        {
            Need(hours != null && hours.Name == "CME US Index Futures ETH" && hours.Version == 5119 && hours.TimeZoneInfo != null
                && hours.TimeZoneInfo.Id == "Central Standard Time");
            Need(hours.Sessions != null && hours.Sessions.Count <= 4096 && hours.Holidays != null
                && hours.Holidays.Count <= 4096 && hours.PartialHolidays != null && hours.PartialHolidays.Count <= 4096);
            var sessions = new List<object>(); var holidays = new List<CursorTime>(); var partials = new List<object>();
            foreach (var s in hours.Sessions) sessions.Add(SessionFact(s));
            var dates = new List<DateTime>(hours.Holidays.Keys); dates.Sort();
            foreach (var date in dates) holidays.Add(CursorTime.Of(date));
            dates = new List<DateTime>(hours.PartialHolidays.Keys); dates.Sort();
            foreach (var date in dates)
            {
                var h = hours.PartialHolidays[date]; Need(h != null);
                var definitions = new List<object>();
                if (h.Sessions != null)
                { Need(h.Sessions.Count <= 32); foreach (var s in h.Sessions) definitions.Add(SessionFact(s)); }
                partials.Add(Map("date", CursorTime.Of(date), "early", h.IsEarlyEnd, "late", h.IsLateBegin,
                    "constraint", h.Constraint == null ? null : SessionFact(h.Constraint), "sessions", definitions));
            }
            var adjustments = new List<object>();
            foreach (var rule in hours.TimeZoneInfo.GetAdjustmentRules())
            {
                // The operator contract is 2026; lookback/lookahead can cross adjacent years.
                if (rule.DateEnd.Year < 2025 || rule.DateStart.Year > 2027) continue;
                adjustments.Add(Map("start", rule.DateStart.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
                    "end", rule.DateEnd.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
                    "delta_ticks", rule.DaylightDelta.Ticks, "transition_start", Transition(rule.DaylightTransitionStart),
                    "transition_end", Transition(rule.DaylightTransitionEnd)));
            }
            string rules = Json(Map("sessions", sessions, "holidays", holidays, "partials", partials));
            string zone = Json(Map("id", hours.TimeZoneInfo.Id, "base_offset_ticks", hours.TimeZoneInfo.BaseUtcOffset.Ticks,
                "supports_dst", hours.TimeZoneInfo.SupportsDaylightSavingTime, "years", new[] { 2025, 2026, 2027 }, "adjustments", adjustments));
            Need(Encoding.UTF8.GetByteCount(rules) <= 131072 && Encoding.UTF8.GetByteCount(zone) <= 32768);
            return Map("name", hours.Name, "version", hours.Version, "timezone", hours.TimeZoneInfo.Id,
                "timezone_rules_json", zone, "timezone_rules_sha256", HashText(zone),
                "calendar_rules_json", rules, "calendar_rules_sha256", HashText(rules));
        }
        private void InstrumentContract(Instrument value)
        {
            Need(profile != null && value != null && value.MasterInstrument != null
                && value.FullName == profile.InstrumentName && value.MasterInstrument.Name == profile.Master
                && value.Expiry.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) == profile.Expiry
                && value.MasterInstrument.TickSize == .25 && value.MasterInstrument.PointValue == 20);
        }
        private static void PeriodContract(BarsPeriod period)
        { Need(period != null && period.BarsPeriodType == BarsPeriodType.Minute && period.Value == 1 && period.MarketDataType == MarketDataType.Last); }
        private void EnvironmentContract()
        {
            Need(!CancellationRequested && !terminal && !terminated && ProbeEnabled && RepositoryPrerequisitesConfirmed && OutputDirectory == output
                && FromUtcDate == fromText && ThroughUtcDate == throughText
                && profile != null && DiagnosticProfile == profile.Id);
            Need(Core.Globals.GeneralOptions.TimeZoneInfo.Id == "UTC" && Connection.PlaybackConnection == null);
        }
        private Dictionary<string, object> RequestFact()
        {
            InstrumentContract(request.Instrument); PeriodContract(request.BarsPeriod);
            Need(request.MergePolicy == MergePolicy.DoNotMerge && request.LookupPolicy == LookupPolicies.Repository
                && request.IsResetOnNewTradingDay && !request.IsDividendAdjusted && !request.IsSplitAdjusted);
            Need(Object.ReferenceEquals(request.TradingHours, requestedHours));
            Need(request.FromLocal.Ticks == from.Ticks && request.ToLocal.Ticks == through.Ticks);
            var assembly = typeof(BarsRequest).Assembly;
            Need(assembly.FullName.Length <= 512 && assembly.GetName().Version.ToString() == "8.1.8.2");
            return Map("instrument", request.Instrument.FullName, "master", request.Instrument.MasterInstrument.Name,
                "expiry", request.Instrument.Expiry.ToString("yyyy-MM-dd"), "tick_size", .25, "point_value", 20,
                "period", "Minute", "period_value", 1, "market_data", "Last", "lookup", "Repository", "merge", "DoNotMerge",
                "reset", true, "dividend_adjusted", false, "split_adjusted", false,
                "configured_from", fromText, "configured_through", throughText,
                "submitted_from", CursorTime.Of(from), "submitted_through", CursorTime.Of(through),
                "actual_from", CursorTime.Of(request.FromLocal), "actual_through", CursorTime.Of(request.ToLocal),
                "trading_hours", Calendar(request.TradingHours), "application_timezone", "UTC",
                "sdk_version", assembly.GetName().Version.ToString(), "sdk_assembly", assembly.FullName,
                "sdk_mvid", assembly.ManifestModule.ModuleVersionId.ToString("D"));
        }
        private void CheckContext()
        {
            EnvironmentContract();
            Need(Json(RequestFact()) == requestJson);
            Need(Object.ReferenceEquals(request.Bars, returnedBars) && Object.ReferenceEquals(returnedBars.TradingHours, returnedHours));
            InstrumentContract(returnedBars.Instrument); PeriodContract(returnedBars.BarsPeriod);
            Need(Json(Calendar(returnedBars.TradingHours)) == calendarJson);
            if (before != null) Need(returnedBars.Count == (int)before["count"]);
        }
        private Dictionary<string, object> Snapshot()
        {
            CheckContext();
            int count = returnedBars.Count; Need(count >= 3 && count <= 10002);
            DateTime first = DateTime.MinValue, last = DateTime.MinValue;
            string digest;
            using (var hash = SHA256.Create())
            {
                byte[] header = Encoding.UTF8.GetBytes("R55_SNAPSHOT_BITS_V1|" + Number(count) + "\n");
                hash.TransformBlock(header, 0, header.Length, header, 0);
                for (int i = 0; i < count; i++)
                {
                    DateTime t = returnedBars.GetTime(i); if (i == 0) first = t; last = t;
                    long[] fields = { i, t.Ticks, (long)t.Kind, BitConverter.DoubleToInt64Bits(returnedBars.GetOpen(i)),
                        BitConverter.DoubleToInt64Bits(returnedBars.GetHigh(i)), BitConverter.DoubleToInt64Bits(returnedBars.GetLow(i)),
                        BitConverter.DoubleToInt64Bits(returnedBars.GetClose(i)), returnedBars.GetVolume(i) };
                    byte[] row = Encoding.UTF8.GetBytes(String.Join("|", Array.ConvertAll(fields, Number)) + "\n");
                    hash.TransformBlock(row, 0, row.Length, row, 0);
                }
                hash.TransformFinalBlock(new byte[0], 0, 0);
                digest = BitConverter.ToString(hash.Hash).Replace("-", "").ToLowerInvariant();
            }
            Need(returnedBars.Count == count); CheckContext();
            return Map("identity", "RETURNED_BARS_1", "callback_request_identity_verified", true, "count", count,
                "first", CursorTime.Of(first), "last", CursorTime.Of(last),
                "instrument", returnedBars.Instrument.FullName, "expiry", returnedBars.Instrument.Expiry.ToString("yyyy-MM-dd"),
                "period", "Minute", "period_value", 1, "market_data", "Last", "trading_hours", Calendar(returnedBars.TradingHours),
                "snapshot_algorithm", "R55_SNAPSHOT_BITS_V1", "snapshot_sha256", digest);
        }
        private static string DirectoryContract(string path)
        {
            Need(!String.IsNullOrWhiteSpace(path) && Path.IsPathRooted(path));
            string full = Path.GetFullPath(path), root = Path.GetPathRoot(full);
            Need(!root.StartsWith(@"\\") && Directory.Exists(full) && new DriveInfo(root).DriveType == DriveType.Fixed);
            Need(String.Equals(full.TrimEnd(Path.DirectorySeparatorChar), path.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase));
            for (var item = new DirectoryInfo(full); item != null; item = item.Parent)
                Need((item.Attributes & FileAttributes.ReparsePoint) == 0);
            return full;
        }
        private void Start()
        {
            output = OutputDirectory; fromText = FromUtcDate; throughText = ThroughUtcDate;
            profile = ResolveProfile(DiagnosticProfile); // Frozen policy; never derived from returned metadata.
            EnvironmentContract();
            from = DateTime.ParseExact(fromText, "yyyy-MM-dd", CultureInfo.InvariantCulture);
            through = DateTime.ParseExact(throughText, "yyyy-MM-dd", CultureInfo.InvariantCulture);
            Need(from.Year == 2026 && through.Year == 2026 && through >= from && (through - from).TotalDays <= 14);
            Need(profile.RequiredDate == null || (fromText == profile.RequiredDate && throughText == profile.RequiredDate));
            output = DirectoryContract(output); Need(Directory.GetFileSystemEntries(output).Length == 0);
            runId = Guid.NewGuid().ToString("D");
            reservation = new FileStream(Path.Combine(output, EvidenceName + ".tmp"), FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough);
            var instrument = Instrument.GetInstrument(profile.InstrumentName); InstrumentContract(instrument);
            constructorAttempts++;
            request = new BarsRequest(instrument, from, through);
            request.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1, MarketDataType = MarketDataType.Last };
            request.TradingHours = TradingHours.Get("CME US Index Futures ETH");
            request.MergePolicy = MergePolicy.DoNotMerge; request.LookupPolicy = LookupPolicies.Repository;
            request.IsResetOnNewTradingDay = true; request.IsDividendAdjusted = false; request.IsSplitAdjusted = false;
            requestedHours = request.TradingHours; requestFact = RequestFact(); requestJson = Json(requestFact);
            EnvironmentContract();
            requestAttempts++; submitting = true;
            try { request.Request(Completed); }
            finally { submitting = false; }
            if (terminal) Close(); else if (ready) Publish();
        }
        private void Completed(BarsRequest received, ErrorCode error, string ignoredProviderMessage)
        {
            lock (sync)
            {
                if (CancellationRequested || terminal || terminated || callbackEntered) return;
                callbackEntered = true;
                try
                {
                    Need(Object.ReferenceEquals(received, request) && error == ErrorCode.NoError);
                    returnedBars = received.Bars; Need(returnedBars != null);
                    returnedHours = returnedBars.TradingHours;
                    Need(returnedHours != null && returnedHours.Name == received.TradingHours.Name && returnedHours.Version == received.TradingHours.Version);
                    calendarJson = Json(Calendar(returnedHours));
                    Need(calendarJson == Json(Calendar(requestedHours)));
                    before = Snapshot();
                    // These are the exporter's explicit configured-date derivations, not repairs.
                    Need(cursorAttempts == 0); cursorAttempts++;
                    traversing = true;
                    try { cursor = HistoricalUtcCalendarCursorDiagnosticV1.Run(returnedBars, from, through, CheckContext); }
                    finally { traversing = false; }
                    Need(Json(before) == Json(Snapshot())); ready = true;
                    if (!submitting) Publish();
                }
                catch (Exception failure) { Fail(failure); }
            }
        }
        private Dictionary<string, object> Envelope(string schema)
        {
            return Map("schema", schema, "diagnostic_profile", profile.Id.ToString(), "run_id", runId, "classification", "DIAGNOSTIC_ONLY", "origin", "OPERATOR_NATIVE_RUN_UNATTESTED",
                "native_provenance_attested", false, "certification_evidence", false, "runtime_admission", false, "execution_authority", false,
                "exporter_invoked", false, "exporter_change", false, "stored_timestamp_mutation", false, "bars_mutation", false,
                "trading_hours_mutation", false, "paper_execution", false, "live_execution", false);
        }
        private void RequireCompleteTraversal()
        {
            Need(cursor != null && cursor.traversal_complete && cursor.paths.Count == 2);
            int n = cursor.schedule.Count;
            Need(n >= 11 && n <= HistoricalUtcCalendarCursorDiagnosticV1.MaxScheduledQueries);
            for (int i = 0; i < 2; i++)
                Need(cursor.paths[i].outcome == "COMPLETE" && cursor.paths[i].calls.Count == n
                    && cursor.paths[i].constructors.Count == (i == 0 ? 1 : n));
        }
        private void Publish()
        {
            Need(!terminal && ready && !submitting); CheckContext();
            var after = Snapshot(); Need(Json(before) == Json(after));
            // Dispose exactly once, before any completion seal. Failed cleanup cannot look complete.
            var prior = request; request = null; prior.Dispose();
            EnvironmentContract();
            var evidence = Envelope("arms.r57.historical-utc-calendar-cursor.v2");
            evidence.Add("request", requestFact); evidence.Add("bars_before", before); evidence.Add("bars_after", after);
            evidence.Add("source_preserved", true); evidence.Add("snapshot_preserved", true); evidence.Add("request_preserved", true);
            evidence.Add("cursor", cursor);
            evidence.Add("initial_query", CursorTime.Of(DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc)));
            evidence.Add("calendar_through", CursorTime.Of(DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc)));
            evidence.Add("request_attempts", requestAttempts); evidence.Add("request_constructor_attempts", constructorAttempts);
            evidence.Add("cursor_attempts", cursorAttempts);
            byte[] raw = Encoding.UTF8.GetBytes(Json(evidence) + "\n"); Need(raw.Length <= MaximumEvidenceBytes);
            var seal = Envelope("arms.r57.historical-utc-calendar-cursor.seal.v2");
            seal.Add("evidence_sha256", Hash(raw)); seal.Add("bytes", raw.Length); seal.Add("complete", true);
            byte[] sealRaw = Encoding.UTF8.GetBytes(Json(seal) + "\n"); Need(sealRaw.Length <= 4096);
            string folder = DirectoryContract(output);
            var entries = Directory.GetFileSystemEntries(folder);
            Need(entries.Length == 1 && Path.GetFullPath(entries[0]) == Path.Combine(folder, EvidenceName + ".tmp"));
            reservation.Write(raw, 0, raw.Length); reservation.Flush(true); reservation.Dispose(); reservation = null;
            EnvironmentContract();
            File.Move(Path.Combine(folder, EvidenceName + ".tmp"), Path.Combine(folder, EvidenceName));
            OfflinePoint("BODY_PUBLISHED");
            EnvironmentContract();
            RequireCompleteTraversal(); // Retain partial body, but never create its completion seal.
            using (var file = new FileStream(Path.Combine(folder, SealName + ".tmp"), FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            { file.Write(sealRaw, 0, sealRaw.Length); file.Flush(true); }
            OfflinePoint("BEFORE_SEAL_COMMIT");
            // Cancellation and the final rename have a single ordering. If
            // cancellation enters first, no final seal is published. If this
            // short commit enters first, later termination cannot undo it.
            lock (sealPublication)
            {
                EnvironmentContract();
                Need(!CancellationRequested);
                RequireCompleteTraversal();
                File.Move(Path.Combine(folder, SealName + ".tmp"), Path.Combine(folder, SealName));
            }
            terminal = true;
            try { Print("ARMS_R57_DIAGNOSTIC_COMPLETE_CONTRACT_ONLY"); } catch { }
        }
        private void Fail(Exception error)
        {
            terminal = true;
            try { Print("ARMS_R57_DIAGNOSTIC_FAILED_" + HistoricalUtcCalendarCursorDiagnosticV1.Error(error)); } catch { }
            Close();
        }
        private void Close()
        {
            if (!submitting && !traversing)
            {
                var prior = request; request = null;
                if (prior != null) try { prior.Dispose(); } catch { }
            }
            if (reservation != null) { try { reservation.Dispose(); } catch { } reservation = null; }
            // Incomplete private files are retained. No delete/overwrite/retry.
        }
    }
}
