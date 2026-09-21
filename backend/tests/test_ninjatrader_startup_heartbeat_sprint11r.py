"""Deterministic dispatcher interleavings using the real native startup methods.

Chart/dispatcher/timer and SafeSource are doubles. No provider is loaded; manual
timer ticks establish logic, not a native fifteen-second wall-clock milestone.
"""
import json
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_ninjatrader_stop_diagnostics_sprint11 import _method


@pytest.fixture(scope="module")
def startup_harness(tmp_path_factory):
    framework = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    compiler = framework / "csc.exe"
    if not compiler.exists():
        pytest.skip("Native startup harness requires Windows .NET Framework compiler")
    source = (Path(__file__).resolve().parents[2] /
              "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    methods = "\n".join(_method(source, signature) for signature in (
        "protected override void OnStateChange(", "private void Heartbeat(",
        "private sealed class TimingEvidence", "private void Emit(", "private static string ErrorCode(", "private void Stop(", "private sealed class ReadinessGate"))
    harness = r'''
using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Diagnostics;
using System.Web.Script.Serialization;
public enum State { SetDefaults, Realtime, Terminated }
public enum Calculate { OnEachTick }
public class Dispatcher {
    private Action queued;
    public void InvokeAsync(Action action) { queued = action; }
    public void Drain() { var action = queued; queued = null; if (action != null) action(); }
}
public class Chart { public Dispatcher Dispatcher = new Dispatcher(); }
public class DispatcherTimer {
    public static DispatcherTimer Last;
    public bool Running;
    public TimeSpan Interval;
    public event EventHandler Tick;
    public DispatcherTimer() { Last = this; }
    public void Start() { Running = true; }
    public void Stop() { Running = false; }
    public void TickOnce() { if (Running && Tick != null) Tick(this, EventArgs.Empty); }
}
public class InstrumentInfo {
    public string FullName = "NQ DEC26";
    public DateTime Expiry = new DateTime(2026, 12, 1);
}
public class Hours { public string Name = "CME US Index Futures ETH"; }
public class BarInfo { public Hours TradingHours = new Hours(); }
public class Indicator { protected virtual void OnStateChange() {} }
public class StartupHarness : Indicator {
    private readonly object sync = new object();
    private StreamWriter writer, connectionWriter;
    private DispatcherTimer timer;
    private string session, contract, template, expiry;
    private long sequence;
    private int firstRealtimeBar;
    private bool failed, sourceHealthy = true;
    private bool started, helloSent;
    private ReadinessGate readiness = new ReadinessGate();
    private TimingEvidence timing;
    private Stopwatch startupClock = new Stopwatch();
    private System.Threading.Timer startupDeadline;
    private string OutputDirectory, ExpectedProvider = "Provider31", Name, Description;
    private bool IsOverlay, IsChartOnly, IsSuspendedWhileInactive;
    private Calculate Calculate;
    private State State;
    private InstrumentInfo Instrument = new InstrumentInfo();
    private BarInfo Bars = new BarInfo();
    private Chart ChartControl = new Chart();
    private bool SafeSource() { return sourceHealthy; }
    private void Print(string text) {}
''' + methods + r'''
    public static void Main(string[] args) {
        var h = new StartupHarness(); h.OutputDirectory = args[1];
        var dispatcher = h.ChartControl.Dispatcher;
        if (args[0] == "unhealthy_start") h.sourceHealthy = false;
        h.State = State.Realtime; h.OnStateChange();
        h.readiness.Event(true,true,true,true,"Connected","Connected","Connecting","Connecting");
        if (args[0] == "stop_before_dispatch") h.Stop("TEST_STOP");
        if (args[0] == "terminate_before_dispatch") { h.State = State.Terminated; h.OnStateChange(); }
        if (args[0] == "loss_before_dispatch") h.sourceHealthy = false;
        dispatcher.Drain();
        var scheduled = DispatcherTimer.Last;
        if (args[0] == "stop_after_dispatch") h.Stop("TEST_STOP");
        if (scheduled != null) {
            if (scheduled.Interval != TimeSpan.FromSeconds(5)) throw new Exception("Unexpected interval");
            for (int i = 0; i < 4; i++) scheduled.TickOnce();
        }
        bool failedBeforeCleanup = h.failed;
        bool runningBeforeCleanup = scheduled != null && scheduled.Running;
        bool writersClosed = h.writer == null && h.connectionWriter == null;
        h.State = State.Terminated; h.OnStateChange();
        dispatcher.Drain();
        if (scheduled != null) scheduled.TickOnce();
        if (h.writer != null || h.connectionWriter != null || h.timer != null)
            throw new Exception("Shutdown incomplete");
        var marketPath = Directory.GetFiles(args[1], "*.jsonl").SingleOrDefault(p => !p.EndsWith(".connection.jsonl"));
        Console.WriteLine(new JavaScriptSerializer().Serialize(new {
            failed = failedBeforeCleanup, timer_created = scheduled != null,
            timer_running = runningBeforeCleanup, writers_closed = writersClosed,
            market = marketPath == null ? "" : File.ReadAllText(marketPath) }));
    }
}
'''
    folder = tmp_path_factory.mktemp("native_startup")
    cs, exe = folder / "StartupHarness.cs", folder / "StartupHarness.exe"
    cs.write_text(harness)
    compiled = subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:" + str(exe),
                               "/reference:" + str(framework / "System.Web.Extensions.dll"), str(cs)],
                              capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stdout
    return exe


@pytest.mark.parametrize("case,timer_created,heartbeats,reason", [
    ("healthy_no_ticks", True, 4, "TERMINATED"),
    ("unhealthy_start", False, 0, None),
    ("stop_before_dispatch", False, 0, "TEST_STOP"),
    ("terminate_before_dispatch", False, 0, "TERMINATED"),
    ("stop_after_dispatch", True, 0, "TEST_STOP"),
    ("loss_before_dispatch", True, 0, "HEARTBEAT_SOURCE_VALIDATION_FAILED"),
])
def test_actual_startup_and_heartbeat_interleavings(startup_harness, tmp_path, case, timer_created, heartbeats, reason):
    result = subprocess.run([str(startup_harness), case, str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, "Isolated native startup harness failed"
    observation = json.loads(result.stdout)
    market = [json.loads(line) for line in observation["market"].splitlines()]
    assert observation["timer_created"] is timer_created
    assert observation["timer_running"] is (case == "healthy_no_ticks")
    assert observation["failed"] is (case != "healthy_no_ticks")
    assert observation["writers_closed"] is (case != "healthy_no_ticks")
    if reason is None:
        assert market == []
    else:
        assert [row["kind"] for row in market] == (["HELLO"] if heartbeats else []) + ["HEARTBEAT"] * heartbeats + ["DISCONNECTED"]
        assert market[-1]["payload"]["reason"] == reason
        assert [row["sequence"] for row in market] == list(range(len(market)))
