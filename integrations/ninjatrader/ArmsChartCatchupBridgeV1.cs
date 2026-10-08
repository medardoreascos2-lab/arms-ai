using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsChartCatchupBridgeV1 : Indicator
    {
        private const int MaxLiveFileBytes = 32 * 1024 * 1024;
        private const string LifecycleFileName = "catchup-lifecycle.jsonl";

        private readonly object sync = new object();

        private bool attempted;
        private bool terminal;
        private bool liveHelloAccepted;
        private int liveAlignmentBar = -1;
        private string liveLineageRootSession;
        private string liveLineageLeafSession;
        private FileStream lifecycleStream;
        private StreamWriter lifecycleWriter;
        private int lifecycleSequence;
        private string lifecycleState;
        private string bindingRunId, bindingRuntimeId, bindingNonce, bindingClaimSha256, bindingHandoffSha256;
        private System.Threading.Timer bindingWatcher;
        private int bindingGeneration, lastAcceptedBindingGeneration;
        private string lastAcceptedBindingRunId, lastAcceptedBindingNonce, lastAcceptedBindingClaimSha256, lastAcceptedBindingRuntimeId;
        private bool bindingSessionActive, bindingPollQueued;

        [NinjaScriptProperty]
        [Display(
            Name = "Capture enabled",
            Order = 1,
            GroupName = "ARMS read-only catch-up"
        )]
        public bool CaptureEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "One Click binding file", Order = 2, GroupName = "ARMS read-only catch-up")]
        public string OneClickBindingFile { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Fresh private output directory",
            Order = 3,
            GroupName = "ARMS read-only catch-up"
        )]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Expected provider enum",
            Order = 4,
            GroupName = "ARMS read-only catch-up"
        )]
        public string ExpectedProvider { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "From close UTC",
            Order = 5,
            GroupName = "ARMS read-only catch-up"
        )]
        public string FromCloseUtc { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Through close UTC / LATEST_CLOSED",
            Order = 6,
            GroupName = "ARMS read-only catch-up"
        )]
        public string ThroughCloseUtc { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Live output directory",
            Order = 7,
            GroupName = "ARMS read-only catch-up"
        )]
        public string LiveOutputDirectory { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsChartCatchupBridgeV1";

                Description =
                    "One-shot loaded-chart catch-up evidence; read only and no execution authority.";

                Calculate = Calculate.OnEachTick;

                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;

                CaptureEnabled = false;
                OneClickBindingFile = "";
                OutputDirectory = "";
                ExpectedProvider = "";
                FromCloseUtc = "";
                ThroughCloseUtc = "";
                LiveOutputDirectory = "";
            }
            else if (
                State == State.Realtime
                && CaptureEnabled
            )
            {
                lock (sync)
                {
                    try
                    {
                        if (!String.IsNullOrWhiteSpace(OneClickBindingFile)) StartBindingWatcher();
                        else ActivateCapture();
                    }
                    catch (Exception error) { FailCapture(ErrorCode(error), false); }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                {
                    if (bindingWatcher != null)
                    {
                        try { bindingWatcher.Dispose(); } catch { }
                        bindingWatcher = null;
                    }
                    if (
                        CaptureEnabled
                        && !terminal
                        && lifecycleWriter != null
                    )
                    {
                        FailCapture(
                            "INDICATOR_TERMINATED",
                            false
                        );
                    }

                    CloseLifecycle();
                }
            }
        }

        private void StartBindingWatcher()
        {
            if (bindingWatcher != null) return;
            Need(SafeBindingControlPath(OneClickBindingFile)
                && Path.GetFileName(OneClickBindingFile) == "active-binding.json"
                && new DirectoryInfo(Path.GetDirectoryName(OneClickBindingFile)).Name == "one-click-native-control");
            bindingWatcher = new System.Threading.Timer(_ => QueueBindingPoll(), null, 0, 500);
        }

        private void QueueBindingPoll()
        {
            lock (sync)
            {
                if (bindingPollQueued) return;
                bindingPollQueued = true;
            }
            try { TriggerCustomEvent(_ => PollBinding(), null); }
            catch { lock (sync) bindingPollQueued = false; }
        }

        private void PollBinding()
        {
            lock (sync)
            {
                bindingPollQueued = false;
                try
                {
                    var info = new FileInfo(OneClickBindingFile);
                    if (!info.Exists || info.Length <= 0 || info.Length > 65536) return;
                    string text;
                    using (var input = new FileStream(OneClickBindingFile, FileMode.Open, FileAccess.Read,
                        FileShare.ReadWrite | FileShare.Delete, 4096, FileOptions.SequentialScan))
                    using (var reader = new StreamReader(input, new UTF8Encoding(false, true)))
                    {
                        if (input.Length <= 0 || input.Length > 65536) return;
                        char[] buffer = new char[65537];
                        int count = reader.ReadBlock(buffer, 0, buffer.Length);
                        if (count <= 0 || count > 65536 || reader.Read() != -1) return;
                        text = new string(buffer, 0, count);
                    }
                    var control = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(text);
                    string state = BindingText(control, "state");
                    if (state == "REVOKED")
                    {
                        string[] revokedAuthorities = { "execution_authority", "order_authority", "paper_execution_authority",
                            "live_execution_authority", "broker_authority", "strategy_enable_authority",
                            "ninjatrader_control_authority", "paper_execution_enabled", "live_execution_allowed",
                            "external_order_authority", "broker_live_order_authority" };
                        int revokedGeneration = control.ContainsKey("generation")
                            ? Convert.ToInt32(control["generation"], CultureInfo.InvariantCulture) : 0;
                        string revokedRun = BindingText(control, "one_click_run_id");
                        string revokedRuntime = BindingText(control, "native_runtime_id");
                        Guid revokedGuid;
                        if ((control.Count != 16 && control.Count != 17)
                            || BindingText(control, "schema") != "arms.one-click-native-binding-control.v1"
                            || revokedAuthorities.Any(key => !control.ContainsKey(key) || !(control[key] is bool) || (bool)control[key])
                            || revokedGeneration < 0
                            || !Regex.IsMatch(revokedRun, @"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
                            || !Guid.TryParseExact(revokedRuntime, "D", out revokedGuid)
                            || revokedGuid.ToString("D") != revokedRuntime) return;
                        if (lastAcceptedBindingGeneration > 0
                            && (revokedGeneration != lastAcceptedBindingGeneration
                                || revokedRun != lastAcceptedBindingRunId
                                || revokedRuntime != lastAcceptedBindingRuntimeId)) return;
                        bindingSessionActive = false;
                        return;
                    }
                    if (state != "ACTIVE") return;
                    string priorRun = bindingRunId, priorRuntime = bindingRuntimeId, priorNonce = bindingNonce;
                    string priorClaim = bindingClaimSha256, priorHandoff = bindingHandoffSha256;
                    string priorOutput = OutputDirectory, priorLive = LiveOutputDirectory;
                    string priorProvider = ExpectedProvider, priorFrom = FromCloseUtc, priorThrough = ThroughCloseUtc;
                    int priorGeneration = bindingGeneration;
                    ResolveOneClickBinding(text);
                    if (bindingGeneration < lastAcceptedBindingGeneration)
                    {
                        bindingRunId = priorRun; bindingRuntimeId = priorRuntime; bindingNonce = priorNonce;
                        bindingClaimSha256 = priorClaim; bindingHandoffSha256 = priorHandoff;
                        OutputDirectory = priorOutput; LiveOutputDirectory = priorLive;
                        ExpectedProvider = priorProvider; FromCloseUtc = priorFrom; ThroughCloseUtc = priorThrough;
                        bindingGeneration = priorGeneration;
                        throw new InvalidOperationException();
                    }
                    if (bindingGeneration == lastAcceptedBindingGeneration)
                    {
                        if (bindingNonce != lastAcceptedBindingNonce
                            || bindingClaimSha256 != lastAcceptedBindingClaimSha256
                            || bindingRuntimeId != lastAcceptedBindingRuntimeId
                            || bindingRunId != lastAcceptedBindingRunId)
                        {
                            bindingRunId = priorRun; bindingRuntimeId = priorRuntime; bindingNonce = priorNonce;
                            bindingClaimSha256 = priorClaim; bindingHandoffSha256 = priorHandoff;
                            OutputDirectory = priorOutput; LiveOutputDirectory = priorLive;
                            ExpectedProvider = priorProvider; FromCloseUtc = priorFrom; ThroughCloseUtc = priorThrough;
                            bindingGeneration = priorGeneration;
                            throw new InvalidOperationException();
                        }
                        return;
                    }
                    if (lifecycleWriter != null) CloseLifecycle();
                    attempted = false; terminal = false; liveHelloAccepted = false;
                    liveAlignmentBar = -1; lifecycleSequence = 0; lifecycleState = null;
                    lastAcceptedBindingGeneration = bindingGeneration;
                    lastAcceptedBindingRunId = bindingRunId;
                    lastAcceptedBindingNonce = bindingNonce;
                    lastAcceptedBindingClaimSha256 = bindingClaimSha256;
                    lastAcceptedBindingRuntimeId = bindingRuntimeId;
                    bindingSessionActive = true;
                    ActivateCapture();
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
                catch (InvalidOperationException) { }
                catch (ArgumentException) { }
                catch (FormatException) { }
            }
        }

        private void ActivateCapture()
        {
            if (attempted || terminal) return;
            try
            {
                OpenLifecycle();
                RecordLifecycle("WAITING_FOR_LIVE_HELLO", null);
                if (String.Equals(ThroughCloseUtc, "LATEST_CLOSED", StringComparison.Ordinal)) return;
                attempted = true;
                ExecuteCapture();
            }
            catch (Exception error) { FailCapture(ErrorCode(error), false); }
        }

        private static void Need(bool value)
        {
            if (!value)
                throw new InvalidOperationException();
        }

        private static string BindingText(IDictionary<string, object> value, string key)
        {
            object raw;
            Need(value.TryGetValue(key, out raw) && raw is string && !String.IsNullOrWhiteSpace((string)raw));
            return (string)raw;
        }

        private static bool SafeBoundPath(string value, bool directory)
        {
            if (String.IsNullOrWhiteSpace(value) || !Path.IsPathRooted(value)
                || Path.GetPathRoot(value).StartsWith(@"\\")) return false;
            string full = Path.GetFullPath(value);
            if (full != value || (directory ? !Directory.Exists(full) : !File.Exists(full))) return false;
            FileSystemInfo item = directory ? (FileSystemInfo)new DirectoryInfo(full) : new FileInfo(full);
            while (item != null)
            {
                if ((item.Attributes & System.IO.FileAttributes.ReparsePoint) != 0) return false;
                item = item is DirectoryInfo ? ((DirectoryInfo)item).Parent : ((FileInfo)item).Directory;
            }
            return new System.IO.DriveInfo(Path.GetPathRoot(full)).DriveType == System.IO.DriveType.Fixed;
        }

        private static bool SafeBindingControlPath(string value)
        {
            if (String.IsNullOrWhiteSpace(value) || !Path.IsPathRooted(value)
                || Path.GetPathRoot(value).StartsWith(@"\\")) return false;
            string full = Path.GetFullPath(value);
            if (full != value || String.IsNullOrWhiteSpace(Path.GetFileName(full))) return false;
            DirectoryInfo item = new FileInfo(full).Directory;
            if (item == null || !item.Exists) return false;
            while (item != null)
            {
                if ((item.Attributes & FileAttributes.ReparsePoint) != 0) return false;
                item = item.Parent;
            }
            return new DriveInfo(Path.GetPathRoot(full)).DriveType == DriveType.Fixed;
        }

        private static bool BindingHex(string value, int length)
        {
            return value != null && value.Length == length
                && value.All(character => (character >= '0' && character <= '9')
                    || (character >= 'a' && character <= 'f'));
        }

        private void ResolveOneClickBinding(string controlJson)
        {
            Need(SafeBoundPath(OneClickBindingFile, false)
                && Path.GetFileName(OneClickBindingFile) == "active-binding.json"
                && new DirectoryInfo(Path.GetDirectoryName(OneClickBindingFile)).Name == "one-click-native-control");
            var serializer = new JavaScriptSerializer();
            var control = serializer.Deserialize<Dictionary<string, object>>(controlJson);
            Need(control.Count == 4
                && BindingText(control, "schema") == "arms.one-click-native-binding-control.v1"
                && BindingText(control, "state") == "ACTIVE");
            string claimJson = BindingText(control, "claim_json");
            string claimSha = BindingText(control, "claim_sha256");
            Need(BindingHex(claimSha, 64) && Hash(Encoding.UTF8.GetBytes(claimJson)) == claimSha);
            var claim = serializer.Deserialize<Dictionary<string, object>>(claimJson);
            string[] authorities = { "execution_authority", "order_authority", "paper_execution_authority",
                "live_execution_authority", "broker_authority", "strategy_enable_authority",
                "ninjatrader_control_authority", "paper_execution_enabled", "live_execution_allowed",
                "external_order_authority", "broker_live_order_authority" };
            Need(claim.Count == 32
                && BindingText(claim, "schema") == "arms.one-click-native-binding-claim.v1"
                && !authorities.Any(key => !claim.ContainsKey(key) || !(claim[key] is bool) || (bool)claim[key])
                && Convert.ToInt32(claim["generation"], CultureInfo.InvariantCulture) > 0
                && Convert.ToInt32(claim["apply_limit"], CultureInfo.InvariantCulture) == 1);
            DateTime created, expires;
            Need(DateTime.TryParse(BindingText(claim, "created_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out created)
                && DateTime.TryParse(BindingText(claim, "expires_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out expires)
                && created <= DateTime.UtcNow && DateTime.UtcNow <= expires
                && expires > created && expires - created <= TimeSpan.FromSeconds(900));
            string runtime = BindingText(claim, "runtime_directory");
            string parent = BindingText(claim, "runtime_parent");
            string inbox = BindingText(claim, "live_inbox");
            string catchup = BindingText(claim, "catchup_output_directory");
            string runtimeId = BindingText(claim, "native_runtime_id");
            Guid runtimeGuid;
            Need(Guid.TryParseExact(runtimeId, "D", out runtimeGuid) && runtimeGuid.ToString("D") == runtimeId
                && Regex.IsMatch(BindingText(claim, "one_click_run_id"), @"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
                && SafeBoundPath(parent, true) && SafeBoundPath(runtime, true)
                && SafeBoundPath(inbox, true) && SafeBoundPath(catchup, true)
                && Directory.GetParent(runtime).FullName == parent && Path.GetFileName(runtime) == runtimeId
                && Path.Combine(runtime, "inbox") == inbox && Path.Combine(runtime, "chart-catchup") == catchup
                && Directory.GetParent(parent).FullName == Directory.GetParent(Path.GetDirectoryName(OneClickBindingFile)).FullName
                && BindingText(claim, "expected_provider") == "Provider31"
                && BindingText(claim, "contract") == "NQ DEC26"
                && BindingText(claim, "bars_period") == "Minute"
                && Convert.ToInt32(claim["bars_value"], CultureInfo.InvariantCulture) == 1
                && BindingText(claim, "trading_hours") == "CME US Index Futures ETH"
                && BindingText(claim, "through_close_utc") == "LATEST_CLOSED"
                && BindingHex(BindingText(claim, "binding_nonce"), 64)
                && BindingHex(BindingText(claim, "handoff_file_sha256"), 64)
                && BindingHex(BindingText(claim, "phase3_source_sha256"), 64));
            DateTime from;
            Need(DateTime.TryParse(BindingText(claim, "from_close_utc"), CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out from));
            OutputDirectory = catchup;
            LiveOutputDirectory = inbox;
            ExpectedProvider = BindingText(claim, "expected_provider");
            FromCloseUtc = BindingText(claim, "from_close_utc");
            ThroughCloseUtc = BindingText(claim, "through_close_utc");
            bindingRuntimeId = runtimeId;
            bindingRunId = BindingText(claim, "one_click_run_id");
            bindingNonce = BindingText(claim, "binding_nonce");
            bindingClaimSha256 = claimSha;
            bindingHandoffSha256 = BindingText(claim, "handoff_file_sha256");
            bindingGeneration = Convert.ToInt32(claim["generation"], CultureInfo.InvariantCulture);
        }

        private void ValidateBindingReceipt(string directory, string session)
        {
            string path = Path.Combine(directory, session + ".one-click-binding.json");
            if (String.IsNullOrWhiteSpace(bindingNonce)) { Need(!File.Exists(path)); return; }
            Need(SafeBoundPath(path, false));
            byte[] raw = File.ReadAllBytes(path);
            Need(raw.Length > 0 && raw.Length <= 4096 && raw[raw.Length - 1] == (byte)'\n');
            var receipt = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(
                Encoding.UTF8.GetString(raw).TrimEnd('\n'));
            Need(receipt.Count == 18
                && BindingText(receipt, "schema") == "arms.nt.one-click-binding-receipt.v1"
                && BindingText(receipt, "session") == session
                && BindingText(receipt, "native_runtime_id") == bindingRuntimeId
                && BindingText(receipt, "binding_nonce") == bindingNonce
                && BindingText(receipt, "binding_claim_sha256") == bindingClaimSha256
                && BindingText(receipt, "handoff_file_sha256") == bindingHandoffSha256
                && receipt["read_only"] is bool && (bool)receipt["read_only"]
                && new[] { "execution_authority", "order_authority", "paper_execution_authority",
                    "live_execution_authority", "broker_authority", "strategy_enable_authority",
                    "ninjatrader_control_authority", "paper_execution_enabled", "live_execution_allowed",
                    "external_order_authority", "broker_live_order_authority" }
                    .All(key => receipt.ContainsKey(key) && receipt[key] is bool && !(bool)receipt[key]));
        }

        private static string ErrorCode(Exception error)
        {
            if (error is InvalidOperationException)
                return "INVALID_OPERATION";

            if (error is UnauthorizedAccessException)
                return "ACCESS_DENIED";

            if (error is IOException)
                return "IO_ERROR";

            if (error is FormatException)
                return "FORMAT_ERROR";

            if (error is ArgumentException)
                return "INVALID_ARGUMENT";

            return "OTHER";
        }

        private void OpenLifecycle()
        {
            if (lifecycleWriter != null)
                return;

            string output =
                LocalDirectory(
                    OutputDirectory,
                    true
                );

            string path =
                Path.Combine(
                    output,
                    LifecycleFileName
                );

            lifecycleStream =
                new FileStream(
                    path,
                    FileMode.CreateNew,
                    FileAccess.Write,
                    FileShare.Read,
                    4096,
                    FileOptions.WriteThrough
                );

            lifecycleWriter =
                new StreamWriter(
                    lifecycleStream,
                    new UTF8Encoding(false)
                );

            lifecycleWriter.NewLine = "\n";
            lifecycleWriter.AutoFlush = true;
        }

        private void RecordLifecycle(
            string state,
            string reason
        )
        {
            Need(
                lifecycleWriter != null
                && !String.IsNullOrWhiteSpace(
                    state
                )
            );

            string row =
                new JavaScriptSerializer()
                    .Serialize(
                        new
                        {
                            schema =
                                "arms.nt.chart-catchup.lifecycle.v1",

                            sequence =
                                lifecycleSequence++,

                            event_time =
                                DateTime.UtcNow.ToString(
                                    "o",
                                    CultureInfo.InvariantCulture
                                ),

                            state = state,
                            reason = reason,

                            observation_only =
                                true,

                            runtime_admission =
                                false,

                            execution_authority =
                                false
                        }
                    );

            lifecycleWriter.WriteLine(
                row
            );

            lifecycleWriter.Flush();
            lifecycleStream.Flush(true);
            lifecycleState = state;
        }

        private void CloseLifecycle()
        {
            try
            {
                if (lifecycleWriter != null)
                    lifecycleWriter.Dispose();
            }
            catch
            {
            }

            lifecycleWriter = null;
            lifecycleStream = null;
        }

        private void ExecuteCapture()
        {
            try
            {
                RecordLifecycle(
                    "CAPTURE_STARTED",
                    null
                );

                Capture();

                RecordLifecycle(
                    "CAPTURE_COMPLETE",
                    null
                );

                terminal = true;

                try
                {
                    Print(
                        "ARMS_CHART_CATCHUP_BRIDGE_COMPLETE"
                    );
                }
                catch
                {
                }
            }
            catch (Exception error)
            {
                FailCapture(
                    ErrorCode(error),
                    false
                );
            }
        }

        private void FailCapture(
            string reason,
            bool alignment
        )
        {
            if (terminal)
                return;

            attempted = true;

            try
            {
                if (
                    lifecycleWriter != null
                    && lifecycleState
                        != "CAPTURE_VALIDATION_FAILED"
                    && lifecycleState
                        != "CAPTURE_FAILED"
                )
                {
                    RecordLifecycle(
                        "CAPTURE_VALIDATION_FAILED",
                        reason
                    );
                }

                if (
                    lifecycleWriter != null
                    && lifecycleState
                        != "CAPTURE_FAILED"
                )
                {
                    RecordLifecycle(
                        "CAPTURE_FAILED",
                        reason
                    );
                }
            }
            catch (Exception diagnosticError)
            {
                try
                {
                    Print(
                        "ARMS_CHART_CATCHUP_DIAGNOSTIC_WRITE_FAILED_"
                        + ErrorCode(
                            diagnosticError
                        )
                    );
                }
                catch
                {
                }
            }

            terminal = true;

            try
            {
                Print(
                    (
                        alignment
                            ? "ARMS_CHART_CATCHUP_BRIDGE_FAILED_ALIGNMENT_"
                            : "ARMS_CHART_CATCHUP_BRIDGE_FAILED_"
                    )
                    + reason
                );
            }
            catch
            {
            }
        }

        private static string ProviderName(
            Connection connection
        )
        {
            if (
                connection == null
                || connection.Options == null
            )
                return "UNKNOWN";

            var provider =
                connection.Options.Provider;

            return Enum.IsDefined(
                provider.GetType(),
                provider
            )
                ? provider.ToString()
                : "UNKNOWN";
        }

        private static string StatusName(
            ConnectionStatus value
        )
        {
            return Enum.IsDefined(
                typeof(ConnectionStatus),
                value
            )
                ? value.ToString()
                : "UNKNOWN";
        }

        private void RequireSource()
        {
            Need(
                Connection.PlaybackConnection
                == null
            );

            Need(
                Core.Globals.GeneralOptions
                    .TimeZoneInfo.Id
                == "UTC"
            );

            Need(
                BarsPeriod.BarsPeriodType
                == BarsPeriodType.Minute
                && BarsPeriod.Value == 1
            );

            Need(
                Instrument != null
                && Instrument.MasterInstrument != null
                && Instrument.MasterInstrument.Name
                    == "NQ"
                && Instrument.FullName
                    == "NQ DEC26"
                && Instrument.Expiry
                    .ToString("yyyy-MM-dd")
                    == "2026-12-01"
                && Instrument.MasterInstrument.TickSize
                    == .25
                && Instrument.MasterInstrument.PointValue
                    == 20
            );

            Need(
                Bars != null
                && Bars.TradingHours != null
                && Bars.TradingHours.Name
                    == "CME US Index Futures ETH"
            );

            Need(
                !String.IsNullOrWhiteSpace(
                    ExpectedProvider
                )
                && !ExpectedProvider
                    .ToLowerInvariant()
                    .Contains("simulat")
                && !ExpectedProvider
                    .ToLowerInvariant()
                    .Contains("playback")
            );

            if (
                !System.Threading.Monitor.TryEnter(
                    Connection.Connections
                )
            )
                throw new InvalidOperationException();

            try
            {
                var futures =
                    Connection.Connections
                        .Where(
                            connection =>
                                connection != null
                                && connection.InstrumentTypes
                                    .Contains(
                                        InstrumentType.Future
                                    )
                        )
                        .ToArray();

                Need(
                    futures.Length == 1
                );

                var source =
                    futures[0];

                Need(
                    ProviderName(source)
                    == ExpectedProvider
                );

                Need(
                    StatusName(
                        source.PriceStatus
                    )
                    == "Connected"
                );

                Need(
                    StatusName(
                        source.Status
                    )
                    == "Connected"
                );

                Need(
                    ProviderName(source)
                    == ExpectedProvider
                );
            }
            finally
            {
                System.Threading.Monitor.Exit(
                    Connection.Connections
                );
            }
        }

        private static DateTime ParseUtc(
            string value
        )
        {
            DateTime parsed;

            Need(
                DateTime.TryParseExact(
                    value,
                    "yyyy-MM-ddTHH:mm:ss'Z'",
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal
                        | DateTimeStyles.AdjustToUniversal,
                    out parsed
                )
            );

            Need(
                parsed.Kind
                == DateTimeKind.Utc
            );

            Need(
                parsed.Second == 0
                && parsed.Millisecond == 0
                && parsed.Ticks
                    % TimeSpan.TicksPerMinute
                    == 0
            );

            return parsed;
        }

        private static DateTime ClockFieldsAsUtc(
            DateTime value
        )
        {
            if (
                value.Kind
                == DateTimeKind.Utc
            )
                return value;

            Need(
                value.Kind
                == DateTimeKind.Unspecified
            );

            DateTime normalized =
                DateTime.SpecifyKind(
                    value,
                    DateTimeKind.Utc
                );

            Need(
                normalized.Ticks
                == value.Ticks
            );

            return normalized;
        }

        private static string LocalDirectory(
            string value,
            bool requireEmpty
        )
        {
            Need(
                !String.IsNullOrWhiteSpace(
                    value
                )
                && Path.IsPathRooted(
                    value
                )
            );

            string full =
                Path.GetFullPath(value);

            string root =
                Path.GetPathRoot(full);

            Need(
                !root.StartsWith(@"\\")
                && Directory.Exists(full)
                && new DriveInfo(root).DriveType
                    == DriveType.Fixed
            );

            for (
                var current =
                    new DirectoryInfo(full);
                current != null;
                current = current.Parent
            )
            {
                Need(
                    (
                        current.Attributes
                        & System.IO.FileAttributes.ReparsePoint
                    )
                    == 0
                );
            }

            string[] entries =
                Directory.GetFileSystemEntries(
                    full
                );

            if (requireEmpty)
            {
                Need(
                    entries.Length == 0
                );
            }
            else
            {
                Need(
                    entries.Length == 1
                    && Path.GetFileName(
                        entries[0]
                    )
                    == LifecycleFileName
                );
            }

            return full;
        }

        private static bool Price(
            double value
        )
        {
            return
                !Double.IsNaN(value)
                && !Double.IsInfinity(value)
                && value > 0
                && value * 4
                    == Math.Truncate(
                        value * 4
                    );
        }

        private static string Hash(
            byte[] value
        )
        {
            using (
                var digest =
                    SHA256.Create()
            )
            {
                return BitConverter
                    .ToString(
                        digest.ComputeHash(
                            value
                        )
                    )
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        private static string LiveDirectory(
            string value
        )
        {
            Need(
                !String.IsNullOrWhiteSpace(
                    value
                )
            );

            Need(
                Path.IsPathRooted(
                    value
                )
            );

            string full =
                Path.GetFullPath(
                    value
                );

            string root =
                Path.GetPathRoot(
                    full
                );

            Need(
                !String.IsNullOrWhiteSpace(
                    root
                )
                && !root.StartsWith(
                    @"\\"
                )
            );

            Need(
                Directory.Exists(
                    full
                )
            );

            Need(
                new DriveInfo(
                    root
                ).DriveType
                == DriveType.Fixed
            );

            for (
                var current =
                    new DirectoryInfo(
                        full
                    );
                current != null;
                current = current.Parent
            )
            {
                Need(
                    (
                        current.Attributes
                        & System.IO.FileAttributes.ReparsePoint
                    )
                    == 0
                );
            }

            return full;
        }

        private sealed class LiveSessionEvidence
        {
            public string Session;
            public DateTime HelloTime;
            public DateTime TerminalTime;
            public bool Terminated;
            public int Records;
        }

        private static Dictionary<string, object> JsonObject(
            object value
        )
        {
            var result =
                value
                as Dictionary<string, object>;

            Need(
                result != null
            );

            return result;
        }

        private static long JsonInteger(
            Dictionary<string, object> value,
            string key
        )
        {
            Need(
                value.ContainsKey(key)
            );

            object raw =
                value[key];

            Need(
                raw is int
                || raw is long
            );

            return Convert.ToInt64(
                raw,
                CultureInfo.InvariantCulture
            );
        }

        private static DateTime EventTime(
            object value
        )
        {
            Need(
                value is string
            );

            DateTime result;

            Need(
                DateTime.TryParseExact(
                    (string)value,
                    "yyyy-MM-ddTHH:mm:ss.fffffff'Z'",
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal
                        | DateTimeStyles.AdjustToUniversal,
                    out result
                )
                && result.Kind
                    == DateTimeKind.Utc
            );

            return result;
        }

        private static List<string> CompleteLines(
            string path
        )
        {
            byte[] bytes;

            using (
                var file =
                    new FileStream(
                        path,
                        FileMode.Open,
                        FileAccess.Read,
                        FileShare.ReadWrite
                    )
            )
            {
                Need(
                    file.Length >= 0
                    && file.Length
                        <= MaxLiveFileBytes
                );

                bytes =
                    new byte[
                        (int)file.Length
                    ];

                int offset = 0;

                while (
                    offset < bytes.Length
                )
                {
                    int count =
                        file.Read(
                            bytes,
                            offset,
                            bytes.Length - offset
                        );

                    Need(
                        count > 0
                    );

                    offset += count;
                }
            }

            int lastNewline =
                Array.LastIndexOf(
                    bytes,
                    (byte)'\n'
                );

            if (lastNewline < 0)
                return new List<string>();

            string text =
                new UTF8Encoding(
                    false,
                    true
                ).GetString(
                    bytes,
                    0,
                    lastNewline + 1
                );

            Need(
                text.IndexOf('\0') < 0
            );

            string[] parts =
                text.Split('\n');

            var result =
                new List<string>();

            for (
                int i = 0;
                i < parts.Length - 1;
                i++
            )
            {
                string line =
                    parts[i];

                if (
                    line.EndsWith(
                        "\r",
                        StringComparison.Ordinal
                    )
                )
                {
                    line =
                        line.Substring(
                            0,
                            line.Length - 1
                        );
                }

                Need(
                    line.Length > 0
                    && line.IndexOf('\r')
                        < 0
                );

                result.Add(
                    line
                );
            }

            return result;
        }

        private void ValidateHello(
            Dictionary<string, object> row,
            string session
        )
        {
            Need(
                row.Count == 6
                && row.ContainsKey("schema")
                && row.ContainsKey("session")
                && row.ContainsKey("sequence")
                && row.ContainsKey("event_time")
                && row.ContainsKey("kind")
                && row.ContainsKey("payload")
                && (string)row["schema"]
                    == "arms.nt.market.v1"
                && (string)row["session"]
                    == session
                && JsonInteger(
                    row,
                    "sequence"
                )
                    == 0
                && (string)row["kind"]
                    == "HELLO"
            );

            EventTime(
                row["event_time"]
            );

            var payload =
                JsonObject(
                    row["payload"]
                );

            Need(
                payload.Count == 12
                && (string)payload["provider"]
                    == ExpectedProvider
                && (string)payload["contract"]
                    == "NQ DEC26"
                && (string)payload["expiry"]
                    == "2026-12-01"
                && (string)payload["instrument"]
                    == "NQ"
                && Convert.ToDouble(
                    payload["tick_size"],
                    CultureInfo.InvariantCulture
                )
                    == .25
                && Convert.ToDouble(
                    payload["point_value"],
                    CultureInfo.InvariantCulture
                )
                    == 20
                && (string)payload["timeframe"]
                    == "1m"
                && (string)payload[
                    "trading_hours_template"
                ]
                    == "CME US Index Futures ETH"
                && (string)payload[
                    "source_timezone"
                ]
                    == "UTC"
                && (string)payload["bar_label"]
                    == "CLOSE"
                && payload["realtime"]
                    is bool
                && (bool)payload["realtime"]
                && payload["read_only"]
                    is bool
                && (bool)payload["read_only"]
            );
        }

        private LiveSessionEvidence ReadLiveEvidence(
            string path
        )
        {
            string session =
                Path.GetFileNameWithoutExtension(
                    path
                );

            Guid parsed;

            Need(
                Guid.TryParseExact(
                    session,
                    "D",
                    out parsed
                )
            );

            List<string> lines =
                CompleteLines(
                    path
                );

            if (lines.Count == 0)
                return null;

            var serializer =
                new JavaScriptSerializer();

            var rows =
                new List<
                    Dictionary<string, object>
                >();

            for (
                int i = 0;
                i < lines.Count;
                i++
            )
            {
                var row =
                    JsonObject(
                        serializer
                            .DeserializeObject(
                                lines[i]
                            )
                    );

                Need(
                    row.Count == 6
                    && (string)row["schema"]
                        == "arms.nt.market.v1"
                    && (string)row["session"]
                        == session
                    && JsonInteger(
                        row,
                        "sequence"
                    )
                        == i
                );

                EventTime(
                    row["event_time"]
                );

                rows.Add(
                    row
                );
            }

            ValidateHello(
                rows[0],
                session
            );

            ValidateBindingReceipt(
                Path.GetDirectoryName(path),
                session
            );

            var result =
                new LiveSessionEvidence();

            result.Session =
                session;

            result.HelloTime =
                EventTime(
                    rows[0]["event_time"]
                );

            result.Records =
                rows.Count;

            var last =
                rows[
                    rows.Count - 1
                ];

            if (
                (string)last["kind"]
                == "DISCONNECTED"
            )
            {
                var payload =
                    JsonObject(
                        last["payload"]
                    );

                Need(
                    rows.Count >= 2
                    && payload.Count == 3
                    && payload["connected"]
                        is bool
                    && !(bool)payload["connected"]
                    && (string)payload["reason"]
                        == "TERMINATED"
                    && (string)payload["error_code"]
                        == "NONE"
                );

                result.Terminated =
                    true;

                result.TerminalTime =
                    EventTime(
                        last["event_time"]
                    );
            }
            else
            {
                string lastKind =
                    (string)last["kind"];

                Need(
                    (
                        rows.Count == 1
                        && lastKind == "HELLO"
                    )
                    || lastKind == "HEARTBEAT"
                    || lastKind == "CLOSED"
                    || lastKind == "FORMING"
                );
            }

            for (
                int i = 1;
                i < rows.Count - 1;
                i++
            )
            {
                string kind =
                    (string)rows[i]["kind"];

                Need(
                    kind == "HEARTBEAT"
                    || kind == "CLOSED"
                    || kind == "FORMING"
                );
            }

            return result;
        }

        private void ValidateTimingSeal(
            string directory,
            LiveSessionEvidence predecessor
        )
        {
            string timingPath =
                Path.Combine(
                    directory,
                    "timing",
                    predecessor.Session
                    + ".production-timing.jsonl"
                );

            string sealPath =
                timingPath
                + ".done.json";

            Need(
                File.Exists(
                    timingPath
                )
                && File.Exists(
                    sealPath
                )
            );

            byte[] timing;

            using (
                var file =
                    new FileStream(
                        timingPath,
                        FileMode.Open,
                        FileAccess.Read,
                        FileShare.ReadWrite
                    )
            )
            {
                Need(
                    file.Length >= 0
                    && file.Length
                        <= MaxLiveFileBytes
                );

                timing =
                    new byte[
                        (int)file.Length
                    ];

                int offset = 0;

                while (
                    offset < timing.Length
                )
                {
                    int count =
                        file.Read(
                            timing,
                            offset,
                            timing.Length - offset
                        );

                    Need(
                        count > 0
                    );

                    offset += count;
                }
            }

            int timingRecords = 0;

            for (
                int i = 0;
                i < timing.Length;
                i++
            )
            {
                if (timing[i] == (byte)'\n')
                    timingRecords++;
            }

            Need(
                timing.Length == 0
                || timing[
                    timing.Length - 1
                ]
                    == (byte)'\n'
            );

            string sealText;

            using (
                var file =
                    new FileStream(
                        sealPath,
                        FileMode.Open,
                        FileAccess.Read,
                        FileShare.ReadWrite
                    )
            )
            {
                Need(
                    file.Length > 0
                    && file.Length <= 4096
                );

                using (
                    var reader =
                        new StreamReader(
                            file,
                            new UTF8Encoding(
                                false,
                                true
                            )
                        )
                )
                {
                    sealText =
                        reader.ReadToEnd();
                }
            }

            var seal =
                JsonObject(
                    new JavaScriptSerializer()
                        .DeserializeObject(
                            sealText
                        )
                );

            Need(
                seal.Count == 9
                && (string)seal["schema"]
                    == "arms.nt.production-timing.seal.v1"
                && (string)seal["session"]
                    == predecessor.Session
                && JsonInteger(
                    seal,
                    "records"
                )
                    == timingRecords
                && JsonInteger(
                    seal,
                    "bytes"
                )
                    == timing.Length
                && (string)seal["sha256"]
                    == Hash(timing)
                && JsonInteger(
                    seal,
                    "canonical_records"
                )
                    == predecessor.Records
                && seal["canonical_writer_closed"]
                    is bool
                && (bool)seal[
                    "canonical_writer_closed"
                ]
                && seal["timing_writer_closed"]
                    is bool
                && (bool)seal[
                    "timing_writer_closed"
                ]
                && seal["complete"]
                    is bool
                && (bool)seal["complete"]
            );
        }

        private bool LiveHelloReady()
        {
            string directory =
                LiveDirectory(
                    LiveOutputDirectory
                );

            string[] files =
                Directory.GetFiles(
                    directory,
                    "*.jsonl",
                    SearchOption.TopDirectoryOnly
                )
                .Where(
                    candidate =>
                        !Path.GetFileName(
                            candidate
                        ).EndsWith(
                            ".connection.jsonl",
                            StringComparison.OrdinalIgnoreCase
                        )
                )
                .OrderBy(
                    candidate =>
                        candidate,
                    StringComparer.Ordinal
                )
                .ToArray();

            Need(
                files.Length <= 2
            );

            if (
                files.Length == 0
            )
                return false;

            if (
                liveLineageRootSession
                == null
            )
            {
                Need(
                    files.Length == 1
                );

                LiveSessionEvidence first =
                    ReadLiveEvidence(
                        files[0]
                    );

                if (first == null)
                    return false;

                Need(
                    !first.Terminated
                );

                liveLineageRootSession =
                    first.Session;

                liveLineageLeafSession =
                    first.Session;

                return true;
            }

            string rootPath =
                files.FirstOrDefault(
                    candidate =>
                        Path.GetFileNameWithoutExtension(
                            candidate
                        )
                        == liveLineageRootSession
                );

            Need(
                rootPath != null
            );

            if (
                files.Length == 1
            )
            {
                LiveSessionEvidence root =
                    ReadLiveEvidence(
                        rootPath
                    );

                Need(
                    root != null
                    && !root.Terminated
                    && liveLineageLeafSession
                        == liveLineageRootSession
                );

                return true;
            }

            string replacementPath =
                files.Single(
                    candidate =>
                        candidate != rootPath
                );

            LiveSessionEvidence predecessor =
                ReadLiveEvidence(
                    rootPath
                );

            Need(
                predecessor != null
                && predecessor.Terminated
            );

            ValidateTimingSeal(
                directory,
                predecessor
            );

            LiveSessionEvidence replacement =
                ReadLiveEvidence(
                    replacementPath
                );

            if (replacement == null)
                return false;

            Need(
                !replacement.Terminated
                && predecessor.TerminalTime
                    < replacement.HelloTime
                && (
                    liveLineageLeafSession
                        == liveLineageRootSession
                    || liveLineageLeafSession
                        == replacement.Session
                )
            );

            liveLineageLeafSession =
                replacement.Session;

            return true;
        }

        protected override void OnBarUpdate()
        {
            if (
                State != State.Realtime
                || BarsInProgress != 0
                || !IsFirstTickOfBar
            )
                return;

            if (
                !CaptureEnabled
                || attempted
                || terminal
                || !String.Equals(
                    ThroughCloseUtc,
                    "LATEST_CLOSED",
                    StringComparison.Ordinal
                )
            )
                return;

            lock (sync)
            {
                if (
                    attempted
                    || terminal
                )
                    return;

                try
                {
                    if (
                        !LiveHelloReady()
                    )
                        return;

                    if (
                        !liveHelloAccepted
                    )
                    {
                        RecordLifecycle(
                            "LIVE_HELLO_ACCEPTED",
                            null
                        );

                        liveHelloAccepted =
                            true;
                    }

                    if (
                        liveAlignmentBar < 0
                    )
                    {
                        liveAlignmentBar =
                            CurrentBar;

                        RecordLifecycle(
                            "ALIGNMENT_BAR_CAPTURED",
                            null
                        );

                        RecordLifecycle(
                            "WAITING_FOR_SECOND_BAR_ADVANCE",
                            null
                        );

                        return;
                    }

                    if (
                        !(CurrentBar > liveAlignmentBar)
                    )
                        return;

                    if (
                        CurrentBar - 1
                        <= liveAlignmentBar
                    )
                        return;
                }
                catch (
                    Exception error
                )
                {
                    FailCapture(
                        ErrorCode(error),
                        true
                    );

                    return;
                }

                attempted = true;
                ExecuteCapture();
            }
        }

        private void Capture()
        {
            RequireSource();

            string output =
                LocalDirectory(
                    OutputDirectory,
                    false
                );

            DateTime from =
                ParseUtc(
                    FromCloseUtc
                );

            int count =
                Bars.Count;

            Need(
                count >= 3
                && count <= 1000000
            );

            bool latestClosed =
                String.Equals(
                    ThroughCloseUtc,
                    "LATEST_CLOSED",
                    StringComparison.Ordinal
                );

            DateTime through;

            if (latestClosed)
            {
                DateTime latestRaw =
                    Bars.GetTime(
                        count - 2
                    );

                Need(
                    latestRaw.Kind
                        == DateTimeKind.Utc
                    || latestRaw.Kind
                        == DateTimeKind.Unspecified
                );

                Need(
                    latestRaw.Ticks
                    % TimeSpan.TicksPerMinute
                    == 0
                );

                through =
                    ClockFieldsAsUtc(
                        latestRaw
                    );
            }
            else
            {
                through =
                    ParseUtc(
                        ThroughCloseUtc
                    );
            }

            Need(
                from <= through
                && through - from
                    <= TimeSpan.FromDays(2)
            );

            var indexes =
                new List<int>();

            DateTimeKind? selectedKind =
                null;

            DateTime previousRaw =
                DateTime.MinValue;

            // The newest chart row may still be forming.
            // Never admit it into catch-up evidence.
            for (
                int i = 0;
                i < count - 1;
                i++
            )
            {
                DateTime raw =
                    Bars.GetTime(i);

                Need(
                    raw.Kind
                        == DateTimeKind.Utc
                    || raw.Kind
                        == DateTimeKind.Unspecified
                );

                Need(
                    raw.Ticks
                    % TimeSpan.TicksPerMinute
                    == 0
                );

                if (
                    previousRaw
                    != DateTime.MinValue
                )
                {
                    Need(
                        raw.Ticks
                        > previousRaw.Ticks
                    );
                }

                previousRaw = raw;

                DateTime label =
                    ClockFieldsAsUtc(raw);

                if (
                    label < from
                    || label > through
                )
                    continue;

                if (!selectedKind.HasValue)
                {
                    selectedKind =
                        raw.Kind;
                }
                else
                {
                    Need(
                        selectedKind.Value
                        == raw.Kind
                    );
                }

                indexes.Add(i);
            }

            Need(
                indexes.Count > 0
                && indexes.Count <= 3000
            );

            DateTime firstLabel =
                ClockFieldsAsUtc(
                    Bars.GetTime(
                        indexes[0]
                    )
                );

            DateTime lastLabel =
                ClockFieldsAsUtc(
                    Bars.GetTime(
                        indexes[
                            indexes.Count - 1
                        ]
                    )
                );

            Need(
                firstLabel == from
                && lastLabel == through
            );

            if (latestClosed)
            {
                Need(
                    indexes[
                        indexes.Count - 1
                    ]
                    == count - 2
                );
            }

            string runId =
                Guid.NewGuid()
                    .ToString("D");

            var serializer =
                new JavaScriptSerializer();

            var lines =
                new List<string>();

            lines.Add(
                serializer.Serialize(
                    new
                    {
                        schema =
                            "arms.nt.chart-catchup.header.v1",

                        run_id =
                            runId,

                        exporter =
                            "ArmsChartCatchupBridgeV1/1",

                        source =
                            "NINJATRADER_LOADED_CHART_BARS",

                        provider =
                            ExpectedProvider,

                        instrument =
                            "NQ",

                        contract =
                            "NQ DEC26",

                        expiry =
                            "2026-12-01",

                        bars_type =
                            "Minute",

                        bars_value =
                            1,

                        timeframe =
                            "1m",

                        trading_hours =
                            "CME US Index Futures ETH",

                        application_timezone =
                            "UTC",

                        bar_label =
                            "CLOSE",

                        tick_size =
                            .25,

                        point_value =
                            20,

                        requested_from_close =
                            from.ToString("o"),

                        configured_through_close =
                            ThroughCloseUtc,

                        through_selection =
                            latestClosed
                                ? "CHART_LATEST_CLOSED"
                                : "EXPLICIT_UTC",

                        requested_through_close =
                            through.ToString("o"),

                        chart_bar_count =
                            count,

                        excluded_last =
                            true,

                        raw_time_kind =
                            selectedKind.Value.ToString(),

                        classification =
                            "CHART_CATCHUP",

                        observation_only =
                            true,

                        runtime_admission =
                            false,

                        execution_authority =
                            false
                    }
                )
            );

            for (
                int selected = 0;
                selected < indexes.Count;
                selected++
            )
            {
                int index =
                    indexes[selected];

                DateTime raw =
                    Bars.GetTime(index);

                DateTime label =
                    ClockFieldsAsUtc(raw);

                double open =
                    Bars.GetOpen(index);

                double high =
                    Bars.GetHigh(index);

                double low =
                    Bars.GetLow(index);

                double close =
                    Bars.GetClose(index);

                long volume =
                    Bars.GetVolume(index);

                Need(
                    raw.Kind
                    == selectedKind.Value
                );

                Need(
                    Price(open)
                    && Price(high)
                    && Price(low)
                    && Price(close)
                    && volume >= 0
                );

                Need(
                    low
                    <= Math.Min(
                        open,
                        close
                    )
                    && high
                    >= Math.Max(
                        open,
                        close
                    )
                );

                lines.Add(
                    serializer.Serialize(
                        new
                        {
                            schema =
                                "arms.nt.chart-catchup.bar.v1",

                            run_id =
                                runId,

                            index =
                                selected,

                            chart_index =
                                index,

                            raw_time =
                                raw.ToString(
                                    "o",
                                    CultureInfo.InvariantCulture
                                ),

                            raw_time_kind =
                                raw.Kind.ToString(),

                            raw_ticks =
                                raw.Ticks,

                            bar_time =
                                label.ToString(
                                    "o",
                                    CultureInfo.InvariantCulture
                                ),

                            open = open,
                            high = high,
                            low = low,
                            close = close,
                            volume = volume,

                            classification =
                                "CHART_CATCHUP",

                            observation_only =
                                true,

                            runtime_admission =
                                false,

                            execution_authority =
                                false
                        }
                    )
                );
            }

            Need(
                Bars.Count
                == count
            );

            byte[] body =
                Encoding.UTF8.GetBytes(
                    String.Join(
                        "\n",
                        lines
                    )
                    + "\n"
                );

            Need(
                body.Length
                <= 16 * 1024 * 1024
            );

            string bodyPath =
                Path.Combine(
                    output,
                    runId
                    + ".chart-catchup.jsonl"
                );

            using (
                var file =
                    new FileStream(
                        bodyPath,
                        FileMode.CreateNew,
                        FileAccess.Write,
                        FileShare.Read,
                        4096,
                        FileOptions.WriteThrough
                    )
            )
            {
                file.Write(
                    body,
                    0,
                    body.Length
                );

                file.Flush(true);
            }

            RecordLifecycle(
                "CAPTURE_BODY_WRITTEN",
                null
            );

            var seal =
                new
                {
                    schema =
                        "arms.nt.chart-catchup.seal.v1",

                    run_id =
                        runId,

                    bytes =
                        body.Length,

                    records =
                        lines.Count,

                    bars =
                        indexes.Count,

                    sha256 =
                        Hash(body),

                    writer_closed =
                        true,

                    complete =
                        true,

                    classification =
                        "CHART_CATCHUP",

                    runtime_admission =
                        false,

                    execution_authority =
                        false
                };

            string temporary =
                bodyPath
                + ".done.tmp";

            string final =
                bodyPath
                + ".done.json";

            using (
                var writer =
                    new StreamWriter(
                        new FileStream(
                            temporary,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.Read
                        ),
                        new UTF8Encoding(false)
                    )
            )
            {
                writer.Write(
                    serializer.Serialize(
                        seal
                    )
                );
            }

            File.Move(
                temporary,
                final
            );

            RecordLifecycle(
                "CAPTURE_SEAL_WRITTEN",
                null
            );
        }
    }
}
