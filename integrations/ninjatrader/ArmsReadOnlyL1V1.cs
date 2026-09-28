// Native BID/ASK observations only. No account objects or order interfaces.
// Separate indicator/directory preserves the hash-pinned candle exporter.
using System;
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
    public class ArmsReadOnlyL1V1 : Indicator
    {
        private readonly object sync = new object();
        private StreamWriter output;
        private DispatcherTimer timer;
        private Connection source;
        private string session;
        private long sequence, bytes;
        private bool started, stopped;
        private double? bid, ask;
        private DateTime bidTime, askTime, lastTime;

        [NinjaScriptProperty]
        [Display(Name = "Private L1 output directory", Order = 1, GroupName = "ARMS read only L1")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expected provider enum", Order = 2, GroupName = "ARMS read only L1")]
        public string ExpectedProvider { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsReadOnlyL1V1";
                Description = "Native two-sided L1 observations; no execution capability.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true; IsChartOnly = true; IsSuspendedWhileInactive = false;
                OutputDirectory = ""; ExpectedProvider = "";
                return;
            }
            lock (sync)
            {
                if (State == State.Realtime)
                {
                    if (started || stopped) { Stop("LIFECYCLE_REENTRY"); return; }
                    started = true;
                    try
                    {
                        if (!SafeSource() || ChartControl == null || String.IsNullOrWhiteSpace(OutputDirectory)
                            || !Path.IsPathRooted(OutputDirectory) || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\")
                            || !Directory.Exists(OutputDirectory)) throw new InvalidOperationException();
                        session = Guid.NewGuid().ToString();
                        output = new StreamWriter(new FileStream(Path.Combine(OutputDirectory, session + ".l1.jsonl"),
                            FileMode.CreateNew, FileAccess.Write, FileShare.Read), new UTF8Encoding(false));
                        output.AutoFlush = true; output.NewLine = "\n";
                        Emit("HELLO", new { provider = ExpectedProvider, contract = "NQ DEC26", instrument = "NQ",
                            expiry = "2026-12-01", tick_size = .25, point_value = 20, application_timezone = "UTC",
                            trading_hours_template = "CME US Index Futures ETH", realtime = true, read_only = true, level = 1 }, DateTime.UtcNow);
                        Print("ARMS_L1_HELLO");
                        ChartControl.Dispatcher.InvokeAsync(new Action(() => {
                            lock (sync)
                            {
                                if (stopped) return;
                                try { timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(5) };
                                    timer.Tick += Heartbeat; timer.Start(); }
                                catch { Stop("HEARTBEAT_START_FAILED"); }
                            }
                        }));
                    }
                    catch { Stop("STARTUP_FAILED"); }
                }
                else if (started) Stop("TERMINATED_OR_STATE_CHANGED");
            }
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
                    if (ask.Value < bid.Value) { Stop("CROSSED_QUOTE"); return; }
                    // A fresh update on one side must never rejuvenate the other.
                    if ((now - bidTime).TotalSeconds > 30 || (now - askTime).TotalSeconds > 30) return;
                    Emit("QUOTE", new { bid = bid.Value, ask = ask.Value,
                        bid_time = bidTime.ToString("o"), ask_time = askTime.ToString("o") }, now);
                }
                catch { Stop("CALLBACK_FAILED"); }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            lock (sync)
            {
                if (!started || stopped) return;
                try
                {
                    if (update == null) { Stop("CONNECTION_FAILED"); return; }
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
                        Stop("CONNECTION_CONTINUITY_LOST");
                }
                catch { Stop("CONNECTION_FAILED"); }
            }
        }

        private void Heartbeat(object sender, EventArgs args)
        {
            lock (sync)
            {
                if (stopped || output == null) return;
                try { if (!SafeSource()) { Stop("SOURCE_CHANGED"); return; }
                    Emit("HEARTBEAT", new { connected = true }, DateTime.UtcNow); }
                catch { Stop("HEARTBEAT_FAILED"); }
            }
        }

        private void Emit(string kind, object payload, DateTime now)
        {
            if (now.Kind != DateTimeKind.Utc || now < lastTime) throw new InvalidOperationException();
            string line = new JavaScriptSerializer().Serialize(new { schema = "arms.nt.l1.v1", session = session,
                sequence = sequence, event_time = now.ToString("o"), kind = kind, payload = payload });
            int count = Encoding.UTF8.GetByteCount(line + "\n");
            if (bytes + count > 32 * 1024 * 1024 - 4096 && kind != "TERMINAL") throw new IOException();
            output.WriteLine(line); sequence++; bytes += count; lastTime = now;
        }

        private void Stop(string reason)
        {
            if (stopped) return;
            stopped = true; bid = ask = null;
            if (timer != null) { try { timer.Stop(); timer.Tick -= Heartbeat; } catch { } timer = null; }
            if (output != null)
            {
                try { Emit("TERMINAL", new { connected = false, reason = reason }, DateTime.UtcNow); } catch { }
                try { output.Dispose(); } catch { } output = null;
            }
            try { Print("ARMS_L1_STOP reason=" + reason); } catch { }
        }
    }
}
