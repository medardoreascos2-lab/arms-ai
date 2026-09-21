// Separate, opt-in repository-only historical export. Never touches the live exporter.
// No account objects, orders, connection changes, provider requests or Update subscription.
using System;
using System.Collections.Generic;
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
    public class ArmsHistoricalBootstrapV1 : Indicator
    {
        private readonly object sync = new object();
        private BarsRequest request;
        private bool attempted, terminated;
        private string directory;
        private DateTime from, through;

        [NinjaScriptProperty]
        [Display(Name = "Capture enabled", Order = 1, GroupName = "ARMS historical only")]
        public bool CaptureEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Fresh private output directory", Order = 2, GroupName = "ARMS historical only")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "From UTC date yyyy-MM-dd", Order = 3, GroupName = "ARMS historical only")]
        public string FromUtcDate { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Through UTC date yyyy-MM-dd", Order = 4, GroupName = "ARMS historical only")]
        public string ThroughUtcDate { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsHistoricalBootstrapV1";
                Description = "One-shot unmerged native repository history; no live or execution authority.";
                IsOverlay = true;
                IsChartOnly = true;
                CaptureEnabled = false;
                OutputDirectory = FromUtcDate = ThroughUtcDate = "";
            }
            else if (State == State.DataLoaded)
            {
                lock (sync)
                {
                    if (!CaptureEnabled || attempted || terminated) return;
                    attempted = true;
                    try
                    {
                        if (Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                            || Connection.PlaybackConnection != null) throw new InvalidOperationException();
                        from = DateTime.ParseExact(FromUtcDate, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                        through = DateTime.ParseExact(ThroughUtcDate, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                        if (from.Year != 2026 || through.Year != 2026 || through < from
                            || (through - from).TotalDays > 14) throw new InvalidOperationException();
                        directory = LocalDirectory(OutputDirectory);
                        if (Directory.GetFileSystemEntries(directory).Length != 0) throw new InvalidOperationException();
                        var instrument = Instrument.GetInstrument("NQ DEC26");
                        ValidateInstrument(instrument);
                        request = new BarsRequest(instrument, from, through);
                        request.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1,
                            MarketDataType = MarketDataType.Last };
                        request.TradingHours = TradingHours.Get("CME US Index Futures ETH");
                        request.MergePolicy = MergePolicy.DoNotMerge;
                        request.LookupPolicy = LookupPolicies.Repository;
                        request.IsResetOnNewTradingDay = true;
                        request.IsDividendAdjusted = false;
                        request.IsSplitAdjusted = false;
                        request.Request(Completed); // Exactly once; no realtime Update handler.
                    }
                    catch { DisposeRequest(); Print("ARMS_HISTORICAL_BOOTSTRAP_FAILED_START"); }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync) { terminated = true; DisposeRequest(); }
            }
        }

        private static string LocalDirectory(string value)
        {
            if (String.IsNullOrWhiteSpace(value) || !Path.IsPathRooted(value)
                || Path.GetPathRoot(value).StartsWith(@"\\") || !Directory.Exists(value))
                throw new InvalidOperationException();
            var full = Path.GetFullPath(value);
            if (new DriveInfo(Path.GetPathRoot(full)).DriveType != DriveType.Fixed) throw new InvalidOperationException();
            for (var d = new DirectoryInfo(full); d != null; d = d.Parent)
                if ((d.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException();
            return full;
        }

        private static void ValidateInstrument(Instrument value)
        {
            if (value == null || value.FullName != "NQ DEC26" || value.MasterInstrument.Name != "NQ"
                || value.Expiry.ToString("yyyy-MM-dd") != "2026-12-01"
                || value.MasterInstrument.TickSize != .25 || value.MasterInstrument.PointValue != 20)
                throw new InvalidOperationException();
        }

        private static string Utc(DateTime value)
        {
            // No relabeling of Unspecified/local times to pretend native UTC proof.
            if (value.Kind != DateTimeKind.Utc) throw new InvalidOperationException();
            return value.ToString("o");
        }

        private static bool Price(double value)
        {
            return !Double.IsNaN(value) && !Double.IsInfinity(value) && value > 0
                && value * 4 == Math.Truncate(value * 4);
        }

        private void Completed(BarsRequest received, ErrorCode error, string ignoredProviderMessage)
        {
            lock (sync)
            {
                if (terminated || !Object.ReferenceEquals(received, request)) return;
                try
                {
                    if (error != ErrorCode.NoError || Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                        || Connection.PlaybackConnection != null) throw new InvalidOperationException();
                    ValidateInstrument(received.Instrument);
                    if (received.MergePolicy != MergePolicy.DoNotMerge || received.LookupPolicy != LookupPolicies.Repository
                        || received.BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || received.BarsPeriod.Value != 1
                        || received.BarsPeriod.MarketDataType != MarketDataType.Last
                        || !received.IsResetOnNewTradingDay || received.IsDividendAdjusted || received.IsSplitAdjusted)
                        throw new InvalidOperationException();
                    var bars = received.Bars;
                    ValidateInstrument(bars.Instrument);
                    if (bars.BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || bars.BarsPeriod.Value != 1
                        || bars.BarsPeriod.MarketDataType != MarketDataType.Last) throw new InvalidOperationException();
                    var hours = bars.TradingHours;
                    if (hours.Name != "CME US Index Futures ETH" || hours.TimeZoneInfo.Id != "Central Standard Time"
                        || hours.Name != received.TradingHours.Name || hours.Version != received.TradingHours.Version)
                        throw new InvalidOperationException();
                    int returned = bars.Count;
                    if (returned < 3 || returned > 10002) throw new InvalidOperationException();
                    string dataset = Guid.NewGuid().ToString();
                    var serializer = new JavaScriptSerializer();
                    var lines = new List<string>();
                    var intervals = new List<object>();
                    var calendarFrom = DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc);
                    var calendarThrough = DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc);
                    var iterator = new SessionIterator(bars);
                    DateTime query = calendarFrom, lastEnd = DateTime.MinValue;
                    for (int count = 0; count < 64; count++)
                    {
                        if (!iterator.GetNextSession(query, true)) throw new InvalidOperationException();
                        var begin = iterator.ActualSessionBegin;
                        var end = iterator.ActualSessionEnd;
                        if (begin >= end || end <= lastEnd) throw new InvalidOperationException();
                        if (begin >= calendarThrough) break;
                        intervals.Add(new { begin = Utc(begin), end = Utc(end),
                            trading_day = iterator.ActualTradingDayExchange.ToString("yyyy-MM-dd") });
                        lastEnd = end;
                        query = end.AddTicks(1);
                        if (query >= calendarThrough) break;
                        if (count == 63) throw new InvalidOperationException();
                    }
                    lines.Add(serializer.Serialize(new {
                        schema = "arms.nt.historical-bootstrap.header.v1", dataset = dataset,
                        exporter = "ArmsHistoricalBootstrapV1/1", sdk_version = typeof(BarsRequest).Assembly.GetName().Version.ToString(),
                        source = "NINJATRADER_LOCAL_REPOSITORY", provider_attribution = "UNATTESTED",
                        instrument = "NQ", contract = "NQ DEC26", expiry = "2026-12-01", bars_type = "Minute", bars_value = 1,
                        market_data_type = "Last", template = hours.Name, template_version = hours.Version,
                        template_timezone = hours.TimeZoneInfo.Id, application_timezone = "UTC", bar_label = "CLOSE",
                        tick_size = .25, point_value = 20, lookup_policy = "Repository", merge_policy = "DoNotMerge",
                        reset_on_new_trading_day = true, split_adjusted = false, dividend_adjusted = false,
                        requested_from = FromUtcDate, requested_through = ThroughUtcDate,
                        calendar_from = Utc(calendarFrom), calendar_through = Utc(calendarThrough), calendar_intervals = intervals,
                        returned_bar_count = returned, excluded_first_and_last = true, classification = "HISTORICAL",
                        realtime = false, observation_only = true, runtime_admission = false }));
                    DateTime previous = DateTime.MinValue;
                    // First may be a boundary fragment; last may still be forming. Exclude both.
                    for (int i = 1; i < returned - 1; i++)
                    {
                        var time = bars.GetTime(i);
                        double open = bars.GetOpen(i), high = bars.GetHigh(i), low = bars.GetLow(i), close = bars.GetClose(i);
                        long volume = bars.GetVolume(i);
                        if (time <= previous || time.Ticks % TimeSpan.TicksPerMinute != 0
                            || !Price(open) || !Price(high) || !Price(low) || !Price(close) || volume < 0
                            || low > Math.Min(open, close) || high < Math.Max(open, close)
                            || bars.GetTime(i + 1) <= time) throw new InvalidOperationException();
                        lines.Add(serializer.Serialize(new { schema = "arms.nt.historical-bootstrap.bar.v1", dataset = dataset,
                            index = i - 1, source_index = i, instrument = "NQ", contract = "NQ DEC26", bars_type = "Minute",
                            bars_value = 1, template = hours.Name, classification = "HISTORICAL", realtime = false,
                            bar_time = Utc(time), bar_time_kind = time.Kind.ToString(), open = open, high = high,
                            low = low, close = close, volume = volume }));
                        previous = time;
                    }
                    if (bars.Count != returned) throw new InvalidOperationException();
                    // The request owns this historical snapshot; there is no Update subscription.
                    var outputDirectory = LocalDirectory(directory);
                    if (Directory.GetFileSystemEntries(outputDirectory).Length != 0) throw new InvalidOperationException();
                    var path = Path.Combine(outputDirectory, dataset + ".historical.jsonl");
                    byte[] raw = Encoding.UTF8.GetBytes(String.Join("\n", lines) + "\n");
                    string hash;
                    using (var digest = SHA256.Create()) hash = BitConverter.ToString(digest.ComputeHash(raw)).Replace("-", "").ToLowerInvariant();
                    using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
                        output.Write(raw, 0, raw.Length);
                    using (var seal = new StreamWriter(new FileStream(path + ".done.tmp", FileMode.CreateNew,
                        FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                        seal.Write(serializer.Serialize(new { schema = "arms.nt.historical-bootstrap.seal.v1", dataset = dataset,
                            bytes = raw.Length, records = lines.Count, bars = returned - 2, sha256 = hash,
                            writer_closed = true, complete = true, classification = "HISTORICAL", runtime_admission = false }));
                    File.Move(path + ".done.tmp", path + ".done.json");
                    Print("ARMS_HISTORICAL_BOOTSTRAP_COMPLETE_HISTORY_ONLY");
                }
                catch { Print("ARMS_HISTORICAL_BOOTSTRAP_FAILED_NO_CERTIFICATION"); }
                finally { DisposeRequest(); }
            }
        }

        private void DisposeRequest()
        {
            var prior = request; request = null;
            if (prior != null) try { prior.Dispose(); } catch { }
        }
    }
}
