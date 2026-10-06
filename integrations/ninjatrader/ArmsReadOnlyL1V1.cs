// Native BID/ASK observations only. No account objects or order interfaces.
// Separate indicator/directory preserves the hash-pinned candle exporter.
using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
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
        private const long L1_STREAM_MAX_BYTES = 256L * 1024 * 1024;
        private const int TERMINAL_RESERVE_BYTES = 4096;
        private const string ManifestSchema = "arms.nt.l1.manifest.v1";
        private readonly object sync = new object();
        private readonly List<Dictionary<string, object>> sealedSegments = new List<Dictionary<string, object>>();
        private StreamWriter output;
        private DispatcherTimer timer;
        private Connection source;
        private string session, manifestPath, segmentPath;
        private long sequence, bytes, segmentFirstSequence;
        private int segmentIndex;
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
                                if (stopped) return;
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
                else if (started) Stop("SESSION_TERMINATED");
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
            stopped = true; bid = ask = null;
            if (timer != null) { try { timer.Stop(); timer.Tick -= Heartbeat; } catch { } timer = null; }
            if (output != null)
            {
                try { Emit("TERMINAL", new { connected = false, reason = reason }, DateTime.UtcNow); } catch { }
                try { SealSegment(); WriteManifest("TERMINATED", reason); } catch { }
                if (output != null) { try { output.Dispose(); } catch { } output = null; }
            }
            try { Print("ARMS_L1_STOP reason=" + reason); } catch { }
        }
    }
}
