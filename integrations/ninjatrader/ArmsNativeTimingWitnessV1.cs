// Standalone diagnostic stream. Never edits or timestamps another exporter's rows.
// Market metadata only; no execution or account API. Not a market admission source.
using System;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsNativeTimingWitnessV1 : Indicator
    {
        private const int WindowMs = 330000, MaximumRecords = 16, RequiredClosed = 3;
        private readonly object sync = new object();
        private StreamWriter writer;
        private Timer deadline, startupDeadline;
        private DispatcherTimer alignmentTimer;
        private Connection source;
        private string session, path, calendarJson, calendarHash, sessionKey;
        private bool started, stopped, realtime;
        private int sequence, firstBar = -1, lastBar = -1, closedCount;
        private DateTime lastLabel;
        private long startQpc;
        private enum Continuity { PRE_BASELINE, WAIT_ALIGNMENT, BASELINE_PROVEN, STOPPED }
        private Continuity continuity = Continuity.PRE_BASELINE;
        private int connectionSequence;
        private int alignedEvent = -1;
        private long realtimeQpc, alignedEventQpc, baselineReadyQpc;

        [NinjaScriptProperty]
        [Display(Name = "Private timing directory", Order = 1, GroupName = "ARMS timing")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Capture run UUID", Order = 2, GroupName = "ARMS timing")]
        public string CaptureRunId { get; set; }

        private sealed class Pair
        {
            public long qpc_before, utc_ticks, qpc_after;
            public string utc;
        }

        private static Pair ReadPair()
        {
            long before = Stopwatch.GetTimestamp();
            DateTime utc = DateTime.UtcNow;
            long after = Stopwatch.GetTimestamp();
            return new Pair { qpc_before = before, utc_ticks = utc.Ticks,
                qpc_after = after, utc = utc.ToString("o", CultureInfo.InvariantCulture) };
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsNativeTimingWitnessV1";
                Description = "Bounded paired UTC/QPC market timing; no admission authority.";
                Calculate = Calculate.OnEachTick;
                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;
                OutputDirectory = "";
                CaptureRunId = "";
                return;
            }
            lock (sync)
            {
                if (State == State.Terminated) { Finish("HOST_TERMINATED"); return; }
                if (State == State.DataLoaded)
                {
                    if (started || stopped) { Finish("LIFECYCLE_REENTRY"); return; }
                    started = true;
                    startQpc = Stopwatch.GetTimestamp();
                    try
                    {
                        Guid run;
                        if (!Guid.TryParseExact(CaptureRunId, "D", out run)
                            || !Stopwatch.IsHighResolution || String.IsNullOrWhiteSpace(OutputDirectory)
                            || !Path.IsPathRooted(OutputDirectory) || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\")
                            || !Directory.Exists(OutputDirectory) || !SafeSource()) throw new InvalidOperationException();
                        calendarJson = CalendarJson();
                        calendarHash = Hash(Encoding.UTF8.GetBytes(calendarJson));
                        session = Guid.NewGuid().ToString("D");
                        path = Path.Combine(OutputDirectory, session + ".timing.jsonl");
                        writer = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                            FileShare.Read), new UTF8Encoding(false));
                        writer.AutoFlush = true;
                        deadline = new Timer(_ => { lock (sync) Finish("WINDOW_END"); }, null,
                            Math.Max(1, WindowMs - (int)ElapsedMs()), Timeout.Infinite);
                        Emit("HELLO", new { provider = "Provider31", instrument = "NQ", contract = "NQ DEC26",
                            bars_type = "Minute", bars_value = 1, application_timezone = "UTC",
                            template = "CME US Index Futures ETH", bar_label = "CLOSE",
                            calendar_json = calendarJson, calendar_sha256 = calendarHash,
                            capture_ms = WindowMs, required_closed = RequiredClosed,
                            continuity_contract = "SPRINT11T_STARTUP_ALIGNMENT_R4" }, ReadPair());
                    }
                    catch { Finish("START_FAILED"); }
                }
                else if (started && !stopped && State == State.Realtime)
                {
                    if (realtime) { Finish("REALTIME_REENTRY"); return; }
                    realtime = true;
                    try
                    {
                        Pair entry = ReadPair();
                        realtimeQpc = entry.qpc_before;
                        alignedEvent = -1; // A historical event cannot establish realtime alignment.
                        Emit("REALTIME", new { state = "Realtime" }, entry);
                        if (stopped) return;
                        startupDeadline = new Timer(_ => { lock (sync)
                            if (!stopped && continuity != Continuity.BASELINE_PROVEN) Finish("STOP_STARTUP_TIMEOUT");
                        }, null, Math.Max(1, 30000 - (int)StartupMs()), Timeout.Infinite);
                        if (ChartControl == null) { Finish("CHART_UNAVAILABLE"); return; }
                        // Same dispatcher/poll architecture as certified Sprint 11T.
                        ChartControl.Dispatcher.InvokeAsync(new Action(() => { lock (sync)
                        {
                            if (stopped || writer == null) return;
                            try
                            {
                                alignmentTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(5) };
                                alignmentTimer.Tick += AlignmentPoll;
                                alignmentTimer.Start();
                            }
                            catch { Finish("ALIGNMENT_TIMER_FAILED"); }
                        }}));
                    }
                    catch { Finish("WRITE_FAILED"); }
                }
                else if (started && realtime && !stopped) Finish("LIFECYCLE_CHANGED");
            }
        }

        private double ElapsedMs()
        { return (Stopwatch.GetTimestamp() - startQpc) * 1000.0 / Stopwatch.Frequency; }

        private double StartupMs()
        { return (Stopwatch.GetTimestamp() - realtimeQpc) * 1000.0 / Stopwatch.Frequency; }

        private bool SafeSource()
        {
            if (Core.Globals.GeneralOptions.TimeZoneInfo.Id != "UTC"
                || Instrument.FullName != "NQ DEC26" || Instrument.MasterInstrument.Name != "NQ"
                || Instrument.MasterInstrument.TickSize != .25 || Instrument.MasterInstrument.PointValue != 20
                || BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 1
                || Bars.TradingHours.Name != "CME US Index Futures ETH" || Connection.PlaybackConnection != null)
                return false;
            if (!Monitor.TryEnter(Connection.Connections)) return false;
            try
            {
                var feeds = Connection.Connections.Where(c => c != null
                    && c.InstrumentTypes.Contains(InstrumentType.Future)).ToArray();
                if (feeds.Length != 1 || (source != null && !Object.ReferenceEquals(source, feeds[0]))) return false;
                var selected = feeds[0];
                if (selected.Options == null) return false;
                var status = selected.Status; var price = selected.PriceStatus;
                var provider = selected.Options.Provider;
                if (status != ConnectionStatus.Connected || price != ConnectionStatus.Connected
                    || provider.ToString() != "Provider31" || selected.Status != status
                    || selected.PriceStatus != price || selected.Options == null || selected.Options.Provider != provider) return false;
                source = selected;
                return true;
            }
            finally { Monitor.Exit(Connection.Connections); }
        }

        private static string Hash(byte[] bytes)
        { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }

        private static object SessionMetadata(Session s)
        { return new { begin_day = s.BeginDay.ToString(), begin_time = s.BeginTime,
            end_day = s.EndDay.ToString(), end_time = s.EndTime, trading_day = s.TradingDay.ToString() }; }

        private string CalendarJson()
        {
            var h = Bars.TradingHours;
            return new JavaScriptSerializer().Serialize(new { template = h.Name, template_version = h.Version,
                template_timezone = h.TimeZoneInfo.Id, sessions = h.Sessions.Select(SessionMetadata).ToArray(),
                holiday_dates = h.Holidays.Keys.OrderBy(d => d).Select(d => d.ToString("yyyy-MM-dd")).ToArray(),
                partial_holiday_dates = h.PartialHolidays.Keys.OrderBy(d => d).Select(d => d.ToString("yyyy-MM-dd")).ToArray(),
                partial_holidays_2026 = h.PartialHolidays.OrderBy(p => p.Key).Where(p => p.Key.Year == 2026).Select(p => new {
                    date = p.Key.ToString("yyyy-MM-dd"), early_end = p.Value.IsEarlyEnd, late_begin = p.Value.IsLateBegin,
                    constraint = SessionMetadata(p.Value.Constraint), sessions = p.Value.Sessions.Select(SessionMetadata).ToArray() }).ToArray() });
        }

        private static DateTime UtcWall(DateTime value)
        {
            // Configured application UTC is checked. Preserve raw Kind separately.
            if (value.Kind == DateTimeKind.Local) throw new InvalidOperationException();
            return DateTime.SpecifyKind(value, DateTimeKind.Utc);
        }

        private object Observation(int ago, Pair callback)
        {
            var raw = Time[ago];
            var label = UtcWall(raw);
            var indexed = Bars.GetTime(CurrentBar - ago);
            if (indexed.Ticks != raw.Ticks || indexed.Kind != raw.Kind || label.Ticks % TimeSpan.TicksPerMinute != 0)
                throw new InvalidOperationException();
            var iterator = new SessionIterator(Bars);
            iterator.GetNextSession(raw, true);
            var begin = UtcWall(iterator.ActualSessionBegin);
            var end = UtcWall(iterator.ActualSessionEnd);
            var start = label.AddMinutes(-1);
            var day = iterator.ActualTradingDayExchange.ToString("yyyy-MM-dd");
            var key = begin.ToString("o") + "/" + end.ToString("o") + "/" + day;
            if (start < begin || label > end || (sessionKey != null && sessionKey != key))
                throw new InvalidOperationException();
            sessionKey = key;
            return new { callback = callback, callback_index = CurrentBar, bar_index = CurrentBar - ago,
                bars_ago = ago, first_tick = IsFirstTickOfBar, bars_in_progress = BarsInProgress,
                state = State.ToString(), native_label = raw.ToString("o"), native_kind = raw.Kind.ToString(),
                indexed_label = indexed.ToString("o"), indexed_kind = indexed.Kind.ToString(),
                close_label_utc = label.ToString("o"), implied_start_utc = start.ToString("o"), bar_label = "CLOSE",
                calendar_sha256 = calendarHash, session_begin_utc = begin.ToString("o"), session_end_utc = end.ToString("o"),
                session_begin_raw = iterator.ActualSessionBegin.ToString("o"), session_begin_kind = iterator.ActualSessionBegin.Kind.ToString(),
                session_end_raw = iterator.ActualSessionEnd.ToString("o"), session_end_kind = iterator.ActualSessionEnd.Kind.ToString(),
                trading_day = day, provider = "Provider31", instrument = "NQ", contract = "NQ DEC26",
                bars_type = "Minute", bars_value = 1, application_timezone = "UTC", template = "CME US Index Futures ETH" };
        }

        protected override void OnBarUpdate()
        {
            Pair callback = ReadPair(); // At this callback entry, before locks/metadata/I/O.
            if (State != State.Realtime || BarsInProgress != 0 || !IsFirstTickOfBar) return;
            lock (sync)
            {
                if (!realtime || stopped || writer == null) return;
                try
                {
                    if (ElapsedMs() >= WindowMs) { Finish("WINDOW_END"); return; }
                    if (!SafeSource() || CalendarJson() != calendarJson) { Finish("SOURCE_OR_CALENDAR_CHANGED"); return; }
                    if (continuity != Continuity.BASELINE_PROVEN || callback.qpc_before < baselineReadyQpc) return;
                    var label = UtcWall(Time[0]);
                    if (lastBar >= 0 && (CurrentBar != lastBar + 1 || label != lastLabel.AddMinutes(1)))
                    { Finish("BAR_CONTINUITY_FAILED"); return; }
                    if (firstBar < 0) firstBar = CurrentBar;
                    if (CurrentBar - 1 > firstBar)
                    { Emit("CLOSED", Observation(1, callback), callback); if (!stopped) closedCount++; }
                    Emit("FORMING", Observation(0, callback), callback);
                    lastBar = CurrentBar;
                    lastLabel = label;
                    if (closedCount >= RequiredClosed) Finish("BOUNDARIES_COMPLETE");
                }
                catch { Finish("CALLBACK_FAILED"); }
            }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            Pair callback = ReadPair();
            lock (sync)
            {
                if (!started || stopped || source == null) return;
                try
                {
                    var before = continuity;
                    var callbackSource = update == null ? null : update.Connection;
                    bool same = callbackSource != null && Object.ReferenceEquals(callbackSource, source);
                    // Copy event scalars once. Never retain or serialize provider objects.
                    ConnectionStatus? status = update == null ? (ConnectionStatus?)null : update.Status;
                    ConnectionStatus? price = update == null ? (ConnectionStatus?)null : update.PriceStatus;
                    ConnectionStatus? previous = update == null ? (ConnectionStatus?)null : update.PreviousStatus;
                    ConnectionStatus? previousPrice = update == null ? (ConnectionStatus?)null : update.PreviousPriceStatus;
                    var sourceStatus = source.Status; var sourcePrice = source.PriceStatus;
                    bool sourceValid = SafeSource();
                    var afterStatus = source.Status; var afterPrice = source.PriceStatus;
                    bool agree = sourceStatus == afterStatus && sourcePrice == afterPrice;
                    string reason = StartupEventReason(update != null, callbackSource != null, same,
                        sourceValid, agree, status, price, previous, previousPrice, sourceStatus, sourcePrice);
                    if (reason == "CONTINUE" || reason == "WAIT_STARTUP_ALIGNMENT")
                    {
                        if (before != Continuity.BASELINE_PROVEN) continuity = Continuity.WAIT_ALIGNMENT;
                        alignedEvent = reason == "CONTINUE" && realtime && State == State.Realtime
                            && callback.qpc_before >= realtimeQpc ? connectionSequence : -1;
                        if (realtime && before != Continuity.BASELINE_PROVEN && StartupMs() >= 30000)
                            reason = "STOP_STARTUP_TIMEOUT";
                    }
                    if (reason != "CONTINUE" && reason != "WAIT_STARTUP_ALIGNMENT") continuity = Continuity.STOPPED;
                    Emit("CONNECTION_EVENT", new { event_sequence = connectionSequence++,
                        event_present = update != null, connection_present = callbackSource != null, same_source = same,
                        event_status = StatusName(status), event_price_status = StatusName(price),
                        previous_status = StatusName(previous), previous_price_status = StatusName(previousPrice),
                        source_status = StatusName(sourceStatus), source_price_status = StatusName(sourcePrice),
                        source_status_after = StatusName(afterStatus), source_price_status_after = StatusName(afterPrice),
                        source_valid = sourceValid, samples_agree = agree,
                        baseline_established = before == Continuity.BASELINE_PROVEN,
                        continuity_before = before.ToString(), continuity_after = continuity.ToString(),
                        state = State.ToString(), bar_evidence_emitted = lastBar >= 0, reason = reason }, callback);
                    if (reason == "CONTINUE" && alignedEvent >= 0) alignedEventQpc = Stopwatch.GetTimestamp();
                    if (continuity == Continuity.STOPPED) Finish(reason);
                }
                catch { Finish("CONNECTION_DIAGNOSTIC_FAILED"); }
            }
        }

        // Sprint 11T admission predicates and ordering, with explicit null diagnostics.
        // A quarantined callback is recorded, not ignored or declared stale/harmless.
        private string StartupEventReason(bool present, bool hasSource, bool same, bool healthy, bool stable,
            ConnectionStatus? status, ConnectionStatus? price, ConnectionStatus? previous,
            ConnectionStatus? previousPrice, ConnectionStatus sourceStatus, ConnectionStatus sourcePrice)
        {
            if (!present) return "CONNECTION_EVENT_NULL";
            if (!hasSource) return "CONNECTION_EVENT_SOURCE_NULL";
            if (new[] { status, price, previous, previousPrice, sourceStatus, sourcePrice }.Any(v =>
                !v.HasValue || !Enum.IsDefined(typeof(ConnectionStatus), v.Value))) return "STOP_UNKNOWN_CONNECTION_STATE";
            if (!same) return "STOP_CONNECTION_IDENTITY_MISMATCH";
            if (!stable) return "STOP_UNSTABLE_CONNECTION_STATE";
            if (!healthy || sourceStatus != ConnectionStatus.Connected || sourcePrice != ConnectionStatus.Connected)
                return "STOP_CURRENT_CONNECTION_NOT_READY";
            if (new[] { status, price }.Any(v => v == ConnectionStatus.Disconnected
                || v == ConnectionStatus.Disconnecting || v == ConnectionStatus.ConnectionLost)) return "STOP_CONNECTION_LOSS_EVENT";
            if (new[] { previous, previousPrice }.Any(v => v == ConnectionStatus.Disconnecting || v == ConnectionStatus.ConnectionLost)
                || (continuity == Continuity.BASELINE_PROVEN && (previous != ConnectionStatus.Connected || previousPrice != ConnectionStatus.Connected)))
                return "STOP_RECONNECT_OR_UNPROVEN_CONTINUITY";
            if (status != ConnectionStatus.Connected || price != ConnectionStatus.Connected)
            {
                if (continuity == Continuity.BASELINE_PROVEN || previous == ConnectionStatus.Connected || previousPrice == ConnectionStatus.Connected)
                    return "STOP_CONNECTION_REGRESSION";
                return "WAIT_STARTUP_ALIGNMENT";
            }
            return "CONTINUE"; // Never establishes baseline in the event callback.
        }

        private void AlignmentPoll(object sender, EventArgs args)
        {
            Pair callback = ReadPair();
            lock (sync)
            {
                if (stopped || !realtime || writer == null) return;
                try
                {
                    if (ElapsedMs() >= WindowMs) { Finish("WINDOW_END"); return; }
                    var status = source.Status; var price = source.PriceStatus;
                    bool valid = SafeSource();
                    var afterStatus = source.Status; var afterPrice = source.PriceStatus;
                    bool agree = status == afterStatus && price == afterPrice;
                    if (!valid || !agree || status != ConnectionStatus.Connected || price != ConnectionStatus.Connected)
                    { Finish("STOP_CURRENT_CONNECTION_NOT_READY"); return; }
                    if (CalendarJson() != calendarJson) { Finish("SOURCE_OR_CALENDAR_CHANGED"); return; }
                    if (continuity == Continuity.BASELINE_PROVEN) return;
                    if (StartupMs() >= 30000) { Finish("STOP_STARTUP_TIMEOUT"); return; }
                    if (alignedEvent < 0 || callback.qpc_before < alignedEventQpc || State != State.Realtime) return;
                    var before = continuity;
                    continuity = Continuity.BASELINE_PROVEN;
                    Emit("BASELINE", new { aligned_event_sequence = alignedEvent, state = State.ToString(),
                        continuity_before = before.ToString(), continuity_after = continuity.ToString(),
                        source_status = StatusName(status), source_price_status = StatusName(price),
                        source_status_after = StatusName(afterStatus), source_price_status_after = StatusName(afterPrice),
                        source_valid = valid, samples_agree = agree, calendar_sha256 = calendarHash }, callback);
                    baselineReadyQpc = Stopwatch.GetTimestamp();
                    if (startupDeadline != null) startupDeadline.Dispose();
                    startupDeadline = null;
                }
                catch { Finish("ALIGNMENT_POLL_FAILED"); }
            }
        }

        private static string StatusName(ConnectionStatus? value)
        {
            if (!value.HasValue) return "UNAVAILABLE";
            return Enum.IsDefined(typeof(ConnectionStatus), value.Value) ? value.Value.ToString()
                : "UNDEFINED_" + ((int)value.Value).ToString(CultureInfo.InvariantCulture);
        }

        private void Emit(string kind, object payload, Pair callback)
        {
            if (stopped || writer == null) return;
            if (ElapsedMs() >= WindowMs && kind != "END") { Finish("WINDOW_END"); return; }
            if (sequence >= MaximumRecords - 1 && kind != "END") { Finish("RECORD_LIMIT"); return; }
            // This pair supplies this exact record's event_time. No second UTC read.
            Pair emission = ReadPair();
            writer.WriteLine(new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.native-timing.v3", run_id = CaptureRunId, session = session,
                sequence = sequence++, kind = kind, event_time = emission.utc, emission = emission,
                callback = callback, qpc_frequency = Stopwatch.Frequency, start_qpc = startQpc,
                observation_only = true, runtime_admission = false, payload = payload }));
        }

        private void Finish(string reason)
        {
            if (stopped) return;
            bool terminalWritten = false;
            try
            {
                if (writer != null)
                { Emit("END", new { reason = reason, closed_count = closedCount }, ReadPair()); terminalWritten = true; }
            }
            catch { }
            stopped = true;
            continuity = Continuity.STOPPED;
            bool timersDetached = true;
            try { if (startupDeadline != null) startupDeadline.Dispose(); } catch { timersDetached = false; }
            startupDeadline = null;
            try { if (alignmentTimer != null) { alignmentTimer.Stop(); alignmentTimer.Tick -= AlignmentPoll; } }
            catch { timersDetached = false; }
            alignmentTimer = null;
            try { if (deadline != null) deadline.Dispose(); } catch { timersDetached = false; }
            deadline = null;
            source = null;
            bool closed = false;
            try { if (writer != null) { writer.Dispose(); closed = true; } } catch { }
            writer = null;
            if (closed && terminalWritten)
            {
                try
                {
                    byte[] bytes = File.ReadAllBytes(path);
                    using (var seal = new StreamWriter(new FileStream(path + ".done.tmp", FileMode.CreateNew,
                        FileAccess.Write, FileShare.Read), new UTF8Encoding(false)))
                        seal.Write(new JavaScriptSerializer().Serialize(new { schema = "arms.nt.native-timing.seal.v1",
                            run_id = CaptureRunId, session = session, writer_closed = true, timers_detached = timersDetached,
                            records = sequence, bytes = bytes.Length, sha256 = Hash(bytes), reason = reason }));
                    // Publish only a fully disposed seal; a reader must never see partial JSON.
                    File.Move(path + ".done.tmp", path + ".done.json");
                }
                catch { }
            }
            try { Print("ARMS_NATIVE_TIMING_END reason=" + reason); } catch { }
        }
    }
}
