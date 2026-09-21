// Opt-in diagnostic only. One repository request, two private iterators, four calls maximum.
// No account/order APIs, connection mutations, realtime subscription or history admission.
using System;
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
    public class ArmsSessionIteratorProbeV1 : Indicator
    {
        private const string Version = "ArmsSessionIteratorProbeV1/1";
        private const string Template = "CME US Index Futures ETH";
        private const int MaximumCalls = 4, MaximumRecords = 64, MaximumBytes = 131072;
        private readonly object sync = new object();
        private ArmsSessionIteratorProbeV1 owner;
        private BarsRequest request;
        private FileStream stream;
        private StreamWriter diagnostic;
        private bool attempted, submitted, submitting, callbackEntered, callbackFinished, terminal, terminated;
        private string directory, outputProperty, probeId, snapshotId, snapshotHash;
        private string stage = "NOT_STARTED", outcome = "UNRESOLVED", sdkVersion, applicationTimezone;
        private int records, bytes, calls, returnedRows = -1;
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
            public string Sequence, Iterator, Phase = "NOT_CALLED", Error = "NONE", Guard = "NONE";
            public int Index;
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
                Name = "ArmsSessionIteratorProbeV1";
                Description = "Diagnostic repository-only SessionIterator A/B; no historical or execution authority.";
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
                        stream = new FileStream(Path.Combine(directory, "session-iterator-probe.jsonl"),
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
            templateVersion = hours.Version;
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
                    // Private instances share only the returned read-only snapshot, never iterator state.
                    stage = "ITERATOR_A_CREATE"; var a = new SessionIterator(received.Bars);
                    var firstA = Observe(a, "A_TICK", "A", 0, Initial);
                    Observation secondA = null, secondB = null;
                    if (firstA.Valid) secondA = Observe(a, "A_TICK", "A", 1, firstA.End.Value.AddTicks(1));
                    ValidateSnapshot(received);
                    stage = "ITERATOR_B_CREATE"; var b = new SessionIterator(received.Bars);
                    Require(!Object.ReferenceEquals(a, b));
                    var firstB = Observe(b, "B_SECOND", "B", 0, Initial);
                    if (firstB.Valid) secondB = Observe(b, "B_SECOND", "B", 1, firstB.End.Value.AddSeconds(1));
                    ValidateSnapshot(received);
                    stage = "SNAPSHOT_STABILITY";
                    Require(received.Bars.Count == returnedRows && Fingerprint(received.Bars) == snapshotHash);
                    outcome = Adjudicate(firstA, secondA, firstB, secondB);
                    callbackFinished = true;
                    if (!submitting) Finish();
                }
                catch (Exception failure) { Fail(failure); }
            }
        }

        private Observation Observe(SessionIterator iterator, string sequence, string identity, int index, DateTime query)
        {
            ValidateSnapshot(request);
            var value = new Observation { Sequence = sequence, Iterator = identity, Index = index, Query = query };
            stage = "CALL_LIMIT"; Require(calls < MaximumCalls);
            Trace("CALL_BEGIN", value); // Persist input before native code; failure here prevents the call.
            calls++;
            try
            {
                value.Phase = "GET_NEXT_SESSION";
                value.Result = iterator.GetNextSession(query, true);
                if (value.Result.Value)
                {
                    value.Phase = "BEGIN_READ"; value.Begin = iterator.ActualSessionBegin;
                    value.Phase = "END_READ"; value.End = iterator.ActualSessionEnd;
                    value.Phase = "BOUNDS_GUARD";
                    if (value.Begin.Value.Kind != DateTimeKind.Utc || value.End.Value.Kind != DateTimeKind.Utc)
                        value.Guard = "UTC_KIND_REQUIRED";
                    else if (value.Begin >= value.End) value.Guard = "REVERSED_OR_EMPTY_BOUNDS";
                    else if (index == 0 && (value.Begin != FirstBegin || value.End != FirstEnd)) value.Guard = "R2_ANCHOR_MISMATCH";
                    else if (index == 1 && (value.Begin != FirstBegin.AddDays(1) || value.End != FirstEnd.AddDays(1)))
                        value.Guard = "NEXT_SESSION_MISMATCH";
                    else value.Valid = true;
                }
                // No bound reads after false: stale state must not look like successful native bounds.
                value.Phase = "RETURNED";
            }
            catch (Exception error) { value.Error = SafeError(error); }
            Trace("CALL_RESULT", value);
            return value;
        }

        private static string Adjudicate(Observation a0, Observation a1, Observation b0, Observation b1)
        {
            if (!a0.Valid || !b0.Valid || a0.Begin != b0.Begin || a0.End != b0.End || a1 == null || b1 == null
                || a1.Error != "NONE" || b1.Error != "NONE" || !a1.Result.HasValue || !b1.Result.HasValue
                || (a1.Result.Value && !a1.Valid) || (b1.Result.Value && !b1.Valid)) return "UNRESOLVED";
            if (!a1.Result.Value && b1.Result.Value) return "PASS";
            if (!a1.Result.Value && !b1.Result.Value) return "FAIL";
            if (a1.Result.Value && b1.Result.Value) return "R2_FALSE_RETURN_NOT_REPRODUCED";
            return "UNRESOLVED";
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
            var row = new {
                schema = "arms.nt.session-iterator-probe.record.v1", classification = "DIAGNOSTIC_ONLY",
                certification_evidence = false, runtime_admission = false, probe_uuid = probeId, probe_version = Version,
                sequence = records, stage = eventName, operation = stage, state = State.ToString(), sdk_version = sdkVersion,
                component_assembly_mvid = typeof(ArmsSessionIteratorProbeV1).Assembly.ManifestModule.ModuleVersionId.ToString(),
                instrument = "NQ", contract = "NQ DEC26", bars_type = "Minute", bars_value = 1, market_data_type = "Last",
                trading_hours = Template, trading_hours_version = templateVersion, trading_hours_timezone = "Central Standard Time",
                application_timezone = applicationTimezone, application_timezone_required = "UTC", source_identity_verified = snapshotHash != null,
                snapshot_id = snapshotId, snapshot_sha256 = snapshotHash, returned_rows = returnedRows,
                requested_from = "2026-09-16", requested_through = "2026-09-21", lookup_policy = "Repository", merge_policy = "DoNotMerge",
                market_reopen_confirmed = MarketReopenConfirmed, nq_data_flow_confirmed = NqDataFlowConfirmed,
                connection_stable_confirmed = ConnectionStableConfirmed,
                experiment_sequence = value == null ? null : value.Sequence, iterator_local_identity = value == null ? null : value.Iterator,
                call_index = value == null ? -1 : value.Index, query = value == null ? null : Stamp(value.Query),
                query_kind = value == null ? "NONE" : value.Query.Kind.ToString(), include_end_time = true,
                boolean_result = value == null ? (bool?)null : value.Result,
                session_begin = value == null ? null : Stamp(value.Begin), session_end = value == null ? null : Stamp(value.End),
                session_begin_kind = value == null ? "NONE" : Kind(value.Begin), session_end_kind = value == null ? "NONE" : Kind(value.End),
                bounds_valid = value != null && value.Valid, guard_failure = value == null ? "NONE" : value.Guard,
                call_phase = value == null ? "NONE" : value.Phase,
                exception_type = value == null ? error : value.Error,
                exception_message = (value == null ? error : value.Error) == "NONE" ? "NONE" : "REDACTED_NATIVE_OR_GUARD_MESSAGE",
                native_calls = calls, maximum_native_calls = MaximumCalls, native_confirmation = outcome
            };
            string line = new JavaScriptSerializer().Serialize(row);
            int size = Encoding.UTF8.GetByteCount(line) + 1;
            Require(size <= 8192 && bytes + size <= MaximumBytes);
            diagnostic.WriteLine(line); records++; bytes += size;
        }

        private void Finish()
        {
            if (terminal || submitting || !callbackFinished) return;
            try
            {
                ValidateSnapshot(request);
                stage = "OUTPUT_OWNERSHIP";
                Require(LocalDirectory(directory) == directory);
                var entries = Directory.GetFileSystemEntries(directory);
                Require(entries.Length == 1 && Path.GetFullPath(entries[0]) == Path.Combine(directory, "session-iterator-probe.jsonl"));
                Trace("EXPERIMENT_COMPLETE", null);
                stage = "DIAGNOSTIC_CLOSE";
                diagnostic.Flush(); stream.Flush(true); stream.Position = 0;
                string hash;
                using (var h = SHA256.Create()) hash = BitConverter.ToString(h.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                diagnostic.Dispose(); diagnostic = null; stream = null;
                stage = "DIAGNOSTIC_SEAL";
                string path = Path.Combine(directory, "session-iterator-probe.done");
                using (var seal = new StreamWriter(new FileStream(path + ".tmp", FileMode.CreateNew, FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                    seal.Write(new JavaScriptSerializer().Serialize(new {
                        schema = "arms.nt.session-iterator-probe.seal.v1", classification = "DIAGNOSTIC_ONLY",
                        probe_uuid = probeId, probe_version = Version, sha256 = hash, records = records, bytes = bytes,
                        native_calls = calls, diagnostic_complete = true, writer_closed = true,
                        native_confirmation = outcome, certification_evidence = false, runtime_admission = false }));
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
