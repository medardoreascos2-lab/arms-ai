// ARMS AI R5.2 diagnostic only.
// Raw BarsRequest DateTime domain characterization.
// No SessionIterator, account, order, execution or timestamp conversion.

using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsTimestampDomainProbeV1 : Indicator
    {
        private const string Version = "ArmsTimestampDomainProbeV1/1";
        private const string Template = "CME US Index Futures ETH";
        private const int MaximumRecords = 40;
        private const int MaximumBytes = 262144;
        private const int MaximumTransitions = 16;
        private const int MaximumDateBuckets = 32;

        private readonly object sync = new object();

        private BarsRequest request;
        private FileStream stream;
        private StreamWriter diagnostic;

        private bool attempted;
        private bool submitted;
        private bool submitting;
        private bool callbackEntered;
        private bool callbackFinished;
        private bool terminal;
        private bool terminated;

        private string directory;
        private string outputProperty;
        private string probeId;
        private string requestId;
        private string snapshotHash;
        private string sdkVersion;
        private string applicationTimezone;
        private string stage = "NOT_STARTED";

        private int records;
        private int bytes;
        private int returnedRows = -1;

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

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsTimestampDomainProbeV1";
                Description = "R5.2 raw timestamp-domain diagnostic only.";
                IsOverlay = true;
                IsChartOnly = true;

                ProbeEnabled = false;
                OutputDirectory = "";
                MarketReopenConfirmed = false;
                NqDataFlowConfirmed = false;
                ConnectionStableConfirmed = false;
            }
            else if (State == State.DataLoaded)
            {
                lock (sync)
                {
                    if (!ProbeEnabled || attempted || terminated)
                        return;

                    attempted = true;
                    outputProperty = OutputDirectory;
                    probeId = Guid.NewGuid().ToString();
                    requestId = Guid.NewGuid().ToString();

                    try
                    {
                        stage = "OUTPUT_OPEN";
                        directory = LocalDirectory(outputProperty);
                        Require(Directory.GetFileSystemEntries(directory).Length == 0);

                        stream = new FileStream(
                            Path.Combine(directory, "timestamp-domain-probe.jsonl"),
                            FileMode.CreateNew,
                            FileAccess.ReadWrite,
                            FileShare.Read,
                            4096,
                            FileOptions.WriteThrough);

                        diagnostic = new StreamWriter(stream, new UTF8Encoding(false));
                        diagnostic.NewLine = "\n";
                        diagnostic.AutoFlush = true;

                        Trace("ATTEMPT_STARTED", null);
                        ValidateEnvironment();

                        stage = "INSTRUMENT";
                        var instrument = Instrument.GetInstrument("NQ DEC26");
                        ValidateInstrument(instrument);

                        stage = "REQUEST_CREATE";

                        request = new BarsRequest(
                            instrument,
                            new DateTime(2026, 9, 16),
                            new DateTime(2026, 9, 21));

                        request.BarsPeriod = new BarsPeriod
                        {
                            BarsPeriodType = BarsPeriodType.Minute,
                            Value = 1,
                            MarketDataType = MarketDataType.Last
                        };

                        request.TradingHours = TradingHours.Get(Template);
                        request.LookupPolicy = LookupPolicies.Repository;
                        request.MergePolicy = MergePolicy.DoNotMerge;
                        request.IsResetOnNewTradingDay = true;
                        request.IsDividendAdjusted = false;
                        request.IsSplitAdjusted = false;

                        stage = "REQUEST_INVOKE";
                        submitted = true;
                        submitting = true;

                        Trace("REQUEST_SUBMITTING", null);
                        request.Request(Completed);
                        Trace("REQUEST_RETURNED", null);
                    }
                    catch (Exception error)
                    {
                        Fail(error);
                    }
                    finally
                    {
                        submitting = false;

                        if (terminal)
                            Release();
                        else if (callbackFinished)
                            Finish();
                    }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                {
                    terminated = true;

                    if (attempted && !terminal)
                    {
                        stage = "TERMINATED_INCOMPLETE";
                        Fail(new InvalidOperationException());
                    }

                    if (!submitting)
                        Release();
                }
            }
        }

        private static void Require(bool condition)
        {
            if (!condition)
                throw new InvalidOperationException();
        }

        private void ValidateEnvironment()
        {
            stage = "OPERATOR_GATES";

            Require(
                !terminated &&
                ProbeEnabled &&
                OutputDirectory == outputProperty &&
                MarketReopenConfirmed &&
                NqDataFlowConfirmed &&
                ConnectionStableConfirmed);

            stage = "SDK_VERSION";
            sdkVersion = typeof(BarsRequest).Assembly.GetName().Version.ToString();
            Require(sdkVersion == "8.1.8.2");

            stage = "TIMEZONE_PLAYBACK";
            applicationTimezone = Core.Globals.GeneralOptions.TimeZoneInfo.Id;
            Require(applicationTimezone == "UTC");
            Require(Connection.PlaybackConnection == null);
        }

        private static void ValidateInstrument(Instrument value)
        {
            Require(
                value != null &&
                value.FullName == "NQ DEC26" &&
                value.MasterInstrument.Name == "NQ" &&
                value.Expiry.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) == "2026-12-01" &&
                value.MasterInstrument.TickSize == .25 &&
                value.MasterInstrument.PointValue == 20);
        }

        private static void ValidatePeriod(BarsPeriod value)
        {
            Require(
                value != null &&
                value.BarsPeriodType == BarsPeriodType.Minute &&
                value.Value == 1 &&
                value.MarketDataType == MarketDataType.Last);
        }

        private void ValidateSnapshot(BarsRequest value)
        {
            ValidateEnvironment();
            stage = "SNAPSHOT_IDENTITY";

            Require(value != null);
            ValidateInstrument(value.Instrument);
            ValidatePeriod(value.BarsPeriod);

            Require(value.LookupPolicy == LookupPolicies.Repository);
            Require(value.MergePolicy == MergePolicy.DoNotMerge);
            Require(value.IsResetOnNewTradingDay);
            Require(!value.IsDividendAdjusted);
            Require(!value.IsSplitAdjusted);

            var bars = value.Bars;

            Require(bars != null);
            ValidateInstrument(bars.Instrument);
            ValidatePeriod(bars.BarsPeriod);

            Require(bars.TradingHours != null);
            Require(bars.TradingHours.Name == Template);
            Require(bars.TradingHours.TimeZoneInfo.Id == "Central Standard Time");

            Require(bars.Count >= 3 && bars.Count <= 10002);
        }

        private void Completed(
            BarsRequest received,
            ErrorCode error,
            string ignoredProviderMessage)
        {
            lock (sync)
            {
                if (terminal || terminated || callbackEntered)
                    return;

                callbackEntered = true;

                try
                {
                    stage = "CALLBACK_IDENTITY";
                    Require(submitted && Object.ReferenceEquals(received, request));

                    stage = "CALLBACK_ERROR";
                    Require(error == ErrorCode.NoError);

                    ValidateSnapshot(received);

                    returnedRows = received.Bars.Count;

                    stage = "SNAPSHOT_FINGERPRINT";
                    snapshotHash = Fingerprint(received.Bars);

                    Trace("SNAPSHOT_VERIFIED", null);

                    stage = "TIMESTAMP_DOMAIN";
                    object summary = Characterize(received.Bars);

                    Trace("TIMESTAMP_DOMAIN_CHARACTERIZED", summary);

                    ValidateSnapshot(received);

                    stage = "SNAPSHOT_STABILITY";
                    Require(received.Bars.Count == returnedRows);
                    Require(Fingerprint(received.Bars) == snapshotHash);

                    callbackFinished = true;

                    if (!submitting)
                        Finish();
                }
                catch (Exception error2)
                {
                    Fail(error2);
                }
            }
        }

        private object Characterize(Bars bars)
        {
            int utc = 0, unspecified = 0, local = 0;

            int firstUtc = -1, lastUtc = -1;
            int firstUnspecified = -1, lastUnspecified = -1;
            int firstLocal = -1, lastLocal = -1;

            int transitions = 0;
            int increasing = 0, duplicates = 0, decreasing = 0;
            int misaligned = 0;

            int firstDuplicate = -1;
            int firstDecrease = -1;
            int firstMisaligned = -1;

            var transitionRows = new List<object>();
            var dateBuckets = new SortedDictionary<string, int>(StringComparer.Ordinal);

            DateTime? first = null;
            DateTime? last = null;
            DateTime previous = DateTime.MinValue;

            for (int i = 0; i < returnedRows; i++)
            {
                stage = "GET_TIME";
                DateTime current = bars.GetTime(i);

                if (!first.HasValue)
                    first = current;

                last = current;

                if (current.Kind == DateTimeKind.Utc)
                {
                    utc++;
                    if (firstUtc < 0) firstUtc = i;
                    lastUtc = i;
                }
                else if (current.Kind == DateTimeKind.Unspecified)
                {
                    unspecified++;
                    if (firstUnspecified < 0) firstUnspecified = i;
                    lastUnspecified = i;
                }
                else
                {
                    local++;
                    if (firstLocal < 0) firstLocal = i;
                    lastLocal = i;
                }

                if (i > 0)
                {
                    if (current.Kind != previous.Kind)
                    {
                        transitions++;
                        Require(transitions <= MaximumTransitions);

                        transitionRows.Add(new
                        {
                            ordinal = transitions,
                            previous_index = i - 1,
                            index = i,
                            previous = Stamp(previous),
                            previous_kind = previous.Kind.ToString(),
                            current = Stamp(current),
                            current_kind = current.Kind.ToString(),
                            previous_ticks = previous.Ticks,
                            current_ticks = current.Ticks,
                            tick_delta = current.Ticks - previous.Ticks
                        });
                    }

                    if (current.Ticks > previous.Ticks)
                        increasing++;
                    else if (current.Ticks == previous.Ticks)
                    {
                        duplicates++;
                        if (firstDuplicate < 0) firstDuplicate = i;
                    }
                    else
                    {
                        decreasing++;
                        if (firstDecrease < 0) firstDecrease = i;
                    }
                }

                if (current.Ticks % TimeSpan.TicksPerMinute != 0)
                {
                    misaligned++;
                    if (firstMisaligned < 0) firstMisaligned = i;
                }

                string rawDate =
                    current.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);

                if (!dateBuckets.ContainsKey(rawDate))
                {
                    Require(dateBuckets.Count < MaximumDateBuckets);
                    dateBuckets.Add(rawDate, 0);
                }

                dateBuckets[rawDate]++;
                previous = current;
            }

            Require(bars.Count == returnedRows);
            Require(first.HasValue && last.HasValue);
            Require(utc + unspecified + local == returnedRows);
            Require(increasing + duplicates + decreasing == returnedRows - 1);

            return new
            {
                interpretation = "RAW_DATETIME_DATE_NO_TIMEZONE_INTERPRETATION",
                conversion_performed = false,
                returned_rows = returnedRows,

                first = Stamp(first),
                first_kind = first.Value.Kind.ToString(),
                first_ticks = first.Value.Ticks,

                last = Stamp(last),
                last_kind = last.Value.Kind.ToString(),
                last_ticks = last.Value.Ticks,

                utc_count = utc,
                unspecified_count = unspecified,
                local_count = local,

                first_utc_index = firstUtc,
                last_utc_index = lastUtc,
                first_unspecified_index = firstUnspecified,
                last_unspecified_index = lastUnspecified,
                first_local_index = firstLocal,
                last_local_index = lastLocal,

                transition_count = transitions,
                transition_limit = MaximumTransitions,
                transition_rows = transitionRows,

                increasing_adjacent_pairs = increasing,
                duplicate_adjacent_timestamps = duplicates,
                decreasing_adjacent_timestamps = decreasing,

                first_duplicate_index = firstDuplicate,
                first_decrease_index = firstDecrease,

                minute_misalignment_count = misaligned,
                first_minute_misalignment_index = firstMisaligned,

                raw_date_bucket_count = dateBuckets.Count,
                raw_date_buckets = dateBuckets,

                session_iterator_calls = 0,
                account_access = false,
                order_calls = 0,
                timestamp_conversion = false
            };
        }

        private string Fingerprint(Bars bars)
        {
            Require(bars != null);
            Require(bars.Count == returnedRows);

            using (var hash = SHA256.Create())
            {
                for (int i = 0; i < returnedRows; i++)
                {
                    DateTime t = bars.GetTime(i);

                    string row = String.Join("|", new[]
                    {
                        i.ToString(CultureInfo.InvariantCulture),
                        t.Ticks.ToString(CultureInfo.InvariantCulture),
                        ((int)t.Kind).ToString(CultureInfo.InvariantCulture),
                        bars.GetOpen(i).ToString("R", CultureInfo.InvariantCulture),
                        bars.GetHigh(i).ToString("R", CultureInfo.InvariantCulture),
                        bars.GetLow(i).ToString("R", CultureInfo.InvariantCulture),
                        bars.GetClose(i).ToString("R", CultureInfo.InvariantCulture),
                        bars.GetVolume(i).ToString(CultureInfo.InvariantCulture)
                    }) + "\n";

                    byte[] data = Encoding.UTF8.GetBytes(row);
                    hash.TransformBlock(data, 0, data.Length, null, 0);
                }

                hash.TransformFinalBlock(new byte[0], 0, 0);

                Require(bars.Count == returnedRows);

                return BitConverter.ToString(hash.Hash)
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        private void Trace(
            string eventName,
            object payload,
            string error = "NONE")
        {
            Require(diagnostic != null);
            Require(records < MaximumRecords);

            var row = new
            {
                schema = "arms.nt.timestamp-domain-probe.record.v1",
                classification = "DIAGNOSTIC_ONLY",
                certification_evidence = false,
                runtime_admission = false,

                probe_uuid = probeId,
                probe_version = Version,
                request_uuid = requestId,

                sequence = records,
                stage = eventName,
                operation = stage,
                state = State.ToString(),

                sdk_version = sdkVersion,
                application_timezone = applicationTimezone,

                returned_rows = returnedRows,
                snapshot_sha256 = snapshotHash,

                request_count = submitted ? 1 : 0,
                maximum_requests = 1,

                session_iterator_calls = 0,
                account_access = false,
                order_calls = 0,
                execution_authority = false,
                timestamp_conversion = false,

                payload = payload,

                exception_type = error,
                exception_message =
                    error == "NONE"
                        ? "NONE"
                        : "REDACTED_NATIVE_OR_GUARD_MESSAGE"
            };

            string line =
                new JavaScriptSerializer().Serialize(row);

            int size =
                Encoding.UTF8.GetByteCount(line) + 1;

            Require(size <= 32768);
            Require(bytes + size <= MaximumBytes);

            diagnostic.WriteLine(line);

            records++;
            bytes += size;
        }

        private void Finish()
        {
            if (
                terminal ||
                submitting ||
                !callbackFinished)
                return;

            try
            {
                ValidateSnapshot(request);

                Require(
                    Fingerprint(request.Bars) ==
                    snapshotHash);

                stage = "OUTPUT_OWNERSHIP";

                Require(
                    LocalDirectory(directory) ==
                    directory);

                var entries =
                    Directory.GetFileSystemEntries(directory);

                Require(
                    entries.Length == 1 &&
                    Path.GetFullPath(entries[0]) ==
                    Path.Combine(
                        directory,
                        "timestamp-domain-probe.jsonl"));

                Trace("EXPERIMENT_COMPLETE", null);

                stage = "DIAGNOSTIC_CLOSE";

                diagnostic.Flush();
                stream.Flush(true);
                stream.Position = 0;

                string hash;

                using (var h = SHA256.Create())
                {
                    hash =
                        BitConverter.ToString(
                            h.ComputeHash(stream))
                        .Replace("-", "")
                        .ToLowerInvariant();
                }

                diagnostic.Dispose();
                diagnostic = null;
                stream = null;

                stage = "DIAGNOSTIC_SEAL";

                string sealBase =
                    Path.Combine(
                        directory,
                        "timestamp-domain-probe.done");

                string temporary =
                    sealBase + ".tmp";

                string final =
                    sealBase + ".json";

                using (
                    var seal =
                        new StreamWriter(
                            new FileStream(
                                temporary,
                                FileMode.CreateNew,
                                FileAccess.Write,
                                FileShare.Read),
                            new UTF8Encoding(false)))
                {
                    seal.Write(
                        new JavaScriptSerializer()
                        .Serialize(
                            new
                            {
                                schema =
                                    "arms.nt.timestamp-domain-probe.seal.v1",

                                classification =
                                    "DIAGNOSTIC_ONLY",

                                probe_uuid =
                                    probeId,

                                probe_version =
                                    Version,

                                request_uuid =
                                    requestId,

                                sha256 =
                                    hash,

                                records =
                                    records,

                                bytes =
                                    bytes,

                                returned_rows =
                                    returnedRows,

                                request_count =
                                    1,

                                session_iterator_calls =
                                    0,

                                account_access =
                                    false,

                                order_calls =
                                    0,

                                execution_authority =
                                    false,

                                timestamp_conversion =
                                    false,

                                diagnostic_complete =
                                    true,

                                writer_closed =
                                    true,

                                certification_evidence =
                                    false,

                                runtime_admission =
                                    false
                            }));
                }

                File.Move(
                    temporary,
                    final);

                terminal = true;
            }
            catch (Exception error)
            {
                Fail(error);
            }
            finally
            {
                if (!submitting)
                    Release();
            }
        }

        private void Fail(Exception error)
        {
            if (terminal)
                return;

            terminal = true;

            try
            {
                Trace(
                    "ATTEMPT_FAILED",
                    null,
                    SafeError(error));
            }
            catch
            {
            }

            if (!submitting)
                Release();
        }

        private static string SafeError(
            Exception error)
        {
            if (error is UnauthorizedAccessException)
                return "UnauthorizedAccessException";

            if (error is IOException)
                return "IOException";

            if (error is ArgumentException)
                return "ArgumentException";

            if (error is InvalidOperationException)
                return "InvalidOperationException";

            if (error is NullReferenceException)
                return "NullReferenceException";

            return "OTHER";
        }

        private static string LocalDirectory(
            string value)
        {
            Require(
                !String.IsNullOrWhiteSpace(value) &&
                Path.IsPathRooted(value) &&
                !Path.GetPathRoot(value).StartsWith(@"\\") &&
                Directory.Exists(value));

            string full =
                Path.GetFullPath(value);

            Require(
                new DriveInfo(
                    Path.GetPathRoot(full))
                .DriveType ==
                DriveType.Fixed);

            for (
                var d = new DirectoryInfo(full);
                d != null;
                d = d.Parent)
            {
                Require(
                    (d.Attributes &
                    FileAttributes.ReparsePoint) ==
                    0);
            }

            return full;
        }

        private static string Stamp(
            DateTime value)
        {
            return value.ToString(
                "yyyy-MM-ddTHH:mm:ss.fffffffK",
                CultureInfo.InvariantCulture);
        }

        private static string Stamp(
            DateTime? value)
        {
            return value.HasValue
                ? Stamp(value.Value)
                : null;
        }

        private static string Hash(
            byte[] value)
        {
            using (var h = SHA256.Create())
            {
                return BitConverter.ToString(
                    h.ComputeHash(value))
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        private void Release()
        {
            var prior = request;
            request = null;

            if (prior != null)
            {
                try
                {
                    prior.Dispose();
                }
                catch
                {
                }
            }

            try
            {
                if (diagnostic != null)
                    diagnostic.Dispose();
                else if (stream != null)
                    stream.Dispose();
            }
            catch
            {
            }

            diagnostic = null;
            stream = null;
        }
    }
}
