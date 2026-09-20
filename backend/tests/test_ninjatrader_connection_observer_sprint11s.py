"""Whole-source observer tests: metadata-only native API, manual monotonic clock/timers.

No NinjaTrader process is loaded. These tests cannot certify native event ordering.
"""
import json
from pathlib import Path
import re
import subprocess

import pytest

from backend.tests.test_ninjatrader_market_sprint11 import setup, api_settings


SOURCE = Path(__file__).resolve().parents[2] / "integrations/ninjatrader/ArmsConnectionObserverV1.cs"


@pytest.fixture(scope="module")
def observer_harness(tmp_path_factory):
    framework = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    compiler = framework / "csc.exe"
    if not compiler.exists():
        pytest.skip("Native observer harness requires Windows .NET Framework compiler")
    folder = tmp_path_factory.mktemp("native_observer")
    # Replace only time dependencies, leaving all observer method bodies intact.
    source = SOURCE.read_text().replace("using System.Diagnostics;", "using Stopwatch = ObserverDoubles.Clock;")
    source = source.replace("using System.Threading;", "using Timer = ObserverDoubles.ManualTimer;\nusing Timeout = System.Threading.Timeout;")
    cs = folder / "ArmsConnectionObserverV1.cs"
    cs.write_text(source)
    doubles = folder / "Harness.cs"
    doubles.write_text(r'''
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
namespace ObserverDoubles {
    public class Clock {
        public static double Now;
        private double origin, stoppedAt;
        private bool running;
        public void Start() { origin = Now; running = true; }
        public void Stop() { stoppedAt = Now; running = false; }
        public TimeSpan Elapsed { get { return TimeSpan.FromMilliseconds((running ? Now : stoppedAt) - origin); } }
    }
    public class ManualTimer : IDisposable {
        public static readonly List<ManualTimer> All = new List<ManualTimer>();
        public static bool ThrowOnDispose, DeadlineFirst;
        public bool Disposed;
        public double Due;
        public int Period;
        private System.Threading.TimerCallback callback;
        private object state;
        public ManualTimer(System.Threading.TimerCallback cb, object s, int due, int period) {
            callback = cb; state = s; Due = Clock.Now + due; Period = period; All.Add(this);
        }
        public void Dispose() { Disposed = true; if (ThrowOnDispose) throw new IOException("PRIVATE_SENTINEL"); }
        public void QueuedCallback() { callback(state); }
        public static void Advance(double target) {
            while (true) {
                var timer = All.Where(t => !t.Disposed && t.Due <= target)
                    .OrderBy(t => t.Due).ThenBy(t => DeadlineFirst && t.Period < 0 ? 0 : 1).FirstOrDefault();
                if (timer == null) break;
                Clock.Now = Math.Max(Clock.Now, timer.Due);
                timer.Due = timer.Period < 0 ? Double.PositiveInfinity : timer.Due + timer.Period;
                timer.QueuedCallback();
            }
            Clock.Now = Math.Max(Clock.Now, target);
        }
    }
}
namespace NinjaTrader.Cbi {
    public enum ConnectionStatus { Disconnected, Connecting, Connected, Disconnecting, ConnectionLost }
    public enum Provider { Provider31, Other }
    public class ConnectionOptions {
        public Provider Provider = Provider.Provider31;
        public string Name { get { throw new Exception("PRIVATE_SENTINEL"); } }
    }
    public class Connection {
        public static readonly List<Connection> Connections = new List<Connection>();
        public static event EventHandler<ConnectionStatusEventArgs> ConnectionStatusUpdate;
        public static int Subscribers { get { return ConnectionStatusUpdate == null ? 0 : ConnectionStatusUpdate.GetInvocationList().Length; } }
        public static void Raise(ConnectionStatusEventArgs e) { if (ConnectionStatusUpdate != null) ConnectionStatusUpdate(null, e); }
        public ConnectionOptions Options = new ConnectionOptions();
        public ConnectionStatus price = ConnectionStatus.Connected, status = ConnectionStatus.Connected;
        public bool Fault, Flip, CrossDeadline;
        private int reads;
        public ConnectionStatus PriceStatus { get { if (Fault) throw new Exception("PRIVATE_SENTINEL"); return price; } }
        public ConnectionStatus Status {
            get {
                if (Fault) throw new Exception("PRIVATE_SENTINEL");
                if (CrossDeadline) ObserverDoubles.Clock.Now = 30000;
                return Flip && ++reads % 2 == 0 ? ConnectionStatus.Disconnected : status;
            }
        }
    }
    public class ConnectionStatusEventArgs {
        public Connection Connection;
        public ConnectionStatus Status = ConnectionStatus.Connected, PreviousStatus = ConnectionStatus.Disconnected;
        public ConnectionStatus PriceStatus = ConnectionStatus.Connected, PreviousPriceStatus = ConnectionStatus.Disconnected;
        public string NativeError { get { throw new Exception("PRIVATE_SENTINEL"); } }
    }
}
namespace NinjaTrader.NinjaScript {
    public enum State { SetDefaults, Configure, DataLoaded, Historical, Transition, Realtime, Terminated }
    public class NinjaScriptPropertyAttribute : Attribute {}
    // No accounts, orders, market series, admission, network or execution API exists here.
    public class Indicator {
        public State State;
        public string Name, Description;
        public bool IsOverlay, IsChartOnly, IsSuspendedWhileInactive;
        protected virtual void OnStateChange() {}
        protected virtual void OnConnectionStatusUpdate(ConnectionStatusEventArgs e) {}
        protected void Print(string value) { if (value.Contains("PRIVATE_SENTINEL")) throw new Exception("Leak"); }
    }
}
public class Host : NinjaTrader.NinjaScript.Indicators.ArmsConnectionObserverV1 {
    public void Step(State state) { State = state; OnStateChange(); }
    public void Send(ConnectionStatusEventArgs e) { OnConnectionStatusUpdate(e); }
}
public class Harness {
    private static System.Threading.ManualResetEventSlim held = new System.Threading.ManualResetEventSlim();
    private static System.Threading.ManualResetEventSlim release = new System.Threading.ManualResetEventSlim();
    private static System.Threading.Thread HoldRegistry() {
        var thread = new System.Threading.Thread(() => {
            lock (Connection.Connections) {
                held.Set();
                if (!release.Wait(3000)) throw new Exception("Registry test timed out");
            }
        });
        thread.Start();
        if (!held.Wait(3000)) throw new Exception("Registry test failed to start");
        return thread;
    }
    public static void Main(string[] args) {
        var selected = new Connection();
        if (args[0] != "no_source" && args[0] != "late_source") Connection.Connections.Add(selected);
        if (args[0] == "ambiguous") Connection.Connections.Add(new Connection());
        if (args[0] == "closed_disconnected") selected.price = selected.status = ConnectionStatus.Disconnected;
        var host = new Host(); host.Step(State.SetDefaults);
        host.OutputDirectory = args[1]; host.ExpectedProvider = "Provider31";
        host.Send(null); // Prior to DataLoaded: no file or authority.
        if (Directory.GetFiles(args[1]).Length != 0) throw new Exception("Premature file");
        var registryThread = args[0] == "registry_busy_start" ? HoldRegistry() : null;
        host.Step(State.DataLoaded); host.Step(State.Historical); host.Step(State.Transition); host.Step(State.Realtime);
        if (registryThread != null) { release.Set(); registryThread.Join(); }
        var e = new ConnectionStatusEventArgs { Connection = selected };
        switch (args[0]) {
            case "normal": break;
            case "contradiction":
                e.PriceStatus = e.Status = ConnectionStatus.Connecting;
                host.Send(e); Connection.Raise(e);
                e.PreviousPriceStatus = e.PreviousStatus = ConnectionStatus.Connecting;
                e.PriceStatus = e.Status = ConnectionStatus.Connected; break;
            case "duplicates": host.Send(e); break;
            case "source_mismatch": e.Connection = new Connection(); break;
            case "provider_mismatch": e.Connection = new Connection(); e.Connection.Options.Provider = Provider.Other; break;
            case "null_event": e = null; break;
            case "null_connection": e.Connection = null; break;
            case "no_source": break;
            case "late_source": Connection.Connections.Add(selected); break;
            case "ambiguous": break;
            case "unknown_enum": selected.price = (ConnectionStatus)999; e.Status = (ConnectionStatus)999; break;
            case "unknown_provider": selected.Options.Provider = (Provider)999; break;
            case "null_options": selected.Options = null; break;
            case "read_fault": selected.Fault = true; break;
            case "source_removed": Connection.Connections.Remove(selected); break;
            case "source_replaced": Connection.Connections.Remove(selected); e.Connection = new Connection(); Connection.Connections.Add(e.Connection); break;
            case "instability": selected.Flip = true; break;
            case "closed_disconnected": e.PriceStatus = e.Status = ConnectionStatus.Disconnected; break;
            case "host_terminate": ObserverDoubles.ManualTimer.Advance(5000); host.Step(State.Terminated); break;
            case "record_limit": for (int i = 0; i < 600; i++) host.Send(e); break;
            case "io_failure":
                var field = typeof(NinjaTrader.NinjaScript.Indicators.ArmsConnectionObserverV1).GetField("writer", BindingFlags.Instance | BindingFlags.NonPublic);
                ((StreamWriter)field.GetValue(host)).Dispose(); break;
            case "cleanup_fault": ObserverDoubles.ManualTimer.ThrowOnDispose = true; break;
            case "late_callback": ObserverDoubles.Clock.Now = 31000; break;
            case "cross_deadline": selected.CrossDeadline = true; break;
            case "deadline_first": ObserverDoubles.ManualTimer.DeadlineFirst = true; break;
            case "repeat_dataloaded": host.Step(State.DataLoaded); break;
            case "registry_busy_start": break;
            case "registry_busy_callback": registryThread = HoldRegistry(); break;
            default: throw new Exception("Unknown case");
        }
        host.Send(e);
        if (registryThread != null) { release.Set(); registryThread.Join(); }
        ObserverDoubles.ManualTimer.Advance(32000);
        var files = Directory.GetFiles(args[1], "*.observer.jsonl");
        if (files.Length != 1) throw new Exception("Session count");
        var before = File.ReadAllText(files[0]);
        Connection.Raise(e); host.Send(e);
        foreach (var timer in ObserverDoubles.ManualTimer.All) timer.QueuedCallback();
        host.Step(State.DataLoaded); host.Step(State.Terminated);
        var after = File.ReadAllText(files[0]);
        if (before != after || Connection.Subscribers != 0 || ObserverDoubles.ManualTimer.All.Any(t => !t.Disposed))
            throw new Exception("Cleanup or latch failure");
        // Exclusive open proves writer handle released; no old evidence is touched.
        using (var exclusive = new FileStream(files[0], FileMode.Open, FileAccess.Read, FileShare.None)) {}
        Console.WriteLine(new JavaScriptSerializer().Serialize(new { records = after, subscribers = Connection.Subscribers }));
    }
}
''')
    exe = folder / "ObserverHarness.exe"
    result = subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(exe),
                             "/reference:" + str(framework / "System.Web.Extensions.dll"),
                             "/reference:" + str(framework / "System.ComponentModel.DataAnnotations.dll"),
                             str(cs), str(doubles)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    return exe


CASES = ["normal", "contradiction", "duplicates", "source_mismatch", "provider_mismatch",
         "null_event", "null_connection", "no_source", "late_source", "ambiguous", "unknown_enum",
         "unknown_provider", "null_options", "read_fault", "source_removed", "source_replaced",
         "instability", "closed_disconnected", "host_terminate", "record_limit", "io_failure",
         "cleanup_fault", "late_callback", "cross_deadline", "deadline_first", "repeat_dataloaded",
         "registry_busy_start", "registry_busy_callback"]


def run_observer(exe, directory, case):
    result = subprocess.run([str(exe), case, str(directory)], capture_output=True, text=True)
    assert result.returncode == 0, "Isolated whole-source observer harness failed"
    assert "PRIVATE_SENTINEL" not in result.stdout
    output = json.loads(result.stdout)
    assert output["subscribers"] == 0
    return [json.loads(line) for line in output["records"].splitlines()]


@pytest.mark.parametrize("case", CASES)
def test_bounded_observer_lifecycle_and_privacy(observer_harness, tmp_path, case):
    records = run_observer(observer_harness, tmp_path, case)
    assert records[0]["kind"] == "OBSERVER_START"
    assert len({r["session"] for r in records}) == 1
    assert [r["sequence"] for r in records] == list(range(len(records)))
    assert [r["elapsed_ms"] for r in records] == sorted(r["elapsed_ms"] for r in records)
    assert len(records) <= 512
    for r in records:
        assert r["schema"] == "arms.nt.connection-observer.v1"
        assert r["event_time"].endswith("Z") and r["callback_received_time"].endswith("Z")
        assert set(r) == {"schema", "session", "sequence", "event_time", "elapsed_ms",
                          "callback_received_time", "callback_received_elapsed_ms", "channel", "kind",
                          "lifecycle_state", "observer_state", "payload"}
        assert r["payload"]["observation_only"] is True
        if r["kind"] != "OBSERVER_END":
            assert r["elapsed_ms"] < 30000
            assert r["observer_state"] == "OBSERVING"
            assert set(r["payload"]) == {"callback_present", "callback_connection_status",
                "callback_previous_connection_status", "callback_price_status", "callback_previous_price_status",
                "same_source", "callback_provider", "source_provider", "source_connection_status_1",
                "source_price_status_1", "source_connection_status_2", "source_price_status_2", "samples_agree",
                "samples_known", "source_present", "source_registered", "identity_status", "source_selection", "observation_only"}
    if case == "io_failure":
        assert not any(r["kind"] == "OBSERVER_END" for r in records)
        return  # I/O failure closes resources; a complete capture cannot be claimed.
    assert records[-1]["kind"] == "OBSERVER_END" and records[-1]["observer_state"] == "ENDED"
    expected_end = {"host_terminate": "HOST_TERMINATED", "record_limit": "RECORD_LIMIT"}.get(case, "WINDOW_END")
    assert records[-1]["payload"]["reason"] == expected_end
    callbacks = [r for r in records if r["kind"] == "CONNECTION_STATUS"]
    heartbeats = [r for r in records if r["kind"] == "OBSERVATION_HEARTBEAT"]
    if case not in {"host_terminate", "record_limit", "late_callback", "cross_deadline"}:
        assert [r["elapsed_ms"] for r in heartbeats] == list(range(2000, 30000, 2000))
        assert records[-1]["elapsed_ms"] == 30000
    if case == "contradiction":
        assert [r["channel"] for r in callbacks] == ["INDICATOR", "GLOBAL", "INDICATOR"]
        assert [r["payload"]["callback_price_status"] for r in callbacks] == ["Connecting", "Connecting", "Connected"]
        assert all(r["payload"]["source_price_status_1"] == "Connected" for r in callbacks)
    if case == "duplicates":
        assert len(callbacks) == 2 and callbacks[0]["payload"] == callbacks[1]["payload"]
    if case in {"source_mismatch", "provider_mismatch", "source_replaced"}:
        assert callbacks[0]["payload"]["same_source"] is False
    if case == "provider_mismatch":
        assert callbacks[0]["payload"]["callback_provider"] == "Other"
        assert callbacks[0]["payload"]["source_provider"] == "Provider31"
    if case in {"no_source", "late_source", "ambiguous"}:
        assert all(not r["payload"]["source_present"] for r in heartbeats)
    if case in {"source_removed", "source_replaced"}:
        assert callbacks[0]["payload"]["identity_status"] == "PINNED_REMOVED"
    if case == "instability":
        assert callbacks[0]["payload"]["samples_agree"] is False
    if case in {"null_event", "null_connection"}:
        assert callbacks[0]["payload"]["callback_price_status"] == "UNKNOWN"
    if case in {"unknown_enum", "read_fault"}:
        assert callbacks[0]["payload"]["samples_known"] is False
    if case == "closed_disconnected":
        assert all(r["payload"]["source_price_status_1"] == "Disconnected" for r in heartbeats)
    if case == "registry_busy_start":
        assert records[0]["payload"]["source_selection"] == "REGISTRY_UNAVAILABLE"
        assert all(not r["payload"]["source_present"] for r in heartbeats)
    if case == "registry_busy_callback":
        assert callbacks[0]["payload"]["source_registered"] is None
        assert callbacks[0]["payload"]["identity_status"] == "REGISTRY_UNAVAILABLE"
        assert all(r["payload"]["identity_status"] == "PINNED_REGISTERED" for r in heartbeats)


def test_observer_has_only_metadata_surface():
    source = SOURCE.read_text()
    # Whole-source compilation above additionally uses a native API with no account,
    # order or market-series members. No reflective/dynamic escape is permitted.
    code = re.sub(r"//[^\n]*", "", source)
    # Display.Order is UI property ordering, not a trading Order API.
    code = re.sub(r"\[Display\([^\n]*\)\]", "", code)
    for pattern in (r"\bAccount\b", r"\bAccounts\b", r"\bOrder\b", r"\bSubmit\w*\s*\(",
                    r"\bCreateOrder\b", r"\bConnect\s*\(", r"\bDisconnect\s*\(", r"\bCancel\w*\s*\(",
                    r"OnBarUpdate", r"OnMarketData", r"\bInstrument\b", r"\bBars\b",
                    r"\bReflection\b", r"\bdynamic\b", r"DllImport", r"\bProcess\b",
                    r"TcpClient|HttpClient|WebRequest|Socket|NinjaTrader\.Client", r"\.Name\b"):
        assert re.search(pattern, code) is None, pattern
    assert 'schema = "arms.nt.connection-observer.v1"' in source
    assert 'FileMode.CreateNew' in source
    assert 'arms.nt.market.v1' not in source


def test_observer_output_cannot_enter_market_runtime(observer_harness, tmp_path, api_settings):
    observation_dir = tmp_path / "observer"
    observation_dir.mkdir()
    rows = run_observer(observer_harness, observation_dir, "normal")
    reader, _ = setup(tmp_path)
    reader.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(ValueError):
        reader.poll()
    assert reader.service._runtime is None
    assert reader.service.gate.closed_count == reader.candle_sequence == 0
    assert reader.get_snapshot()["external_order_authority"] is False
    reader.close()
