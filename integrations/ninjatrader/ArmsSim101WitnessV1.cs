// Bounded scalar metadata witness only. A consistent candidate is NOT SIM proof.
// No account identifiers, balances, positions, executions or order operations.
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
    public class ArmsSim101WitnessV1 : Indicator
    {
        private const int WindowMs = 30000, IntervalMs = 5000, MaximumRecords = 8;
        private readonly object sync = new object();
        private readonly Stopwatch clock = new Stopwatch();
        private Account pinned;
        private Connection connection;
        private StreamWriter writer;
        private Timer sampleTimer, deadlineTimer;
        private bool started, stopped, subscribed;
        private string session;
        private int sequence;

        [NinjaScriptProperty]
        [Display(Name = "Private witness directory", Order = 1, GroupName = "ARMS SIM witness")]
        public string OutputDirectory { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsSim101WitnessV1";
                Description = "30-second metadata witness; no simulation proof or execution authority.";
                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;
                OutputDirectory = "";
                return;
            }
            lock (sync)
            {
                if (State == State.Terminated) { Finish("HOST_TERMINATED"); return; }
                if (State != State.DataLoaded || started || stopped) return;
                started = true;
                clock.Start();
                try
                {
                    if (String.IsNullOrWhiteSpace(OutputDirectory) || !Path.IsPathRooted(OutputDirectory)
                        || Path.GetPathRoot(OutputDirectory).StartsWith(@"\\") || !Directory.Exists(OutputDirectory))
                        throw new InvalidOperationException();
                    session = Guid.NewGuid().ToString();
                    writer = new StreamWriter(new FileStream(Path.Combine(OutputDirectory,
                        session + ".sim101-witness.jsonl"), FileMode.CreateNew, FileAccess.Write, FileShare.Read),
                        new UTF8Encoding(false));
                    writer.AutoFlush = true;
                    Account.SimulationAccountReset += OnReset;
                    subscribed = true;
                    Observe("WITNESS_START", true);
                    if (stopped) return;
                    sampleTimer = new Timer(_ => { lock (sync) Observe("WITNESS_SAMPLE", false); },
                        null, IntervalMs, IntervalMs);
                    deadlineTimer = new Timer(_ => { lock (sync) Finish("WINDOW_END"); }, null,
                        Math.Max(1, WindowMs - (int)clock.Elapsed.TotalMilliseconds), Timeout.Infinite);
                }
                catch { Finish("START_FAILED"); }
            }
        }

        private void OnReset(object sender, EventArgs args)
        {
            // Passive subscription only. No reset is requested. An unidentifiable
            // reset also ends this observation; it cannot grant built-in identity.
            lock (sync)
                if (!stopped && (pinned == null || sender == null || Object.ReferenceEquals(sender, pinned)))
                    Finish("RESET_OBSERVED");
        }

        private sealed class Scalars
        {
            public bool ExactName, SameConnection;
            public string AccountProvider, AccountState, ConnectionState, PriceState, ConnectionProvider;
            public bool Same(Scalars other)
            {
                return ExactName == other.ExactName && SameConnection == other.SameConnection
                    && AccountProvider == other.AccountProvider && AccountState == other.AccountState
                    && ConnectionState == other.ConnectionState && PriceState == other.PriceState
                    && ConnectionProvider == other.ConnectionProvider;
            }
        }

        private Scalars ReadScalars()
        {
            return new Scalars { ExactName = pinned.Name == "Sim101",
                SameConnection = Object.ReferenceEquals(pinned.Connection, connection),
                AccountProvider = EnumName(pinned.Provider), AccountState = EnumName(pinned.ConnectionStatus),
                ConnectionState = connection == null ? "UNKNOWN" : EnumName(connection.Status),
                PriceState = connection == null ? "UNKNOWN" : EnumName(connection.PriceStatus),
                ConnectionProvider = connection == null || connection.Options == null ? "UNKNOWN"
                    : EnumName(connection.Options.Provider) };
        }

        private static string EnumName<T>(T value) where T : struct
        {
            return Enum.IsDefined(typeof(T), value) ? value.ToString() : "UNKNOWN";
        }

        private void Observe(string kind, bool initial)
        {
            if (stopped || writer == null) return;
            if (clock.Elapsed.TotalMilliseconds >= WindowMs) { Finish("WINDOW_END"); return; }
            if (sequence >= MaximumRecords - 1) { Finish("RECORD_LIMIT"); return; }
            try
            {
                int count;
                bool same;
                // Never block provider threads or acquire both registries together.
                if (!Monitor.TryEnter(Account.All)) { Finish("ACCOUNT_REGISTRY_UNAVAILABLE"); return; }
                try
                {
                    var candidates = Account.All.Where(a => a != null && a.Name == "Sim101").ToArray();
                    count = candidates.Length;
                    if (initial && count == 1) { pinned = candidates[0]; connection = pinned.Connection; }
                    same = count == 1 && Object.ReferenceEquals(pinned, candidates[0]);
                }
                finally { Monitor.Exit(Account.All); }
                if (!same)
                {
                    Write(kind, new { exact_name_candidates = count, same_pinned_account = false,
                        candidate_status = "REJECTED_CANDIDATE_SELECTION" });
                    Finish(count == 0 ? "NO_CANDIDATE" : count > 1 ? "AMBIGUOUS_CANDIDATES" : "ACCOUNT_REPLACED");
                    return;
                }
                var before = ReadScalars();
                bool registered;
                if (!Monitor.TryEnter(Connection.Connections)) { Finish("CONNECTION_REGISTRY_UNAVAILABLE"); return; }
                try { registered = connection != null && Connection.Connections.Any(c => Object.ReferenceEquals(c, connection)); }
                finally { Monitor.Exit(Connection.Connections); }
                var after = ReadScalars();
                bool stable = before.Same(after);
                bool consistent = stable && after.ExactName && after.SameConnection && registered
                    && after.AccountProvider == "Simulator" && after.ConnectionProvider == "Provider31"
                    && after.AccountState == "Connected" && after.ConnectionState == "Connected" && after.PriceState == "Connected";
                Write(kind, new { exact_name_candidates = count, same_pinned_account = same,
                    exact_builtin_name = after.ExactName, same_pinned_connection = after.SameConnection,
                    connection_registered = registered, samples_agree = stable,
                    account_provider = after.AccountProvider, account_connection_status = after.AccountState,
                    connection_provider = after.ConnectionProvider, connection_status = after.ConnectionState,
                    price_status = after.PriceState,
                    candidate_status = consistent ? "CANDIDATE_CONSISTENT_NOT_PROVEN" : "REJECTED_CANDIDATE_PRECONDITIONS" });
                if (!consistent) Finish("CANDIDATE_PRECONDITIONS_FAILED");
            }
            catch { Finish("METADATA_READ_FAILED"); }
        }

        private void Write(string kind, object payload)
        {
            if (kind != "WITNESS_END" && clock.Elapsed.TotalMilliseconds >= WindowMs)
            {
                Finish("WINDOW_END");
                return;
            }
            writer.WriteLine(new JavaScriptSerializer().Serialize(new {
                schema = "arms.nt.sim101-witness.v1", session = session, sequence = sequence++,
                event_time = DateTime.UtcNow.ToString("o"), elapsed_ms = clock.Elapsed.TotalMilliseconds,
                kind = kind, observation_only = true, builtin_sim101_proof = "NOT_PROVEN",
                generic_classification = "UNKNOWN", future_sim_eligible = false,
                sim_execution_authority = "DISABLED", payload = payload }));
        }

        private void Finish(string reason)
        {
            if (stopped) return;
            stopped = true;
            bool unsubscribed = true, timersDisposed = true;
            if (subscribed)
            {
                try { Account.SimulationAccountReset -= OnReset; } catch { unsubscribed = false; }
                subscribed = false;
            }
            try { if (sampleTimer != null) sampleTimer.Dispose(); } catch { timersDisposed = false; }
            try { if (deadlineTimer != null) deadlineTimer.Dispose(); } catch { timersDisposed = false; }
            sampleTimer = deadlineTimer = null;
            pinned = null;
            connection = null;
            if (writer != null)
            {
                try { Write("WITNESS_END", new { reason = reason, reset_unsubscribed = unsubscribed,
                    timers_disposed = timersDisposed, native_references_released = true,
                    window_ms = WindowMs, maximum_records = MaximumRecords }); } catch { }
                try { writer.Dispose(); } catch { }
                writer = null;
            }
            clock.Stop();
            try { Print("ARMS_SIM101_WITNESS_END reason=" + reason); } catch { }
        }
    }
}
