using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;

namespace NinjaTrader.Cbi
{
    public enum ConnectionStatus { Disconnected, Connected }
    public enum Provider { Provider31, Other }
    public enum InstrumentType { Future }

    public sealed class ConnectionOptions
    {
        public Provider Provider = Provider.Provider31;
    }

    public sealed class Connection
    {
        public static Connection PlaybackConnection;
        public static readonly List<Connection> Connections = new List<Connection>();
        public ConnectionOptions Options = new ConnectionOptions();
        public InstrumentType[] InstrumentTypes = { InstrumentType.Future };
        public ConnectionStatus PriceStatus = ConnectionStatus.Connected;
        public ConnectionStatus Status = ConnectionStatus.Connected;
    }
}

namespace NinjaTrader.Data
{
    public enum BarsPeriodType { Minute }

    public sealed class BarsPeriod
    {
        public BarsPeriodType BarsPeriodType = BarsPeriodType.Minute;
        public int Value = 1;
    }
}

namespace NinjaTrader.Core
{
    public static class Globals
    {
        public static readonly GeneralOptions GeneralOptions = new GeneralOptions();
    }

    public sealed class GeneralOptions
    {
        public TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc;
    }
}

namespace NinjaTrader.NinjaScript
{
    public enum State { SetDefaults, Realtime, Terminated }
    public enum Calculate { OnEachTick }

    public sealed class NinjaScriptPropertyAttribute : Attribute { }

    public sealed class MasterInstrument
    {
        public string Name = "NQ";
        public double TickSize = .25;
        public double PointValue = 20;
    }

    public sealed class InstrumentInfo
    {
        public MasterInstrument MasterInstrument = new MasterInstrument();
        public string FullName = "NQ DEC26";
        public DateTime Expiry = new DateTime(2026, 12, 1);
    }

    public sealed class TradingHours
    {
        public string Name = "CME US Index Futures ETH";
    }

    public sealed class BarSeries
    {
        private readonly DateTime[] times;

        public BarSeries()
        {
            times = new[] {
                new DateTime(2026, 10, 5, 3, 33, 0, DateTimeKind.Utc),
                new DateTime(2026, 10, 5, 3, 34, 0, DateTimeKind.Utc),
                new DateTime(2026, 10, 5, 3, 35, 0, DateTimeKind.Utc),
                new DateTime(2026, 10, 5, 3, 36, 0, DateTimeKind.Utc),
            };
        }

        public TradingHours TradingHours = new TradingHours();
        public int Count { get { return times.Length; } }
        public DateTime GetTime(int index) { return times[index]; }
        public double GetOpen(int index) { return 20000 + index * .25; }
        public double GetHigh(int index) { return GetOpen(index) + 1; }
        public double GetLow(int index) { return GetOpen(index) - 1; }
        public double GetClose(int index) { return GetOpen(index) + .25; }
        public long GetVolume(int index) { return 10 + index; }
    }

    public class Indicator
    {
        public string Name;
        public string Description;
        public Calculate Calculate;
        public bool IsOverlay;
        public bool IsChartOnly;
        public bool IsSuspendedWhileInactive;
        public State State;
        public int BarsInProgress;
        public bool IsFirstTickOfBar = true;
        public int CurrentBar;
        public InstrumentInfo Instrument = new InstrumentInfo();
        public BarSeries Bars = new BarSeries();
        public NinjaTrader.Data.BarsPeriod BarsPeriod = new NinjaTrader.Data.BarsPeriod();

        protected virtual void OnStateChange() { }
        protected virtual void OnBarUpdate() { }
        protected void TriggerCustomEvent(Action<object> action, object state) { action(state); }
        protected void Print(string value) { }
    }
}

internal sealed class Host : NinjaTrader.NinjaScript.Indicators.ArmsChartCatchupBridgeV1
{
    public void Step(State state)
    {
        State = state;
        OnStateChange();
    }

    public void Bar(int currentBar)
    {
        CurrentBar = currentBar;
        OnBarUpdate();
    }
}

internal static class Harness
{
    private static readonly JavaScriptSerializer Serializer = new JavaScriptSerializer();

    private static void Need(bool value, string reason)
    {
        if (!value)
            throw new InvalidOperationException(reason);
    }

    private static string[] ReadLines(string path)
    {
        using (var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite
        ))
        using (var reader = new StreamReader(stream, new UTF8Encoding(false, true)))
        {
            return reader.ReadToEnd()
                .Split(new[] { '\n' }, StringSplitOptions.RemoveEmptyEntries);
        }
    }

    private static string Stamp(DateTime value)
    {
        return value.ToUniversalTime().ToString(
            "yyyy-MM-ddTHH:mm:ss.fffffff'Z'",
            CultureInfo.InvariantCulture
        );
    }

    private static void WriteHello(string path, string session, DateTime time)
    {
        File.WriteAllText(
            path,
            Serializer.Serialize(new {
                schema = "arms.nt.market.v1",
                session = session,
                sequence = 0,
                event_time = Stamp(time),
                kind = "HELLO",
                payload = new {
                    provider = "Provider31",
                    contract = "NQ DEC26",
                    expiry = "2026-12-01",
                    instrument = "NQ",
                    tick_size = .25,
                    point_value = 20,
                    timeframe = "1m",
                    trading_hours_template = "CME US Index Futures ETH",
                    source_timezone = "UTC",
                    bar_label = "CLOSE",
                    realtime = true,
                    read_only = true,
                },
            }) + "\n",
            new UTF8Encoding(false)
        );
    }

    private static void TerminateAndSeal(
        string live,
        string session,
        DateTime time
    )
    {
        string canonical = Path.Combine(live, session + ".jsonl");
        File.AppendAllText(
            canonical,
            Serializer.Serialize(new {
                schema = "arms.nt.market.v1",
                session = session,
                sequence = 1,
                event_time = Stamp(time),
                kind = "DISCONNECTED",
                payload = new {
                    connected = false,
                    reason = "TERMINATED",
                    error_code = "NONE",
                },
            }) + "\n",
            new UTF8Encoding(false)
        );

        WriteTimingSeal(live, session, 2);
    }

    private static void WriteTimingSeal(
        string live,
        string session,
        int canonicalRecords
    )
    {
        string timingDirectory = Path.Combine(live, "timing");
        Directory.CreateDirectory(timingDirectory);
        string timing = Path.Combine(
            timingDirectory,
            session + ".production-timing.jsonl"
        );
        File.WriteAllBytes(timing, new byte[0]);
        File.WriteAllText(
            timing + ".done.json",
            Serializer.Serialize(new {
                schema = "arms.nt.production-timing.seal.v1",
                session = session,
                records = 0,
                bytes = 0,
                sha256 = "e3b0c44298fc1c149afbf4c8996fb924" +
                    "27ae41e4649b934ca495991b7852b855",
                canonical_records = canonicalRecords,
                canonical_writer_closed = true,
                timing_writer_closed = true,
                complete = true,
            }),
            new UTF8Encoding(false)
        );
    }

    public static void Main(string[] args)
    {
        string output = args[0];
        string live = args[1];
        string root = "11111111-1111-4111-8111-111111111111";
        string replacement = "22222222-2222-4222-8222-222222222222";
        DateTime start = new DateTime(2026, 10, 5, 3, 30, 0, DateTimeKind.Utc);
        bool rejectUnterminated = args.Length > 2 && args[2] == "unterminated";

        Directory.CreateDirectory(output);
        Directory.CreateDirectory(live);
        WriteHello(Path.Combine(live, root + ".jsonl"), root, start);
        Connection.Connections.Add(new Connection());

        var host = new Host();
        host.Step(State.SetDefaults);
        host.CaptureEnabled = true;
        host.OutputDirectory = output;
        host.LiveOutputDirectory = live;
        host.ExpectedProvider = "Provider31";
        host.FromCloseUtc = "2026-10-05T03:33:00Z";
        host.ThroughCloseUtc = "LATEST_CLOSED";
        host.Step(State.Realtime);

        host.Bar(100);
        Need(
            Directory.GetFiles(output, "*.chart-catchup.jsonl").Length == 0,
            "capture before alignment advance"
        );

        if (rejectUnterminated)
            WriteTimingSeal(live, root, 1);
        else
            TerminateAndSeal(live, root, start.AddSeconds(1));
        WriteHello(
            Path.Combine(live, replacement + ".jsonl"),
            replacement,
            start.AddSeconds(2)
        );

        host.Bar(101);
        if (rejectUnterminated)
        {
            string failedLifecycle = Path.Combine(output, "catchup-lifecycle.jsonl");
            string[] failedRows = ReadLines(failedLifecycle);
            string[] failedStates = failedRows
                .Select(line => (string)((Dictionary<string, object>)
                    Serializer.DeserializeObject(line))["state"])
                .ToArray();
            string[] expectedFailure = {
                "WAITING_FOR_LIVE_HELLO",
                "LIVE_HELLO_ACCEPTED",
                "ALIGNMENT_BAR_CAPTURED",
                "WAITING_FOR_SECOND_BAR_ADVANCE",
                "CAPTURE_VALIDATION_FAILED",
                "CAPTURE_FAILED",
            };
            Need(failedStates.SequenceEqual(expectedFailure), "failure lifecycle");
            host.Bar(102);
            host.Step(State.Terminated);
            Need(
                Directory.GetFiles(output, "*.chart-catchup.jsonl").Length == 0,
                "unterminated predecessor capture"
            );
            Console.WriteLine(Serializer.Serialize(new {
                classification = "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
                predecessor_rejected = true,
                states = failedStates,
                captures = 0,
                real_native_api_calls = 0,
                order_calls = 0,
            }));
            return;
        }

        Need(
            Directory.GetFiles(output, "*.chart-catchup.jsonl").Length == 0,
            "capture on first post-alignment bar"
        );

        host.Bar(102);
        string lifecycle = Path.Combine(output, "catchup-lifecycle.jsonl");
        string[] before = ReadLines(lifecycle);
        string[] expected = {
            "WAITING_FOR_LIVE_HELLO",
            "LIVE_HELLO_ACCEPTED",
            "ALIGNMENT_BAR_CAPTURED",
            "WAITING_FOR_SECOND_BAR_ADVANCE",
            "CAPTURE_STARTED",
            "CAPTURE_BODY_WRITTEN",
            "CAPTURE_SEAL_WRITTEN",
            "CAPTURE_COMPLETE",
        };
        string[] states = before
            .Select(line => (string)((Dictionary<string, object>)
                Serializer.DeserializeObject(line))["state"])
            .ToArray();
        Need(states.SequenceEqual(expected), "lifecycle sequence");
        Need(
            Directory.GetFiles(output, "*.chart-catchup.jsonl").Length == 1 &&
            Directory.GetFiles(output, "*.chart-catchup.jsonl.done.json").Length == 1 &&
            Directory.GetFiles(output, "*.done.tmp").Length == 0,
            "capture file count"
        );

        host.Bar(103);
        host.Step(State.Realtime);
        Need(ReadLines(lifecycle).Length == before.Length, "repeat lifecycle");
        Need(
            Directory.GetFiles(output, "*.chart-catchup.jsonl").Length == 1,
            "repeat capture"
        );
        host.Step(State.Terminated);

        using (File.Open(lifecycle, FileMode.Open, FileAccess.Read, FileShare.None)) { }

        Console.WriteLine(Serializer.Serialize(new {
            classification = "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
            alignment = true,
            terminate_recreate = true,
            states = states,
            captures = 1,
            real_native_api_calls = 0,
            order_calls = 0,
        }));
    }
}
