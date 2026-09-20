// Temporary connection-metadata observer. No market admission or execution path.
// Separate from ArmsReadOnlyMarketV1; never changes that exporter's policy.
using System;
using System.ComponentModel.DataAnnotations;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsConnectionObserverV1 : Indicator
    {
        private const int WindowMilliseconds = 30000;
        private const int HeartbeatMilliseconds = 2000;
        private const int MaximumRecords = 512; // Includes START and END.
        private readonly object sync = new object();
        private readonly Stopwatch clock = new Stopwatch();
        private StreamWriter writer;
        private Timer heartbeatTimer, deadlineTimer;
        private Connection selected;
        private string session, selection = "NOT_SELECTED";
        private long sequence;
        private bool started, stopped, subscribed;

        [NinjaScriptProperty]
        [Display(Name = "Private observation directory", Order = 1, GroupName = "ARMS observer")]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Expected provider enum", Order = 2, GroupName = "ARMS observer")]
        public string ExpectedProvider { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsConnectionObserverV1";
                Description = "Bounded connection metadata only; no admission authority.";
                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;
                OutputDirectory = "";
                ExpectedProvider = "";
                return;
            }
            lock (sync)
            {
                if (State == State.Terminated) { Finish("HOST_TERMINATED"); return; }
                if (State == State.DataLoaded && !started && !stopped) StartObservation();
                else if (started && !stopped) Observe("LIFECYCLE", "INDICATOR", null);
            }
        }

        private void StartObservation()
        {
            started = true;
            clock.Start();
            try
            {
                if (String.IsNullOrWhiteSpace(OutputDirectory) || !Path.IsPathRooted(OutputDirectory)
                    || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\")
                    || !Directory.Exists(OutputDirectory) || String.IsNullOrWhiteSpace(ExpectedProvider))
                    throw new InvalidOperationException();
                session = Guid.NewGuid().ToString();
                writer = new StreamWriter(new FileStream(Path.Combine(OutputDirectory,
                    session + ".observer.jsonl"), FileMode.CreateNew, FileAccess.Write, FileShare.Read),
                    new UTF8Encoding(false));
                writer.AutoFlush = true;
                // Pin a single matching object without requiring a connected state.
                // Never select by private name; never silently rebind this source.
                // Never wait on the registry while holding our observation lock:
                // a provider thread may be delivering a callback under its own lock.
                if (!System.Threading.Monitor.TryEnter(Connection.Connections)) selection = "REGISTRY_UNAVAILABLE";
                else
                {
                    try
                    {
                        var candidates = Connection.Connections.Where(c => c != null
                            && ProviderName(c) == ExpectedProvider).ToArray();
                        selected = candidates.Length == 1 ? candidates[0] : null;
                        selection = candidates.Length == 1 ? "ONE_PROVIDER_MATCH"
                            : candidates.Length == 0 ? "NO_PROVIDER_MATCH" : "AMBIGUOUS_PROVIDER_MATCH";
                    }
                    finally { System.Threading.Monitor.Exit(Connection.Connections); }
                }
                subscribed = true;
                Connection.ConnectionStatusUpdate += OnGlobalConnectionStatus;
                Observe("OBSERVER_START", "LIFECYCLE", null);
                if (stopped) return;
                // Thread-pool timers do not depend on ticks or the chart dispatcher.
                heartbeatTimer = new Timer(OnHeartbeat, null, HeartbeatMilliseconds, HeartbeatMilliseconds);
                int remaining = Math.Max(1, WindowMilliseconds - (int)clock.Elapsed.TotalMilliseconds);
                deadlineTimer = new Timer(OnDeadline, null, remaining, Timeout.Infinite);
            }
            catch (Exception error) { Finish("START_FAILED", ErrorCode(error)); }
        }

        protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs update)
        {
            Observe("CONNECTION_STATUS", "INDICATOR", update);
        }

        private void OnGlobalConnectionStatus(object sender, ConnectionStatusEventArgs update)
        {
            Observe("CONNECTION_STATUS", "GLOBAL", update);
        }

        private void OnHeartbeat(object state)
        {
            Observe("OBSERVATION_HEARTBEAT", "TIMER", null);
        }

        private void OnDeadline(object state)
        {
            lock (sync) Finish("WINDOW_END");
        }

        private void Observe(string kind, string channel, ConnectionStatusEventArgs update)
        {
            var received = DateTime.UtcNow.ToString("o");
            var receivedElapsed = clock.Elapsed.TotalMilliseconds;
            lock (sync)
            {
                if (!started || stopped || writer == null) return;
                if (clock.Elapsed.TotalMilliseconds >= WindowMilliseconds) { Finish("WINDOW_END"); return; }
                if (sequence >= MaximumRecords - 1) { Finish("RECORD_LIMIT"); return; }
                try
                {
                    var callback = Object.ReferenceEquals(update, null) ? null : update.Connection;
                    var source = selected;
                    var price1 = CurrentStatus(source, true);
                    var status1 = CurrentStatus(source, false);
                    var provider = ProviderName(source);
                    bool? registered = null;
                    if (System.Threading.Monitor.TryEnter(Connection.Connections))
                    {
                        try { registered = source != null && Connection.Connections.Any(c => Object.ReferenceEquals(c, source)); }
                        finally { System.Threading.Monitor.Exit(Connection.Connections); }
                    }
                    var price2 = CurrentStatus(source, true);
                    var status2 = CurrentStatus(source, false);
                    var payload = new {
                        callback_present = callback != null,
                        callback_connection_status = callback == null ? "UNKNOWN" : StatusName(update.Status),
                        callback_previous_connection_status = callback == null ? "UNKNOWN" : StatusName(update.PreviousStatus),
                        callback_price_status = callback == null ? "UNKNOWN" : StatusName(update.PriceStatus),
                        callback_previous_price_status = callback == null ? "UNKNOWN" : StatusName(update.PreviousPriceStatus),
                        same_source = callback != null && Object.ReferenceEquals(callback, source),
                        callback_provider = ProviderName(callback), source_provider = provider,
                        source_connection_status_1 = status1, source_price_status_1 = price1,
                        source_connection_status_2 = status2, source_price_status_2 = price2,
                        samples_agree = price1 == price2 && status1 == status2,
                        samples_known = !new[] { price1, price2, status1, status2 }.Contains("UNKNOWN"),
                        source_present = source != null, source_registered = registered,
                        identity_status = source == null ? "NO_SELECTED_SOURCE"
                            : !registered.HasValue ? "REGISTRY_UNAVAILABLE"
                            : registered.Value ? "PINNED_REGISTERED" : "PINNED_REMOVED",
                        source_selection = selection, observation_only = true };
                    // Never convert a contradiction, a loss or a duplicate into a decision.
                    Write(kind, channel, received, receivedElapsed, payload);
                }
                catch (Exception error) { Finish("OBSERVATION_FAILED", ErrorCode(error)); }
            }
        }

        private void Write(string kind, string channel, string received, double receivedElapsed, object payload)
        {
            if (kind != "OBSERVER_END" && clock.Elapsed.TotalMilliseconds >= WindowMilliseconds)
            {
                Finish("WINDOW_END");
                return;
            }
            writer.WriteLine(new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.connection-observer.v1", session = session, sequence = sequence++,
                event_time = DateTime.UtcNow.ToString("o"), elapsed_ms = clock.Elapsed.TotalMilliseconds,
                callback_received_time = received, callback_received_elapsed_ms = receivedElapsed,
                channel = channel, kind = kind,
                lifecycle_state = Enum.IsDefined(typeof(State), State) ? State.ToString() : "UNKNOWN",
                observer_state = stopped ? "ENDED" : "OBSERVING", payload = payload }));
        }

        private static string StatusName(ConnectionStatus value)
        {
            return Enum.IsDefined(typeof(ConnectionStatus), value) ? value.ToString() : "UNKNOWN";
        }

        private static string CurrentStatus(Connection connection, bool price)
        {
            try { return connection == null ? "UNKNOWN" : StatusName(price ? connection.PriceStatus : connection.Status); }
            catch { return "UNKNOWN"; }
        }

        private static string ProviderName(Connection connection)
        {
            try
            {
                if (connection == null || connection.Options == null) return "UNKNOWN";
                var provider = connection.Options.Provider;
                return Enum.IsDefined(provider.GetType(), provider) ? provider.ToString() : "UNKNOWN";
            }
            catch { return "UNKNOWN"; }
        }

        private static string ErrorCode(Exception error)
        {
            if (error is UnauthorizedAccessException) return "ACCESS_DENIED";
            if (error is IOException) return "IO_ERROR";
            if (error is ArgumentException) return "INVALID_ARGUMENT";
            if (error is InvalidOperationException) return "INVALID_OPERATION";
            return "OTHER";
        }

        private void Finish(string reason, string errorCode = "NONE")
        {
            if (stopped) return;
            stopped = true;
            if (subscribed)
            {
                try { Connection.ConnectionStatusUpdate -= OnGlobalConnectionStatus; } catch { }
                subscribed = false;
            }
            if (heartbeatTimer != null)
            {
                try { heartbeatTimer.Dispose(); } catch { }
                heartbeatTimer = null;
            }
            if (deadlineTimer != null)
            {
                try { deadlineTimer.Dispose(); } catch { }
                deadlineTimer = null;
            }
            if (writer != null)
            {
                try { Write("OBSERVER_END", "LIFECYCLE", DateTime.UtcNow.ToString("o"),
                    clock.Elapsed.TotalMilliseconds, new { reason = reason, error_code = errorCode,
                        observation_only = true, window_ms = WindowMilliseconds, maximum_records = MaximumRecords }); } catch { }
                try { writer.Dispose(); } catch { }
                writer = null;
            }
            clock.Stop();
            selected = null;
            try { Print("ARMS_CONNECTION_OBSERVER_END reason=" + reason + " error=" + errorCode); } catch { }
        }
    }
}
