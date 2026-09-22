// R5.2 synthetic offline harness.
// Actual ArmsTimestampDomainProbeV1 source executes against these doubles.
// No NinjaTrader assembly is loaded by this harness.

using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;

[assembly: AssemblyVersion("8.1.8.2")]

namespace NinjaTrader.Core
{
    public static class Globals
    {
        public static Options GeneralOptions = new Options();
    }

    public class Options
    {
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc;
    }
}

namespace NinjaTrader.Cbi
{
    public enum ErrorCode
    {
        NoError,
        Failed
    }

    public enum MergePolicy
    {
        DoNotMerge,
        MergeBackAdjusted
    }

    public enum LookupPolicies
    {
        Repository,
        Provider
    }

    public class Connection
    {
        public static Connection PlaybackConnection;
    }

    public class MasterInstrument
    {
        public string Name = "NQ";
        public double TickSize = .25;
        public double PointValue = 20;
    }

    public class Instrument
    {
        public string FullName = "NQ DEC26";

        public MasterInstrument MasterInstrument =
            new MasterInstrument();

        public DateTime Expiry =
            new DateTime(2026, 12, 1);

        public static Instrument GetInstrument(string value)
        {
            if (value != "NQ DEC26")
                throw new Exception(Harness.Secret);

            return new Instrument();
        }
    }
}

namespace NinjaTrader.Data
{
    using NinjaTrader.Cbi;

    public enum BarsPeriodType
    {
        Minute
    }

    public enum MarketDataType
    {
        Last
    }

    public class BarsPeriod
    {
        public BarsPeriodType BarsPeriodType;
        public int Value;
        public MarketDataType MarketDataType;
    }

    public class TradingHours
    {
        public string Name =
            "CME US Index Futures ETH";

        public TimeZoneInfo TimeZoneInfo =
            TimeZoneInfo.FindSystemTimeZoneById(
                "Central Standard Time");

        public static TradingHours Get(string name)
        {
            if (name != "CME US Index Futures ETH")
                throw new Exception(Harness.Secret);

            return new TradingHours();
        }
    }

    public class Bars
    {
        public Instrument Instrument;
        public BarsPeriod BarsPeriod;
        public TradingHours TradingHours;

        public int Count = 5;

        public int TimeReads;
        public int OpenReads;
        public int HighReads;
        public int LowReads;
        public int CloseReads;
        public int VolumeReads;

        public DateTime GetTime(int i)
        {
            TimeReads++;

            if (
                Harness.Mode == "gettime_throw" &&
                i == 2)
            {
                throw new InvalidOperationException(
                    Harness.Secret);
            }

            DateTime value =
                new DateTime(
                    2026,
                    9,
                    16,
                    12,
                    0,
                    0,
                    DateTimeKind.Utc)
                .AddMinutes(i);

            if (Harness.Mode == "all_unspecified")
            {
                value =
                    DateTime.SpecifyKind(
                        value,
                        DateTimeKind.Unspecified);
            }

            if (Harness.Mode == "mixed")
            {
                value =
                    DateTime.SpecifyKind(
                        value,
                        i < 3
                            ? DateTimeKind.Unspecified
                            : DateTimeKind.Utc);
            }

            if (Harness.Mode == "local")
            {
                value =
                    DateTime.SpecifyKind(
                        value,
                        DateTimeKind.Local);
            }

            if (Harness.Mode == "duplicate" && i == 2)
            {
                value =
                    new DateTime(
                        2026,
                        9,
                        16,
                        12,
                        1,
                        0,
                        DateTimeKind.Utc);
            }

            if (Harness.Mode == "decreasing" && i == 2)
            {
                value =
                    new DateTime(
                        2026,
                        9,
                        16,
                        11,
                        59,
                        0,
                        DateTimeKind.Utc);
            }

            if (Harness.Mode == "misaligned" && i == 2)
            {
                value =
                    value.AddSeconds(1);
            }

            if (Harness.Mode == "too_many_dates")
            {
                value =
                    new DateTime(
                        2026,
                        1,
                        1,
                        12,
                        0,
                        0,
                        DateTimeKind.Utc)
                    .AddDays(i);
            }

            if (Harness.Mode == "too_many_transitions")
            {
                value =
                    DateTime.SpecifyKind(
                        value,
                        i % 2 == 0
                            ? DateTimeKind.Utc
                            : DateTimeKind.Unspecified);
            }

            return value;
        }

        public double GetOpen(int i)
        {
            OpenReads++;

            if (
                Harness.Mode == "snapshot_mutated" &&
                OpenReads > Count)
            {
                return 20002;
            }

            return 20000;
        }

        public double GetHigh(int i)
        {
            HighReads++;
            return 20003;
        }

        public double GetLow(int i)
        {
            LowReads++;
            return 19999;
        }

        public double GetClose(int i)
        {
            CloseReads++;
            return 20000.25;
        }

        public long GetVolume(int i)
        {
            VolumeReads++;
            return 10;
        }
    }

    public class BarsRequest : IDisposable
    {
        public static int Creates;
        public static int Invokes;
        public static int Disposes;
        public static BarsRequest Last;

        public Instrument Instrument;
        public BarsPeriod BarsPeriod;
        public TradingHours TradingHours;

        public MergePolicy MergePolicy;
        public LookupPolicies LookupPolicy;

        public bool IsResetOnNewTradingDay;
        public bool IsDividendAdjusted;
        public bool IsSplitAdjusted;

        public Bars Bars;

        private Action<BarsRequest, ErrorCode, string> callback;

        public BarsRequest(
            Instrument instrument,
            DateTime from,
            DateTime through)
        {
            Creates++;
            Last = this;
            Instrument = instrument;

            if (
                from != new DateTime(2026, 9, 16) ||
                through != new DateTime(2026, 9, 21) ||
                from.Kind != DateTimeKind.Unspecified ||
                through.Kind != DateTimeKind.Unspecified)
            {
                throw new Exception(
                    "request date contract");
            }
        }

        public void Request(
            Action<BarsRequest, ErrorCode, string> value)
        {
            Invokes++;
            callback = value;

            if (
                LookupPolicy != LookupPolicies.Repository ||
                MergePolicy != MergePolicy.DoNotMerge ||
                !IsResetOnNewTradingDay ||
                IsDividendAdjusted ||
                IsSplitAdjusted ||
                BarsPeriod == null ||
                BarsPeriod.BarsPeriodType != BarsPeriodType.Minute ||
                BarsPeriod.Value != 1 ||
                BarsPeriod.MarketDataType != MarketDataType.Last ||
                TradingHours == null ||
                TradingHours.Name != "CME US Index Futures ETH")
            {
                throw new Exception(
                    "request contract");
            }

            Bars = new Bars
            {
                Instrument = Instrument,
                BarsPeriod = BarsPeriod,
                TradingHours = TradingHours
            };

            if (Harness.Mode == "empty")
                Bars.Count = 0;

            if (Harness.Mode == "too_many")
                Bars.Count = 10003;

            if (Harness.Mode == "large")
                Bars.Count = 4503;

            if (Harness.Mode == "too_many_dates")
                Bars.Count = 33;

            if (Harness.Mode == "too_many_transitions")
                Bars.Count = 18;

            if (Harness.Mode == "wrong_instrument")
                Instrument.FullName = "OTHER";

            if (Harness.Mode == "wrong_period")
                BarsPeriod.Value = 2;

            if (Harness.Mode == "provider_policy")
                LookupPolicy = LookupPolicies.Provider;

            if (Harness.Mode == "wrong_template")
                TradingHours.Name = "OTHER";

            if (Harness.Mode == "inline")
                Fire();

            if (Harness.Mode == "inline_then_throw")
            {
                Fire();
                throw new IOException(Harness.Secret);
            }

            if (Harness.Mode == "request_throw")
                throw new IOException(Harness.Secret);
        }

        public void Fire()
        {
            callback(
                Harness.Mode == "wrong_callback"
                    ? null
                    : this,

                Harness.Mode == "callback_error"
                    ? ErrorCode.Failed
                    : ErrorCode.NoError,

                Harness.Secret);
        }

        public void Dispose()
        {
            Disposes++;
        }
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State
    {
        SetDefaults,
        Configure,
        DataLoaded,
        Historical,
        Transition,
        Realtime,
        Terminated
    }

    [AttributeUsage(AttributeTargets.Property)]
    public class NinjaScriptPropertyAttribute :
        Attribute
    {
    }
}

namespace NinjaTrader.NinjaScript.Indicators
{
    public class Indicator
    {
        public State State;

        public string Name;
        public string Description;

        public bool IsOverlay;
        public bool IsChartOnly;

        protected virtual void OnStateChange()
        {
        }
    }

    public class ProbeHost :
        ArmsTimestampDomainProbeV1
    {
        public void Step(State value)
        {
            State = value;
            OnStateChange();
        }

        public ProbeHost Clone()
        {
            return (ProbeHost)MemberwiseClone();
        }

        public void SetPrivate(
            string name,
            object value)
        {
            typeof(ArmsTimestampDomainProbeV1)
                .GetField(
                    name,
                    BindingFlags.Instance |
                    BindingFlags.NonPublic)
                .SetValue(this, value);
        }
    }
}

public static class Harness
{
    public const string Secret =
        "PRIVATE_PROVIDER_SENTINEL";

    public static string Mode;
    public static string Output;

    public static
        NinjaTrader.NinjaScript.Indicators.ProbeHost
        Host;

    public static int Main(string[] args)
    {
        Mode = args[0];
        Output = args[1];

        Host =
            new NinjaTrader.NinjaScript.Indicators.ProbeHost();

        Host.Step(
            NinjaTrader.NinjaScript.State.SetDefaults);

        if (Mode != "defaults")
        {
            Host.ProbeEnabled = true;
            Host.OutputDirectory = Output;

            Host.MarketReopenConfirmed =
                Mode != "closed";

            Host.NqDataFlowConfirmed =
                Mode != "no_flow";

            Host.ConnectionStableConfirmed =
                Mode != "unstable";
        }

        if (Mode == "playback")
        {
            NinjaTrader.Cbi.Connection.PlaybackConnection =
                new NinjaTrader.Cbi.Connection();
        }

        if (Mode == "timezone")
        {
            NinjaTrader.Core.Globals
                .GeneralOptions
                .TimeZoneInfo =
                TimeZoneInfo.Local;
        }

        Host.Step(
            NinjaTrader.NinjaScript.State.Configure);

        Host.Step(
            NinjaTrader.NinjaScript.State.DataLoaded);

        if (Mode == "clone")
        {
            var clone = Host.Clone();

            clone.Step(
                NinjaTrader.NinjaScript.State.SetDefaults);

            clone.Step(
                NinjaTrader.NinjaScript.State.Terminated);
        }

        if (Mode == "record_cap")
        {
            Host.SetPrivate(
                "records",
                40);
        }

        if (Mode == "byte_cap")
        {
            Host.SetPrivate(
                "bytes",
                262144);
        }

        if (Mode == "changed_properties")
        {
            Host.OutputDirectory =
                Secret;
        }

        if (Mode == "terminated")
        {
            Host.Step(
                NinjaTrader.NinjaScript.State.Terminated);
        }

        var request =
            NinjaTrader.Data.BarsRequest.Last;

        if (
            request != null &&
            Mode != "pending" &&
            Mode != "request_throw" &&
            Mode != "inline" &&
            Mode != "inline_then_throw")
        {
            if (Mode == "async")
            {
                var thread =
                    new System.Threading.Thread(
                        request.Fire);

                thread.Start();
                thread.Join();
            }
            else
            {
                request.Fire();
            }

            // Deliberate duplicate callback.
            // Probe must not produce a second result.
            request.Fire();
        }

        for (int i = 0; i < 100; i++)
        {
            Host.Step(
                NinjaTrader.NinjaScript.State.DataLoaded);
        }

        if (Mode != "pending")
        {
            Host.Step(
                NinjaTrader.NinjaScript.State.Terminated);
        }

        var bars =
            request == null
                ? null
                : request.Bars;

        Console.WriteLine(
            new JavaScriptSerializer().Serialize(
                new
                {
                    request_creates =
                        NinjaTrader.Data.BarsRequest.Creates,

                    request_invokes =
                        NinjaTrader.Data.BarsRequest.Invokes,

                    request_disposes =
                        NinjaTrader.Data.BarsRequest.Disposes,

                    bars_count =
                        bars == null
                            ? -1
                            : bars.Count,

                    time_reads =
                        bars == null
                            ? 0
                            : bars.TimeReads,

                    open_reads =
                        bars == null
                            ? 0
                            : bars.OpenReads,

                    high_reads =
                        bars == null
                            ? 0
                            : bars.HighReads,

                    low_reads =
                        bars == null
                            ? 0
                            : bars.LowReads,

                    close_reads =
                        bars == null
                            ? 0
                            : bars.CloseReads,

                    volume_reads =
                        bars == null
                            ? 0
                            : bars.VolumeReads,

                    session_iterator_calls =
                        0,

                    account_access =
                        false,

                    order_calls =
                        0,

                    timestamp_conversion =
                        false,

                    ninjatrader_assemblies_loaded =
                        Array.FindAll(
                            AppDomain.CurrentDomain
                                .GetAssemblies(),
                            assembly =>
                                assembly.GetName()
                                    .Name.StartsWith(
                                        "NinjaTrader"))
                        .Length
                }));

        return 0;
    }
}
