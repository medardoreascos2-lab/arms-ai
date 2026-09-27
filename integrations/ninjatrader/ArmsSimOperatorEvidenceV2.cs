// Operator-bound native SIM scalar evidence only.
// No account balances, positions, executions or order operations.
// No execution authority. No built-in Sim101 proof.

using System;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSimOperatorEvidenceV2 : Indicator
    {
        private const int IntervalMilliseconds = 5000;
        private const int MaximumRecords = 512;

        private readonly object sync = new object();

        private StreamWriter writer;
        private Timer sampleTimer;

        private Account pinnedAccount;
        private Connection pinnedConnection;

        private byte[] secret;

        private bool started;
        private bool stopped;
        private bool subscribed;

        private string session;
        private string runtimeRef;
        private string connectionEpoch;

        private string installationRef;
        private string accountRef;
        private string connectionRef;
        private string labelRef;

        private long sequence;

        [NinjaScriptProperty]
        [Display(
            Name = "Private evidence directory",
            Order = 1,
            GroupName = "ARMS SIM operator evidence"
        )]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Selected account name",
            Order = 2,
            GroupName = "ARMS SIM operator evidence"
        )]
        public string SelectedAccountName { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Private HMAC secret path",
            Order = 3,
            GroupName = "ARMS SIM operator evidence"
        )]
        public string SecretPath { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsSimOperatorEvidenceV2";
                Description =
                    "Operator-bound simulation identity evidence only; no order authority.";

                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;

                OutputDirectory = "";
                SelectedAccountName = "";
                SecretPath = "";

                return;
            }

            lock (sync)
            {
                if (State == State.Terminated)
                {
                    Finish("HOST_TERMINATED");
                    return;
                }

                if (
                    State == State.DataLoaded
                    && !started
                    && !stopped
                )
                {
                    StartEvidence();
                }
            }
        }

        private void StartEvidence()
        {
            started = true;
            string startupStage = "BEGIN";

            try
            {
                Print("ARMS_SIM_OPERATOR_EVIDENCE_START");

                startupStage = "VALIDATE_INPUTS";
                ValidatePathsAndInputs();

                startupStage = "READ_SECRET";
                secret = File.ReadAllBytes(
                    SecretPath
                );

                if (
                    secret == null
                    || secret.Length < 32
                )
                    throw new InvalidOperationException();

                startupStage = "CREATE_RUNTIME_IDENTITY";
                session = Guid.NewGuid().ToString();
                runtimeRef = Guid.NewGuid().ToString();
                connectionEpoch = Guid.NewGuid().ToString();

                startupStage = "SELECT_ACCOUNT";
                SelectAndPinAccount();

                startupStage = "VALIDATE_SIMULATION";
                ValidateNativeSimulation();

                startupStage = "DERIVE_REFS";
                installationRef = DeriveRef(
                    "installation",
                    Environment.MachineName
                );

                accountRef = DeriveRef(
                    "account",
                    AccountIdentity(
                        pinnedAccount
                    )
                );

                connectionRef = DeriveRef(
                    "connection",
                    ConnectionIdentity(
                        pinnedConnection
                    )
                );

                labelRef = DeriveRef(
                    "label",
                    SelectedAccountName
                );

                var path = Path.Combine(
                    OutputDirectory,
                    session
                        + ".sim-operator.jsonl"
                );

                startupStage = "OPEN_EVIDENCE_FILE";
                writer = new StreamWriter(
                    new FileStream(
                        path,
                        FileMode.CreateNew,
                        FileAccess.Write,
                        FileShare.Read
                    ),
                    new UTF8Encoding(false)
                );

                writer.AutoFlush = true;

                startupStage = "SUBSCRIBE_CONNECTION";
                Connection.ConnectionStatusUpdate
                    += OnGlobalConnectionStatus;

                subscribed = true;

                startupStage = "FIRST_OBSERVATION";
                Observe();

                if (stopped)
                    return;

                sampleTimer = new Timer(
                    _ =>
                    {
                        lock (sync)
                            Observe();
                    },
                    null,
                    IntervalMilliseconds,
                    IntervalMilliseconds
                );
            }
            catch (Exception error)
            {
                try
                {
                    Print(
                        "ARMS_SIM_OPERATOR_EVIDENCE_START_FAILED"
                        + " stage=" + startupStage
                        + " error=" + error.GetType().Name
                        + " reason=" + error.Message
                    );
                }
                catch
                {
                }

                Finish("START_FAILED");
            }
        }

        private void ValidatePathsAndInputs()
        {
            if (
                String.IsNullOrWhiteSpace(
                    OutputDirectory
                )
                || !Path.IsPathRooted(
                    OutputDirectory
                )
                || Path.GetPathRoot(
                    OutputDirectory
                ).StartsWith(@"\\")
                || !Directory.Exists(
                    OutputDirectory
                )
                || String.IsNullOrWhiteSpace(
                    SelectedAccountName
                )
                || String.IsNullOrWhiteSpace(
                    SecretPath
                )
                || !Path.IsPathRooted(
                    SecretPath
                )
                || Path.GetPathRoot(
                    SecretPath
                ).StartsWith(@"\\")
                || !File.Exists(
                    SecretPath
                )
            )
                throw new InvalidOperationException();
        }

        private void SelectAndPinAccount()
        {
            if (
                !Monitor.TryEnter(
                    Account.All
                )
            )
                throw new InvalidOperationException();

            try
            {
                var candidates = Account.All
                    .Where(
                        a =>
                            a != null
                            && a.Name
                                == SelectedAccountName
                    )
                    .ToArray();

                if (
                    candidates.Length != 1
                )
                    throw new InvalidOperationException();

                pinnedAccount = candidates[0];
                pinnedConnection =
                    pinnedAccount.Connection;

                if (
                    pinnedConnection == null
                )
                    throw new InvalidOperationException();
            }
            finally
            {
                Monitor.Exit(
                    Account.All
                );
            }
        }

        private void ValidateNativeSimulation()
        {
            if (pinnedAccount == null)
                throw new InvalidOperationException("ACCOUNT_NULL");

            if (pinnedConnection == null)
                throw new InvalidOperationException("CONNECTION_NULL");

            string accountProvider =
                Enum.IsDefined(
                    typeof(Provider),
                    pinnedAccount.Provider
                )
                ? pinnedAccount.Provider.ToString()
                : "UNKNOWN";

            string accountStatus =
                Enum.IsDefined(
                    typeof(ConnectionStatus),
                    pinnedAccount.ConnectionStatus
                )
                ? pinnedAccount.ConnectionStatus.ToString()
                : "UNKNOWN";

            string connectionStatus =
                Enum.IsDefined(
                    typeof(ConnectionStatus),
                    pinnedConnection.Status
                )
                ? pinnedConnection.Status.ToString()
                : "UNKNOWN";

            string mode =
                pinnedConnection.Options == null
                ? "OPTIONS_NULL"
                : (
                    Enum.IsDefined(
                        typeof(Mode),
                        pinnedConnection.Options.Mode
                    )
                    ? pinnedConnection.Options.Mode.ToString()
                    : "UNKNOWN"
                );

            try
            {
                Print(
                    "ARMS_SIM_OPERATOR_EVIDENCE_SIM_CHECK"
                    + " account_provider=" + accountProvider
                    + " account_status=" + accountStatus
                    + " connection_status=" + connectionStatus
                    + " mode=" + mode
                );
            }
            catch
            {
            }

            if (pinnedAccount.Provider != Provider.Simulator)
                throw new InvalidOperationException(
                    "ACCOUNT_PROVIDER_NOT_SIMULATOR"
                );

            if (
                pinnedAccount.ConnectionStatus
                != ConnectionStatus.Connected
            )
                throw new InvalidOperationException(
                    "ACCOUNT_NOT_CONNECTED"
                );

            if (
                pinnedConnection.Status
                != ConnectionStatus.Connected
            )
                throw new InvalidOperationException(
                    "CONNECTION_NOT_CONNECTED"
                );

            if (pinnedConnection.Options == null)
                throw new InvalidOperationException(
                    "CONNECTION_OPTIONS_NULL"
                );

            if (
                !Enum.IsDefined(
                    typeof(Mode),
                    pinnedConnection.Options.Mode
                )
            )
                throw new InvalidOperationException(
                    "CONNECTION_MODE_UNKNOWN"
                );
        }

        private void Observe()
        {
            if (
                stopped
                || writer == null
            )
                return;

            try
            {
                if (
                    sequence >= MaximumRecords
                )
                {
                    Finish(
                        "RECORD_LIMIT"
                    );
                    return;
                }

                ValidatePinnedIdentity();

                var payload = new
                {
                    installation_ref =
                        installationRef,
                    account_ref =
                        accountRef,
                    connection_ref =
                        connectionRef,
                    label_ref =
                        labelRef,
                    provider =
                        "Simulator",
                    connection_mode =
                        pinnedConnection.Options.Mode.ToString(),
                    account_count =
                        1,
                    connected =
                        true,
                    revoked =
                        false,
                    runtime_ref =
                        runtimeRef,
                    connection_epoch =
                        connectionEpoch
                };

                writer.WriteLine(
                    new JavaScriptSerializer()
                        .Serialize(
                            new
                            {
                                schema =
                                    "arms.nt.sim-operator-evidence.v2",
                                session =
                                    session,
                                sequence =
                                    sequence++,
                                observed_at =
                                    DateTime.UtcNow
                                        .ToString("o"),
                                payload =
                                    payload
                            }
                        )
                );
            }
            catch
            {
                Finish(
                    "EVIDENCE_READ_FAILED"
                );
            }
        }

        private void ValidatePinnedIdentity()
        {
            ValidateNativeSimulation();

            if (
                !Monitor.TryEnter(
                    Account.All
                )
            )
                throw new InvalidOperationException();

            try
            {
                var candidates = Account.All
                    .Where(
                        a =>
                            a != null
                            && a.Name
                                == SelectedAccountName
                    )
                    .ToArray();

                if (
                    candidates.Length != 1
                    || !Object.ReferenceEquals(
                        candidates[0],
                        pinnedAccount
                    )
                )
                    throw new InvalidOperationException();
            }
            finally
            {
                Monitor.Exit(
                    Account.All
                );
            }

            if (
                !Monitor.TryEnter(
                    Connection.Connections
                )
            )
                throw new InvalidOperationException();

            try
            {
                var same = Connection.Connections
                    .Any(
                        c =>
                            Object.ReferenceEquals(
                                c,
                                pinnedConnection
                            )
                    );

                if (!same)
                    throw new InvalidOperationException();
            }
            finally
            {
                Monitor.Exit(
                    Connection.Connections
                );
            }
        }

        private void OnGlobalConnectionStatus(
            object sender,
            ConnectionStatusEventArgs update
        )
        {
            lock (sync)
            {
                if (
                    stopped
                    || update == null
                    || update.Connection == null
                )
                    return;

                if (
                    !Object.ReferenceEquals(
                        update.Connection,
                        pinnedConnection
                    )
                )
                    return;

                if (
                    update.Status
                        == ConnectionStatus.Disconnected
                    || update.Status
                        == ConnectionStatus.Disconnecting
                    || update.Status
                        == ConnectionStatus.ConnectionLost
                    || update.PriceStatus
                        == ConnectionStatus.Disconnected
                    || update.PriceStatus
                        == ConnectionStatus.Disconnecting
                    || update.PriceStatus
                        == ConnectionStatus.ConnectionLost
                )
                {
                    Finish(
                        "CONNECTION_EPOCH_REVOKED"
                    );
                }
            }
        }

        private string DeriveRef(
            string domain,
            string value
        )
        {
            if (
                secret == null
                || String.IsNullOrWhiteSpace(
                    domain
                )
                || String.IsNullOrEmpty(
                    value
                )
            )
                throw new InvalidOperationException();

            var payload = Encoding.UTF8.GetBytes(
                "arms.sim.operator-binding.v2"
                + "\0"
                + domain
                + "\0"
                + value
            );

            using (
                var hmac =
                    new HMACSHA256(secret)
            )
            {
                return Hex(
                    hmac.ComputeHash(
                        payload
                    )
                );
            }
        }

        private static string Hex(
            byte[] value
        )
        {
            return BitConverter
                .ToString(value)
                .Replace("-", "")
                .ToLowerInvariant();
        }

        private static string AccountIdentity(
            Account account
        )
        {
            if (account == null)
                throw new InvalidOperationException();

            return String.Join(
                "\0",
                new[]
                {
                    account.Name ?? "",
                    account.Id.ToString(),
                    account.Provider.ToString()
                }
            );
        }

        private static string ConnectionIdentity(
            Connection connection
        )
        {
            if (
                connection == null
                || connection.Options == null
            )
                throw new InvalidOperationException();

            return String.Join(
                "\0",
                new[]
                {
                    connection.Options.Name ?? "",
                    connection.Options.TypeName ?? "",
                    connection.Options.Provider.ToString(),
                    connection.Options.Mode.ToString()
                }
            );
        }

        private void Finish(
            string reason
        )
        {
            if (stopped)
                return;

            stopped = true;

            if (subscribed)
            {
                try
                {
                    Connection.ConnectionStatusUpdate
                        -= OnGlobalConnectionStatus;
                }
                catch
                {
                }

                subscribed = false;
            }

            if (sampleTimer != null)
            {
                try
                {
                    sampleTimer.Dispose();
                }
                catch
                {
                }

                sampleTimer = null;
            }

            if (writer != null)
            {
                try
                {
                    writer.Dispose();
                }
                catch
                {
                }

                writer = null;
            }

            if (secret != null)
            {
                Array.Clear(
                    secret,
                    0,
                    secret.Length
                );

                secret = null;
            }

            pinnedAccount = null;
            pinnedConnection = null;

            try
            {
                Print(
                    "ARMS_SIM_OPERATOR_EVIDENCE_END reason="
                    + reason
                );
            }
            catch
            {
            }
        }
    }
}
