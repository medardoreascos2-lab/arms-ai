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
        private ArmsHistoricalBootstrapV1 owner;
        private StreamWriter diagnostic;
        private string diagnosticPath, attemptId, fromProperty, throughProperty, outputProperty;
        private string stage = "NOT_STARTED", observedTimeKind = "NONE", requestError = "NONE";
        private int diagnosticSequence, returnedRows = -1, currentIndex = -1;
        private bool terminal, submitted, submitting, completed;
        private readonly HashSet<State> observedStates = new HashSet<State>();
        // At most 64 calendar iterations, four progress rows each, plus lifecycle/terminal rows.
        private const int MaximumDiagnosticRecords = 512;
        private int calendarIteration = -1;
        private DateTime? calendarQuery, lastCalendarQuery, sessionBegin, sessionEnd;
        private DateTime? lastSessionBegin, lastSessionEnd;
        private string calendarAdvanceResult = "NOT_CALLED", boundsRead = "NONE";

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
            // A UI clone must never dispose or write through the running instance's resources.
            else if (owner != null && !Object.ReferenceEquals(owner, this)) return;
            else if (State == State.Configure)
            {
                lock (sync) BeginAttempt(); // Private diagnostic probe only; no request before DataLoaded.
            }
            else if (State == State.DataLoaded)
            {
                lock (sync)
                {
                    BeginAttempt(); // Also supports a host that supplies properties only before DataLoaded.
                    if (!attempted || terminal || submitted || terminated) return;
                    try
                    {
                        Trace("STATE_DATALOADED");
                        stage = "EFFECTIVE_PROPERTIES";
                        if (!PropertiesMatch()) throw new InvalidOperationException();
                        stage = "SOURCE_TIMEZONE";
                        if (Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC") throw new InvalidOperationException();
                        stage = "PLAYBACK_GUARD";
                        if (Connection.PlaybackConnection != null) throw new InvalidOperationException();
                        stage = "INSTRUMENT_IDENTITY";
                        var instrument = Instrument.GetInstrument("NQ DEC26");
                        ValidateInstrument(instrument);
                        stage = "REQUEST_CREATE";
                        request = new BarsRequest(instrument, from, through);
                        Trace("REQUEST_CREATED");
                        stage = "REQUEST_PARAMETERS";
                        request.BarsPeriod = new BarsPeriod { BarsPeriodType = BarsPeriodType.Minute, Value = 1,
                            MarketDataType = MarketDataType.Last };
                        request.TradingHours = TradingHours.Get("CME US Index Futures ETH");
                        request.MergePolicy = MergePolicy.DoNotMerge;
                        request.LookupPolicy = LookupPolicies.Repository;
                        request.IsResetOnNewTradingDay = true;
                        request.IsDividendAdjusted = false;
                        request.IsSplitAdjusted = false;
                        stage = "REQUEST_INVOKE";
                        Trace("REQUEST_SUBMITTING");
                        submitted = true; submitting = true; // At most one invocation, including exceptions.
                        request.Request(Completed); // Exactly once; no realtime Update handler.
                        Trace("REQUEST_SUBMITTED"); // May follow an inline callback; means Request returned.
                    }
                    catch (Exception error) { Fail(error); }
                    finally { submitting = false; if (terminal) CloseDiagnostic(); }
                }
            }
            else if (State == State.Terminated)
            {
                lock (sync)
                {
                    terminated = true;
                    if (attempted && !terminal)
                    {
                        stage = "TERMINATED_BEFORE_COMPLETION";
                        Fail(new InvalidOperationException());
                    }
                    DisposeRequest(); CloseDiagnostic();
                }
            }
            else if (attempted && !terminal)
            {
                lock (sync)
                {
                    try { if (observedStates.Add(State)) Trace("STATE_" + State.ToString().ToUpperInvariant()); }
                    catch (Exception error) { Fail(error); }
                }
            }
        }

        private void BeginAttempt()
        {
            if (!CaptureEnabled || attempted || terminated) return;
            owner = this; attempted = true;
            outputProperty = OutputDirectory; fromProperty = FromUtcDate; throughProperty = ThroughUtcDate;
            attemptId = Guid.NewGuid().ToString();
            try
            {
                stage = "DIAGNOSTIC_OPEN";
                directory = LocalDirectory(outputProperty);
                if (Directory.GetFileSystemEntries(directory).Length != 0) throw new InvalidOperationException();
                // A fixed CreateNew name also prevents two instances from owning the same fresh directory.
                diagnosticPath = Path.Combine(directory, "historical-diagnostic.jsonl");
                diagnostic = new StreamWriter(new FileStream(diagnosticPath, FileMode.CreateNew, FileAccess.Write,
                    FileShare.Read, 4096, FileOptions.WriteThrough), new UTF8Encoding(false));
                diagnostic.NewLine = "\n"; diagnostic.AutoFlush = true;
                Trace("INSTANCE_STARTED");
                stage = "CONFIG_DATE_PARSE";
                from = DateTime.ParseExact(fromProperty, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                through = DateTime.ParseExact(throughProperty, "yyyy-MM-dd", CultureInfo.InvariantCulture);
                stage = "CONFIG_DATE_RANGE";
                if (from.Year != 2026 || through.Year != 2026 || through < from
                    || (through - from).TotalDays > 14) throw new InvalidOperationException();
                Trace("CONFIG_VALIDATED");
            }
            catch (Exception error) { Fail(error); }
        }

        private bool PropertiesMatch()
        {
            return CaptureEnabled && OutputDirectory == outputProperty && FromUtcDate == fromProperty
                && ThroughUtcDate == throughProperty;
        }

        private static string SafeDate(string value)
        {
            DateTime parsed;
            return DateTime.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture,
                DateTimeStyles.None, out parsed) ? parsed.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) : "INVALID";
        }

        private void Trace(string value, string errorType = "NONE")
        {
            if (diagnostic == null || diagnosticSequence >= MaximumDiagnosticRecords) throw new InvalidOperationException();
            diagnostic.WriteLine(new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.historical-diagnostic.v1", classification = "DIAGNOSTIC_ONLY",
                certification_evidence = false, runtime_admission = false, instance = attemptId,
                sequence = diagnosticSequence++, stage = value, state = State.ToString(),
                capture_enabled = CaptureEnabled, properties_match = PropertiesMatch(),
                from_utc_date = SafeDate(fromProperty), through_utc_date = SafeDate(throughProperty),
                output_directory_verified = directory != null, output_directory_identity = DirectoryIdentity(),
                request_invoked = submitted, capture_completed = completed,
                attempt_failed = terminal && !completed,
                returned_rows = returnedRows, source_index = currentIndex, observed_time_kind = observedTimeKind,
                request_error = requestError, exception_type = errorType,
                // Full redaction is intentional: provider-owned exception.Message is never serialized.
                exception_message = errorType == "NONE" ? "NONE" :
                    stage == "CALENDAR_ADVANCE_FALSE" ? "GetNextSession returned false." : "REDACTED_NATIVE_OR_GUARD_MESSAGE",
                calendar_iteration = calendarIteration, calendar_query = DiagnosticTime(calendarQuery),
                calendar_query_kind = DiagnosticKind(calendarQuery), include_end_time = true,
                calendar_advance_result = calendarAdvanceResult, calendar_bounds_read = boundsRead,
                last_successful_query = DiagnosticTime(lastCalendarQuery),
                last_successful_query_kind = DiagnosticKind(lastCalendarQuery),
                session_begin = DiagnosticTime(sessionBegin), session_begin_kind = DiagnosticKind(sessionBegin),
                session_end = DiagnosticTime(sessionEnd), session_end_kind = DiagnosticKind(sessionEnd),
                last_successful_session_begin = DiagnosticTime(lastSessionBegin),
                last_successful_session_begin_kind = DiagnosticKind(lastSessionBegin),
                last_successful_session_end = DiagnosticTime(lastSessionEnd),
                last_successful_session_end_kind = DiagnosticKind(lastSessionEnd),
                requested_from_kind = from.Kind.ToString(), requested_through_kind = through.Kind.ToString(),
                expected_trading_hours = "CME US Index Futures ETH", expected_template_timezone = "Central Standard Time",
                required_application_timezone = "UTC" }));
        }

        private static string DiagnosticTime(DateTime? value)
        { return value.HasValue ? value.Value.ToString("o", CultureInfo.InvariantCulture) : null; }

        private static string DiagnosticKind(DateTime? value)
        { return value.HasValue ? value.Value.Kind.ToString() : "NONE"; }

        private List<object> CalendarIntervals(Bars bars, DateTime calendarFrom, DateTime calendarThrough)
        {
            var intervals = new List<object>();
            stage = "CALENDAR_ITERATOR_CREATE_EXCEPTION";
            var iterator = new SessionIterator(bars); // Uses the returned Bars.TradingHours.
            stage = "CALENDAR_ITERATOR_CREATED";
            Trace("CALENDAR_ITERATOR_CREATED");
            DateTime query = calendarFrom, lastEnd = DateTime.MinValue;
            for (int count = 0; count < 64; count++)
            {
                calendarIteration = count; calendarQuery = query;
                sessionBegin = sessionEnd = null; boundsRead = "NONE";
                calendarAdvanceResult = "NOT_RETURNED";
                stage = "CALENDAR_QUERY_BEGIN";
                Trace("CALENDAR_QUERY_BEGIN"); // Persist exact input before invoking native code.
                stage = "CALENDAR_ADVANCE_EXCEPTION";
                bool advanced = iterator.GetNextSession(query, true);
                calendarAdvanceResult = advanced ? "TRUE" : "FALSE";
                if (!advanced)
                {
                    stage = "CALENDAR_ADVANCE_FALSE";
                    throw new InvalidOperationException(); // Same fail-closed admission as before.
                }
                stage = "CALENDAR_ADVANCE_SUCCESS";
                Trace("CALENDAR_ADVANCE_SUCCESS");
                stage = "CALENDAR_SESSION_BOUNDS_READ_EXCEPTION";
                boundsRead = "BEGIN"; var begin = iterator.ActualSessionBegin; sessionBegin = begin;
                boundsRead = "END"; var end = iterator.ActualSessionEnd; sessionEnd = end;
                boundsRead = "COMPLETE";
                stage = "CALENDAR_SESSION_BOUNDS_READ_SUCCESS";
                Trace("CALENDAR_SESSION_BOUNDS_READ_SUCCESS");
                stage = "CALENDAR_INTERVAL_ORDER";
                if (begin >= end || end <= lastEnd) throw new InvalidOperationException();
                if (begin >= calendarThrough) break;
                stage = "CALENDAR_BEGIN_UTC_KIND"; observedTimeKind = begin.Kind.ToString();
                var beginText = Utc(begin);
                stage = "CALENDAR_END_UTC_KIND"; observedTimeKind = end.Kind.ToString();
                var endText = Utc(end);
                stage = "CALENDAR_TRADING_DAY_READ_EXCEPTION";
                intervals.Add(new { begin = beginText, end = endText,
                    trading_day = iterator.ActualTradingDayExchange.ToString("yyyy-MM-dd") });
                lastCalendarQuery = query; lastSessionBegin = begin; lastSessionEnd = end;
                lastEnd = end;
                stage = "CALENDAR_QUERY_UPDATE";
                query = end.AddTicks(1); // Preserve the original one-tick advancement exactly.
                calendarQuery = query;
                Trace("CALENDAR_QUERY_ADVANCED");
                if (query >= calendarThrough) break;
                stage = "CALENDAR_INTERVAL_LIMIT";
                if (count == 63) throw new InvalidOperationException();
            }
            stage = "CALENDAR_ITERATION_COMPLETE";
            Trace("CALENDAR_ITERATION_COMPLETE");
            return intervals;
        }

        private string DirectoryIdentity()
        {
            if (directory == null) return "UNAVAILABLE";
            using (var h = SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes(directory))).Replace("-", "").ToLowerInvariant();
        }

        private static string SafeError(Exception error)
        {
            if (error is UnauthorizedAccessException) return "UnauthorizedAccessException";
            if (error is IOException) return "IOException";
            if (error is FormatException) return "FormatException";
            if (error is ArgumentException) return "ArgumentException";
            if (error is NullReferenceException) return "NullReferenceException";
            if (error is InvalidOperationException) return "InvalidOperationException";
            return "OTHER"; // Never provider-owned Message, StackTrace or arbitrary type names.
        }

        private void Fail(Exception error)
        {
            if (terminal) return;
            terminal = true;
            try { Trace("FAILED_" + stage, SafeError(error)); } catch { }
            try { Print("ARMS_HISTORICAL_BOOTSTRAP_FAILED_" + stage + " error=" + SafeError(error)); } catch { }
            DisposeRequest();
            if (!submitting) CloseDiagnostic();
        }

        private void CloseDiagnostic()
        {
            try { if (diagnostic != null) diagnostic.Dispose(); } catch { }
            diagnostic = null;
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
                if (terminated || terminal) return;
                try
                {
                    stage = "CALLBACK_IDENTITY";
                    requestError = Enum.IsDefined(typeof(ErrorCode), error) ? error.ToString() : "UNKNOWN";
                    Trace("CALLBACK_ENTERED");
                    if (!Object.ReferenceEquals(received, request)) throw new InvalidOperationException();
                    stage = "CALLBACK_ERROR";
                    if (error != ErrorCode.NoError) throw new InvalidOperationException();
                    stage = "CALLBACK_PROPERTIES";
                    if (!PropertiesMatch()) throw new InvalidOperationException();
                    stage = "CALLBACK_SOURCE";
                    if (Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                        || Connection.PlaybackConnection != null) throw new InvalidOperationException();
                    stage = "CALLBACK_INSTRUMENT";
                    ValidateInstrument(received.Instrument);
                    stage = "CALLBACK_REQUEST_PARAMETERS";
                    if (received.MergePolicy != MergePolicy.DoNotMerge || received.LookupPolicy != LookupPolicies.Repository
                        || received.BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || received.BarsPeriod.Value != 1
                        || received.BarsPeriod.MarketDataType != MarketDataType.Last
                        || !received.IsResetOnNewTradingDay || received.IsDividendAdjusted || received.IsSplitAdjusted)
                        throw new InvalidOperationException();
                    var bars = received.Bars;
                    stage = "CALLBACK_BARS_IDENTITY";
                    ValidateInstrument(bars.Instrument);
                    if (bars.BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || bars.BarsPeriod.Value != 1
                        || bars.BarsPeriod.MarketDataType != MarketDataType.Last) throw new InvalidOperationException();
                    var hours = bars.TradingHours;
                    stage = "CALLBACK_TRADING_HOURS";
                    if (hours.Name != "CME US Index Futures ETH" || hours.TimeZoneInfo.Id != "Central Standard Time"
                        || hours.Name != received.TradingHours.Name || hours.Version != received.TradingHours.Version)
                        throw new InvalidOperationException();
                    int returned = bars.Count;
                    returnedRows = returned;
                    Trace("ROWS_RECEIVED");
                    stage = "ROW_COUNT";
                    if (returned < 3 || returned > 10002) throw new InvalidOperationException();
                    string dataset = Guid.NewGuid().ToString();
                    var serializer = new JavaScriptSerializer();
                    var lines = new List<string>();
                    var calendarFrom = DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc);
                    var calendarThrough = DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc);
                    var intervals = CalendarIntervals(bars, calendarFrom, calendarThrough);
                    stage = "HEADER_SERIALIZATION";
                    Trace("SERIALIZATION_STARTED");
                    lines.Add(serializer.Serialize(new {
                        schema = "arms.nt.historical-bootstrap.header.v1", dataset = dataset,
                        exporter = "ArmsHistoricalBootstrapV1/1", sdk_version = typeof(BarsRequest).Assembly.GetName().Version.ToString(),
                        source = "NINJATRADER_LOCAL_REPOSITORY", provider_attribution = "UNATTESTED",
                        instrument = "NQ", contract = "NQ DEC26", expiry = "2026-12-01", bars_type = "Minute", bars_value = 1,
                        market_data_type = "Last", template = hours.Name, template_version = hours.Version,
                        template_timezone = hours.TimeZoneInfo.Id, application_timezone = "UTC", bar_label = "CLOSE",
                        tick_size = .25, point_value = 20, lookup_policy = "Repository", merge_policy = "DoNotMerge",
                        reset_on_new_trading_day = true, split_adjusted = false, dividend_adjusted = false,
                        requested_from = fromProperty, requested_through = throughProperty,
                        calendar_from = Utc(calendarFrom), calendar_through = Utc(calendarThrough), calendar_intervals = intervals,
                        returned_bar_count = returned, excluded_first_and_last = true, classification = "HISTORICAL",
                        realtime = false, observation_only = true, runtime_admission = false }));
                    DateTime previous = DateTime.MinValue;
                    // First may be a boundary fragment; last may still be forming. Exclude both.
                    for (int i = 1; i < returned - 1; i++)
                    {
                        currentIndex = i; stage = "BAR_READ";
                        var time = bars.GetTime(i);
                        double open = bars.GetOpen(i), high = bars.GetHigh(i), low = bars.GetLow(i), close = bars.GetClose(i);
                        long volume = bars.GetVolume(i);
                        stage = "BAR_LABEL_ORDER";
                        if (time <= previous || time.Ticks % TimeSpan.TicksPerMinute != 0
                            || bars.GetTime(i + 1) <= time) throw new InvalidOperationException();
                        stage = "BAR_OHLCV";
                        if (!Price(open) || !Price(high) || !Price(low) || !Price(close) || volume < 0
                            || low > Math.Min(open, close) || high < Math.Max(open, close))
                            throw new InvalidOperationException();
                        stage = "BAR_UTC_KIND"; observedTimeKind = time.Kind.ToString();
                        var barTime = Utc(time);
                        stage = "BAR_SERIALIZATION";
                        lines.Add(serializer.Serialize(new { schema = "arms.nt.historical-bootstrap.bar.v1", dataset = dataset,
                            index = i - 1, source_index = i, instrument = "NQ", contract = "NQ DEC26", bars_type = "Minute",
                            bars_value = 1, template = hours.Name, classification = "HISTORICAL", realtime = false,
                            bar_time = barTime, bar_time_kind = time.Kind.ToString(), open = open, high = high,
                            low = low, close = close, volume = volume }));
                        previous = time;
                    }
                    stage = "SNAPSHOT_COUNT_STABLE";
                    if (bars.Count != returned) throw new InvalidOperationException();
                    // The request owns this historical snapshot; there is no Update subscription.
                    stage = "OUTPUT_OWNERSHIP";
                    var outputDirectory = LocalDirectory(directory);
                    var entries = Directory.GetFileSystemEntries(outputDirectory);
                    if (entries.Length != 1 || Path.GetFullPath(entries[0]) != diagnosticPath) throw new InvalidOperationException();
                    var path = Path.Combine(outputDirectory, dataset + ".historical.jsonl");
                    byte[] raw = Encoding.UTF8.GetBytes(String.Join("\n", lines) + "\n");
                    string hash;
                    using (var digest = SHA256.Create()) hash = BitConverter.ToString(digest.ComputeHash(raw)).Replace("-", "").ToLowerInvariant();
                    stage = "HISTORY_WRITE";
                    Trace("HISTORY_WRITE_STARTED");
                    using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read))
                        output.Write(raw, 0, raw.Length);
                    stage = "SEAL_WRITE";
                    using (var seal = new StreamWriter(new FileStream(path + ".done.tmp", FileMode.CreateNew,
                        FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                        seal.Write(serializer.Serialize(new { schema = "arms.nt.historical-bootstrap.seal.v1", dataset = dataset,
                            bytes = raw.Length, records = lines.Count, bars = returned - 2, sha256 = hash,
                            writer_closed = true, complete = true, classification = "HISTORICAL", runtime_admission = false }));
                    stage = "SEAL_RENAME";
                    File.Move(path + ".done.tmp", path + ".done.json");
                    completed = true;
                    Trace("SEAL_WRITTEN");
                    terminal = true;
                    try { Print("ARMS_HISTORICAL_BOOTSTRAP_COMPLETE_HISTORY_ONLY"); } catch { }
                }
                catch (Exception failure) { Fail(failure); }
                finally { DisposeRequest(); if (!submitting) CloseDiagnostic(); }
            }
        }

        private void DisposeRequest()
        {
            var prior = request; request = null;
            if (prior != null) try { prior.Dispose(); } catch { }
        }
    }
}
