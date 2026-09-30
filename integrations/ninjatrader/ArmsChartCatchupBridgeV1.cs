using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.NinjaScript.Indicators
{
    public class ArmsChartCatchupBridgeV1 : Indicator
    {
        private readonly object sync = new object();

        private bool attempted;
        private bool terminal;

        [NinjaScriptProperty]
        [Display(
            Name = "Capture enabled",
            Order = 1,
            GroupName = "ARMS read-only catch-up"
        )]
        public bool CaptureEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Fresh private output directory",
            Order = 2,
            GroupName = "ARMS read-only catch-up"
        )]
        public string OutputDirectory { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Expected provider enum",
            Order = 3,
            GroupName = "ARMS read-only catch-up"
        )]
        public string ExpectedProvider { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "From close UTC",
            Order = 4,
            GroupName = "ARMS read-only catch-up"
        )]
        public string FromCloseUtc { get; set; }

        [NinjaScriptProperty]
        [Display(
            Name = "Through close UTC",
            Order = 5,
            GroupName = "ARMS read-only catch-up"
        )]
        public string ThroughCloseUtc { get; set; }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ArmsChartCatchupBridgeV1";

                Description =
                    "One-shot loaded-chart catch-up evidence; read only and no execution authority.";

                Calculate = Calculate.OnEachTick;

                IsOverlay = true;
                IsChartOnly = true;
                IsSuspendedWhileInactive = false;

                CaptureEnabled = false;
                OutputDirectory = "";
                ExpectedProvider = "";
                FromCloseUtc = "";
                ThroughCloseUtc = "";
            }
            else if (
                State == State.Realtime
                && CaptureEnabled
            )
            {
                lock (sync)
                {
                    if (
                        attempted
                        || terminal
                    )
                        return;

                    attempted = true;

                    try
                    {
                        Capture();

                        terminal = true;

                        try
                        {
                            Print(
                                "ARMS_CHART_CATCHUP_BRIDGE_COMPLETE"
                            );
                        }
                        catch
                        {
                        }
                    }
                    catch (Exception error)
                    {
                        terminal = true;

                        try
                        {
                            Print(
                                "ARMS_CHART_CATCHUP_BRIDGE_FAILED_"
                                + ErrorCode(error)
                            );
                        }
                        catch
                        {
                        }
                    }
                }
            }
        }

        private static void Need(bool value)
        {
            if (!value)
                throw new InvalidOperationException();
        }

        private static string ErrorCode(Exception error)
        {
            if (error is InvalidOperationException)
                return "INVALID_OPERATION";

            if (error is UnauthorizedAccessException)
                return "ACCESS_DENIED";

            if (error is IOException)
                return "IO_ERROR";

            if (error is FormatException)
                return "FORMAT_ERROR";

            if (error is ArgumentException)
                return "INVALID_ARGUMENT";

            return "OTHER";
        }

        private static string ProviderName(
            Connection connection
        )
        {
            if (
                connection == null
                || connection.Options == null
            )
                return "UNKNOWN";

            var provider =
                connection.Options.Provider;

            return Enum.IsDefined(
                provider.GetType(),
                provider
            )
                ? provider.ToString()
                : "UNKNOWN";
        }

        private static string StatusName(
            ConnectionStatus value
        )
        {
            return Enum.IsDefined(
                typeof(ConnectionStatus),
                value
            )
                ? value.ToString()
                : "UNKNOWN";
        }

        private void RequireSource()
        {
            Need(
                Connection.PlaybackConnection
                == null
            );

            Need(
                Core.Globals.GeneralOptions
                    .TimeZoneInfo.Id
                == "UTC"
            );

            Need(
                BarsPeriod.BarsPeriodType
                == BarsPeriodType.Minute
                && BarsPeriod.Value == 1
            );

            Need(
                Instrument != null
                && Instrument.MasterInstrument != null
                && Instrument.MasterInstrument.Name
                    == "NQ"
                && Instrument.FullName
                    == "NQ DEC26"
                && Instrument.Expiry
                    .ToString("yyyy-MM-dd")
                    == "2026-12-01"
                && Instrument.MasterInstrument.TickSize
                    == .25
                && Instrument.MasterInstrument.PointValue
                    == 20
            );

            Need(
                Bars != null
                && Bars.TradingHours != null
                && Bars.TradingHours.Name
                    == "CME US Index Futures ETH"
            );

            Need(
                !String.IsNullOrWhiteSpace(
                    ExpectedProvider
                )
                && !ExpectedProvider
                    .ToLowerInvariant()
                    .Contains("simulat")
                && !ExpectedProvider
                    .ToLowerInvariant()
                    .Contains("playback")
            );

            if (
                !System.Threading.Monitor.TryEnter(
                    Connection.Connections
                )
            )
                throw new InvalidOperationException();

            try
            {
                var futures =
                    Connection.Connections
                        .Where(
                            connection =>
                                connection != null
                                && connection.InstrumentTypes
                                    .Contains(
                                        InstrumentType.Future
                                    )
                        )
                        .ToArray();

                Need(
                    futures.Length == 1
                );

                var source =
                    futures[0];

                Need(
                    ProviderName(source)
                    == ExpectedProvider
                );

                Need(
                    StatusName(
                        source.PriceStatus
                    )
                    == "Connected"
                );

                Need(
                    StatusName(
                        source.Status
                    )
                    == "Connected"
                );

                Need(
                    ProviderName(source)
                    == ExpectedProvider
                );
            }
            finally
            {
                System.Threading.Monitor.Exit(
                    Connection.Connections
                );
            }
        }

        private static DateTime ParseUtc(
            string value
        )
        {
            DateTime parsed;

            Need(
                DateTime.TryParseExact(
                    value,
                    "yyyy-MM-ddTHH:mm:ss'Z'",
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal
                        | DateTimeStyles.AdjustToUniversal,
                    out parsed
                )
            );

            Need(
                parsed.Kind
                == DateTimeKind.Utc
            );

            Need(
                parsed.Second == 0
                && parsed.Millisecond == 0
                && parsed.Ticks
                    % TimeSpan.TicksPerMinute
                    == 0
            );

            return parsed;
        }

        private static DateTime ClockFieldsAsUtc(
            DateTime value
        )
        {
            if (
                value.Kind
                == DateTimeKind.Utc
            )
                return value;

            Need(
                value.Kind
                == DateTimeKind.Unspecified
            );

            DateTime normalized =
                DateTime.SpecifyKind(
                    value,
                    DateTimeKind.Utc
                );

            Need(
                normalized.Ticks
                == value.Ticks
            );

            return normalized;
        }

        private static string LocalDirectory(
            string value
        )
        {
            Need(
                !String.IsNullOrWhiteSpace(
                    value
                )
                && Path.IsPathRooted(
                    value
                )
            );

            string full =
                Path.GetFullPath(value);

            string root =
                Path.GetPathRoot(full);

            Need(
                !root.StartsWith(@"\\")
                && Directory.Exists(full)
                && new DriveInfo(root).DriveType
                    == DriveType.Fixed
            );

            for (
                var current =
                    new DirectoryInfo(full);
                current != null;
                current = current.Parent
            )
            {
                Need(
                    (
                        current.Attributes
                        & FileAttributes.ReparsePoint
                    )
                    == 0
                );
            }

            Need(
                Directory.GetFileSystemEntries(
                    full
                ).Length
                == 0
            );

            return full;
        }

        private static bool Price(
            double value
        )
        {
            return
                !Double.IsNaN(value)
                && !Double.IsInfinity(value)
                && value > 0
                && value * 4
                    == Math.Truncate(
                        value * 4
                    );
        }

        private static string Hash(
            byte[] value
        )
        {
            using (
                var digest =
                    SHA256.Create()
            )
            {
                return BitConverter
                    .ToString(
                        digest.ComputeHash(
                            value
                        )
                    )
                    .Replace("-", "")
                    .ToLowerInvariant();
            }
        }

        private void Capture()
        {
            RequireSource();

            string output =
                LocalDirectory(
                    OutputDirectory
                );

            DateTime from =
                ParseUtc(
                    FromCloseUtc
                );

            DateTime through =
                ParseUtc(
                    ThroughCloseUtc
                );

            Need(
                from <= through
                && through - from
                    <= TimeSpan.FromDays(2)
            );

            int count =
                Bars.Count;

            Need(
                count >= 3
                && count <= 1000000
            );

            var indexes =
                new List<int>();

            DateTimeKind? selectedKind =
                null;

            DateTime previousRaw =
                DateTime.MinValue;

            // The newest chart row may still be forming.
            // Never admit it into catch-up evidence.
            for (
                int i = 0;
                i < count - 1;
                i++
            )
            {
                DateTime raw =
                    Bars.GetTime(i);

                Need(
                    raw.Kind
                        == DateTimeKind.Utc
                    || raw.Kind
                        == DateTimeKind.Unspecified
                );

                Need(
                    raw.Ticks
                    % TimeSpan.TicksPerMinute
                    == 0
                );

                if (
                    previousRaw
                    != DateTime.MinValue
                )
                {
                    Need(
                        raw.Ticks
                        > previousRaw.Ticks
                    );
                }

                previousRaw = raw;

                DateTime label =
                    ClockFieldsAsUtc(raw);

                if (
                    label < from
                    || label > through
                )
                    continue;

                if (!selectedKind.HasValue)
                {
                    selectedKind =
                        raw.Kind;
                }
                else
                {
                    Need(
                        selectedKind.Value
                        == raw.Kind
                    );
                }

                indexes.Add(i);
            }

            Need(
                indexes.Count > 0
                && indexes.Count <= 3000
            );

            DateTime firstLabel =
                ClockFieldsAsUtc(
                    Bars.GetTime(
                        indexes[0]
                    )
                );

            DateTime lastLabel =
                ClockFieldsAsUtc(
                    Bars.GetTime(
                        indexes[
                            indexes.Count - 1
                        ]
                    )
                );

            Need(
                firstLabel == from
                && lastLabel == through
            );

            string runId =
                Guid.NewGuid()
                    .ToString("D");

            var serializer =
                new JavaScriptSerializer();

            var lines =
                new List<string>();

            lines.Add(
                serializer.Serialize(
                    new
                    {
                        schema =
                            "arms.nt.chart-catchup.header.v1",

                        run_id =
                            runId,

                        exporter =
                            "ArmsChartCatchupBridgeV1/1",

                        source =
                            "NINJATRADER_LOADED_CHART_BARS",

                        provider =
                            ExpectedProvider,

                        instrument =
                            "NQ",

                        contract =
                            "NQ DEC26",

                        expiry =
                            "2026-12-01",

                        bars_type =
                            "Minute",

                        bars_value =
                            1,

                        timeframe =
                            "1m",

                        trading_hours =
                            "CME US Index Futures ETH",

                        application_timezone =
                            "UTC",

                        bar_label =
                            "CLOSE",

                        tick_size =
                            .25,

                        point_value =
                            20,

                        requested_from_close =
                            from.ToString("o"),

                        requested_through_close =
                            through.ToString("o"),

                        chart_bar_count =
                            count,

                        excluded_last =
                            true,

                        raw_time_kind =
                            selectedKind.Value.ToString(),

                        classification =
                            "CHART_CATCHUP",

                        observation_only =
                            true,

                        runtime_admission =
                            false,

                        execution_authority =
                            false
                    }
                )
            );

            for (
                int selected = 0;
                selected < indexes.Count;
                selected++
            )
            {
                int index =
                    indexes[selected];

                DateTime raw =
                    Bars.GetTime(index);

                DateTime label =
                    ClockFieldsAsUtc(raw);

                double open =
                    Bars.GetOpen(index);

                double high =
                    Bars.GetHigh(index);

                double low =
                    Bars.GetLow(index);

                double close =
                    Bars.GetClose(index);

                long volume =
                    Bars.GetVolume(index);

                Need(
                    raw.Kind
                    == selectedKind.Value
                );

                Need(
                    Price(open)
                    && Price(high)
                    && Price(low)
                    && Price(close)
                    && volume >= 0
                );

                Need(
                    low
                    <= Math.Min(
                        open,
                        close
                    )
                    && high
                    >= Math.Max(
                        open,
                        close
                    )
                );

                lines.Add(
                    serializer.Serialize(
                        new
                        {
                            schema =
                                "arms.nt.chart-catchup.bar.v1",

                            run_id =
                                runId,

                            index =
                                selected,

                            chart_index =
                                index,

                            raw_time =
                                raw.ToString(
                                    "o",
                                    CultureInfo.InvariantCulture
                                ),

                            raw_time_kind =
                                raw.Kind.ToString(),

                            raw_ticks =
                                raw.Ticks,

                            bar_time =
                                label.ToString(
                                    "o",
                                    CultureInfo.InvariantCulture
                                ),

                            open = open,
                            high = high,
                            low = low,
                            close = close,
                            volume = volume,

                            classification =
                                "CHART_CATCHUP",

                            observation_only =
                                true,

                            runtime_admission =
                                false,

                            execution_authority =
                                false
                        }
                    )
                );
            }

            Need(
                Bars.Count
                == count
            );

            byte[] body =
                Encoding.UTF8.GetBytes(
                    String.Join(
                        "\n",
                        lines
                    )
                    + "\n"
                );

            Need(
                body.Length
                <= 16 * 1024 * 1024
            );

            string bodyPath =
                Path.Combine(
                    output,
                    runId
                    + ".chart-catchup.jsonl"
                );

            using (
                var file =
                    new FileStream(
                        bodyPath,
                        FileMode.CreateNew,
                        FileAccess.Write,
                        FileShare.Read,
                        4096,
                        FileOptions.WriteThrough
                    )
            )
            {
                file.Write(
                    body,
                    0,
                    body.Length
                );

                file.Flush(true);
            }

            var seal =
                new
                {
                    schema =
                        "arms.nt.chart-catchup.seal.v1",

                    run_id =
                        runId,

                    bytes =
                        body.Length,

                    records =
                        lines.Count,

                    bars =
                        indexes.Count,

                    sha256 =
                        Hash(body),

                    writer_closed =
                        true,

                    complete =
                        true,

                    classification =
                        "CHART_CATCHUP",

                    runtime_admission =
                        false,

                    execution_authority =
                        false
                };

            string temporary =
                bodyPath
                + ".done.tmp";

            string final =
                bodyPath
                + ".done.json";

            using (
                var writer =
                    new StreamWriter(
                        new FileStream(
                            temporary,
                            FileMode.CreateNew,
                            FileAccess.Write,
                            FileShare.Read
                        ),
                        new UTF8Encoding(false)
                    )
            )
            {
                writer.Write(
                    serializer.Serialize(
                        seal
                    )
                );
            }

            File.Move(
                temporary,
                final
            );
        }
    }
}
