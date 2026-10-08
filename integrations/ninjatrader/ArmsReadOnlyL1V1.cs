// Native BID/ASK observations only. No account objects or order interfaces.
// Separate indicator/directory preserves the hash-pinned candle exporter.
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
using System.Windows.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsReadOnlyL1V1 : Indicator
    {
        private const long L1_STREAM_MAX_BYTES = 256L * 1024 * 1024;
        private const int TERMINAL_RESERVE_BYTES = 4096;
        private const string ManifestSchema = "arms.nt.l1.manifest.v1";
        private readonly object sync = new object();
        private readonly List<Dictionary<string, object>> sealedSegments = new List<Dictionary<string, object>>();
        private StreamWriter output;
        private DispatcherTimer timer;
        private System.Threading.Timer bindingWatcher;
        private Connection source;
        private string session, manifestPath, segmentPath;
        private long sequence, bytes, segmentFirstSequence;
        private int segmentIndex;
        private bool started, stopped;
        private bool bindingSessionActive, bindingPollQueued;
        private int bindingGeneration, lastAcceptedBindingGeneration;
        private string bindingRunId, bindingRuntimeId, bindingNonce, bindingClaimSha256;
        private string lastAcceptedBindingRunId, lastAcceptedBindingRuntimeId;
        private string lastAcceptedBindingNonce, lastAcceptedBindingClaimSha256;
        private double? bid, ask;
        private DateTime bidTime, askTime, lastTime;

        [NinjaScriptProperty]
        [Display(Name = "One Click binding file", Order = 1, GroupName = "ARMS read only L1")]
        public string OneClickBindingFile { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Private L1 output directory", Order = 2, GroupName = "ARMS read only L1")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expected provider enum", Order = 3, GroupName = "ARMS read only L1")]
        public string ExpectedProvider { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsReadOnlyL1V1";
                Description = "Native two-sided L1 observations; no execution capability.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true; IsChartOnly = true; IsSuspendedWhileInactive = false;
                OneClickBindingFile = ""; OutputDirectory = ""; ExpectedProvider = "";
                return;
            }
            if (State == State.Realtime)
            {
                lock (sync)
                {
                    if (!String.IsNullOrWhiteSpace(OneClickBindingFile)) StartBindingWatcher();
                    else if (started || stopped) Stop("LIFECYCLE_REENTRY");
                    else StartObservation();
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
                    Stop("SESSION_TERMINATED");
                }
            }
            else if (started) lock (sync) Stop("SESSION_TERMINATED");
        }

        private void StartObservation()
        {
            if (started || stopped) return;
            started = true;
            try
            {
                if (!SafeSource() || ChartControl == null || String.IsNullOrWhiteSpace(OutputDirectory)
                    || !SafeLocalPath(OutputDirectory, true)) throw new InvalidOperationException();
                sealedSegments.Clear(); sequence = 0; segmentIndex = 0; lastTime = default(DateTime);
                session = Guid.NewGuid().ToString();
                manifestPath = Path.Combine(OutputDirectory, session + ".l1.manifest.json");
                OpenSegment(1);
                WriteManifest("ACTIVE", null);
                Emit("HELLO", new { provider = ExpectedProvider, contract = "NQ DEC26", instrument = "NQ",
                    expiry = "2026-12-01", tick_size = .25, point_value = 20, application_timezone = "UTC",
                    trading_hours_template = "CME US Index Futures ETH", realtime = true, read_only = true, level = 1 }, DateTime.UtcNow);
                Print("ARMS_L1_HELLO");
                ChartControl.Dispatcher.InvokeAsync(new Action(() => {
                    lock (sync)
                    {
                        if (stopped || !started) return;
                        try { timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(5) };
                            timer.Tick += Heartbeat; timer.Start(); }
                        catch { Stop("HEARTBEAT_START_FAILED"); }
                    }
                }));
            }
            catch (StreamCapacityException) { Stop("STREAM_CAPACITY_REACHED"); }
            catch (IOException) { Stop("FILE_IO_ERROR"); }
            catch { Stop("CALLBACK_EXCEPTION"); }
        }

        private void StartBindingWatcher()
        {
            if (bindingWatcher != null || stopped) return;
            if (!SafeBindingControlPath(OneClickBindingFile)
                || Path.GetFileName(OneClickBindingFile) != "active-binding.json"
                || new DirectoryInfo(Path.GetDirectoryName(OneClickBindingFile)).Name != "one-click-native-control")
            { Stop("BINDING_WATCH_PATH_INVALID"); return; }
            bindingWatcher = new System.Threading.Timer(_ => QueueBindingPoll(), null, 0, 500);
        }

        private void QueueBindingPoll()
        {
            lock (sync)
            {
                if (stopped || bindingPollQueued) return;
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
                if (stopped) return;
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
                    string state = Text(control, "state");
                    if (state == "REVOKED")
                    {
                        string[] revokedAuthorities = { "execution_authority", "order_authority", "paper_execution_authority",
                            "live_execution_authority", "broker_authority", "strategy_enable_authority",
                            "ninjatrader_control_authority", "paper_execution_enabled", "live_execution_allowed",
                            "external_order_authority", "broker_live_order_authority" };
                        int revokedGeneration = control.ContainsKey("generation")
                            ? Convert.ToInt32(control["generation"], CultureInfo.InvariantCulture) : 0;
                        string revokedRun = Text(control, "one_click_run_id");
                        string revokedRuntime = Text(control, "native_runtime_id");
                        Guid revokedGuid;
                        if ((control.Count != 16 && control.Count != 17)
                            || Text(control, "schema") != "arms.one-click-native-binding-control.v1"
                            || revokedAuthorities.Any(key => !control.ContainsKey(key) || !(control[key] is bool) || (bool)control[key])
                            || revokedGeneration < 0
                            || !Regex.IsMatch(revokedRun, @"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
                            || !Guid.TryParseExact(revokedRuntime, "D", out revokedGuid)
                            || revokedGuid.ToString("D") != revokedRuntime) return;
                        if (lastAcceptedBindingGeneration > 0
                            && (revokedGeneration != lastAcceptedBindingGeneration
                                || revokedRun != lastAcceptedBindingRunId
                                || revokedRuntime != lastAcceptedBindingRuntimeId)) return;
                        if (started) CloseObservation("BINDING_REVOKED");
                        bindingSessionActive = false;
                        return;
                    }
                    if (state != "ACTIVE") return;
                    string priorRun = bindingRunId, priorRuntime = bindingRuntimeId;
                    string priorNonce = bindingNonce, priorClaim = bindingClaimSha256;
                    int priorGeneration = bindingGeneration;
                    ResolveOneClickBinding(text);
                    if (bindingGeneration < lastAcceptedBindingGeneration
                        || (bindingGeneration == lastAcceptedBindingGeneration
                            && (bindingNonce != lastAcceptedBindingNonce
                                || bindingClaimSha256 != lastAcceptedBindingClaimSha256
                                || bindingRuntimeId != lastAcceptedBindingRuntimeId
                                || bindingRunId != lastAcceptedBindingRunId)))
                    {
                        bindingRunId = priorRun; bindingRuntimeId = priorRuntime;
                        bindingNonce = priorNonce; bindingClaimSha256 = priorClaim;
                        bindingGeneration = priorGeneration;
                        throw new InvalidOperationException();
                    }
                    if (bindingGeneration == lastAcceptedBindingGeneration) return;
                    if (started) CloseObservation("BINDING_GENERATION_REPLACED");
                    lastAcceptedBindingGeneration = bindingGeneration;
                    lastAcceptedBindingRunId = bindingRunId;
                    lastAcceptedBindingRuntimeId = bindingRuntimeId;
                    lastAcceptedBindingNonce = bindingNonce;
                    lastAcceptedBindingClaimSha256 = bindingClaimSha256;
                    bindingSessionActive = true;
                    StartObservation();
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
                catch (InvalidOperationException) { }
                catch (ArgumentException) { }
                catch (FormatException) { }
            }
        }

        private static string Text(IDictionary<string, object> value, string key)
        {
            object raw;
            if (!value.TryGetValue(key, out raw) || !(raw is string)
                || String.IsNullOrWhiteSpace((string)raw)) throw new InvalidOperationException();
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
                if ((item.Attributes & FileAttributes.ReparsePoint) != 0) return false;
                item = item is DirectoryInfo ? ((DirectoryInfo)item).Parent : ((FileInfo)item).Directory;
            }
            return new DriveInfo(Path.GetPathRoot(full)).DriveType == DriveType.Fixed;
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

        private void ResolveOneClickBinding(string controlJson)
        {
            if (!SafeLocalPath(OneClickBindingFile, false)
                || Path.GetFileName(OneClickBindingFile) != "active-binding.json"
                || new DirectoryInfo(Path.GetDirectoryName(OneClickBindingFile)).Name != "one-click-native-control")
                throw new InvalidOperationException();
            var serializer = new JavaScriptSerializer();
            var control = serializer.Deserialize<Dictionary<string, object>>(controlJson);
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
                || Convert.ToInt32(claim["generation"], CultureInfo.InvariantCulture) <= 0
                || Convert.ToInt32(claim["apply_limit"], CultureInfo.InvariantCulture) != 1)
                throw new InvalidOperationException();
            DateTime created, expires;
            if (!DateTime.TryParse(Text(claim, "created_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out created)
                || !DateTime.TryParse(Text(claim, "expires_utc"), CultureInfo.InvariantCulture,
                    DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out expires)
                || created > DateTime.UtcNow || DateTime.UtcNow > expires
                || expires <= created || expires - created > TimeSpan.FromSeconds(900))
                throw new InvalidOperationException();
            string runtime = Text(claim, "runtime_directory");
            string parent = Text(claim, "runtime_parent");
            string inbox = Text(claim, "live_inbox");
            string catchup = Text(claim, "catchup_output_directory");
            string runId = Text(claim, "one_click_run_id");
            string runtimeId = Text(claim, "native_runtime_id");
            Guid runtimeGuid;
            string expectedL1 = Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData), "ARMS-AI", "current-paper-l1-v1", runId);
            if (!Guid.TryParseExact(runtimeId, "D", out runtimeGuid) || runtimeGuid.ToString("D") != runtimeId
                || !SafeLocalPath(parent, true) || !SafeLocalPath(runtime, true)
                || !SafeLocalPath(inbox, true) || !SafeLocalPath(catchup, true)
                || Directory.GetParent(runtime).FullName != parent || Path.GetFileName(runtime) != runtimeId
                || Path.Combine(runtime, "inbox") != inbox || Path.Combine(runtime, "chart-catchup") != catchup
                || Directory.GetParent(parent).FullName != Directory.GetParent(Path.GetDirectoryName(OneClickBindingFile)).FullName
                || !Regex.IsMatch(runId, @"^[0-9]{8}T[0-9]{6}Z-oneclick-[0-9a-f]{12}$")
                || Path.GetFullPath(OutputDirectory) != expectedL1 || !SafeLocalPath(OutputDirectory, true)
                || Text(claim, "expected_provider") != "Provider31" || ExpectedProvider != "Provider31"
                || Text(claim, "contract") != "NQ DEC26" || Text(claim, "bars_period") != "Minute"
                || Convert.ToInt32(claim["bars_value"], CultureInfo.InvariantCulture) != 1
                || Text(claim, "trading_hours") != "CME US Index Futures ETH"
                || Text(claim, "through_close_utc") != "LATEST_CLOSED"
                || !Hex(Text(claim, "binding_nonce"), 64)
                || !Hex(Text(claim, "handoff_file_sha256"), 64)
                || !Hex(Text(claim, "phase3_source_sha256"), 64))
                throw new InvalidOperationException();
            DateTime from;
            if (!DateTime.TryParse(Text(claim, "from_close_utc"), CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out from))
                throw new InvalidOperationException();
            bindingRuntimeId = runtimeId; bindingRunId = runId;
            bindingNonce = Text(claim, "binding_nonce"); bindingClaimSha256 = claimSha;
            bindingGeneration = Convert.ToInt32(claim["generation"], CultureInfo.InvariantCulture);
        }

        private bool SafeSource()
        {
            if (State != State.Realtime || Connection.PlaybackConnection != null
                || ExpectedProvider != "Provider31" || Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                || Instrument.FullName != "NQ DEC26" || Instrument.MasterInstrument.Name != "NQ"
                || Instrument.Expiry.ToString("yyyy-MM-dd") != "2026-12-01"
                || Instrument.MasterInstrument.TickSize != .25 || Instrument.MasterInstrument.PointValue != 20
                || BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 1
                || Bars.TradingHours.Name != "CME US Index Futures ETH"
                || Bars.TradingHours.TimeZoneInfo.Id != "Central Standard Time") return false;
            if (!System.Threading.Monitor.TryEnter(Connection.Connections)) return false;
            try
            {
                var feeds = Connection.Connections.Where(c => c != null && c.InstrumentTypes.Contains(InstrumentType.Future)).ToArray();
                if (feeds.Length != 1 || feeds[0].Options == null || feeds[0].Options.Provider.ToString() != ExpectedProvider
                    || (source != null && !Object.ReferenceEquals(source, feeds[0]))) return false;
                var feed = feeds[0];
                if (feed.PriceStatus != ConnectionStatus.Connected || feed.Status != ConnectionStatus.Connected
                    || feed.PriceStatus != ConnectionStatus.Connected || feed.Status != ConnectionStatus.Connected) return false;
                source = feed;
                return true;
            }
            finally { System.Threading.Monitor.Exit(Connection.Connections); }
        }

        protected override void OnMarketData(MarketDataEventArgs update)
        {
            if (State != State.Realtime) return;
            lock (sync)
            {
                if (stopped || output == null) return;
                try
                {
                    if (!SafeSource() || update == null || update.Instrument == null
                        || !Object.ReferenceEquals(update.Instrument, Instrument)) { Stop("SOURCE_CHANGED"); return; }
                    if (update.MarketDataType != MarketDataType.Bid && update.MarketDataType != MarketDataType.Ask) return;
                    var now = DateTime.UtcNow;
                    if (now < lastTime || Double.IsNaN(update.Price) || Double.IsInfinity(update.Price) || update.Price <= 0)
                    { Stop("INVALID_QUOTE"); return; }
                    if (update.MarketDataType == MarketDataType.Bid) { bid = update.Price; bidTime = now; }
                    else { ask = update.Price; askTime = now; }
                    if (!bid.HasValue || !ask.HasValue) return;
                    if (ask.Value < bid.Value)
                    {
                        // BID and ASK arrive independently. A fresh update on one side
                        // can transiently cross the still-cached opposite side.
                        // Never publish the crossed pair; wait for a coherent pair.
                        return;
                    }
                    // A fresh update on one side must never rejuvenate the other.
                    if ((now - bidTime).TotalSeconds > 30 || (now - askTime).TotalSeconds > 30) return;
                    Emit("QUOTE", new { bid = bid.Value, ask = ask.Value,
                        bid_time = bidTime.ToString("o"), ask_time = askTime.ToString("o") }, now);
                }
                catch (StreamCapacityException) { Stop("STREAM_CAPACITY_REACHED"); }
                catch (IOException) { Stop("FILE_IO_ERROR"); }
                catch { Stop("CALLBACK_EXCEPTION"); }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            lock (sync)
            {
                if (!started || stopped) return;
                try
                {
                    if (update == null) { Stop("CALLBACK_EXCEPTION"); return; }
                    // NinjaTrader can publish status callbacks for unrelated connections
                    // and can replay the current source state after subscription. Neither
                    // is continuity loss. The pinned source identity plus CURRENT status
                    // own continuity; a real source disconnect still revokes immediately.
                    if (!Object.ReferenceEquals(update.Connection, source)) return;

                    // NinjaTrader can deliver a stale/transitional callback such as
                    // Connecting after the pinned source is already fully Connected.
                    // Continuity is owned by the CURRENT pinned source state, not by
                    // the callback snapshot. SafeSource() also verifies identity,
                    // provider, contract and that the current source remains connected.
                    if (source == null
                        || source.PriceStatus != ConnectionStatus.Connected
                        || source.Status != ConnectionStatus.Connected
                        || !SafeSource())
                        Stop("PROVIDER_DISCONNECTED");
                }
                catch (IOException) { Stop("FILE_IO_ERROR"); }
                catch { Stop("CALLBACK_EXCEPTION"); }
            }
        }

        private void Heartbeat(object sender, EventArgs args)
        {
            lock (sync)
            {
                if (stopped || output == null) return;
                try { if (!SafeSource()) { Stop("SOURCE_CHANGED"); return; }
                    Emit("HEARTBEAT", new { connected = true }, DateTime.UtcNow); }
                catch (StreamCapacityException) { Stop("STREAM_CAPACITY_REACHED"); }
                catch (IOException) { Stop("FILE_IO_ERROR"); }
                catch { Stop("CALLBACK_EXCEPTION"); }
            }
        }

        private sealed class StreamCapacityException : IOException { }

        private string SegmentName(int index)
        {
            return session + ".segment." + index.ToString("D6") + ".l1.jsonl";
        }

        private void OpenSegment(int index)
        {
            segmentIndex = index;
            segmentFirstSequence = sequence;
            bytes = 0;
            segmentPath = Path.Combine(OutputDirectory, SegmentName(index));
            output = new StreamWriter(new FileStream(segmentPath, FileMode.CreateNew, FileAccess.Write,
                FileShare.Read), new UTF8Encoding(false));
            output.AutoFlush = true;
            output.NewLine = "\n";
        }

        private string FileSha256(string path)
        {
            using (var algorithm = SHA256.Create())
            using (var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
                return String.Concat(algorithm.ComputeHash(input).Select(b => b.ToString("x2")));
        }

        private void SealSegment()
        {
            if (output == null) return;
            output.Flush();
            output.Dispose();
            output = null;
            sealedSegments.Add(new Dictionary<string, object> {
                { "index", segmentIndex }, { "file", Path.GetFileName(segmentPath) },
                { "first_sequence", segmentFirstSequence }, { "last_sequence", sequence - 1 },
                { "bytes", bytes }, { "sha256", FileSha256(segmentPath) }, { "sealed", true }
            });
        }

        private void WriteManifest(string state, string terminalReason)
        {
            var segments = new List<Dictionary<string, object>>(sealedSegments);
            if (output != null)
                segments.Add(new Dictionary<string, object> {
                    { "index", segmentIndex }, { "file", Path.GetFileName(segmentPath) },
                    { "first_sequence", segmentFirstSequence }, { "last_sequence", null },
                    { "bytes", null }, { "sha256", null }, { "sealed", false }
                });
            var value = new Dictionary<string, object> {
                { "schema", ManifestSchema }, { "session", session }, { "provider", ExpectedProvider },
                { "instrument", "NQ" }, { "contract", "NQ DEC26" },
                { "segment_capacity_bytes", L1_STREAM_MAX_BYTES }, { "state", state },
                { "terminal_reason", terminalReason }, { "segments", segments }
            };
            string temporary = manifestPath + ".tmp." + Guid.NewGuid().ToString("N");
            byte[] data = new UTF8Encoding(false).GetBytes(new JavaScriptSerializer().Serialize(value) + "\n");
            try
            {
                using (var target = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write,
                    FileShare.None, 4096, FileOptions.WriteThrough))
                {
                    target.Write(data, 0, data.Length);
                    target.Flush(true);
                }
                if (File.Exists(manifestPath)) File.Replace(temporary, manifestPath, null);
                else File.Move(temporary, manifestPath);
            }
            finally
            {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
        }

        private void RotateSegment()
        {
            SealSegment();
            OpenSegment(segmentIndex + 1);
            WriteManifest("ACTIVE", null);
        }

        private void Emit(string kind, object payload, DateTime now)
        {
            if (now.Kind != DateTimeKind.Utc || now < lastTime) throw new InvalidOperationException();
            string line = new JavaScriptSerializer().Serialize(new { schema = "arms.nt.l1.v1", session = session,
                sequence = sequence, event_time = now.ToString("o"), kind = kind, payload = payload });
            int count = Encoding.UTF8.GetByteCount(line + "\n");
            long limit = L1_STREAM_MAX_BYTES - (kind == "TERMINAL" ? 0 : TERMINAL_RESERVE_BYTES);
            if (count > limit) throw new StreamCapacityException();
            if (bytes + count > limit)
            {
                if (kind == "TERMINAL") throw new StreamCapacityException();
                RotateSegment();
            }
            output.WriteLine(line); sequence++; bytes += count; lastTime = now;
        }

        private void Stop(string reason)
        {
            if (stopped) return;
            stopped = true;
            CloseObservation(reason);
        }

        private void CloseObservation(string reason)
        {
            bid = ask = null;
            if (timer != null) { try { timer.Stop(); timer.Tick -= Heartbeat; } catch { } timer = null; }
            if (output != null)
            {
                try { Emit("TERMINAL", new { connected = false, reason = reason }, DateTime.UtcNow); } catch { }
                try { SealSegment(); WriteManifest("TERMINATED", reason); } catch { }
                if (output != null) { try { output.Dispose(); } catch { } output = null; }
            }
            try { Print("ARMS_L1_STOP reason=" + reason); } catch { }
            started = false; source = null; session = manifestPath = segmentPath = null;
            bytes = sequence = segmentFirstSequence = 0; segmentIndex = 0;
            bidTime = askTime = lastTime = default(DateTime);
            sealedSegments.Clear();
        }
    }
}
