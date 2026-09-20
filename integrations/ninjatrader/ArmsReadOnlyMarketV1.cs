// Market-data-only NinjaScript indicator. No accounts, orders, ATI or network.
// Compile in NinjaScript Editor; configure UTC and an explicit NQ minute chart.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
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
        private DispatcherTimer timer;
        private string session, contract, template, expiry;
        private long sequence;
        private int firstRealtimeBar;
        private bool failed;
        private Connection source;

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
                        firstRealtimeBar = -1;
                        startupStage = "HELLO_WRITE";
                        Emit("HELLO", new { provider = ExpectedProvider, contract = contract, expiry = expiry,
                            instrument = "NQ", tick_size = .25, point_value = 20, timeframe = "1m",
                            trading_hours_template = template, source_timezone = "UTC", bar_label = "CLOSE",
                            realtime = true, read_only = true });
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
            lock (Connection.Connections)
            {
                var feeds = Connection.Connections.Where(c => c.PriceStatus == ConnectionStatus.Connected
                    && c.InstrumentTypes.Contains(InstrumentType.Future)).ToArray();
                if (feeds.Length != 1) return false;
                if (feeds[0].Options.Provider.ToString() != ExpectedProvider)
                {
                    // Enum only: no connection name, credentials or account IDs.
                    Print("ARMS_READ_ONLY_PROVIDER_ENUM=" + feeds[0].Options.Provider.ToString());
                    return false;
                }
                if (source != null && source != feeds[0]) return false;
                source = feeds[0];
                return true;
            }
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
                    Emit("HEARTBEAT", new { connected = true });
                }
                catch (Exception error) { Stop("HEARTBEAT_CALLBACK_FAILED", ErrorCode(error)); }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            lock (sync)
            {
                if (writer != null && !failed && update.Connection == source
                    && update.PriceStatus != ConnectionStatus.Connected) Stop("PRICE_CONNECTION_LOST");
            }
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
            // No native error strings, account identifiers or personal paths logged.
        }
    }
}
