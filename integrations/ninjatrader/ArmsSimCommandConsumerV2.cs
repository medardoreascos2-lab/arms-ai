using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsSimCommandConsumerV2 : Indicator
    {
        private const string SIM_EXECUTION_AUTHORITY = "DISABLED";
        private const bool EXTERNAL_ORDER_AUTHORITY = false;

        private const string VALIDATION_STATUS =
            "VALIDATED_NO_EXECUTION";

        private const string RESPONSE_STATUS_FIELD =
            "status";

        private const string RESPONSE_SIM_AUTHORITY_FIELD =
            "sim_execution_authority";

        private const string RESPONSE_EXTERNAL_AUTHORITY_FIELD =
            "external_order_authority";

        private readonly HashSet<string> validatedFiles =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        private DateTime nextScanUtc = DateTime.MinValue;
        private Account selectedAccount;

        [NinjaScriptProperty]
        [Display(
            Name = "CommandDirectory",
            Order = 1,
            GroupName = "ARMS SIM"
        )]
        public string CommandDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "ResponseDirectory",
            Order = 2,
            GroupName = "ARMS SIM"
        )]
        public string ResponseDirectory
        {
            get;
            set;
        }

        [NinjaScriptProperty]
        [Display(
            Name = "SelectedAccountName",
            Order = 3,
            GroupName = "ARMS SIM"
        )]
        public string SelectedAccountName
        {
            get;
            set;
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsSimCommandConsumerV2";
                Description =
                    "ARMS SIM command validation skeleton. "
                    + "Native execution is disabled.";

                Calculate = Calculate.OnEachTick;
                IsOverlay = true;

                CommandDirectory = string.Empty;
                ResponseDirectory = string.Empty;
                SelectedAccountName = "Sim101";
            }
            else if (State == State.DataLoaded)
            {
                selectedAccount = ResolveSelectedAccount();

                ValidateSelectedAccount();
                ValidateCommandDirectory();
                ValidateResponseDirectory();

                Print(
                    "ARMS_SIM_COMMAND_CONSUMER_START "
                    + "authority="
                    + SIM_EXECUTION_AUTHORITY
                    + " external_order_authority="
                    + EXTERNAL_ORDER_AUTHORITY
                );

                // Initial read-only scan does not depend on market ticks.
                ScanCommands();
            }
            else if (State == State.Terminated)
            {
                selectedAccount = null;
                validatedFiles.Clear();
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 0)
                return;

            DateTime now = DateTime.UtcNow;

            if (now < nextScanUtc)
                return;

            nextScanUtc = now.AddSeconds(1);

            ValidateSelectedAccount();
            ValidateCommandDirectory();
            ValidateResponseDirectory();
            ScanCommands();
        }

        private Account ResolveSelectedAccount()
        {
            if (string.IsNullOrWhiteSpace(SelectedAccountName))
                throw new InvalidOperationException(
                    "SelectedAccountName is required."
                );

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

            if (count != 1 || match == null)
                throw new InvalidOperationException(
                    "Exactly one selected SIM account is required."
                );

            if (match.Provider != Provider.Simulator)
                throw new InvalidOperationException(
                    "Selected account is not Provider.Simulator."
                );

            return match;
        }

        private void ValidateSelectedAccount()
        {
            if (selectedAccount == null)
                throw new InvalidOperationException(
                    "Selected SIM account is unavailable."
                );

            if (selectedAccount.Provider != Provider.Simulator)
                throw new InvalidOperationException(
                    "Selected SIM account provider changed."
                );

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

        private void ValidateCommandDirectory()
        {
            if (string.IsNullOrWhiteSpace(CommandDirectory))
                throw new InvalidOperationException(
                    "CommandDirectory is required."
                );

            string fullPath = Path.GetFullPath(
                CommandDirectory.Trim()
            );

            if (!Path.IsPathRooted(fullPath))
                throw new InvalidOperationException(
                    "CommandDirectory must be absolute."
                );

            if (!Directory.Exists(fullPath))
                throw new InvalidOperationException(
                    "CommandDirectory does not exist."
                );
        }

        private void ValidateResponseDirectory()
        {
            if (string.IsNullOrWhiteSpace(ResponseDirectory))
                throw new InvalidOperationException(
                    "ResponseDirectory is required."
                );

            string fullPath = Path.GetFullPath(
                ResponseDirectory.Trim()
            );

            if (!Path.IsPathRooted(fullPath))
                throw new InvalidOperationException(
                    "ResponseDirectory must be absolute."
                );

            if (!Directory.Exists(fullPath))
                throw new InvalidOperationException(
                    "ResponseDirectory does not exist."
                );
        }

        private void ScanCommands()
        {
            string directory = Path.GetFullPath(
                CommandDirectory.Trim()
            );

            string[] files = Directory.GetFiles(
                directory,
                "*.json",
                SearchOption.TopDirectoryOnly
            );

            Array.Sort(
                files,
                StringComparer.OrdinalIgnoreCase
            );

            foreach (string file in files)
            {
                if (validatedFiles.Contains(file))
                    continue;

                ValidateCommandFile(file);
                validatedFiles.Add(file);
            }
        }

        private void ValidateCommandFile(string file)
        {
            FileInfo info = new FileInfo(file);

            if (!info.Exists)
                throw new InvalidOperationException(
                    "Command file disappeared."
                );

            if (info.Length <= 0 || info.Length > 1024 * 1024)
                throw new InvalidOperationException(
                    "Command file size is invalid."
                );

            string json;

            using (
                FileStream stream = new FileStream(
                    file,
                    FileMode.Open,
                    FileAccess.Read,
                    FileShare.Read
                )
            )
            using (
                StreamReader reader = new StreamReader(stream)
            )
            {
                json = reader.ReadToEnd();
            }

            string commandId = ExtractRequiredString(
                json,
                "command_id"
            );

            string operationId = ExtractRequiredString(
                json,
                "operation_id"
            );

            string clientOrderId = ExtractRequiredString(
                json,
                "client_order_id"
            );

            string commandType = ExtractRequiredString(
                json,
                "command"
            );

            if (
                !string.Equals(
                    commandType,
                    "SUBMIT_ORDER",
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Unsupported SIM command type."
                );
            }

            if (
                !string.Equals(
                    operationId,
                    clientOrderId,
                    StringComparison.Ordinal
                )
            )
            {
                throw new InvalidOperationException(
                    "Durable SIM command identity mismatch."
                );
            }

            if (
                string.IsNullOrWhiteSpace(commandId)
                || string.IsNullOrWhiteSpace(operationId)
                || string.IsNullOrWhiteSpace(clientOrderId)
            )
            {
                throw new InvalidOperationException(
                    "SIM command identity is invalid."
                );
            }

            WriteValidationResponse(
                commandId,
                operationId,
                clientOrderId
            );

            Print(
                "ARMS_SIM_COMMAND_CONSUMER "
                + "status=VALIDATED_NO_EXECUTION "
                + "authority="
                + SIM_EXECUTION_AUTHORITY
                + " external_order_authority="
                + EXTERNAL_ORDER_AUTHORITY
                + " command_id="
                + commandId
            );
        }

        private void WriteValidationResponse(
            string commandId,
            string operationId,
            string clientOrderId
        )
        {
            ValidateSafeIdentity(
                commandId,
                "command_id"
            );

            ValidateSafeIdentity(
                operationId,
                "operation_id"
            );

            ValidateSafeIdentity(
                clientOrderId,
                "client_order_id"
            );

            string responseDirectory =
                Path.GetFullPath(
                    ResponseDirectory.Trim()
                );

            string responsePath = Path.Combine(
                responseDirectory,
                commandId + ".json"
            );

            string responseJson =
                "{"
                + "\"command_id\":\""
                + EscapeJson(commandId)
                + "\","
                + "\"operation_id\":\""
                + EscapeJson(operationId)
                + "\","
                + "\"client_order_id\":\""
                + EscapeJson(clientOrderId)
                + "\","
                + "\""
                + RESPONSE_STATUS_FIELD
                + "\":\""
                + VALIDATION_STATUS
                + "\","
                + "\""
                + RESPONSE_SIM_AUTHORITY_FIELD
                + "\":\""
                + SIM_EXECUTION_AUTHORITY
                + "\","
                + "\""
                + RESPONSE_EXTERNAL_AUTHORITY_FIELD
                + "\":false"
                + "}\n";

            byte[] payload =
                new UTF8Encoding(false).GetBytes(
                    responseJson
                );

            try
            {
                using (
                    FileStream stream = new FileStream(
                        responsePath,
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
                if (!File.Exists(responsePath))
                    throw;

                byte[] existing =
                    File.ReadAllBytes(
                        responsePath
                    );

                if (BytesEqual(
                    existing,
                    payload
                ))
                {
                    Print(
                        "ARMS_SIM_COMMAND_CONSUMER "
                        + "idempotent response evidence "
                        + "command_id="
                        + commandId
                    );

                    return;
                }

                throw new InvalidOperationException(
                    "response evidence collision."
                );
            }
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

        private static string ExtractRequiredString(
            string json,
            string propertyName
        )
        {
            if (string.IsNullOrWhiteSpace(json))
                throw new InvalidOperationException(
                    "Command JSON is empty."
                );

            string pattern =
                "\""
                + Regex.Escape(propertyName)
                + "\"\\s*:\\s*\"(?<value>(?:\\\\.|[^\"])*)\"";

            Match match = Regex.Match(
                json,
                pattern,
                RegexOptions.CultureInvariant
            );

            if (!match.Success)
                throw new InvalidOperationException(
                    "Required command property is missing."
                );

            string value = Regex.Unescape(
                match.Groups["value"].Value
            );

            if (string.IsNullOrWhiteSpace(value))
                throw new InvalidOperationException(
                    "Required command property is empty."
                );

            return value;
        }
    }
}
