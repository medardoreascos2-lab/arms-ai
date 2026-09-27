using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSimNativeSubmitBridgeV2 : Indicator
    {
        private const string SIM_EXECUTION_AUTHORITY = "DISABLED";
        private const bool EXTERNAL_ORDER_AUTHORITY = false;

        // R48T3 remains hard-disabled.
        // The executable path is compiled/tested but cannot submit yet.
        private const bool NATIVE_SUBMIT_ENABLED = false;
        private const bool NATIVE_EMERGENCY_FLATTEN_ENABLED = true;
        private const bool AUTO_RETRY_ALLOWED = false;

        private const string REQUIRED_ARM_TOKEN =
            "ARM_SIM_ONE_SHOT_V2";

        private const string EMERGENCY_FLATTEN_ARM_TOKEN =
            "ARM_SIM_EMERGENCY_FLATTEN_V2";

        private const string EMERGENCY_FLATTEN_DURABLE_PERMIT =
            "EMERGENCY_FLATTEN_SIM101_V2";

        private const int EMERGENCY_ACTIVATION_MAX_AGE_SECONDS = 300;
        private const int EMERGENCY_ACTIVATION_FUTURE_TOLERANCE_SECONDS = 5;

        private Account selectedAccount;
        private bool submitAttempted;
        private string validatedSubmitActivationPath;
        private bool emergencyFlattenAttempted;
        private bool emergencyFlattenAwaitingConfirmation;
        private string emergencyFlattenInstrumentName;

        private string validatedEmergencyActivationPath;
        private string validatedEmergencyActivationNonce;

        private string activeCommandId;
        private string activeOperationId;
        private string activeClientOrderId;

        [NinjaScriptProperty]
        [Display(
            Name = "SelectedAccountName",
            Order = 1,
            GroupName = "ARMS SIM"
        )]
        public string SelectedAccountName
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "CommandDirectory",
            Order = 2,
            GroupName = "ARMS SIM"
        )]
        public string CommandDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "ValidationResponseDirectory",
            Order = 3,
            GroupName = "ARMS SIM"
        )]
        public string ValidationResponseDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "NativeEvidenceDirectory",
            Order = 4,
            GroupName = "ARMS SIM"
        )]
        public string NativeEvidenceDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "ActivationDirectory",
            Order = 5,
            GroupName = "ARMS SIM"
        )]
        public string ActivationDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "InstrumentName",
            Order = 4,
            GroupName = "ARMS SIM"
        )]
        public string InstrumentName
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "Side",
            Order = 5,
            GroupName = "ARMS SIM"
        )]
        public string Side
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "Quantity",
            Order = 6,
            GroupName = "ARMS SIM"
        )]
        public int Quantity
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "OrderTypeName",
            Order = 7,
            GroupName = "ARMS SIM"
        )]
        public string OrderTypeName
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "CommandId",
            Order = 8,
            GroupName = "ARMS SIM"
        )]
        public string CommandId
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "OperatorArmToken",
            Order = 9,
            GroupName = "ARMS SIM"
        )]
        public string OperatorArmToken
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "RequestOneShotSubmit",
            Order = 10,
            GroupName = "ARMS SIM"
        )]
        public bool RequestOneShotSubmit
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "EmergencyFlattenArmToken",
            Order = 11,
            GroupName = "ARMS SIM"
        )]
        public string EmergencyFlattenArmToken
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "RequestEmergencyFlatten",
            Order = 12,
            GroupName = "ARMS SIM"
        )]
        public bool RequestEmergencyFlatten
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "EmergencyActivationDirectory",
            Order = 13,
            GroupName = "ARMS SIM"
        )]
        public string EmergencyActivationDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "EmergencyActivationId",
            Order = 14,
            GroupName = "ARMS SIM"
        )]
        public string EmergencyActivationId
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "RuntimeSnapshotDirectory",
            Order = 15,
            GroupName = "ARMS SIM"
        )]
        public string RuntimeSnapshotDirectory
        {
            get;
            set;
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsSimNativeSubmitBridgeV2";

                Description =
                    "ARMS SIM guarded one-shot submit bridge. "
                    + "Native submission remains hard-disabled.";

                Calculate = Calculate.OnEachTick;
                IsOverlay = true;

                SelectedAccountName = "Sim101";
                CommandDirectory = string.Empty;
                ValidationResponseDirectory = string.Empty;
                NativeEvidenceDirectory = string.Empty;
                ActivationDirectory = string.Empty;
                InstrumentName = "NQ DEC26";
                Side = "BUY";
                Quantity = 1;
                OrderTypeName = "MARKET";
                CommandId = string.Empty;
                OperatorArmToken = string.Empty;
                RequestOneShotSubmit = false;
                EmergencyFlattenArmToken = string.Empty;
                RequestEmergencyFlatten = false;
                EmergencyActivationDirectory = string.Empty;
                EmergencyActivationId = string.Empty;
                RuntimeSnapshotDirectory = string.Empty;
            }
            else if (State == State.DataLoaded)
            {
                selectedAccount = ResolveSelectedAccount();

                ValidateSelectedAccount();

                selectedAccount.OrderUpdate +=
                    OnNativeOrderUpdate;

                selectedAccount.ExecutionUpdate +=
                    OnNativeExecutionUpdate;

                selectedAccount.PositionUpdate +=
                    OnNativePositionUpdate;

                Print(
                    "ARMS_SIM_NATIVE_OBSERVER_START "
                    + "authority="
                    + SIM_EXECUTION_AUTHORITY
                    + " external_order_authority="
                    + EXTERNAL_ORDER_AUTHORITY
                    + " native_submit_enabled="
                    + NATIVE_SUBMIT_ENABLED
                    + " native_emergency_flatten_enabled="
                    + NATIVE_EMERGENCY_FLATTEN_ENABLED
                    + " auto_retry_allowed="
                    + AUTO_RETRY_ALLOWED
                    + " bridge_version=R48V4F"
                );

                string physicalTestStatus =
                    "SESSION_STATE_UNKNOWN";

                string physicalTestInstrument =
                    string.IsNullOrWhiteSpace(
                        InstrumentName
                    )
                    ? string.Empty
                    : InstrumentName.Trim();

                try
                {
                    NinjaTrader.Cbi.Instrument physicalInstrument =
                        NinjaTrader.Cbi.Instrument.GetInstrument(
                            physicalTestInstrument,
                            true
                        );

                    physicalTestStatus =
                        EvaluatePhysicalTestReadiness(
                            physicalInstrument
                        );
                }
                catch
                {
                    physicalTestStatus =
                        "SESSION_STATE_UNKNOWN";
                }

                string physicalTestSessionWindow =
                    " session_begin=SESSION_WINDOW_UNKNOWN"
                    + " session_end=SESSION_WINDOW_UNKNOWN";

                string physicalTestNextSessionWindow =
                    " next_session_begin=NEXT_SESSION_UNKNOWN"
                    + " next_session_end=NEXT_SESSION_UNKNOWN";

                try
                {
                    NinjaTrader.Cbi.Instrument windowInstrument =
                        NinjaTrader.Cbi.Instrument.GetInstrument(
                            physicalTestInstrument,
                            true
                        );

                    physicalTestSessionWindow =
                        DescribePhysicalTestSessionWindow(
                            windowInstrument
                        );

                    if (
                        windowInstrument != null
                        && windowInstrument.MasterInstrument != null
                        && windowInstrument.MasterInstrument.TradingHours != null
                    )
                    {
                        physicalTestNextSessionWindow =
                            ResolveNextPhysicalTestSessionWindow(
                                windowInstrument.MasterInstrument.TradingHours,
                                DateTime.Now
                            );
                    }
                }
                catch
                {
                    physicalTestSessionWindow =
                        " session_begin=SESSION_WINDOW_UNKNOWN"
                        + " session_end=SESSION_WINDOW_UNKNOWN";

                    physicalTestNextSessionWindow =
                        " next_session_begin=NEXT_SESSION_UNKNOWN"
                        + " next_session_end=NEXT_SESSION_UNKNOWN";
                }

                Print(
                    "ARMS_SIM_PHYSICAL_TEST_READINESS"
                    + " status="
                    + physicalTestStatus
                    + " instrument="
                    + physicalTestInstrument
                    + " connection="
                    + selectedAccount.ConnectionStatus
                    + physicalTestSessionWindow
                    + physicalTestNextSessionWindow
                );

                WriteRuntimeReadinessSnapshot();

                if (
                    RequestOneShotSubmit
                    && RequestEmergencyFlatten
                )
                {
                    throw new InvalidOperationException(
                        "Submit and emergency flatten cannot be requested together."
                    );
                }

                if (RequestOneShotSubmit)
                    AttemptOneShotSubmit();

                if (RequestEmergencyFlatten)
                    AttemptEmergencyFlatten();
            }
            else if (State == State.Terminated)
            {
                if (selectedAccount != null)
                {
                    selectedAccount.OrderUpdate -=
                        OnNativeOrderUpdate;

                    selectedAccount.ExecutionUpdate -=
                        OnNativeExecutionUpdate;

                    selectedAccount.PositionUpdate -=
                        OnNativePositionUpdate;
                }

                selectedAccount = null;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 0)
                return;

            ValidateSelectedAccount();
        }

        private Account ResolveSelectedAccount()
        {
            if (
                string.IsNullOrWhiteSpace(
                    SelectedAccountName
                )
            )
            {
                throw new InvalidOperationException(
                    "SelectedAccountName is required."
                );
            }

            Account match = null;
            int count = 0;

            foreach (Account account in Account.All)
            {
                if (
                    account != null
                    && string.Equals(
                        account.Name,
                        SelectedAccountName.Trim(),
                        StringComparison.Ordinal
                    )
                )
                {
                    match = account;
                    count++;
                }
            }

            if (
                count != 1
                || match == null
            )
            {
                throw new InvalidOperationException(
                    "Exactly one selected SIM account is required."
                );
            }

            if (
                match.Provider
                != Provider.Simulator
            )
            {
                throw new InvalidOperationException(
                    "Selected account is not Provider.Simulator."
                );
            }

            return match;
        }

        private void ValidateSelectedAccount()
        {
            if (selectedAccount == null)
            {
                throw new InvalidOperationException(
                    "Selected SIM account is unavailable."
                );
            }

            if (
                selectedAccount.Provider != Provider.Simulator
            )
            {
                throw new InvalidOperationException(
                    "Selected SIM account provider changed."
                );
            }

            if (
                !string.Equals(
                    selectedAccount.Name,
                    SelectedAccountName.Trim(),
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Selected SIM account identity changed."
                );
            }
        }

        private sealed class SubmitCommandEvidence
        {
            public string OperationId;
            public string ClientOrderId;
            public string Symbol;
            public string Side;
            public int Quantity;
            public string OrderType;
        }

        private void AttemptOneShotSubmit()
        {
            ValidateSelectedAccount();

            if (submitAttempted)
            {
                throw new InvalidOperationException(
                    "one-shot submit already attempted"
                );
            }

            // Latch before reading or touching native execution state.
            // No automatic retry is allowed after this point.
            submitAttempted = true;

            if (
                !string.Equals(
                    OperatorArmToken,
                    REQUIRED_ARM_TOKEN,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Explicit operator arm token is required."
                );
            }

            if (
                selectedAccount.Provider != Provider.Simulator
            )
            {
                throw new InvalidOperationException(
                    "Native submit requires Provider.Simulator."
                );
            }

            if (
                string.IsNullOrWhiteSpace(
                    CommandId
                )
            )
            {
                throw new InvalidOperationException(
                    "CommandId is required."
                );
            }

            ValidateSafeIdentity(
                CommandId.Trim(),
                "command_id"
            );

            SubmitCommandEvidence command =
                ReadSubmitCommand(
                    CommandId.Trim()
                );

            ValidateValidationResponse(
                CommandId.Trim(),
                command.OperationId,
                command.ClientOrderId
            );

            ValidateDirectory(
                NativeEvidenceDirectory,
                "NativeEvidenceDirectory"
            );

            activeCommandId = CommandId.Trim();
            activeOperationId = command.OperationId;
            activeClientOrderId = command.ClientOrderId;

            ReadActivationEvidence(
                CommandId.Trim(),
                command.OperationId,
                command.ClientOrderId
            );

            int quantity = command.Quantity;

            if (quantity != 1)
            {
                throw new InvalidOperationException(
                    "Only quantity 1 is allowed."
                );
            }

            string orderType =
                (command.OrderType ?? string.Empty)
                .Trim()
                .ToUpperInvariant();

            if (orderType != "MARKET")
            {
                throw new InvalidOperationException(
                    "Only MARKET is allowed."
                );
            }

            string side =
                (command.Side ?? string.Empty)
                .Trim()
                .ToUpperInvariant();

            OrderAction action;

            if (side == "BUY")
            {
                action = OrderAction.Buy;
            }
            else if (side == "SELL")
            {
                action = OrderAction.Sell;
            }
            else
            {
                throw new InvalidOperationException(
                    "Unsupported side."
                );
            }

            if (
                string.IsNullOrWhiteSpace(
                    command.Symbol
                )
            )
            {
                throw new InvalidOperationException(
                    "Durable command symbol is required."
                );
            }

            NinjaTrader.Cbi.Instrument instrument =
                NinjaTrader.Cbi.Instrument.GetInstrument(
                    command.Symbol.Trim(),
                    false
                );

            if (instrument == null)
            {
                throw new InvalidOperationException(
                    "Native instrument was not found."
                );
            }

            ValidateFlatPreflight(
                instrument
            );

            // R48T8 hard stop:
            // provenance, activation and account preflight may run,
            // but native order creation remains unreachable.
            if (!NATIVE_SUBMIT_ENABLED)
            {
                throw new InvalidOperationException(
                    "Native SIM submit remains disabled."
                );
            }

            ConsumeSubmitActivation();

            Order nativeOrder =
                selectedAccount.CreateOrder(
                    instrument,
                    action,
                    OrderType.Market,
                    TimeInForce.Day,
                    quantity,
                    0.0,
                    0.0,
                    string.Empty,
                    CommandId.Trim(),
                    null
                );

            if (nativeOrder == null)
            {
                throw new InvalidOperationException(
                    "Native order creation failed."
                );
            }

            Print(
                "ARMS_SIM_NATIVE_SUBMIT "
                + "status=SUBMIT_CALLED_AWAITING_ORDER_UPDATE "
                + "command_id="
                + CommandId.Trim()
                + " operation_id="
                + command.OperationId
                + " auto_retry_allowed="
                + AUTO_RETRY_ALLOWED
            );

            selectedAccount.Submit(
                new[] { nativeOrder }
            );
        }

        private void ReadActivationEvidence(
            string commandId,
            string operationId,
            string clientOrderId
        )
        {
            ValidateDirectory(
                ActivationDirectory,
                "ActivationDirectory"
            );

            string activationPath =
                Path.Combine(
                    Path.GetFullPath(
                        ActivationDirectory.Trim()
                    ),
                    CommandId.Trim() + ".arm.json"
                );

            if (!File.Exists(activationPath))
            {
                throw new InvalidOperationException(
                    "Activation evidence is required."
                );
            }

            string consumedPath =
                Path.Combine(
                    Path.GetFullPath(
                        ActivationDirectory.Trim()
                    ),
                    CommandId.Trim()
                    + ".arm.json.consumed"
                );

            if (File.Exists(consumedPath))
            {
                throw new InvalidOperationException(
                    "Submit activation evidence was already consumed."
                );
            }

            string json = ReadBoundedJsonFile(
                activationPath,
                "Activation evidence"
            );

            string activationCommandId =
                ExtractRequiredString(
                    json,
                    "command_id"
                );

            string activationOperationId =
                ExtractRequiredString(
                    json,
                    "operation_id"
                );

            string activationClientOrderId =
                ExtractRequiredString(
                    json,
                    "client_order_id"
                );

            string permit =
                ExtractRequiredString(
                    json,
                    "permit"
                );

            string account =
                ExtractRequiredString(
                    json,
                    "account"
                );

            if (
                activationCommandId != commandId
                || activationOperationId != operationId
                || activationClientOrderId != clientOrderId
            )
            {
                throw new InvalidOperationException(
                    "Activation command identity mismatch."
                );
            }

            if (
                permit != "ONE_SHOT_SIM101_V2"
            )
            {
                throw new InvalidOperationException(
                    "Activation permit is invalid."
                );
            }

            if (
                account != "Sim101"
                || selectedAccount == null
                || selectedAccount.Name != "Sim101"
            )
            {
                throw new InvalidOperationException(
                    "Activation account is invalid."
                );
            }

            validatedSubmitActivationPath =
                activationPath;
        }

        private void ConsumeSubmitActivation()
        {
            if (
                string.IsNullOrWhiteSpace(
                    validatedSubmitActivationPath
                )
            )
            {
                throw new InvalidOperationException(
                    "Validated submit activation is unavailable."
                );
            }

            string consumedPath =
                validatedSubmitActivationPath
                + ".consumed";

            byte[] marker =
                System.Text.Encoding.UTF8.GetBytes(
                    "consumed\n"
                );

            try
            {
                using (
                    FileStream stream =
                        new FileStream(
                            consumedPath,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.None
                        )
                )
                {
                    stream.Write(
                        marker,
                        0,
                        marker.Length
                    );

                    stream.Flush(true);
                }
            }
            catch (IOException)
            {
                if (File.Exists(consumedPath))
                {
                    throw new InvalidOperationException(
                        "Submit activation evidence was already consumed."
                    );
                }

                throw;
            }
        }

        private SubmitCommandEvidence ReadSubmitCommand(
            string commandId
        )
        {
            ValidateDirectory(
                CommandDirectory,
                "CommandDirectory"
            );

            string commandPath = Path.Combine(
                Path.GetFullPath(
                    CommandDirectory.Trim()
                ),
                CommandId.Trim() + ".json"
            );

            if (!File.Exists(commandPath))
            {
                throw new InvalidOperationException(
                    "Durable command is required."
                );
            }

            string json = ReadBoundedJsonFile(
                commandPath,
                "Durable command"
            );

            string fileCommandId =
                ExtractRequiredString(
                    json,
                    "command_id"
                );

            string operationId =
                ExtractRequiredString(
                    json,
                    "operation_id"
                );

            string clientOrderId =
                ExtractRequiredString(
                    json,
                    "client_order_id"
                );

            string commandType =
                ExtractRequiredString(
                    json,
                    "command"
                );

            if (
                !string.Equals(
                    fileCommandId,
                    commandId,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Durable command identity mismatch."
                );
            }

            if (operationId != clientOrderId)
            {
                throw new InvalidOperationException(
                    "Durable command identity mismatch."
                );
            }

            if (
                !string.Equals(
                    commandType,
                    "SUBMIT_ORDER",
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Unsupported durable command."
                );
            }

            string symbol =
                ExtractRequiredString(
                    json,
                    "symbol"
                );

            string side =
                ExtractRequiredString(
                    json,
                    "side"
                );

            int quantity =
                ExtractRequiredInteger(
                    json,
                    "quantity"
                );

            // The durable protocol currently represents submit as MARKET-only.
            string orderType = "MARKET";

            return new SubmitCommandEvidence
            {
                OperationId = operationId,
                ClientOrderId = clientOrderId,
                Symbol = symbol,
                Side = side,
                Quantity = quantity,
                OrderType = orderType,
            };
        }

        private void ValidateValidationResponse(
            string commandId,
            string operationId,
            string clientOrderId
        )
        {
            ValidateDirectory(
                ValidationResponseDirectory,
                "ValidationResponseDirectory"
            );

            string responsePath = Path.Combine(
                Path.GetFullPath(
                    ValidationResponseDirectory.Trim()
                ),
                commandId + ".json"
            );

            if (!File.Exists(responsePath))
            {
                throw new InvalidOperationException(
                    "Validation response is required."
                );
            }

            string json = ReadBoundedJsonFile(
                responsePath,
                "Validation response"
            );

            string responseCommandId =
                ExtractRequiredString(
                    json,
                    "command_id"
                );

            string responseOperationId =
                ExtractRequiredString(
                    json,
                    "operation_id"
                );

            string responseClientOrderId =
                ExtractRequiredString(
                    json,
                    "client_order_id"
                );

            string status =
                ExtractRequiredString(
                    json,
                    "status"
                );

            string simExecutionAuthority =
                ExtractRequiredString(
                    json,
                    "sim_execution_authority"
                );

            bool externalOrderAuthority =
                ExtractRequiredBoolean(
                    json,
                    "external_order_authority"
                );

            if (
                responseCommandId != commandId
                || responseOperationId != operationId
                || responseClientOrderId != clientOrderId
            )
            {
                throw new InvalidOperationException(
                    "Validation response identity mismatch."
                );
            }

            if (
                status != "VALIDATED_NO_EXECUTION"
            )
            {
                throw new InvalidOperationException(
                    "Validation response status is invalid."
                );
            }

            if (
                simExecutionAuthority != "DISABLED"
                || externalOrderAuthority
            )
            {
                throw new InvalidOperationException(
                    "Validation response authority is invalid."
                );
            }
        }

        private static void ValidateDirectory(
            string directory,
            string field
        )
        {
            if (string.IsNullOrWhiteSpace(directory))
            {
                throw new InvalidOperationException(
                    field + " is required."
                );
            }

            string fullPath =
                Path.GetFullPath(
                    directory.Trim()
                );

            if (!Path.IsPathRooted(fullPath))
            {
                throw new InvalidOperationException(
                    field + " must be absolute."
                );
            }

            if (!Directory.Exists(fullPath))
            {
                throw new InvalidOperationException(
                    field + " does not exist."
                );
            }
        }

        private static string ReadBoundedJsonFile(
            string path,
            string label
        )
        {
            FileInfo info = new FileInfo(path);

            if (
                !info.Exists
                || info.Length <= 0
                || info.Length > 1024 * 1024
            )
            {
                throw new InvalidOperationException(
                    label + " file size is invalid."
                );
            }

            using (
                FileStream stream = new FileStream(
                    path,
                    FileMode.Open,
                    FileAccess.Read,
                    FileShare.Read
                )
            )
            using (
                StreamReader reader =
                    new StreamReader(stream)
            )
            {
                return reader.ReadToEnd();
            }
        }

        private static string ExtractRequiredString(
            string json,
            string propertyName
        )
        {
            MatchCollection matches =
                Regex.Matches(
                    json,
                    "\""
                    + Regex.Escape(propertyName)
                    + "\"\\s*:\\s*\"(?<value>(?:\\\\.|[^\"])*)\"",
                    RegexOptions.CultureInvariant
                );

            if (matches.Count != 1)
            {
                throw new InvalidOperationException(
                    "Required durable property is missing or duplicated."
                );
            }

            string value =
                Regex.Unescape(
                    matches[0]
                    .Groups["value"]
                    .Value
                );

            if (string.IsNullOrWhiteSpace(value))
            {
                throw new InvalidOperationException(
                    "Required durable property is empty."
                );
            }

            return value;
        }

        private static int ExtractRequiredInteger(
            string json,
            string propertyName
        )
        {
            MatchCollection matches =
                Regex.Matches(
                    json,
                    "\""
                    + Regex.Escape(propertyName)
                    + "\"\\s*:\\s*(?<value>-?[0-9]+)",
                    RegexOptions.CultureInvariant
                );

            if (matches.Count != 1)
            {
                throw new InvalidOperationException(
                    "Required integer property is missing or duplicated."
                );
            }

            int value;

            if (
                !int.TryParse(
                    matches[0]
                    .Groups["value"]
                    .Value,
                    out value
                )
            )
            {
                throw new InvalidOperationException(
                    "Required integer property is invalid."
                );
            }

            return value;
        }

        private static bool ExtractRequiredBoolean(
            string json,
            string propertyName
        )
        {
            MatchCollection matches =
                Regex.Matches(
                    json,
                    "\""
                    + Regex.Escape(propertyName)
                    + "\"\\s*:\\s*(?<value>true|false)",
                    RegexOptions.CultureInvariant
                    | RegexOptions.IgnoreCase
                );

            if (matches.Count != 1)
            {
                throw new InvalidOperationException(
                    "Required boolean property is missing or duplicated."
                );
            }

            return string.Equals(
                matches[0]
                .Groups["value"]
                .Value,
                "true",
                StringComparison.OrdinalIgnoreCase
            );
        }

        private static void ValidateSafeIdentity(
            string value,
            string field
        )
        {
            if (
                string.IsNullOrWhiteSpace(value)
                || !Regex.IsMatch(
                    value,
                    @"\A[A-Za-z0-9._-]+\z",
                    RegexOptions.CultureInvariant
                )
            )
            {
                throw new InvalidOperationException(
                    field + " is invalid."
                );
            }
        }

        private string ReadEmergencyActivationScalar(
            string json,
            string key
        )
        {
            string pattern =
                "\"" + Regex.Escape(key)
                + "\"\\s*:\\s*\"([^\"\\\\]*)\"";

            MatchCollection matches =
                Regex.Matches(
                    json,
                    pattern,
                    RegexOptions.CultureInvariant
                );

            if (matches.Count != 1)
            {
                throw new InvalidOperationException(
                    "Emergency activation field is missing or duplicated: "
                    + key
                );
            }

            return matches[0].Groups[1].Value;
        }

        private void ReadEmergencyFlattenActivation(
            NinjaTrader.Cbi.Instrument instrument
        )
        {
            if (instrument == null)
            {
                throw new InvalidOperationException(
                    "Emergency activation instrument is required."
                );
            }

            if (
                string.IsNullOrWhiteSpace(
                    EmergencyActivationDirectory
                )
            )
            {
                throw new InvalidOperationException(
                    "EmergencyActivationDirectory is required."
                );
            }

            string directory =
                Path.GetFullPath(
                    EmergencyActivationDirectory.Trim()
                );

            if (
                !Path.IsPathRooted(directory)
                || !Directory.Exists(directory)
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation directory is invalid."
                );
            }

            if (
                string.IsNullOrWhiteSpace(
                    EmergencyActivationId
                )
            )
            {
                throw new InvalidOperationException(
                    "EmergencyActivationId is required."
                );
            }

            string activationId =
                EmergencyActivationId.Trim();

            if (
                !Regex.IsMatch(
                    activationId,
                    "^[A-Za-z0-9._-]+$",
                    RegexOptions.CultureInvariant
                )
            )
            {
                throw new InvalidOperationException(
                    "EmergencyActivationId is invalid."
                );
            }

            string activationPath =
                Path.Combine(
                    directory,
                    activationId
                    + ".flatten.arm.json"
                );

            if (!File.Exists(activationPath))
            {
                throw new InvalidOperationException(
                    "Emergency flatten activation evidence is required."
                );
            }

            FileInfo info =
                new FileInfo(
                    activationPath
                );

            if (
                info.Length <= 0
                || info.Length > 1024 * 1024
            )
            {
                throw new InvalidOperationException(
                    "Emergency flatten activation evidence size is invalid."
                );
            }

            string json =
                File.ReadAllText(
                    activationPath,
                    Encoding.UTF8
                );

            string evidenceActivationId =
                ReadEmergencyActivationScalar(
                    json,
                    "activation_id"
                );

            string permit =
                ReadEmergencyActivationScalar(
                    json,
                    "permit"
                );

            string account =
                ReadEmergencyActivationScalar(
                    json,
                    "account"
                );

            string evidenceInstrument =
                ReadEmergencyActivationScalar(
                    json,
                    "instrument"
                );

            string createdUtcText =
                ReadEmergencyActivationScalar(
                    json,
                    "created_utc"
                );

            string nonce =
                ReadEmergencyActivationScalar(
                    json,
                    "nonce"
                );

            if (
                string.IsNullOrWhiteSpace(nonce)
                || !Regex.IsMatch(
                    nonce,
                    "^[A-Za-z0-9._-]+$",
                    RegexOptions.CultureInvariant
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation nonce is invalid."
                );
            }

            DateTimeOffset createdUtc;

            if (
                !DateTimeOffset.TryParse(
                    createdUtcText,
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal
                    | DateTimeStyles.AdjustToUniversal,
                    out createdUtc
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation timestamp is invalid."
                );
            }

            DateTimeOffset nowUtc =
                DateTimeOffset.UtcNow;

            if (
                createdUtc
                > nowUtc.AddSeconds(
                    EMERGENCY_ACTIVATION_FUTURE_TOLERANCE_SECONDS
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation timestamp is in the future."
                );
            }

            if (
                nowUtc - createdUtc
                > TimeSpan.FromSeconds(
                    EMERGENCY_ACTIVATION_MAX_AGE_SECONDS
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation evidence expired."
                );
            }

            string consumedPath =
                activationPath
                + "."
                + nonce
                + ".consumed";

            if (File.Exists(consumedPath))
            {
                throw new InvalidOperationException(
                    "Emergency activation evidence was already consumed."
                );
            }

            if (
                !string.Equals(
                    evidenceActivationId,
                    activationId,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation identity mismatch."
                );
            }

            if (
                !string.Equals(
                    permit,
                    EMERGENCY_FLATTEN_DURABLE_PERMIT,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency flatten durable permit is invalid."
                );
            }

            if (
                !string.Equals(
                    account,
                    "Sim101",
                    StringComparison.Ordinal
                )
                || !string.Equals(
                    selectedAccount.Name,
                    "Sim101",
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation account mismatch."
                );
            }

            if (
                !string.Equals(
                    evidenceInstrument,
                    InstrumentName.Trim(),
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency activation instrument mismatch."
                );
            }

            validatedEmergencyActivationPath =
                activationPath;

            validatedEmergencyActivationNonce =
                nonce;
        }

        private void ConsumeEmergencyFlattenActivation()
        {
            if (
                string.IsNullOrWhiteSpace(
                    validatedEmergencyActivationPath
                )
                || string.IsNullOrWhiteSpace(
                    validatedEmergencyActivationNonce
                )
            )
            {
                throw new InvalidOperationException(
                    "Validated emergency activation is unavailable."
                );
            }

            string consumedPath =
                validatedEmergencyActivationPath
                + "."
                + validatedEmergencyActivationNonce
                + ".consumed";

            try
            {
                using (
                    FileStream stream =
                        new FileStream(
                            consumedPath,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.None
                        )
                )
                using (
                    StreamWriter writer =
                        new StreamWriter(
                            stream,
                            new UTF8Encoding(false)
                        )
                )
                {
                    writer.Write(
                        "consumed"
                    );

                    writer.Flush();
                    stream.Flush(true);
                }
            }
            catch (IOException)
            {
                if (File.Exists(consumedPath))
                {
                    throw new InvalidOperationException(
                        "Emergency activation evidence was already consumed."
                    );
                }

                throw;
            }
        }

        private string ResolveNextPhysicalTestSessionWindow(
            TradingHours tradingHours,
            DateTime nowLocal
        )
        {
            if (tradingHours == null)
            {
                return
                    " next_session_begin=NEXT_SESSION_UNKNOWN"
                    + " next_session_end=NEXT_SESSION_UNKNOWN";
            }

            for (
                int dayOffset = 0;
                dayOffset <= 7;
                dayOffset++
            )
            {
                DateTime candidateDay =
                    nowLocal.AddDays(
                        dayOffset
                    );

                SessionIterator candidateIterator =
                    new SessionIterator(
                        tradingHours
                    );

                bool found =
                    false;

                try
                {
                    found =
                        candidateIterator.GetNextSession(
                            candidateDay,
                            false
                        );
                }
                catch
                {
                    found = false;
                }

                if (!found)
                    continue;

                DateTime begin =
                    candidateIterator.ActualSessionBegin;

                DateTime end =
                    candidateIterator.ActualSessionEnd;

                return
                    " next_session_begin="
                    + begin.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    )
                    + " next_session_end="
                    + end.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    );
            }

            return
                " next_session_begin=NEXT_SESSION_UNKNOWN"
                + " next_session_end=NEXT_SESSION_UNKNOWN";
        }

        private void PrintNextSessionSearchDiagnostics(
            TradingHours tradingHours,
            DateTime nowLocal
        )
        {
            if (tradingHours == null)
                return;

            for (
                int dayOffset = 0;
                dayOffset <= 3;
                dayOffset++
            )
            {
                DateTime candidateDay =
                    nowLocal.AddDays(
                        dayOffset
                    );

                SessionIterator candidateIterator =
                    new SessionIterator(
                        tradingHours
                    );

                bool found =
                    false;

                string begin =
                    "SESSION_WINDOW_UNKNOWN";

                string end =
                    "SESSION_WINDOW_UNKNOWN";

                try
                {
                    found =
                        candidateIterator.GetNextSession(
                            candidateDay,
                            false
                        );

                    if (found)
                    {
                        begin =
                            candidateIterator.ActualSessionBegin.ToString(
                                "o",
                                CultureInfo.InvariantCulture
                            );

                        end =
                            candidateIterator.ActualSessionEnd.ToString(
                                "o",
                                CultureInfo.InvariantCulture
                            );
                    }
                }
                catch
                {
                    found = false;
                }

                Print(
                    "ARMS_SIM_NEXT_SESSION_SEARCH"
                    + " day_offset="
                    + dayOffset
                    + " candidate="
                    + candidateDay.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    )
                    + " found="
                    + found
                    + " begin="
                    + begin
                    + " end="
                    + end
                );
            }
        }

        private string DescribePhysicalTestSessionWindow(
            NinjaTrader.Cbi.Instrument instrument
        )
        {
            try
            {
                if (
                    instrument == null
                    || instrument.MasterInstrument == null
                    || instrument.MasterInstrument.TradingHours == null
                )
                {
                    Print(
                        "ARMS_SIM_SESSION_WINDOW_DIAGNOSTIC"
                        + " trading_hours=UNKNOWN"
                        + " timezone=UNKNOWN"
                        + " now_local="
                        + DateTime.Now.ToString(
                            "o",
                            CultureInfo.InvariantCulture
                        )
                        + " is_in_session=UNKNOWN"
                        + " next_session_found=False"
                        + " actual_begin=SESSION_WINDOW_UNKNOWN"
                        + " actual_end=SESSION_WINDOW_UNKNOWN"
                    );

                    return
                        " session_begin=SESSION_WINDOW_UNKNOWN"
                        + " session_end=SESSION_WINDOW_UNKNOWN";
                }

                TradingHours tradingHours =
                    instrument.MasterInstrument.TradingHours;

                SessionIterator sessionIterator =
                    new SessionIterator(
                        tradingHours
                    );

                DateTime nowLocal =
                    DateTime.Now;

                PrintNextSessionSearchDiagnostics(
                    tradingHours,
                    nowLocal
                );

                bool isInSession =
                    sessionIterator.IsInSession(
                        nowLocal,
                        false,
                        true
                    );

                bool found =
                    sessionIterator.GetNextSession(
                        nowLocal,
                        false
                    );

                string actualBegin =
                    "SESSION_WINDOW_UNKNOWN";

                string actualEnd =
                    "SESSION_WINDOW_UNKNOWN";

                if (found)
                {
                    actualBegin =
                        sessionIterator.ActualSessionBegin.ToString(
                            "o",
                            CultureInfo.InvariantCulture
                        );

                    actualEnd =
                        sessionIterator.ActualSessionEnd.ToString(
                            "o",
                            CultureInfo.InvariantCulture
                        );
                }

                Print(
                    "ARMS_SIM_SESSION_WINDOW_DIAGNOSTIC"
                    + " trading_hours="
                    + tradingHours.Name
                    + " timezone="
                    + tradingHours.TimeZone
                    + " now_local="
                    + nowLocal.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    )
                    + " is_in_session="
                    + isInSession
                    + " next_session_found="
                    + found
                    + " actual_begin="
                    + actualBegin
                    + " actual_end="
                    + actualEnd
                );

                if (!found)
                {
                    return
                        " session_begin=SESSION_WINDOW_UNKNOWN"
                        + " session_end=SESSION_WINDOW_UNKNOWN";
                }

                return
                    " session_begin="
                    + actualBegin
                    + " session_end="
                    + actualEnd;
            }
            catch (Exception ex)
            {
                Print(
                    "ARMS_SIM_SESSION_WINDOW_DIAGNOSTIC"
                    + " trading_hours=UNKNOWN"
                    + " timezone=UNKNOWN"
                    + " now_local="
                    + DateTime.Now.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    )
                    + " is_in_session=UNKNOWN"
                    + " next_session_found=False"
                    + " actual_begin=SESSION_WINDOW_UNKNOWN"
                    + " actual_end=SESSION_WINDOW_UNKNOWN"
                    + " error="
                    + ex.GetType().Name
                );

                return
                    " session_begin=SESSION_WINDOW_UNKNOWN"
                    + " session_end=SESSION_WINDOW_UNKNOWN";
            }
        }

        private void WriteRuntimeReadinessSnapshot()
        {
            // Snapshot emission is optional until an operator provides
            // an explicit local directory. No broker mutation occurs.
            if (
                string.IsNullOrWhiteSpace(
                    RuntimeSnapshotDirectory
                )
            )
            {
                return;
            }

            ValidateDirectory(
                RuntimeSnapshotDirectory,
                "RuntimeSnapshotDirectory"
            );

            ValidateSelectedAccount();

            string accountName =
                selectedAccount.Name ?? string.Empty;

            if (accountName != "Sim101")
            {
                throw new InvalidOperationException(
                    "Runtime snapshot requires Sim101."
                );
            }

            if (
                selectedAccount.Provider
                != Provider.Simulator
            )
            {
                throw new InvalidOperationException(
                    "Runtime snapshot requires Provider.Simulator."
                );
            }

            string instrumentName =
                string.IsNullOrWhiteSpace(
                    InstrumentName
                )
                ? string.Empty
                : InstrumentName.Trim();

            NinjaTrader.Cbi.Instrument instrument =
                NinjaTrader.Cbi.Instrument.GetInstrument(
                    instrumentName,
                    true
                );

            if (instrument == null)
            {
                throw new InvalidOperationException(
                    "Runtime snapshot instrument was not found."
                );
            }

            string readiness =
                EvaluatePhysicalTestReadiness(
                    instrument
                );

            string positionState = "FLAT";
            int matchingPositionCount = 0;

            foreach (
                Position position
                in selectedAccount.Positions
            )
            {
                if (
                    position == null
                    || position.Instrument == null
                    || !ReferenceEquals(
                        position.Instrument,
                        instrument
                    )
                )
                {
                    continue;
                }

                matchingPositionCount++;

                if (
                    position.MarketPosition
                    != MarketPosition.Flat
                )
                {
                    string observedPosition =
                        position.MarketPosition
                        .ToString()
                        .Trim()
                        .ToUpperInvariant();

                    if (
                        positionState != "FLAT"
                        && positionState
                            != observedPosition
                    )
                    {
                        positionState =
                            "UNKNOWN";
                    }
                    else
                    {
                        positionState =
                            observedPosition;
                    }
                }
            }

            if (matchingPositionCount > 1)
            {
                // Multiple native rows for the target instrument are
                // treated as ambiguous rather than assumed safe.
                positionState = "UNKNOWN";
            }

            int activeOrderCount = 0;

            foreach (
                Order order
                in selectedAccount.Orders
            )
            {
                if (
                    order == null
                    || order.Instrument == null
                    || !ReferenceEquals(
                        order.Instrument,
                        instrument
                    )
                )
                {
                    continue;
                }

                OrderState state =
                    order.OrderState;

                bool terminal =
                    state == OrderState.Cancelled
                    || state == OrderState.Filled
                    || state == OrderState.Rejected;

                if (!terminal)
                {
                    activeOrderCount++;
                }
            }

            string json =
                "{"
                + "\"schema\":\"arms.nt.sim-runtime-readiness.v2\","
                + "\"observed_at\":\""
                + EscapeJson(
                    DateTime.UtcNow.ToString(
                        "o",
                        CultureInfo.InvariantCulture
                    )
                )
                + "\","
                + "\"account_name\":\""
                + EscapeJson(accountName)
                + "\","
                + "\"provider\":\""
                + EscapeJson(
                    selectedAccount.Provider.ToString()
                )
                + "\","
                + "\"connection_status\":\""
                + EscapeJson(
                    selectedAccount.ConnectionStatus.ToString()
                )
                + "\","
                + "\"instrument\":\""
                + EscapeJson(instrumentName)
                + "\","
                + "\"physical_test_readiness\":\""
                + EscapeJson(readiness)
                + "\","
                + "\"position_state\":\""
                + EscapeJson(positionState)
                + "\","
                + "\"active_order_count\":"
                + activeOrderCount.ToString(
                    CultureInfo.InvariantCulture
                )
                + ","
                + "\"native_submit_enabled\":"
                + (
                    NATIVE_SUBMIT_ENABLED
                    ? "true"
                    : "false"
                )
                + ","
                + "\"auto_retry_allowed\":"
                + (
                    AUTO_RETRY_ALLOWED
                    ? "true"
                    : "false"
                )
                + "}\n";

            string directory =
                Path.GetFullPath(
                    RuntimeSnapshotDirectory.Trim()
                );

            string snapshotPath =
                Path.Combine(
                    directory,
                    "sim-native-runtime-snapshot-v2.json"
                );

            string temporaryPath =
                snapshotPath
                + "."
                + Guid.NewGuid().ToString("N")
                + ".tmp";

            byte[] payload =
                new UTF8Encoding(false).GetBytes(
                    json
                );

            try
            {
                using (
                    FileStream stream =
                        new FileStream(
                            temporaryPath,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.None
                        )
                )
                {
                    stream.Write(
                        payload,
                        0,
                        payload.Length
                    );

                    stream.Flush(true);
                }

                if (File.Exists(snapshotPath))
                {
                    File.Replace(
                        temporaryPath,
                        snapshotPath,
                        null
                    );
                }
                else
                {
                    File.Move(
                        temporaryPath,
                        snapshotPath
                    );
                }
            }
            finally
            {
                if (File.Exists(temporaryPath))
                {
                    File.Delete(
                        temporaryPath
                    );
                }
            }
        }

        private string EvaluatePhysicalTestReadiness(
            NinjaTrader.Cbi.Instrument instrument
        )
        {
            try
            {
                ValidateSelectedAccount();

                if (
                    selectedAccount.ConnectionStatus
                    != ConnectionStatus.Connected
                )
                {
                    return "CONNECTION_NOT_READY";
                }

                if (
                    instrument == null
                    || instrument.MasterInstrument == null
                    || instrument.MasterInstrument.TradingHours == null
                )
                {
                    return "SESSION_STATE_UNKNOWN";
                }

                TradingHours tradingHours =
                    instrument.MasterInstrument.TradingHours;

                SessionIterator sessionIterator =
                    new SessionIterator(
                        tradingHours
                    );

                DateTime nowLocal =
                    DateTime.Now;

                bool isInSession =
                    sessionIterator.IsInSession(
                        nowLocal,
                        false,
                        true
                    );

                if (!isInSession)
                {
                    return "MARKET_SESSION_CLOSED";
                }

                return "PHYSICAL_TEST_READY";
            }
            catch
            {
                return "SESSION_STATE_UNKNOWN";
            }
        }

        private void AttemptEmergencyFlatten()
        {
            ValidateSelectedAccount();

            if (!RequestEmergencyFlatten)
            {
                throw new InvalidOperationException(
                    "Emergency flatten was not explicitly requested."
                );
            }

            if (emergencyFlattenAttempted)
            {
                throw new InvalidOperationException(
                    "emergency flatten already attempted"
                );
            }

            if (
                !string.Equals(
                    EmergencyFlattenArmToken,
                    EMERGENCY_FLATTEN_ARM_TOKEN,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Explicit emergency flatten arm token is required."
                );
            }

            if (
                selectedAccount.Provider
                != Provider.Simulator
            )
            {
                throw new InvalidOperationException(
                    "Emergency flatten requires Provider.Simulator."
                );
            }

            if (
                !string.Equals(
                    selectedAccount.Name,
                    "Sim101",
                    StringComparison.Ordinal
                )
                || !string.Equals(
                    SelectedAccountName,
                    "Sim101",
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency flatten is restricted to Sim101."
                );
            }

            if (
                string.IsNullOrWhiteSpace(
                    InstrumentName
                )
            )
            {
                throw new InvalidOperationException(
                    "Emergency flatten instrument is required."
                );
            }

            NinjaTrader.Cbi.Instrument instrument =
                NinjaTrader.Cbi.Instrument.GetInstrument(
                    InstrumentName.Trim(),
                    true
                );

            if (instrument == null)
            {
                throw new InvalidOperationException(
                    "Emergency flatten instrument was not found."
                );
            }

            ReadEmergencyFlattenActivation(
                instrument
            );

            List<Order> activeOrders =
                new List<Order>();

            foreach (
                Order order
                in selectedAccount.Orders
            )
            {
                if (
                    order == null
                    || order.Instrument == null
                    || !ReferenceEquals(
                        order.Instrument,
                        instrument
                    )
                )
                    continue;

                OrderState state =
                    order.OrderState;

                bool terminal =
                    state == OrderState.Cancelled
                    || state == OrderState.Filled
                    || state == OrderState.Rejected;

                if (!terminal)
                    activeOrders.Add(order);
            }

            int nonFlatPositions = 0;

            foreach (
                Position position
                in selectedAccount.Positions
            )
            {
                if (
                    position == null
                    || position.Instrument == null
                    || !ReferenceEquals(
                        position.Instrument,
                        instrument
                    )
                )
                    continue;

                if (
                    position.MarketPosition
                    != MarketPosition.Flat
                )
                {
                    nonFlatPositions++;
                }
            }

            if (nonFlatPositions > 1)
            {
                throw new InvalidOperationException(
                    "Target instrument position state is ambiguous."
                );
            }

            bool targetAlreadyFlat =
                nonFlatPositions == 0;

            if (targetAlreadyFlat)
            {
                Print(
                    "Target instrument already flat."
                );

                Print(
                    "ARMS_SIM_EMERGENCY_ALREADY_FLAT_NO_MUTATION "
                    + "instrument="
                    + InstrumentName.Trim()
                );
            }

            // One-shot latch is set before any native mutation.
            // No automatic retry is allowed after this point.
            emergencyFlattenAttempted = true;

            ConsumeEmergencyFlattenActivation();

            // R48U hard stop:
            // account/order/position state may be inspected,
            // but Cancel/Flatten remain unreachable.
            if (!NATIVE_EMERGENCY_FLATTEN_ENABLED)
            {
                throw new InvalidOperationException(
                    "Native SIM emergency flatten remains disabled."
                );
            }

            if (activeOrders.Count > 0)
            {
                Print(
                    "ARMS_SIM_EMERGENCY_CANCEL_CALL "
                    + "instrument="
                    + InstrumentName.Trim()
                    + " count="
                    + activeOrders.Count
                );

                selectedAccount.Cancel(
                    activeOrders
                );
            }

            if (targetAlreadyFlat)
                return;

            emergencyFlattenInstrumentName =
                InstrumentName.Trim();

            emergencyFlattenAwaitingConfirmation =
                true;

            Print(
                "ARMS_SIM_EMERGENCY_FLATTEN_PENDING_CONFIRMATION "
                + "instrument="
                + emergencyFlattenInstrumentName
            );

            Print(
                "ARMS_SIM_EMERGENCY_FLATTEN_CALL "
                + "instrument="
                + emergencyFlattenInstrumentName
            );

            selectedAccount.Flatten(
                new List<NinjaTrader.Cbi.Instrument>
                {
                    instrument
                }
            );
        }

        private void ValidateFlatPreflight(
            NinjaTrader.Cbi.Instrument instrument
        )
        {
            if (instrument == null)
            {
                throw new InvalidOperationException(
                    "Target instrument is required."
                );
            }

            ValidateSelectedAccount();

            foreach (
                Position position
                in selectedAccount.Positions
            )
            {
                if (
                    position == null
                    || position.Instrument == null
                    || !ReferenceEquals(
                        position.Instrument,
                        instrument
                    )
                )
                    continue;

                if (
                    position.MarketPosition
                    != MarketPosition.Flat
                )
                {
                    throw new InvalidOperationException(
                        "Target instrument is not flat."
                    );
                }
            }

            foreach (
                Order order
                in selectedAccount.Orders
            )
            {
                if (
                    order == null
                    || order.Instrument == null
                    || !ReferenceEquals(
                        order.Instrument,
                        instrument
                    )
                )
                    continue;

                OrderState state =
                    order.OrderState;

                bool terminal =
                    state == OrderState.Cancelled
                    || state == OrderState.Filled
                    || state == OrderState.Rejected;

                if (!terminal)
                {
                    throw new InvalidOperationException(
                        "Target instrument has active native order."
                    );
                }
            }
        }

        private bool HasActiveDurableIdentity()
        {
            return
                !string.IsNullOrWhiteSpace(activeCommandId)
                && !string.IsNullOrWhiteSpace(activeOperationId)
                && !string.IsNullOrWhiteSpace(activeClientOrderId);
        }

        private void WriteOrderEvidence(
            string orderId,
            OrderState orderState,
            int quantity,
            int filled,
            double averageFillPrice
        )
        {
            if (!HasActiveDurableIdentity())
                return;

            string safeOrderId =
                SafeFileComponent(
                    string.IsNullOrWhiteSpace(orderId)
                    ? "pending"
                    : orderId
                );

            string fileName =
                activeCommandId
                + ".order."
                + safeOrderId
                + "."
                + orderState
                + "."
                + filled
                + ".json";

            string json =
                "{"
                + "\"event_type\":\"ORDER_UPDATE\","
                + "\"command_id\":\""
                + EscapeJson(activeCommandId)
                + "\","
                + "\"operation_id\":\""
                + EscapeJson(activeOperationId)
                + "\","
                + "\"client_order_id\":\""
                + EscapeJson(activeClientOrderId)
                + "\","
                + "\"order_id\":\""
                + EscapeJson(orderId ?? string.Empty)
                + "\","
                + "\"order_state\":\""
                + EscapeJson(orderState.ToString())
                + "\","
                + "\"quantity\":"
                + quantity
                + ","
                + "\"filled\":"
                + filled
                + ","
                + "\"average_fill_price\":"
                + averageFillPrice.ToString(
                    System.Globalization.CultureInfo.InvariantCulture
                )
                + "}\n";

            WriteNativeEvidence(
                fileName,
                json
            );
        }

        private void WriteExecutionEvidence(
            string executionId,
            string orderId,
            int quantity,
            double price
        )
        {
            if (!HasActiveDurableIdentity())
                return;

            string safeExecutionId =
                SafeFileComponent(
                    string.IsNullOrWhiteSpace(executionId)
                    ? "unknown"
                    : executionId
                );

            string fileName =
                activeCommandId
                + ".execution."
                + safeExecutionId
                + ".json";

            string json =
                "{"
                + "\"event_type\":\"EXECUTION_UPDATE\","
                + "\"command_id\":\""
                + EscapeJson(activeCommandId)
                + "\","
                + "\"operation_id\":\""
                + EscapeJson(activeOperationId)
                + "\","
                + "\"client_order_id\":\""
                + EscapeJson(activeClientOrderId)
                + "\","
                + "\"execution_id\":\""
                + EscapeJson(executionId ?? string.Empty)
                + "\","
                + "\"order_id\":\""
                + EscapeJson(orderId ?? string.Empty)
                + "\","
                + "\"quantity\":"
                + quantity
                + ","
                + "\"price\":"
                + price.ToString(
                    System.Globalization.CultureInfo.InvariantCulture
                )
                + "}\n";

            WriteNativeEvidence(
                fileName,
                json
            );
        }

        private void WriteNativeEvidence(
            string fileName,
            string json
        )
        {
            ValidateDirectory(
                NativeEvidenceDirectory,
                "NativeEvidenceDirectory"
            );

            string evidencePath =
                Path.Combine(
                    Path.GetFullPath(
                        NativeEvidenceDirectory.Trim()
                    ),
                    fileName
                );

            byte[] payload =
                new UTF8Encoding(false).GetBytes(
                    json
                );

            try
            {
                using (
                    FileStream stream =
                        new FileStream(
                            evidencePath,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.Read
                        )
                )
                {
                    stream.Write(
                        payload,
                        0,
                        payload.Length
                    );

                    stream.Flush(true);
                }
            }
            catch (IOException)
            {
                if (!File.Exists(evidencePath))
                    throw;

                byte[] existing =
                    File.ReadAllBytes(
                        evidencePath
                    );

                if (BytesEqual(existing, payload))
                    return;

                throw new InvalidOperationException(
                    "native evidence collision."
                );
            }
        }

        private static string SafeFileComponent(
            string value
        )
        {
            if (string.IsNullOrWhiteSpace(value))
                return "unknown";

            return Regex.Replace(
                value,
                @"[^A-Za-z0-9._-]",
                "_",
                RegexOptions.CultureInvariant
            );
        }

        private static string EscapeJson(
            string value
        )
        {
            if (value == null)
                return string.Empty;

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"");
        }

        private static bool BytesEqual(
            byte[] left,
            byte[] right
        )
        {
            if (
                left == null
                || right == null
                || left.Length != right.Length
            )
                return false;

            for (
                int index = 0;
                index < left.Length;
                index++
            )
            {
                if (left[index] != right[index])
                    return false;
            }

            return true;
        }

        private void OnNativePositionUpdate(
            object sender,
            PositionEventArgs e
        )
        {
            if (
                !emergencyFlattenAwaitingConfirmation
                || e == null
                || e.Position == null
                || e.Position.Instrument == null
                || string.IsNullOrWhiteSpace(
                    emergencyFlattenInstrumentName
                )
            )
                return;

            Position position =
                e.Position;

            string instrumentName =
                position.Instrument.FullName;

            if (
                !string.Equals(
                    instrumentName,
                    emergencyFlattenInstrumentName,
                    StringComparison.Ordinal
                )
            )
                return;

            if (
                position.MarketPosition
                != MarketPosition.Flat
            )
                return;

            emergencyFlattenAwaitingConfirmation = false;

            Print(
                "ARMS_SIM_EMERGENCY_FLATTEN_CONFIRMED "
                + "instrument="
                + emergencyFlattenInstrumentName
                + " market_position=Flat"
            );
        }

        private void OnNativeOrderUpdate(
            object sender,
            OrderEventArgs e
        )
        {
            ValidateSelectedAccount();

            if (
                e == null
                || e.Order == null
            )
                return;

            Order order = e.Order;

            if (
                order.Account == null
                || !ReferenceEquals(
                    order.Account,
                    selectedAccount
                )
            )
                return;

            string orderId =
                order.OrderId ?? string.Empty;

            OrderState orderState =
                order.OrderState;

            int quantity =
                order.Quantity;

            int filled =
                order.Filled;

            double averageFillPrice =
                order.AverageFillPrice;

            if (
                HasActiveDurableIdentity()
                && string.Equals(
                    order.Name,
                    activeCommandId,
                    StringComparison.Ordinal
                )
            )
            {
                WriteOrderEvidence(
                    orderId,
                    orderState,
                    quantity,
                    filled,
                    averageFillPrice
                );
            }

            Print(
                "ARMS_SIM_NATIVE_ORDER_UPDATE "
                + "order_id="
                + orderId
                + " state="
                + orderState
                + " quantity="
                + quantity
                + " filled="
                + filled
                + " average_fill_price="
                + averageFillPrice
                + " authority="
                + SIM_EXECUTION_AUTHORITY
                + " native_submit_enabled="
                + NATIVE_SUBMIT_ENABLED
            );
        }

        private void OnNativeExecutionUpdate(
            object sender,
            ExecutionEventArgs e
        )
        {
            ValidateSelectedAccount();

            if (
                e == null
                || e.Execution == null
            )
                return;

            Execution execution =
                e.Execution;

            if (
                execution.Account == null
                || !ReferenceEquals(
                    execution.Account,
                    selectedAccount
                )
            )
                return;

            string executionId =
                execution.ExecutionId
                ?? string.Empty;

            int quantity =
                execution.Quantity;

            double price =
                execution.Price;

            Order order =
                execution.Order;

            string orderId =
                order != null
                ? order.OrderId ?? string.Empty
                : string.Empty;

            if (
                HasActiveDurableIdentity()
                && order != null
                && string.Equals(
                    order.Name,
                    activeCommandId,
                    StringComparison.Ordinal
                )
            )
            {
                WriteExecutionEvidence(
                    executionId,
                    orderId,
                    quantity,
                    price
                );
            }

            Print(
                "ARMS_SIM_NATIVE_EXECUTION_UPDATE "
                + "execution_id="
                + executionId
                + " order_id="
                + orderId
                + " quantity="
                + quantity
                + " price="
                + price
                + " authority="
                + SIM_EXECUTION_AUTHORITY
                + " native_submit_enabled="
                + NATIVE_SUBMIT_ENABLED
            );
        }
    }
}
