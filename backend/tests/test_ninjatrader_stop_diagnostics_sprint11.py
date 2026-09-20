"""Execute the real exporter stop/serialization methods without loading NinjaTrader.

Only Print and the timer are replaced with fault-injecting doubles. No native
account, connection, chart, market series or installed user script is invoked.
"""
import json
from pathlib import Path
import subprocess

import pytest


def _method(source, signature):
    start = source.index(signature)
    opened = source.index("{", start)
    depth = 1
    end = opened + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def test_real_native_stop_serialization_redaction_and_cleanup(tmp_path):
    framework = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319")
    compiler = framework/"csc.exe"
    if not compiler.exists():
        pytest.skip("Native diagnostic harness requires Windows .NET Framework compiler")
    source = (Path(__file__).resolve().parents[2]/"integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    methods = "\n".join(_method(source, signature) for signature in (
        "private void Emit(", "private static string ErrorCode(", "private void Stop("))
    harness = r'''
using System;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;
public class StopHarness {
    private StreamWriter writer;
    private StreamWriter connectionWriter;
    private FaultTimer timer;
    private bool failed;
    private long sequence;
    private string session = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
    private bool printFails;
    class FaultTimer {
        public event EventHandler Tick;
        public void Stop() { throw new InvalidOperationException("PRIVATE_SENTINEL"); }
    }
    private void Heartbeat(object sender, EventArgs args) {}
    private void Print(string text) { if (printFails) throw new IOException("PRIVATE_SENTINEL"); }
''' + methods + r'''
    public static void Main(string[] args) {
        var errors = new Exception[] { new NullReferenceException("PRIVATE_SENTINEL"),
            new InvalidOperationException("PRIVATE_SENTINEL"), new UnauthorizedAccessException("PRIVATE_SENTINEL"),
            new IOException("PRIVATE_SENTINEL"), new ArgumentException("PRIVATE_SENTINEL"),
            new Exception("PRIVATE_SENTINEL") };
        for (int index = 0; index < errors.Length; index++) {
            var h = new StopHarness();
            h.writer = new StreamWriter(Path.Combine(args[0], index + ".jsonl"), false, new UTF8Encoding(false));
            h.connectionWriter = new StreamWriter(Path.Combine(args[0], index + ".connection.jsonl"));
            h.timer = new FaultTimer(); h.printFails = true;
            h.Stop("STARTUP_HEARTBEAT_SCHEDULE_FAILED", ErrorCode(errors[index]));
            h.Stop("TERMINATED");
            if (!h.failed || h.writer != null || h.connectionWriter != null || h.timer != null || h.sequence != 1)
                throw new Exception("stop did not contain or close exactly once");
        }
        var early = new StopHarness();
        early.Stop("CHART_UNAVAILABLE");
        if (!early.failed || early.sequence != 0) throw new Exception("pre-file failure");
    }
}
'''
    cs, exe = tmp_path/"StopHarness.cs", tmp_path/"StopHarness.exe"
    cs.write_text(harness)
    compile_result = subprocess.run([str(compiler), "/nologo", "/target:exe", "/out:"+str(exe),
        "/reference:"+str(framework/"System.Web.Extensions.dll"), str(cs)], capture_output=True, text=True)
    assert compile_result.returncode == 0, compile_result.stdout
    result = subprocess.run([str(exe), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, "native isolated stop harness failed"
    for index, code in enumerate(("NULL_REFERENCE", "INVALID_OPERATION", "ACCESS_DENIED", "IO_ERROR", "INVALID_ARGUMENT", "OTHER")):
        raw = (tmp_path/f"{index}.jsonl").read_text()
        assert "PRIVATE_SENTINEL" not in raw
        lines = raw.splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["sequence"] == 0 and event["kind"] == "DISCONNECTED"
        assert event["payload"] == dict(connected=False, reason="STARTUP_HEARTBEAT_SCHEDULE_FAILED", error_code=code)
