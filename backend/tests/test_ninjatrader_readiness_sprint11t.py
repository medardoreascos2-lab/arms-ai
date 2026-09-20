"""Readiness state-machine tests; no provider, account or order interface."""
from pathlib import Path
import subprocess

import pytest

from backend.tests.test_ninjatrader_stop_diagnostics_sprint11 import _method

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def readiness_harness(tmp_path_factory):
    source = (ROOT / "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    signature = "private sealed class ReadinessGate"
    gate = _method(source, signature)
    folder = tmp_path_factory.mktemp("readiness")
    cs, exe = folder / "Gate.cs", folder / "Gate.exe"
    cs.write_text('using System; using System.Linq; public class Harness {\n' + gate + r'''
    static void Check(bool ok) { if (!ok) throw new Exception("Readiness invariant failed"); }
    public static void Main(string[] args) {
        var g = new ReadinessGate();
        Check(!g.Poll(true, 0)); // No callback evidence; no admission.
        var c = args[0];
        bool healthy=true, identity=true, known=true, stable=true;
        string price="Connected", status="Connected", previous="Connecting";
        if (c == "provider_mismatch" || c == "source_mismatch") identity=false;
        if (c == "unknown" || c == "null") known=false;
        if (c == "unstable") stable=false;
        if (c == "current_loss" || c == "closed_disconnected") healthy=false;
        if (c == "price_loss") price="ConnectionLost";
        if (c == "connection_loss") status="Disconnected";
        if (c == "callback_loss_current_connected") price="Disconnected";
        if (c == "startup" || c == "transition_pair" || c == "duplicates") {
            Check(g.Event(true,true,true,true,"Connecting","Connecting","Disconnected","Disconnected") == "WAIT_STARTUP_ALIGNMENT");
            Check(!g.Poll(true, 100));
            Check(g.State == "STARTING");
            if (c == "startup") { Check(!g.Poll(true,30000)); Check(g.State=="STOPPED"); return; }
        }
        g.Event(healthy,identity,known,stable,price,status,previous,previous);
        bool safe=healthy && identity && known && stable && price=="Connected" && status=="Connected";
        Check(g.State != "READY"); // Callback grants nothing.
        Check(g.Poll(healthy, 5000) == safe);
        if (c == "duplicates") {
            for(int i=0;i<50;i++) Check(g.Event(true,true,true,true,"Connected","Connected","Connected","Connected")=="CONTINUE");
        }
        if(c == "reconnect" || c == "rapid_ordering") {
            Check(g.State == "READY");
            g.Event(true,true,true,true,"Connecting","Connecting","Connected","Connected");
            g.Event(true,true,true,true,"Connected","Connected","Connecting","Connecting");
            Check(!g.Poll(true, 6000)); Check(g.State=="STOPPED");
        } else if (safe) Check(g.Poll(true,20000));
        else { g.Event(true,true,true,true,"Connected","Connected","Connecting","Connecting"); Check(!g.Poll(true,6000)); }
        if(c=="stable" || c=="closed_connected") { Check(!g.Poll(false,21000)); Check(!g.Poll(true,22000)); }
    }
}''')
    compiler = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    result = subprocess.run([str(compiler), "/nologo", "/out:"+str(exe), str(cs)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    return exe


@pytest.mark.parametrize("case", ["startup", "transition_pair", "stable", "current_loss",
    "price_loss", "connection_loss", "provider_mismatch", "source_mismatch", "unstable",
    "unknown", "null", "closed_connected", "closed_disconnected", "reconnect",
    "rapid_ordering", "duplicates", "callback_loss_current_connected"])
def test_readiness_invariants(readiness_harness, case):
    result = subprocess.run([str(readiness_harness), case], capture_output=True, text=True)
    assert result.returncode == 0, "Isolated readiness invariant failed"
