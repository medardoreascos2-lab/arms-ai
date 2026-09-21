"""Run the actual C# callback/decision/stop methods with deterministic native doubles.

No installed NinjaTrader process, connection, account, or market stream is used.
"""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_ninjatrader_stop_diagnostics_sprint11 import _method


@pytest.fixture(scope="module")
def native_callback_harness(tmp_path_factory):
    framework = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    compiler = framework / "csc.exe"
    if not compiler.exists():
        pytest.skip("Native callback harness requires Windows .NET Framework compiler")
    source = (Path(__file__).resolve().parents[2] /
              "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    methods = "\n".join(_method(source, signature) for signature in (
        "protected override void OnConnectionStatusUpdate(", "private static string StatusName(",
        "private static string ProviderName(", "private sealed class ReadinessGate",
        "private void Heartbeat(", "private sealed class TimingEvidence", "private void Emit(", "private static string ErrorCode(", "private void Stop("))
    harness = r'''
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Diagnostics;
using System.Web.Script.Serialization;
public enum ConnectionStatus { Connected, Disconnected, Connecting, Disconnecting, ConnectionLost }
public enum Provider { Provider31, Other }
public class Options {
    public Provider Provider = Provider.Provider31;
    public string Name = "PRIVATE_SENTINEL";
}
public class Connection {
    public Options Options = new Options();
    public ConnectionStatus price = ConnectionStatus.Connected;
    public ConnectionStatus status = ConnectionStatus.Connected;
    public bool changeStatusOnSecondRead;
    private int statusReads;
    public ConnectionStatus Status {
        get { return changeStatusOnSecondRead && ++statusReads > 1 ? ConnectionStatus.Disconnected : status; }
        set { status = value; }
    }
    public bool changeOnSecondRead;
    private int reads;
    public ConnectionStatus PriceStatus {
        get { return changeOnSecondRead && ++reads > 1 ? ConnectionStatus.Disconnected : price; }
    }
}
public class ConnectionStatusEventArgs {
    public Connection Connection;
    public ConnectionStatus PriceStatus = ConnectionStatus.Connected;
    public ConnectionStatus PreviousPriceStatus = ConnectionStatus.Connected;
    public ConnectionStatus Status = ConnectionStatus.Connected;
    public ConnectionStatus PreviousStatus = ConnectionStatus.Connected;
    public string NativeError = "PRIVATE_SENTINEL";
}
public class Indicator {
    protected virtual void OnConnectionStatusUpdate(ConnectionStatusEventArgs update) {}
}
public class CallbackHarness : Indicator {
    private readonly object sync = new object();
    private StreamWriter writer, connectionWriter;
    private FaultTimer timer;
    private bool failed;
    private bool helloSent = true;
    private int firstRealtimeBar;
    private string contract = "NQ DEC26", expiry = "2026-12-01", template = "CME US Index Futures ETH";
    private ReadinessGate readiness = new ReadinessGate();
    private TimingEvidence timing;
    private Stopwatch startupClock = new Stopwatch();
    private System.Threading.Timer startupDeadline;
    private long sequence, connectionSequence;
    private string session = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    private string ExpectedProvider = "Provider31";
    private Connection source;
    class FaultTimer {
        public event EventHandler Tick;
        public void Stop() { throw new IOException("PRIVATE_SENTINEL"); }
    }
    // Only source health is doubled; actual heartbeat/admission logic is extracted.
    private bool SafeSource() {
        return source != null && source.PriceStatus == ConnectionStatus.Connected
            && source.Options != null && source.Options.Provider.ToString() == ExpectedProvider;
    }
    private void Print(string text) {}
''' + methods + r'''
    public static void Main(string[] args) {
        var h = new CallbackHarness();
        h.source = new Connection();
        var update = new ConnectionStatusEventArgs { Connection = h.source };
        var market = new MemoryStream(); var diagnostic = new MemoryStream();
        h.writer = new StreamWriter(market, new UTF8Encoding(false)); h.writer.AutoFlush = true;
        h.connectionWriter = new StreamWriter(diagnostic, new UTF8Encoding(false)); h.connectionWriter.AutoFlush = true;
        h.timer = new FaultTimer();
        // These existing cases exercise an already admitted session. Startup has
        // separate whole-exporter coverage in Sprint 11T.
        h.readiness.Event(true,true,true,true,"Connected","Connected","Connecting","Connecting");
        h.readiness.Poll(true,0);
        h.Emit("HELLO", new { read_only = true });
        switch (args[0]) {
            case "disconnected_connected": update.PriceStatus = ConnectionStatus.Disconnected; break;
            case "connected_connected": break;
            case "disconnected_disconnected": update.PriceStatus = h.source.price = ConnectionStatus.Disconnected; break;
            case "connected_disconnected": h.source.price = ConnectionStatus.Disconnected; break;
            case "previous_connected_disconnected": update.PreviousPriceStatus = ConnectionStatus.Connected;
                update.PriceStatus = h.source.price = ConnectionStatus.Disconnected; break;
            case "previous_disconnected_connected": update.PreviousPriceStatus = ConnectionStatus.Disconnected;
                update.PreviousStatus = ConnectionStatus.Disconnected; break;
            case "connecting_connected": update.PriceStatus = ConnectionStatus.Connecting; break;
            case "current_connecting": h.source.price = ConnectionStatus.Connecting; break;
            case "current_connection_lost": h.source.price = ConnectionStatus.ConnectionLost; break;
            case "different_connection": update.Connection = new Connection(); break;
            case "unknown_source": h.source = null; break;
            case "unknown_event": update = null; break;
            case "unknown_callback_connection": update.Connection = null; break;
            case "unknown_status": update.Status = (ConnectionStatus)999; break;
            case "unknown_current_price": h.source.price = (ConnectionStatus)999; break;
            case "unknown_current_status": h.source.Status = (ConnectionStatus)999; break;
            case "unknown_previous_price": update.PreviousPriceStatus = (ConnectionStatus)999; break;
            case "unknown_previous_status": update.PreviousStatus = (ConnectionStatus)999; break;
            case "unknown_provider": h.source.Options.Provider = (Provider)999; break;
            case "missing_options": h.source.Options = null; break;
            case "provider_mismatch": h.source.Options.Provider = Provider.Other; break;
            case "adapter_disconnected_price_connected": update.Status = h.source.Status = ConnectionStatus.Disconnected; break;
            case "contradictory_adapter": update.Status = ConnectionStatus.Disconnected; break;
            case "changing_current_snapshot": h.source.changeOnSecondRead = true; break;
            case "changing_adapter_snapshot": h.source.changeStatusOnSecondRead = true; break;
            case "diagnostic_io_failure": h.connectionWriter.Dispose(); break;
            case "inactive": h.writer.Dispose(); h.writer = null; h.source = null; break;
            case "rapid_ordering": break;
            case "startup_disconnected_connecting_connected":
                update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.Disconnected; break;
            case "startup_connecting_connected":
                update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.Connecting; break;
            case "observed_native_startup":
            case "rapid_superseded_startup":
                update.PreviousPriceStatus = update.PreviousStatus = ConnectionStatus.Disconnected;
                update.PriceStatus = update.Status = ConnectionStatus.Connecting; break;
            case "connected_to_connecting": update.PriceStatus = update.Status = ConnectionStatus.Connecting; break;
            case "rapid_ordered_connected": update.PreviousPriceStatus = update.PreviousStatus = ConnectionStatus.Connecting; break;
            case "connected_to_lost": break;
            case "closed_market_connected": break;
            case "closed_market_disconnected":
                update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.Disconnected; break;
            case "heartbeat_current_disconnect": break;
            default: throw new Exception("Unknown test case");
        }
        h.OnConnectionStatusUpdate(update);
        if (args[0] == "rapid_ordering") {
            // Healthy callback, then stale-looking loss: must latch, never auto-recover.
            update.PriceStatus = ConnectionStatus.Disconnected;
            h.OnConnectionStatusUpdate(update);
            update.PriceStatus = ConnectionStatus.Connected;
            h.OnConnectionStatusUpdate(update);
        }
        if (args[0] == "startup_disconnected_connecting_connected") {
            update.PreviousPriceStatus = update.PreviousStatus = ConnectionStatus.Disconnected;
            update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.Connecting;
            h.OnConnectionStatusUpdate(update);
        }
        if (args[0].StartsWith("startup_") || args[0] == "rapid_superseded_startup"
            || args[0] == "rapid_ordered_connected") {
            update.PreviousPriceStatus = update.PreviousStatus = update.PriceStatus;
            update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.Connected;
            h.OnConnectionStatusUpdate(update);
        }
        if (args[0] == "connected_to_lost") {
            update.PreviousPriceStatus = update.PreviousStatus = ConnectionStatus.Connected;
            update.PriceStatus = update.Status = h.source.price = h.source.Status = ConnectionStatus.ConnectionLost;
            h.OnConnectionStatusUpdate(update);
        }
        if (args[0] == "heartbeat_current_disconnect") h.source.price = ConnectionStatus.Disconnected;
        if (args[0].StartsWith("closed_market_") || args[0] == "heartbeat_current_disconnect") {
            // Controlled timer invocations, no fabricated ticks or wall-clock soak claim.
            for (int tick = 0; tick < 4; tick++) h.Heartbeat(null, EventArgs.Empty);
        }
        bool failedBeforeCleanup = h.failed;
        bool writersClosedByStop = h.writer == null && h.connectionWriter == null;
        long sequenceBeforeCleanup = h.sequence;
        long diagnosticSequenceBeforeCleanup = h.connectionSequence;
        if (h.failed) {
            // Even a later objectively connected snapshot cannot undo the fail latch.
            h.source = new Connection();
            h.OnConnectionStatusUpdate(new ConnectionStatusEventArgs { Connection = h.source });
            if (h.sequence != sequenceBeforeCleanup || h.connectionSequence != diagnosticSequenceBeforeCleanup)
                throw new Exception("Failed stream restarted");
        }
        if (h.writer != null) h.writer.Dispose();
        if (h.connectionWriter != null) h.connectionWriter.Dispose();
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            failed = failedBeforeCleanup, writers_closed = writersClosedByStop,
            market = Encoding.UTF8.GetString(market.ToArray()),
            diagnostics = Encoding.UTF8.GetString(diagnostic.ToArray()) }));
    }
}
'''
    folder = tmp_path_factory.mktemp("native_callback")
    cs, exe = folder / "CallbackHarness.cs", folder / "CallbackHarness.exe"
    cs.write_text(harness)
    result = subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(exe),
                             "/reference:" + str(framework / "System.Web.Extensions.dll"), str(cs)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    return exe


@pytest.mark.parametrize("case,decision", [
    ("disconnected_connected", "STOP_CONNECTION_LOSS_EVENT"),
    ("connected_connected", "CONTINUE"),
    ("disconnected_disconnected", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("connected_disconnected", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("previous_connected_disconnected", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("previous_disconnected_connected", "STOP_RECONNECT_OR_UNPROVEN_CONTINUITY"),
    ("connecting_connected", "STOP_CONNECTION_REGRESSION"),
    ("current_connecting", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("current_connection_lost", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("different_connection", "STOP_CONNECTION_IDENTITY_MISMATCH"),
    ("unknown_source", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_event", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_callback_connection", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_status", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_current_price", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_current_status", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_previous_price", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_previous_status", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("unknown_provider", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("missing_options", "STOP_UNKNOWN_CONNECTION_STATE"),
    ("provider_mismatch", "STOP_CONNECTION_IDENTITY_MISMATCH"),
    ("adapter_disconnected_price_connected", "STOP_CURRENT_CONNECTION_NOT_READY"),
    ("contradictory_adapter", "STOP_CONNECTION_LOSS_EVENT"),
    ("changing_current_snapshot", "STOP_UNSTABLE_CONNECTION_STATE"),
    ("changing_adapter_snapshot", "STOP_UNSTABLE_CONNECTION_STATE"),
    ("diagnostic_io_failure", "STOP_CONNECTION_DIAGNOSTIC_FAILED"),
    ("inactive", None),
    ("rapid_ordering", "STOP_CONNECTION_LOSS_EVENT"),
])
def test_actual_native_callback_adjudication(native_callback_harness, case, decision):
    result = subprocess.run([str(native_callback_harness), case], capture_output=True, text=True)
    assert result.returncode == 0, "Isolated native callback harness failed"
    assert "PRIVATE_SENTINEL" not in result.stdout
    observation = json.loads(result.stdout)
    market = [json.loads(line) for line in observation["market"].splitlines()]
    diagnostics = [json.loads(line) for line in observation["diagnostics"].splitlines()]
    stopped = decision is not None and decision != "CONTINUE"
    assert observation["failed"] is stopped
    assert observation["writers_closed"] is stopped
    assert [row["sequence"] for row in market] == list(range(len(market)))
    assert [row["kind"] for row in market] == (["HELLO", "DISCONNECTED"] if stopped else ["HELLO"])
    if stopped:
        assert market[-1]["payload"]["reason"] == decision
    if case in {"inactive", "diagnostic_io_failure"}:
        assert diagnostics == []
        return
    assert len(diagnostics) == (2 if case == "rapid_ordering" else 1)
    assert [row["sequence"] for row in diagnostics] == list(range(len(diagnostics)))
    assert diagnostics[-1]["payload"]["decision"] == decision
    for row in diagnostics:
        assert row["schema"] == "arms.nt.connection-diagnostic.v1"
        assert row["session"] == market[0]["session"]
        assert row["kind"] == "CONNECTION_STATUS" and row["market_next_sequence"] == 1
        assert row["event_time"].endswith("Z") and row["callback_received_time"].endswith("Z")
        assert set(row["payload"]) == {
            "callback_price_status", "callback_previous_price_status", "callback_connection_status",
            "callback_previous_connection_status", "source_price_status", "source_connection_status",
            "source_price_status_after", "source_connection_status_after", "same_source",
            "source_present", "callback_present", "source_snapshot_stable", "callback_provider",
            "source_provider", "decision"}
    if case == "previous_disconnected_connected":
        assert diagnostics[0]["payload"]["callback_previous_price_status"] == "Disconnected"
    if case == "disconnected_connected":
        assert diagnostics[0]["payload"]["callback_price_status"] == "Disconnected"
        assert diagnostics[0]["payload"]["source_price_status"] == "Connected"
    if case == "different_connection":
        assert diagnostics[0]["payload"]["same_source"] is False
    if case == "rapid_ordering":
        assert diagnostics[0]["payload"]["decision"] == "CONTINUE"


@pytest.mark.parametrize("case,decisions,stop,heartbeats", [
    ("startup_disconnected_connecting_connected", ["STOP_CURRENT_CONNECTION_NOT_READY"], "STOP_CURRENT_CONNECTION_NOT_READY", 0),
    ("startup_connecting_connected", ["STOP_CURRENT_CONNECTION_NOT_READY"], "STOP_CURRENT_CONNECTION_NOT_READY", 0),
    ("observed_native_startup", ["STOP_RECONNECT_OR_UNPROVEN_CONTINUITY"], "STOP_RECONNECT_OR_UNPROVEN_CONTINUITY", 0),
    ("rapid_superseded_startup", ["STOP_RECONNECT_OR_UNPROVEN_CONTINUITY"], "STOP_RECONNECT_OR_UNPROVEN_CONTINUITY", 0),
    ("connected_to_connecting", ["STOP_CONNECTION_REGRESSION"], "STOP_CONNECTION_REGRESSION", 0),
    ("rapid_ordered_connected", ["STOP_RECONNECT_OR_UNPROVEN_CONTINUITY"], "STOP_RECONNECT_OR_UNPROVEN_CONTINUITY", 0),
    ("connected_to_lost", ["CONTINUE", "STOP_CURRENT_CONNECTION_NOT_READY"], "STOP_CURRENT_CONNECTION_NOT_READY", 0),
    ("closed_market_connected", ["CONTINUE"], None, 4),
    ("closed_market_disconnected", ["STOP_CURRENT_CONNECTION_NOT_READY"], "STOP_CURRENT_CONNECTION_NOT_READY", 0),
    ("heartbeat_current_disconnect", ["CONTINUE"], "HEARTBEAT_SOURCE_VALIDATION_FAILED", 0),
])
def test_startup_sequences_and_no_tick_heartbeat(native_callback_harness, case, decisions, stop, heartbeats):
    result = subprocess.run([str(native_callback_harness), case], capture_output=True, text=True)
    assert result.returncode == 0, "Isolated native sequence harness failed"
    observation = json.loads(result.stdout)
    assert "PRIVATE_SENTINEL" not in result.stdout
    diagnostics = [json.loads(line) for line in observation["diagnostics"].splitlines()]
    market = [json.loads(line) for line in observation["market"].splitlines()]
    assert [row["payload"]["decision"] for row in diagnostics] == decisions
    assert [row["kind"] for row in market] == ["HELLO"] + ["HEARTBEAT"] * heartbeats + (["DISCONNECTED"] if stop else [])
    assert observation["failed"] is (stop is not None)
    assert observation["writers_closed"] is (stop is not None)
    assert [row["sequence"] for row in market] == list(range(len(market)))
    if stop:
        assert market[-1]["payload"]["reason"] == stop
    if case == "observed_native_startup":
        p = diagnostics[0]["payload"]
        assert p["callback_price_status"] == p["callback_connection_status"] == "Connecting"
        assert p["callback_previous_price_status"] == p["callback_previous_connection_status"] == "Disconnected"
        assert p["source_price_status"] == p["source_price_status_after"] == "Connected"
        assert p["source_connection_status"] == p["source_connection_status_after"] == "Connected"
        assert p["same_source"] and p["source_snapshot_stable"]
