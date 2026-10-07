// Market-data-only NinjaScript indicator. No accounts, orders, ATI or network.
// Compile in NinjaScript Editor; configure UTC and an explicit NQ minute chart.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using System.Windows.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsReadOnlyMarketV1 : Indicator
    {
        private readonly object sync = new object();
        private StreamWriter writer;
        private StreamWriter connectionWriter;
        private long connectionSequence;
        private DispatcherTimer timer;
        private string session, contract, template, expiry;
        private long sequence;
        private int firstRealtimeBar;
        private bool failed;
        private Connection source;
        private readonly ReadinessGate readiness = new ReadinessGate();
        private readonly Stopwatch startupClock = new Stopwatch();
        private System.Threading.Timer startupDeadline;
        private bool helloSent, started;
        private TimingEvidence timing;
        private string bindingRuntimeId, bindingNonce, bindingClaimSha256, bindingHandoffSha256;

        [NinjaScriptProperty]
        [Display(Name = "One Click binding file", Order = 1, GroupName = "ARMS read only")]
        public string OneClickBindingFile { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Private output directory", Order = 2, GroupName = "ARMS read only")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expected provider enum", Order = 3, GroupName = "ARMS read only")]
        public string ExpectedProvider { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsReadOnlyMarketV1";
                Description = "One-way current market JSONL; no execution authority.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;
                OneClickBindingFile = "";
                OutputDirectory = "";
                ExpectedProvider = "";
            }
            else if (State == State.Realtime)
            {
                lock (sync)
                {
                    if (started || failed) { Stop("STOP_LIFECYCLE_REENTRY"); return; }
                    started = true;
                    startupClock.Start();
                    string startupStage = "SOURCE_VALIDATION";
                    try
                    {
                        if (!String.IsNullOrWhiteSpace(OneClickBindingFile)) ResolveOneClickBinding();
                        contract = Instrument.FullName;
                        template = Bars.TradingHours.Name;
                        expiry = Instrument.Expiry.ToString("yyyy-MM-dd");
                        if (String.IsNullOrWhiteSpace(OutputDirectory) || !Path.IsPathRooted(OutputDirectory)
                            || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\")
                            || !Directory.Exists(OutputDirectory)
                            || !SafeSource()) throw new InvalidOperationException();
                        session = Guid.NewGuid().ToString();
                        startupStage = "FILE_OPEN";
                        var file = new FileStream(Path.Combine(OutputDirectory, session + ".jsonl"),
                            FileMode.CreateNew, FileAccess.Write, FileShare.Read);
                        writer = new StreamWriter(file, new UTF8Encoding(false));
                        writer.AutoFlush = true;
                        startupStage = "CONNECTION_DIAGNOSTIC_OPEN";
                        connectionWriter = new StreamWriter(new FileStream(
                            Path.Combine(OutputDirectory, session + ".connection.jsonl"),
                            FileMode.CreateNew, FileAccess.Write, FileShare.Read), new UTF8Encoding(false));
                        connectionWriter.AutoFlush = true;
                        if (!String.IsNullOrWhiteSpace(bindingNonce)) WriteBindingReceipt();
                        firstRealtimeBar = -1;
                        // No HELLO (reader readiness) or candles during STARTING.
                        startupStage = "DEADLINE_SCHEDULE";
                        startupDeadline = new System.Threading.Timer(_ => {
                            lock (sync)
                            {
                                if (!failed && readiness.State == "STARTING") Stop("STOP_STARTUP_TIMEOUT");
                            }
                        }, null, Math.Max(1, 30000 - (int)startupClock.ElapsedMilliseconds), System.Threading.Timeout.Infinite);
                        // Indicator dispatcher timer, as used by the native BarTimer.
                        startupStage = "HEARTBEAT_SCHEDULE";
                        if (ChartControl == null) { Stop("CHART_UNAVAILABLE"); return; }
                        ChartControl.Dispatcher.InvokeAsync(new Action(() => {
                            lock (sync)
                            {
                                if (failed || writer == null) return;
                                try
                                {
                                    timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(5) };
                                    timer.Tick += Heartbeat;
                                    timer.Start();
                                }
                                catch (Exception error) { Stop("HEARTBEAT_START_FAILED", ErrorCode(error)); }
                            }
                        }));
                    }
                    catch (Exception error) { Stop("STARTUP_" + startupStage + "_FAILED", ErrorCode(error)); }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync) Stop("TERMINATED");
            }
            else if (started)
            {
                lock (sync) Stop("STOP_LIFECYCLE_CHANGED");
            }
        }

        private static string Text(IDictionary<string, object> value, string key)
        {
            object raw;
            if (!value.TryGetValue(key, out raw) || !(raw is string) || String.IsNullOrWhiteSpace((string)raw))
                throw new InvalidOperationException();
            return (string)raw;
        }

        private static bool SafeLocalPath(string value, bool directory)
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

        private static string HexSha256(string value)
        {
            using (var hash = SHA256.Create())
                return String.Concat(hash.ComputeHash(Encoding.UTF8.GetBytes(value)).Select(b => b.ToString("x2")));
        }

        private static bool Hex(string value, int length)
        {
            return value != null && value.Length == length
                && value.All(character => (character >= '0' && character <= '9')
                    || (character >= 'a' && character <= 'f'));
        }

        private void ResolveOneClickBinding()
        {
            if (!SafeLocalPath(OneClickBindingFile, false)
                || Path.GetFileName(OneClickBindingFile) != "active-binding.json"
                || new DirectoryInfo(Path.GetDirectoryName(OneClickBindingFile)).Name != "one-click-native-control")
                throw new InvalidOperationException();
            var serializer = new JavaScriptSerializer();
            var control = serializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(OneClickBindingFile, Encoding.UTF8));
            if (control.Count != 4 || Text(control, "schema") != "arms.one-click-native-binding-control.v1"
                || Text(control, "state") != "ACTIVE") throw new InvalidOperationException();
            string claimJson = Text(control, "claim_json");
            string claimSha = Text(control, "claim_sha256");
            if (!Hex(claimSha, 64) || HexSha256(claimJson) != claimSha) throw new InvalidOperationException();
            var claim = serializer.Deserialize<Dictionary<string, object>>(claimJson);
            string[] authorities = { "execution_authority", "order_authority", "paper_execution_authority",
                "live_execution_authority", "broker_authority", "strategy_enable_authority",
                "ninjatrader_control_authority", "paper_execution_enabled", "live_execution_allowed",
                "external_order_authority", "broker_live_order_authority" };
            if (claim.Count != 32 || Text(claim, "schema") != "arms.one-click-native-binding-claim.v1"
                || authorities.Any(key => !claim.ContainsKey(key) || !(claim[key] is bool) || (bool)claim[key])
                || Convert.ToInt32(claim["generation"], CultureInfo.InvariantCulture) != 1
                || Convert.ToInt32(claim["apply_limit"], CultureInfo.InvariantCulture) != 1)
                throw new InvalidOperationException();
            DateTime created, expires;
            if (!DateTime.TryParse(Text(claim, "created_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out created)
                || !DateTime.TryParse(Text(claim, "expires_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out expires)
                || created > DateTime.UtcNow || DateTime.UtcNow > expires
                || expires <= created || expires - created > TimeSpan.FromSeconds(60))
                throw new InvalidOperationException();
            string runtime = Text(claim, "runtime_directory");
            string parent = Text(claim, "runtime_parent");
            string inbox = Text(claim, "live_inbox");
            string catchup = Text(claim, "catchup_output_directory");
            Guid runtimeGuid;
            string runtimeId = Text(claim, "native_runtime_id");
            if (!Guid.TryParseExact(runtimeId, "D", out runtimeGuid) || runtimeGuid.ToString("D") != runtimeId
                || !SafeLocalPath(parent, true) || !SafeLocalPath(runtime, true) || !SafeLocalPath(inbox, true)
                || !SafeLocalPath(catchup, true) || Directory.GetParent(runtime).FullName != parent
                || Path.GetFileName(runtime) != runtimeId || Path.Combine(runtime, "inbox") != inbox
                || Path.Combine(runtime, "chart-catchup") != catchup
                || Directory.GetParent(parent).FullName != Directory.GetParent(Path.GetDirectoryName(OneClickBindingFile)).FullName
                || Text(claim, "expected_provider") != "Provider31" || Text(claim, "contract") != "NQ DEC26"
                || Text(claim, "bars_period") != "Minute" || Convert.ToInt32(claim["bars_value"], CultureInfo.InvariantCulture) != 1
                || Text(claim, "trading_hours") != "CME US Index Futures ETH"
                || Text(claim, "through_close_utc") != "LATEST_CLOSED"
                || !Regex.IsMatch(Text(claim, "one_click_run_id"), @"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
                || !Hex(Text(claim, "binding_nonce"), 64) || !Hex(Text(claim, "handoff_file_sha256"), 64)
                || !Hex(Text(claim, "phase3_source_sha256"), 64))
                throw new InvalidOperationException();
            DateTime from;
            if (!DateTime.TryParse(Text(claim, "from_close_utc"), CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out from)) throw new InvalidOperationException();
            OutputDirectory = inbox;
            ExpectedProvider = Text(claim, "expected_provider");
            bindingRuntimeId = runtimeId;
            bindingNonce = Text(claim, "binding_nonce");
            bindingClaimSha256 = claimSha;
            bindingHandoffSha256 = Text(claim, "handoff_file_sha256");
        }

        private void WriteBindingReceipt()
        {
            var receipt = new Dictionary<string, object> {
                { "schema", "arms.nt.one-click-binding-receipt.v1" }, { "session", session },
                { "native_runtime_id", bindingRuntimeId }, { "binding_nonce", bindingNonce },
                { "binding_claim_sha256", bindingClaimSha256 }, { "handoff_file_sha256", bindingHandoffSha256 },
                { "read_only", true }, { "execution_authority", false }, { "order_authority", false },
                { "paper_execution_authority", false }, { "live_execution_authority", false },
                { "broker_authority", false }, { "strategy_enable_authority", false },
                { "ninjatrader_control_authority", false }, { "paper_execution_enabled", false },
                { "live_execution_allowed", false }, { "external_order_authority", false },
                { "broker_live_order_authority", false } };
            using (var stream = new FileStream(Path.Combine(OutputDirectory, session + ".one-click-binding.json"),
                FileMode.CreateNew, FileAccess.Write, FileShare.Read, 4096, FileOptions.WriteThrough))
            using (var output = new StreamWriter(stream, new UTF8Encoding(false)))
            {
                output.WriteLine(new JavaScriptSerializer().Serialize(receipt));
                output.Flush();
                stream.Flush(true);
            }
        }

        private bool SafeSource()
        {
            if (Connection.PlaybackConnection != null || Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                || BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 1
                || Instrument.MasterInstrument.Name != "NQ" || Instrument.FullName != contract
                || Instrument.Expiry.ToString("yyyy-MM-dd") != expiry || Bars.TradingHours.Name != template
                || Instrument.MasterInstrument.TickSize != .25 || Instrument.MasterInstrument.PointValue != 20
                || ExpectedProvider.ToLowerInvariant().Contains("simulat")
                || ExpectedProvider.ToLowerInvariant().Contains("playback")) return false;
            if (!System.Threading.Monitor.TryEnter(Connection.Connections)) return false;
            try
            {
                // Do not hide an additional transitioning futures source by filtering its status.
                var feeds = Connection.Connections.Where(c => c != null
                    && c.InstrumentTypes.Contains(InstrumentType.Future)).ToArray();
                if (feeds.Length != 1) return false;
                if (ProviderName(feeds[0]) != ExpectedProvider)
                {
                    // Enum only: no connection name, credentials or account IDs.
                    Print("ARMS_READ_ONLY_PROVIDER_ENUM=" + ProviderName(feeds[0]));
                    return false;
                }
                if (source != null && source != feeds[0]) return false;
                var price = StatusName(feeds[0].PriceStatus);
                var status = StatusName(feeds[0].Status);
                if (price != "Connected" || status != "Connected"
                    || StatusName(feeds[0].PriceStatus) != price || StatusName(feeds[0].Status) != status
                    || ProviderName(feeds[0]) != ExpectedProvider)
                    return false;
                source = feeds[0];
                return true;
            }
            finally { System.Threading.Monitor.Exit(Connection.Connections); }
        }

        private void Emit(string kind, object payload)
        {
            writer.WriteLine(new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.market.v1", session = session, sequence = sequence++,
                event_time = DateTime.UtcNow.ToString("o"), kind = kind, payload = payload }));
        }

        private object Candle(int ago)
        {
            var volume = Volume[ago];
            if (Double.IsNaN(volume) || Double.IsInfinity(volume) || volume < 0
                || volume >= (double)Int64.MaxValue || volume != Math.Truncate(volume))
                throw new InvalidOperationException("INVALID_VOLUME");
            return new { bar_time = DateTime.SpecifyKind(Time[ago], DateTimeKind.Utc).ToString("o"),
                open = Open[ago], high = High[ago], low = Low[ago], close = Close[ago], volume = (long)volume };
        }

        protected override void OnBarUpdate()
        {
            if (State != State.Realtime || BarsInProgress != 0 || !IsFirstTickOfBar) return;
            var callbackPair = TimingEvidence.ReadPair(); // After eligibility guards, before lock/metadata/I/O.
            lock (sync)
            {
                if (failed || writer == null) return;
                try
                {
                    if (!SafeSource()) { Stop("BAR_SOURCE_VALIDATION_FAILED"); return; }
                    if (readiness.State != "READY" || !helloSent) return;
                    // Anchor to an observed callback, not CurrentBar at the state
                    // transition (which can precede the first realtime bar).
                    if (firstRealtimeBar < 0) firstRealtimeBar = CurrentBar;
                    // First realtime bar may contain historical/partial observations.
                    // Wait until an entire subsequent bar was observed in real time.
                    if (CurrentBar - 1 > firstRealtimeBar) EmitTimedBar("CLOSED", Candle(1), callbackPair, 1);
                    EmitTimedBar("FORMING", Candle(0), callbackPair, 0);
                }
                catch (Exception error) { Stop("BAR_CALLBACK_FAILED", ErrorCode(error)); }
            }
        }

        private void EmitTimedBar(string kind, object payload, TimingEvidence.Pair callback, int ago)
        {
            var emission = TimingEvidence.ReadPair();
            // Exactly this UTC observation supplies the existing canonical field.
            string utc = emission == null ? DateTime.UtcNow.ToString("o") : emission.utc;
            long rowSequence = sequence++;
            string row = new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.market.v1", session = session, sequence = rowSequence,
                event_time = utc, kind = kind, payload = payload });
            writer.WriteLine(row); // Canonical errors still follow the original BAR_CALLBACK_FAILED path.
            try
            {
                if (timing == null) timing = new TimingEvidence(OutputDirectory, session);
                timing.Record(row, rowSequence, kind, callback, emission, CurrentBar, CurrentBar - ago,
                    ago, DateTime.SpecifyKind(Time[ago], DateTimeKind.Utc).ToString("o"),
                    State.ToString(), BarsInProgress, IsFirstTickOfBar, ExpectedProvider, contract, template);
            }
            catch { if (timing != null) timing.Invalidate(); }
            // Timing failure invalidates provenance only; never changes certified candle admission.
        }

        private sealed class TimingEvidence
        {
            public sealed class Pair
            {
                public long qpc_before, utc_ticks, qpc_after;
                public string utc;
            }
            public static Pair ReadPair()
            {
                try
                {
                    if (!System.Diagnostics.Stopwatch.IsHighResolution) return null;
                    long before = System.Diagnostics.Stopwatch.GetTimestamp();
                    DateTime wall = DateTime.UtcNow;
                    long after = System.Diagnostics.Stopwatch.GetTimestamp();
                    return new Pair { qpc_before = before, utc_ticks = wall.Ticks, qpc_after = after, utc = wall.ToString("o") };
                }
                catch { return null; }
            }
            private StreamWriter output;
            private System.Security.Cryptography.SHA256 digest;
            private string path, owner;
            private long records, bytes;
            private bool invalid, closed;
            public TimingEvidence(string directory, string sessionId)
            {
                owner = sessionId;
                try
                {
                    // Isolated child directory: existing top-level *.jsonl consumers are unchanged.
                    string folder = Path.Combine(directory, "timing");
                    Directory.CreateDirectory(folder);
                    path = Path.Combine(folder, owner + ".production-timing.jsonl");
                    output = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                        FileShare.Read), new UTF8Encoding(false));
                    output.NewLine = "\n";
                    output.AutoFlush = true;
                    digest = System.Security.Cryptography.SHA256.Create();
                }
                catch { Invalidate(); }
            }
            private static string Hex(byte[] value)
            { return BitConverter.ToString(value).Replace("-", "").ToLowerInvariant(); }
            public void Record(string row, long rowSequence, string kind, Pair callback, Pair emission,
                int callbackIndex, int barIndex, int ago, string label, string state, int series, bool firstTick,
                string provider, string contractName, string tradingHours)
            {
                if (invalid || closed) return;
                try
                {
                    if (callback == null || emission == null) { Invalidate(); return; }
                    string rowHash;
                    using (var h = System.Security.Cryptography.SHA256.Create())
                        rowHash = Hex(h.ComputeHash(Encoding.UTF8.GetBytes(row)));
                    string line = new JavaScriptSerializer().Serialize(new {
                        schema = "arms.nt.production-timing.v1", session = owner, pair_sequence = records,
                        canonical_sequence = rowSequence, canonical_sha256 = rowHash, kind = kind,
                        source_bar_label = label, callback = callback, emission = emission,
                        qpc_frequency = System.Diagnostics.Stopwatch.Frequency,
                        callback_index = callbackIndex, bar_index = barIndex, bars_ago = ago,
                        state = state, bars_in_progress = series, first_tick = firstTick,
                        provider = provider, contract = contractName, instrument = "NQ", bars_type = "Minute", bars_value = 1,
                        application_timezone = "UTC", template = tradingHours, bar_label = "CLOSE",
                        observation_only = true, runtime_admission = false });
                    output.WriteLine(line);
                    byte[] encoded = Encoding.UTF8.GetBytes(line + "\n");
                    digest.TransformBlock(encoded, 0, encoded.Length, encoded, 0);
                    bytes += encoded.Length; records++;
                }
                catch { Invalidate(); }
            }
            public void Invalidate()
            {
                invalid = true;
                try { if (output != null) output.Dispose(); } catch { }
                try { if (digest != null) digest.Dispose(); } catch { }
                output = null; digest = null;
            }
            public void Close(long canonicalRecords, bool canonicalClosed, bool terminalWritten)
            {
                if (closed) return;
                closed = true;
                try
                {
                    if (invalid || !canonicalClosed || !terminalWritten) { Invalidate(); return; }
                    output.Dispose(); output = null;
                    digest.TransformFinalBlock(new byte[0], 0, 0);
                    string hash = Hex(digest.Hash); digest.Dispose(); digest = null;
                    using (var seal = new StreamWriter(new FileStream(path + ".done.tmp", FileMode.CreateNew,
                        FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                        seal.Write(new JavaScriptSerializer().Serialize(new {
                            schema = "arms.nt.production-timing.seal.v1", session = owner, records = records,
                            bytes = bytes, sha256 = hash, canonical_records = canonicalRecords,
                            canonical_writer_closed = true, timing_writer_closed = true, complete = true }));
                    File.Move(path + ".done.tmp", path + ".done.json");
                }
                catch { Invalidate(); } // No valid seal on any closure/integrity failure.
            }
        }

        private void Heartbeat(object sender, EventArgs args)
        {
            lock (sync)
            {
                if (failed || writer == null) return;
                try
                {
                    if (!SafeSource()) { Stop("HEARTBEAT_SOURCE_VALIDATION_FAILED"); return; }
                    if (!readiness.Poll(true, startupClock.ElapsedMilliseconds))
                    {
                        if (readiness.State == "STOPPED") Stop(readiness.Reason);
                        return;
                    }
                    if (!helloSent)
                    {
                        // Reanchor after admission; no startup/partial candle is replayed.
                        firstRealtimeBar = -1;
                        Emit("HELLO", new { provider = ExpectedProvider, contract = contract, expiry = expiry,
                            instrument = "NQ", tick_size = .25, point_value = 20, timeframe = "1m",
                            trading_hours_template = template, source_timezone = "UTC", bar_label = "CLOSE",
                            realtime = true, read_only = true });
                        helloSent = true;
                        if (startupDeadline != null) { startupDeadline.Dispose(); startupDeadline = null; }
                    }
                    Emit("HEARTBEAT", new { connected = true });
                }
                catch (Exception error) { Stop("HEARTBEAT_CALLBACK_FAILED", ErrorCode(error)); }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            var received = DateTime.UtcNow.ToString("o");
            lock (sync)
            {
                // Diagnostics can precede HELLO; they cannot grant admission.
                if (writer == null || failed) return;
                try
                {
                    // Copy scalar event values synchronously; never queue provider objects.
                    var callback = Object.ReferenceEquals(update, null) ? null : update.Connection;
                    var selected = source;
                    var price = callback == null ? "UNKNOWN" : StatusName(update.PriceStatus);
                    var previousPrice = callback == null ? "UNKNOWN" : StatusName(update.PreviousPriceStatus);
                    var status = callback == null ? "UNKNOWN" : StatusName(update.Status);
                    var previousStatus = callback == null ? "UNKNOWN" : StatusName(update.PreviousStatus);
                    var currentPrice = selected == null ? "UNKNOWN" : StatusName(selected.PriceStatus);
                    var currentStatus = selected == null ? "UNKNOWN" : StatusName(selected.Status);
                    var callbackProvider = ProviderName(callback);
                    var selectedProvider = ProviderName(selected);
                    var currentPriceAfter = selected == null ? "UNKNOWN" : StatusName(selected.PriceStatus);
                    var currentStatusAfter = selected == null ? "UNKNOWN" : StatusName(selected.Status);
                    var same = callback != null && Object.ReferenceEquals(callback, selected);
                    var stable = Object.ReferenceEquals(source, selected)
                        && currentPrice == currentPriceAfter && currentStatus == currentStatusAfter;
                    var decision = readiness.Event(
                        currentPrice == "Connected" && currentPriceAfter == "Connected" && currentStatus == "Connected"
                            && currentStatusAfter == "Connected",
                        same && callbackProvider == selectedProvider && selectedProvider == ExpectedProvider,
                        !new[] { price, previousPrice, status, previousStatus, currentPrice, currentStatus,
                            currentPriceAfter, currentStatusAfter, callbackProvider, selectedProvider }.Contains("UNKNOWN"),
                        stable, price, status, previousPrice, previousStatus);
                    if (!failed && startupClock.ElapsedMilliseconds >= 30000 && readiness.State == "STARTING")
                        decision = readiness.Revoke("STOP_STARTUP_TIMEOUT");
                    connectionWriter.WriteLine(new JavaScriptSerializer().Serialize(new {
                        schema = "arms.nt.connection-diagnostic.v1", session = session,
                        sequence = connectionSequence++, event_time = DateTime.UtcNow.ToString("o"),
                        callback_received_time = received, market_next_sequence = sequence,
                        kind = "CONNECTION_STATUS", payload = new {
                            callback_price_status = price, callback_previous_price_status = previousPrice,
                            callback_connection_status = status, callback_previous_connection_status = previousStatus,
                            source_price_status = currentPrice, source_connection_status = currentStatus,
                            source_price_status_after = currentPriceAfter, source_connection_status_after = currentStatusAfter,
                            same_source = same, source_present = selected != null, callback_present = callback != null,
                            source_snapshot_stable = stable, callback_provider = callbackProvider,
                            source_provider = selectedProvider, decision = decision } }));
                    if (decision != "CONTINUE" && decision != "WAIT_STARTUP_ALIGNMENT") Stop(decision);
                }
                catch (Exception error) { Stop("STOP_CONNECTION_DIAGNOSTIC_FAILED", ErrorCode(error)); }
            }
        }

        private static string StatusName(ConnectionStatus value)
        {
            return Enum.IsDefined(typeof(ConnectionStatus), value) ? value.ToString() : "UNKNOWN";
        }

        private static string ProviderName(Connection connection)
        {
            if (connection == null || connection.Options == null) return "UNKNOWN";
            var provider = connection.Options.Provider;
            return Enum.IsDefined(provider.GetType(), provider) ? provider.ToString() : "UNKNOWN";
        }

        private sealed class ReadinessGate
        {
            public string State = "STARTING";
            private bool aligned;
            public string Event(bool healthy, bool identity, bool known, bool stable,
                string price, string status, string previousPrice, string previousStatus)
            {
                if (State == "STOPPED") return "STOP_LATCHED";
                if (!known) return Revoke("STOP_UNKNOWN_CONNECTION_STATE");
                if (!identity) return Revoke("STOP_CONNECTION_IDENTITY_MISMATCH");
                if (!stable) return Revoke("STOP_UNSTABLE_CONNECTION_STATE");
                if (!healthy) return Revoke("STOP_CURRENT_CONNECTION_NOT_READY");
                if (new[] { price, status }.Any(s => s == "Disconnected" || s == "Disconnecting" || s == "ConnectionLost"))
                    return Revoke("STOP_CONNECTION_LOSS_EVENT");
                if (new[] { previousPrice, previousStatus }.Any(s => s == "Disconnecting" || s == "ConnectionLost")
                    || (State == "READY" && (previousPrice != "Connected" || previousStatus != "Connected")))
                    return Revoke("STOP_RECONNECT_OR_UNPROVEN_CONTINUITY");
                if (price != "Connected" || status != "Connected")
                {
                    aligned = false;
                    if (State == "READY" || previousPrice == "Connected" || previousStatus == "Connected")
                        return Revoke("STOP_CONNECTION_REGRESSION");
                    // Quarantine, never ignore or declare this event stale. No admission.
                    return "WAIT_STARTUP_ALIGNMENT";
                }
                aligned = true;
                return "CONTINUE"; // A callback cannot grant READY.
            }

            public bool Poll(bool healthy, double elapsed)
            {
                if (State == "STOPPED") return false;
                if (!healthy) { Revoke("STOP_CURRENT_CONNECTION_NOT_READY"); return false; }
                if (State == "STARTING")
                {
                    if (elapsed >= 30000) { Revoke("STOP_STARTUP_TIMEOUT"); return false; }
                    if (!aligned) return false;
                    State = "READY";
                }
                return true;
            }

            public string Reason;
            public string Revoke(string reason) { State = "STOPPED"; Reason = reason; return reason; }
        }

        // Fixed categories only. Never serialize Message, StackTrace, connection
        // names, file paths or other provider-owned exception text.
        private static string ErrorCode(Exception error)
        {
            if (error is NullReferenceException) return "NULL_REFERENCE";
            if (error is InvalidOperationException) return "INVALID_OPERATION";
            if (error is UnauthorizedAccessException) return "ACCESS_DENIED";
            if (error is IOException) return "IO_ERROR";
            if (error is ArgumentException) return "INVALID_ARGUMENT";
            return "OTHER";
        }

        private void Stop(string reason, string errorCode = "NONE")
        {
            if (failed) return;
            failed = true;
            readiness.Revoke(reason);
            if (startupDeadline != null)
            {
                try { startupDeadline.Dispose(); } catch { }
                startupDeadline = null;
            }
            try { Print("ARMS_READ_ONLY_STOP reason=" + reason + " error=" + errorCode); } catch { }
            if (timer != null)
            {
                try { timer.Stop(); timer.Tick -= Heartbeat; } catch { }
                timer = null;
            }
            bool canonicalClosed = false, terminalWritten = false;
            if (writer != null)
            {
                try { Emit("DISCONNECTED", new { connected = false, reason = reason, error_code = errorCode }); terminalWritten = true; } catch { }
                try { writer.Dispose(); canonicalClosed = true; } catch { }
                writer = null;
            }
            if (connectionWriter != null)
            {
                try { connectionWriter.Dispose(); } catch { }
                connectionWriter = null;
            }
            if (timing != null) { timing.Close(sequence, canonicalClosed, terminalWritten); timing = null; }
            // No native error strings, account identifiers or personal paths logged.
        }
    }
}
