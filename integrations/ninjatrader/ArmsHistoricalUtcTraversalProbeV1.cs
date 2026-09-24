// R5.5 offline-authored diagnostic host. Installation/native use requires a later gate.
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
using Arms.AI.Diagnostics.R55;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsHistoricalUtcTraversalProbeV1 : Indicator
    {
        private readonly object sync = new object();
        // This gate covers only cancellation admission / the final rename, never
        // traversal, hashing, writes, flushes or the ordinary state lock.
        private readonly object sealPublication = new object();
        private int terminationIntent;
        private ArmsHistoricalUtcTraversalProbeV1 owner;
        private bool opportunity, terminal, terminated, submitting, traversing, callbackEntered, ready;
        private BarsRequest request;
        private Bars returnedBars;
        private TradingHours requestedHours, returnedHours;
        private int requestAttempts, constructorAttempts, traversalAttempts;
        private string output, fromText, throughText, runId, requestJson, calendarJson;
        private DateTime from, through;
        private FileStream reservation;
        private Dictionary<string, object> requestFact, before;
        private UtcTraversalResult traversal;
        private const int MaximumEvidenceBytes = 262144;
        private const string EvidenceName = "historical-utc-traversal.json";
        private const string SealName = "historical-utc-traversal.done.json";

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
                    Name = "ArmsHistoricalUtcTraversalProbeV1";
                    Description = "Bounded historical UTC diagnostic; no execution authority.";
                    IsOverlay = true; IsChartOnly = true;
                    ProbeEnabled = RepositoryPrerequisitesConfirmed = false;
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
#if R55_OFFLINE_TESTS
        internal Action<string> OfflineCheckpoint;
        internal bool OfflineTerminationIntent { get { return CancellationRequested; } }
#endif
        [System.Diagnostics.Conditional("R55_OFFLINE_TESTS")]
        private void OfflinePoint(string point)
        {
#if R55_OFFLINE_TESTS
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
        private static string SessionText(Session value)
        {
            Need(value != null);
            return String.Join("|", new[] { Number((int)value.BeginDay), Number(value.BeginTime),
                Number((int)value.EndDay), Number(value.EndTime), Number((int)value.TradingDay) });
        }
        private static Dictionary<string, object> Calendar(TradingHours hours)
        {
            Need(hours != null && hours.Name == "CME US Index Futures ETH" && hours.TimeZoneInfo != null
                && hours.TimeZoneInfo.Id == "Central Standard Time");
            Need(hours.Sessions != null && hours.Sessions.Count <= 4096 && hours.Holidays != null
                && hours.Holidays.Count <= 4096 && hours.PartialHolidays != null && hours.PartialHolidays.Count <= 4096);
            var sessions = new List<string>(); var holidays = new List<string>(); var partials = new List<string>();
            foreach (var s in hours.Sessions) sessions.Add(SessionText(s));
            foreach (var h in hours.Holidays) holidays.Add(Number(h.Key.Ticks) + "|" + h.Key.Kind.ToString());
            foreach (var h in hours.PartialHolidays)
            {
                Need(h.Value != null);
                var definitions = new List<string>();
                if (h.Value.Sessions != null)
                {
                    Need(h.Value.Sessions.Count <= 32);
                    foreach (var s in h.Value.Sessions) definitions.Add(SessionText(s));
                }
                partials.Add(Json(new { ticks = h.Key.Ticks, kind = h.Key.Kind.ToString(), early = h.Value.IsEarlyEnd,
                    late = h.Value.IsLateBegin, constraint = h.Value.Constraint == null ? null : SessionText(h.Value.Constraint),
                    sessions = definitions }));
            }
            holidays.Sort(StringComparer.Ordinal); partials.Sort(StringComparer.Ordinal);
            string zone = hours.TimeZoneInfo.ToSerializedString();
            Need(Encoding.UTF8.GetByteCount(zone) <= 32768);
            string rules = Json(new { sessions = sessions, holidays = holidays, partials = partials });
            Need(Encoding.UTF8.GetByteCount(rules) <= 65536);
            return Map("name", hours.Name, "version", hours.Version, "timezone", hours.TimeZoneInfo.Id,
                "timezone_rules_sha256", HashText(zone), "calendar_rules_sha256", HashText(rules));
        }
        private static void InstrumentContract(Instrument value)
        {
            Need(value != null && value.FullName == "NQ DEC26" && value.MasterInstrument.Name == "NQ"
                && value.Expiry.ToString("yyyy-MM-dd") == "2026-12-01"
                && value.MasterInstrument.TickSize == .25 && value.MasterInstrument.PointValue == 20);
        }
        private static void PeriodContract(BarsPeriod period)
        { Need(period != null && period.BarsPeriodType == BarsPeriodType.Minute && period.Value == 1 && period.MarketDataType == MarketDataType.Last); }
        private void EnvironmentContract()
        {
            Need(!CancellationRequested && !terminal && !terminated && ProbeEnabled && RepositoryPrerequisitesConfirmed && OutputDirectory == output
                && FromUtcDate == fromText && ThroughUtcDate == throughText);
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
            Need(assembly.FullName.Length <= 512);
            return Map("instrument", request.Instrument.FullName, "master", request.Instrument.MasterInstrument.Name,
                "expiry", request.Instrument.Expiry.ToString("yyyy-MM-dd"), "tick_size", .25, "point_value", 20,
                "period", "Minute", "period_value", 1, "market_data", "Last", "lookup", "Repository", "merge", "DoNotMerge",
                "reset", true, "dividend_adjusted", false, "split_adjusted", false,
                "configured_from", fromText, "configured_through", throughText,
                "submitted_from", UtcTraversalTime.Of(from), "submitted_through", UtcTraversalTime.Of(through),
                "actual_from", UtcTraversalTime.Of(request.FromLocal), "actual_through", UtcTraversalTime.Of(request.ToLocal),
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
                "first", UtcTraversalTime.Of(first), "last", UtcTraversalTime.Of(last),
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
            EnvironmentContract();
            from = DateTime.ParseExact(fromText, "yyyy-MM-dd", CultureInfo.InvariantCulture);
            through = DateTime.ParseExact(throughText, "yyyy-MM-dd", CultureInfo.InvariantCulture);
            Need(from.Year == 2026 && through.Year == 2026 && through >= from && (through - from).TotalDays <= 14);
            output = DirectoryContract(output); Need(Directory.GetFileSystemEntries(output).Length == 0);
            runId = Guid.NewGuid().ToString("D");
            reservation = new FileStream(Path.Combine(output, EvidenceName + ".tmp"), FileMode.CreateNew,
                FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough);
            var instrument = Instrument.GetInstrument("NQ DEC26"); InstrumentContract(instrument);
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
                    DateTime initial = DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc);
                    DateTime limit = DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc);
                    Need(traversalAttempts == 0); traversalAttempts++;
                    traversing = true;
                    try { traversal = HistoricalUtcTraversalDiagnosticV1.Run(returnedBars, initial, limit, CheckContext); }
                    finally { traversing = false; }
                    Need(Json(before) == Json(Snapshot())); ready = true;
                    if (!submitting) Publish();
                }
                catch (Exception failure) { Fail(failure); }
            }
        }
        private Dictionary<string, object> Envelope(string schema)
        {
            return Map("schema", schema, "run_id", runId, "classification", "DIAGNOSTIC_ONLY", "origin", "OPERATOR_NATIVE_RUN_UNATTESTED",
                "native_provenance_attested", false, "certification_evidence", false, "runtime_admission", false, "execution_authority", false,
                "exporter_invoked", false, "exporter_change", false, "stored_timestamp_mutation", false, "bars_mutation", false,
                "trading_hours_mutation", false, "paper_execution", false, "live_execution", false);
        }
        private void Publish()
        {
            Need(!terminal && ready && !submitting); CheckContext();
            var after = Snapshot(); Need(Json(before) == Json(after));
            // Dispose exactly once, before any completion seal. Failed cleanup cannot look complete.
            var prior = request; request = null; prior.Dispose();
            EnvironmentContract();
            var evidence = Envelope("arms.r55.historical-utc-traversal.v1");
            evidence.Add("request", requestFact); evidence.Add("bars_before", before); evidence.Add("bars_after", after);
            evidence.Add("source_preserved", true); evidence.Add("snapshot_preserved", true); evidence.Add("request_preserved", true);
            evidence.Add("traversal", traversal);
            evidence.Add("initial_query", UtcTraversalTime.Of(DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc)));
            evidence.Add("calendar_through", UtcTraversalTime.Of(DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc)));
            evidence.Add("request_attempts", requestAttempts); evidence.Add("request_constructor_attempts", constructorAttempts);
            evidence.Add("traversal_attempts", traversalAttempts);
            byte[] raw = Encoding.UTF8.GetBytes(Json(evidence) + "\n"); Need(raw.Length <= MaximumEvidenceBytes);
            var seal = Envelope("arms.r55.historical-utc-traversal.seal.v1");
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
                File.Move(Path.Combine(folder, SealName + ".tmp"), Path.Combine(folder, SealName));
            }
            terminal = true;
            try { Print("ARMS_R55_DIAGNOSTIC_COMPLETE_CONTRACT_ONLY"); } catch { }
        }
        private void Fail(Exception error)
        {
            terminal = true;
            try { Print("ARMS_R55_DIAGNOSTIC_FAILED_" + HistoricalUtcTraversalDiagnosticV1.Error(error)); } catch { }
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
