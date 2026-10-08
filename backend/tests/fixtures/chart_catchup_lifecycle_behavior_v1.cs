using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
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

    public void BeginRealtimeWithoutStartingWatcher()
    {
        State = State.Realtime;
    }

    public void PollBinding()
    {
        typeof(NinjaTrader.NinjaScript.Indicators.ArmsChartCatchupBridgeV1)
            .GetMethod("PollBinding", BindingFlags.Instance | BindingFlags.NonPublic)
            .Invoke(this, null);
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

    private static string Hash(string value)
    {
        using (var digest = SHA256.Create())
        {
            return BitConverter.ToString(
                digest.ComputeHash(Encoding.UTF8.GetBytes(value))
            ).Replace("-", "").ToLowerInvariant();
        }
    }

    private static Dictionary<string, object> ZeroAuthority()
    {
        return new Dictionary<string, object> {
            { "execution_authority", false },
            { "order_authority", false },
            { "paper_execution_authority", false },
            { "live_execution_authority", false },
            { "broker_authority", false },
            { "strategy_enable_authority", false },
            { "ninjatrader_control_authority", false },
            { "paper_execution_enabled", false },
            { "live_execution_allowed", false },
            { "external_order_authority", false },
            { "broker_live_order_authority", false },
        };
    }

    private static string WriteBinding(
        string control,
        string runtimeParent,
        string runtime,
        string runId,
        string runtimeId,
        int generation
    )
    {
        string live = Path.Combine(runtime, "inbox");
        string catchup = Path.Combine(runtime, "chart-catchup");
        Directory.CreateDirectory(live);
        Directory.CreateDirectory(catchup);
        string nonce = new string((char)('a' + generation - 1), 64);
        string handoff = new string('c', 64);
        var claim = new Dictionary<string, object> {
            { "schema", "arms.one-click-native-binding-claim.v1" },
            { "one_click_run_id", runId },
            { "native_runtime_id", runtimeId },
            { "runtime_parent", runtimeParent },
            { "runtime_directory", runtime },
            { "live_inbox", live },
            { "catchup_output_directory", catchup },
            { "expected_provider", "Provider31" },
            { "contract", "NQ DEC26" },
            { "bars_period", "Minute" },
            { "bars_value", 1 },
            { "trading_hours", "CME US Index Futures ETH" },
            { "from_close_utc", "2026-10-05T03:33:00Z" },
            { "through_close_utc", "LATEST_CLOSED" },
            { "handoff_file_sha256", handoff },
            { "phase3_source_sha256", new string('d', 64) },
            { "binding_nonce", nonce },
            { "generation", generation },
            { "created_utc", Stamp(DateTime.UtcNow.AddSeconds(-1)) },
            { "expires_utc", Stamp(DateTime.UtcNow.AddMinutes(5)) },
            { "apply_limit", 1 },
        };
        foreach (var item in ZeroAuthority()) claim.Add(item.Key, item.Value);
        string claimJson = Serializer.Serialize(claim);
        string claimHash = Hash(claimJson);
        File.WriteAllText(control, Serializer.Serialize(new {
            schema = "arms.one-click-native-binding-control.v1",
            state = "ACTIVE",
            claim_json = claimJson,
            claim_sha256 = claimHash,
        }), new UTF8Encoding(false));
        string session = generation == 1
            ? "33333333-3333-4333-8333-333333333333"
            : "44444444-4444-4444-8444-444444444444";
        var receipt = new Dictionary<string, object> {
            { "schema", "arms.nt.one-click-binding-receipt.v1" },
            { "session", session },
            { "native_runtime_id", runtimeId },
            { "binding_nonce", nonce },
            { "binding_claim_sha256", claimHash },
            { "handoff_file_sha256", handoff },
            { "read_only", true },
        };
        foreach (var item in ZeroAuthority()) receipt.Add(item.Key, item.Value);
        File.WriteAllText(
            Path.Combine(live, session + ".one-click-binding.json"),
            Serializer.Serialize(receipt) + "\n",
            new UTF8Encoding(false)
        );
        WriteHello(Path.Combine(live, session + ".jsonl"), session, DateTime.UtcNow);
        return catchup;
    }

    private static string[] LifecycleStates(string output)
    {
        return ReadLines(Path.Combine(output, "catchup-lifecycle.jsonl"))
            .Select(line => (string)((Dictionary<string, object>)
                Serializer.DeserializeObject(line))["state"])
            .ToArray();
    }

    private static void RunGenerationRotation(string root)
    {
        string controlDirectory = Path.Combine(root, "one-click-native-control");
        string runtimeParent = Path.Combine(root, "analysis-native");
        Directory.CreateDirectory(controlDirectory);
        Directory.CreateDirectory(runtimeParent);
        string control = Path.Combine(controlDirectory, "active-binding.json");
        string firstId = "55555555-5555-4555-8555-555555555555";
        string secondId = "66666666-6666-4666-8666-666666666666";
        string firstOutput = WriteBinding(
            control, runtimeParent, Path.Combine(runtimeParent, firstId),
            "20261008T030000Z-oneclick-111111111111", firstId, 1);

        Connection.Connections.Add(new Connection());
        var host = new Host();
        host.Step(State.SetDefaults);
        host.CaptureEnabled = true;
        host.OneClickBindingFile = control;
        host.BeginRealtimeWithoutStartingWatcher();
        host.PollBinding();
        host.Bar(100);
        host.Bar(101);
        host.Bar(102);
        Need(LifecycleStates(firstOutput).Last() == "CAPTURE_COMPLETE", "first generation");

        string secondOutput = WriteBinding(
            control, runtimeParent, Path.Combine(runtimeParent, secondId),
            "20261008T030100Z-oneclick-222222222222", secondId, 2);
        host.PollBinding();
        host.Bar(200);
        host.Bar(201);
        host.Bar(202);
        Need(LifecycleStates(secondOutput).Last() == "CAPTURE_COMPLETE", "second generation");
        Need(
            Directory.GetFiles(firstOutput, "*.chart-catchup.jsonl").Length == 1
            && Directory.GetFiles(secondOutput, "*.chart-catchup.jsonl").Length == 1,
            "one capture per generation"
        );
        Console.WriteLine(Serializer.Serialize(new {
            classification = "SYNTHETIC_CSHARP_BEHAVIOR_NO_NINJATRADER_RUNTIME",
            consecutive_binding_generations = true,
            first_states = LifecycleStates(firstOutput),
            second_states = LifecycleStates(secondOutput),
            captures = 2,
            real_native_api_calls = 0,
            order_calls = 0,
        }));
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
        bool generationRotation = args.Length > 2 && args[2] == "generation-rotation";

        if (generationRotation)
        {
            RunGenerationRotation(Directory.GetParent(output).FullName);
            return;
        }

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
