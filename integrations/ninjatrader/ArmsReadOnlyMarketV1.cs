// Market-data-only NinjaScript indicator. No accounts, orders, ATI or network.
// Compile in NinjaScript Editor; configure UTC and an explicit NQ minute chart.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
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

        [NinjaScriptProperty]
        [Display(Name = "Private output directory", Order = 1, GroupName = "ARMS read only")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expected provider enum", Order = 2, GroupName = "ARMS read only")]
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
                    if (CurrentBar - 1 > firstRealtimeBar) Emit("CLOSED", Candle(1));
                    Emit("FORMING", Candle(0));
                }
                catch (Exception error) { Stop("BAR_CALLBACK_FAILED", ErrorCode(error)); }
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
            if (writer != null)
            {
                try { Emit("DISCONNECTED", new { connected = false, reason = reason, error_code = errorCode }); } catch { }
                try { writer.Dispose(); } catch { }
                writer = null;
            }
            if (connectionWriter != null)
            {
                try { connectionWriter.Dispose(); } catch { }
                connectionWriter = null;
            }
            // No native error strings, account identifiers or personal paths logged.
        }
    }
}
