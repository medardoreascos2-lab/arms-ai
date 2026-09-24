// ARMS AI R5.4-C
// One-shot native diagnostic host for the bounded R5.4 repair comparison.
// No account, order, ATM, execution, connection mutation or exporter authority.

using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using Arms.AI.Diagnostics.R54;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSessionIteratorQueryDomainRepairProbeV1 : Indicator
    {
        private const string Version =
            "R5.4-C/native-repair-host/1";

        private readonly object sync = new object();

        private bool configured;
        private bool dataLoadedSeen;
        private bool terminated;
        private bool attempted;

        [NinjaScriptProperty]
        [Display(
            Name="Probe enabled",
            Order=1,
            GroupName="ARMS diagnostic only")]
        public bool ProbeEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name="Fresh private output directory",
            Order=2,
            GroupName="ARMS diagnostic only")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name="Operator confirms market reopened",
            Order=3,
            GroupName="ARMS diagnostic only")]
        public bool MarketReopenConfirmed { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name="Operator confirms NQ data flow",
            Order=4,
            GroupName="ARMS diagnostic only")]
        public bool NqDataFlowConfirmed { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name="Operator confirms stable connection",
            Order=5,
            GroupName="ARMS diagnostic only")]
        public bool ConnectionStableConfirmed { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                lock (sync)
                {
                    Name =
                        "ArmsSessionIteratorQueryDomainRepairProbeV1";

                    Description =
                        "R5.4 bounded SessionIterator query-domain repair diagnostic; no trading authority.";

                    IsOverlay = true;
                    IsChartOnly = true;

                    ProbeEnabled = false;
                    OutputDirectory = "";

                    MarketReopenConfirmed = false;
                    NqDataFlowConfirmed = false;
                    ConnectionStableConfirmed = false;
                }
            }
            else if (State == State.Configure)
            {
                lock (sync)
                {
                    if (!terminated && !dataLoadedSeen)
                        configured = true;
                }
            }
            else if (State == State.DataLoaded)
            {
                bool run = false;

                lock (sync)
                {
                    if (dataLoadedSeen || terminated)
                        return;

                    dataLoadedSeen = true;

                    if (configured &&
                        ProbeEnabled &&
                        !attempted)
                    {
                        attempted = true;
                        run = true;
                    }
                }

                if (run)
                    RunOnce();
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                    terminated = true;
            }
        }

        protected override void OnBarUpdate()
        {
        }

        private sealed class ProbeGuardException
            : InvalidOperationException
        {
            internal string GuardId { get; private set; }

            internal ProbeGuardException(string id)
                : base(id)
            {
                GuardId = id;
            }
        }

        private static void Guard(bool value, string id)
        {
            if (!value)
                throw new ProbeGuardException(id);
        }

        private static string Hash(byte[] data)
        {
            using (SHA256 sha = SHA256.Create())
            {
                return BitConverter
                    .ToString(sha.ComputeHash(data))
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        private static object Timestamp(DateTime value)
        {
            return new
            {
                clock =
                    value.ToString(
                        "yyyy-MM-ddTHH:mm:ss.fffffff"),
                ticks = value.Ticks,
                kind = value.Kind.ToString()
            };
        }

        private static string SafeGuard(Exception error)
        {
            ProbeGuardException p =
                error as ProbeGuardException;

            if (p != null)
                return p.GuardId;

            QueryDomainNativeComparisonGuardException c =
                error as QueryDomainNativeComparisonGuardException;

            if (c != null)
                return c.GuardId;

            SessionIteratorQueryDomainGuardException a =
                error as SessionIteratorQueryDomainGuardException;

            if (a != null)
                return a.GuardId;

            return "UNSPECIFIED_GUARD";
        }

        private static string SafeType(Exception error)
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

        private static string CheckedDirectory(string path)
        {
            Guard(
                !String.IsNullOrWhiteSpace(path) &&
                Path.IsPathRooted(path),
                "OUTPUT_PATH_INVALID");

            string full = Path.GetFullPath(path);
            string root = Path.GetPathRoot(full);

            Guard(
                !String.IsNullOrEmpty(root) &&
                !root.StartsWith(
                    @"\\",
                    StringComparison.Ordinal),
                "OUTPUT_NOT_LOCAL");

            Guard(
                String.Equals(
                    full.TrimEnd(Path.DirectorySeparatorChar),
                    path.TrimEnd(Path.DirectorySeparatorChar),
                    StringComparison.OrdinalIgnoreCase),
                "OUTPUT_PATH_NONCANONICAL");

            Guard(
                Directory.Exists(full),
                "OUTPUT_DIRECTORY_MISSING");

            Guard(
                new DriveInfo(root).DriveType ==
                    DriveType.Fixed,
                "OUTPUT_NOT_FIXED_DRIVE");

            for (
                DirectoryInfo directory =
                    new DirectoryInfo(full);
                directory != null;
                directory = directory.Parent)
            {
                Guard(
                    (directory.Attributes &
                     FileAttributes.ReparsePoint) == 0,
                    "OUTPUT_REPARSE_POINT");
            }

            Guard(
                Directory.GetFileSystemEntries(full).Length == 0,
                "OUTPUT_NOT_EMPTY");

            return full;
        }

        private void ValidateEnvironment(
            string expectedOutput,
            Bars expectedBars)
        {
            bool enabled;
            bool open;
            bool flow;
            bool stable;
            bool stopped;
            string output;

            lock (sync)
            {
                enabled = ProbeEnabled;
                open = MarketReopenConfirmed;
                flow = NqDataFlowConfirmed;
                stable = ConnectionStableConfirmed;
                output = OutputDirectory;
                stopped = terminated;
            }

            Guard(!stopped, "HOST_TERMINATED");
            Guard(enabled, "GATE_DISABLED");
            Guard(open, "GATE_MARKET_CLOSED");
            Guard(flow, "GATE_DATA_FLOW");
            Guard(stable, "GATE_CONNECTION_UNSTABLE");

            Guard(
                String.Equals(
                    output,
                    expectedOutput,
                    StringComparison.Ordinal),
                "OUTPUT_CHANGED");

            Bars bars = Bars;

            Guard(
                bars != null &&
                Object.ReferenceEquals(
                    bars,
                    expectedBars),
                "HOST_CHART_IDENTITY");

            Guard(
                bars.Instrument != null &&
                bars.Instrument.MasterInstrument != null &&
                bars.Instrument.FullName == "NQ DEC26" &&
                bars.Instrument.MasterInstrument.Name == "NQ" &&
                bars.Instrument.Expiry.Year == 2026 &&
                bars.Instrument.Expiry.Month == 12 &&
                bars.Instrument.MasterInstrument.TickSize == .25 &&
                bars.Instrument.MasterInstrument.PointValue == 20,
                "HOST_CHART_INSTRUMENT");

            Guard(
                bars.BarsPeriod != null &&
                bars.BarsPeriod.BarsPeriodType ==
                    BarsPeriodType.Minute &&
                bars.BarsPeriod.Value == 1 &&
                bars.BarsPeriod.MarketDataType ==
                    MarketDataType.Last,
                "HOST_CHART_PERIOD");

            Guard(
                bars.TradingHours != null &&
                bars.TradingHours.Name ==
                    "CME US Index Futures ETH" &&
                bars.TradingHours.TimeZoneInfo != null &&
                bars.TradingHours.TimeZoneInfo.Id ==
                    "Central Standard Time",
                "HOST_CHART_TEMPLATE");
        }

        private static void WriteNew(
            string path,
            byte[] data)
        {
            using (
                FileStream stream =
                    new FileStream(
                        path,
                        FileMode.CreateNew,
                        FileAccess.Write,
                        FileShare.Read,
                        4096,
                        FileOptions.WriteThrough))
            {
                stream.Write(data, 0, data.Length);
                stream.Flush(true);
            }
        }

        private void RunOnce()
        {
            string configuredOutput = OutputDirectory;
            Bars chart = Bars;

            try
            {
                ValidateEnvironment(
                    configuredOutput,
                    chart);

                string folder =
                    CheckedDirectory(configuredOutput);

                DateTime boundary =
                    new DateTime(
                        2026,
                        9,
                        14,
                        21,
                        0,
                        0,
                        DateTimeKind.Unspecified);

                DateTime source =
                    new DateTime(
                        boundary.Ticks + 1,
                        DateTimeKind.Unspecified);

                string probeId =
                    Guid.NewGuid().ToString("D");

                QueryDomainNativeComparisonResultV1 result =
                    SessionIteratorQueryDomainNativeComparisonV1.Compare(
                        source,
                        chart,
                        "R53_NATIVE_REGRESSION",
                        delegate
                        {
                            ValidateEnvironment(
                                configuredOutput,
                                chart);
                        });

                Guard(
                    result != null &&
                    result.Observations != null &&
                    result.Observations.Count == 3,
                    "COMPARISON_RESULT_INVALID");

                QueryDomainNativeObservationV1 raw =
                    result.Observations[0];

                QueryDomainNativeObservationV1 relabel =
                    result.Observations[1];

                QueryDomainNativeObservationV1 adapter =
                    result.Observations[2];

                Guard(
                    raw.CaseId == "C_RAW" &&
                    relabel.CaseId == "C_SAME_TICKS" &&
                    adapter.CaseId == "C_ADAPTER",
                    "COMPARISON_ORDER_INVALID");

                bool expectedPattern =
                    !raw.Returned &&
                    !relabel.Returned &&
                    adapter.Returned &&
                    adapter.BoundsReadable &&
                    adapter.BoundsValid;

                var observations =
                    new List<object>();

                foreach (
                    QueryDomainNativeObservationV1 item
                    in result.Observations)
                {
                    observations.Add(
                        new
                        {
                            case_id = item.CaseId,
                            query = Timestamp(item.Query),
                            returned = item.Returned,
                            begin =
                                item.Begin.HasValue
                                ? Timestamp(item.Begin.Value)
                                : null,
                            end =
                                item.End.HasValue
                                ? Timestamp(item.End.Value)
                                : null,
                            bounds_readable =
                                item.BoundsReadable,
                            bounds_valid =
                                item.BoundsValid,
                            constructor_attempts =
                                item.ConstructorAttemptsAfter,
                            call_attempts =
                                item.CallAttemptsAfter
                        });
                }

                var evidence =
                    new
                    {
                        schema =
                            "arms.r54.native-repair.record.v1",
                        version = Version,
                        classification =
                            "DIAGNOSTIC_ONLY",
                        origin =
                            "OPERATOR_NATIVE_RUN_UNATTESTED",
                        probe_uuid = probeId,
                        diagnostic_complete = true,

                        source_before =
                            Timestamp(result.SourceBefore),

                        source_after =
                            Timestamp(result.SourceAfter),

                        source_preserved =
                            result.SourcePreserved,

                        adapter =
                            new
                            {
                                source_ticks =
                                    result.AdapterResult.SourceTicks,
                                source_kind =
                                    result.AdapterResult.SourceKind,
                                query_ticks =
                                    result.AdapterResult.QueryTicks,
                                query_kind =
                                    result.AdapterResult.QueryKind,
                                source_offset_ticks =
                                    result.AdapterResult.SourceOffsetTicks,
                                zone_id =
                                    result.AdapterResult.ZoneId,
                                zone_fingerprint_sha256 =
                                    result.AdapterResult
                                        .ZoneFingerprintSha256,
                                policy =
                                    result.AdapterResult.Policy,
                                provenance =
                                    result.AdapterResult.Provenance,
                                conversion_performed =
                                    result.AdapterResult
                                        .ConversionPerformed
                            },

                        observations = observations,

                        iterator_constructor_attempts =
                            result.IteratorConstructorAttempts,

                        getnextsession_attempts =
                            result.GetNextSessionAttempts,

                        expected_pattern_confirmed =
                            expectedPattern,

                        native_provenance_attested = false,
                        certification_evidence = false,
                        runtime_admission = false,
                        execution_authority = false,
                        exporter_change = false,
                        stored_timestamp_mutation = false
                    };

                byte[] evidenceBytes =
                    new UTF8Encoding(false, true)
                        .GetBytes(
                            new JavaScriptSerializer()
                                .Serialize(evidence));

                Guard(
                    evidenceBytes.Length > 0 &&
                    evidenceBytes.Length <= 65536,
                    "EVIDENCE_SIZE_INVALID");

                string evidenceName =
                    "session-query-domain-repair.json";

                string sealName =
                    "session-query-domain-repair.done.json";

                string evidencePath =
                    Path.Combine(
                        folder,
                        evidenceName);

                string sealPath =
                    Path.Combine(
                        folder,
                        sealName);

                WriteNew(
                    evidencePath,
                    evidenceBytes);

                string evidenceHash =
                    Hash(evidenceBytes);

                ValidateEnvironment(
                    configuredOutput,
                    chart);

                var seal =
                    new
                    {
                        schema =
                            "arms.r54.native-repair.seal.v1",
                        version = Version,
                        classification =
                            "DIAGNOSTIC_ONLY",
                        origin =
                            "OPERATOR_NATIVE_RUN_UNATTESTED",
                        probe_uuid = probeId,
                        diagnostic_complete = true,
                        writer_closed = true,

                        evidence_file =
                            evidenceName,

                        evidence_bytes =
                            evidenceBytes.Length,

                        evidence_sha256 =
                            evidenceHash,

                        expected_pattern_confirmed =
                            expectedPattern,

                        source_preserved =
                            result.SourcePreserved,

                        iterator_constructor_attempts =
                            result.IteratorConstructorAttempts,

                        getnextsession_attempts =
                            result.GetNextSessionAttempts,

                        native_provenance_attested = false,
                        certification_evidence = false,
                        runtime_admission = false,
                        execution_authority = false
                    };

                byte[] sealBytes =
                    new UTF8Encoding(false, true)
                        .GetBytes(
                            new JavaScriptSerializer()
                                .Serialize(seal));

                Guard(
                    sealBytes.Length > 0 &&
                    sealBytes.Length <= 8192,
                    "SEAL_SIZE_INVALID");

                WriteNew(
                    sealPath,
                    sealBytes);

                Print(
                    "ARMS_R54_C STATUS=SEALED_DIAGNOSTIC_ONLY" +
                    " PATTERN=" +
                    (expectedPattern ? "CONFIRMED" : "DIVERGED") +
                    " SOURCE_PRESERVED=" +
                    (result.SourcePreserved ? "TRUE" : "FALSE") +
                    " GUARD=NONE ERROR_TYPE=NONE");
            }
            catch (Exception error)
            {
                Print(
                    "ARMS_R54_C STATUS=FAILED_CLOSED" +
                    " PATTERN=UNKNOWN" +
                    " SOURCE_PRESERVED=UNKNOWN" +
                    " GUARD=" +
                    SafeGuard(error) +
                    " ERROR_TYPE=" +
                    SafeType(error));
            }
        }
    }
}
