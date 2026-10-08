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
        if (c.StartsWith("snapshot_")) {
            Check(g.Snapshot(true,true,true,true,true,true,0)=="WAIT_STARTUP_ALIGNMENT");
            Check(!g.Poll(true,0));
            if(c=="snapshot_single")return;
            if(c=="snapshot_source_change")Check(g.Snapshot(true,true,true,true,false,true,500)=="STOP_CONNECTION_IDENTITY_MISMATCH");
            else if(c=="snapshot_provider_change")Check(g.Snapshot(true,false,true,true,true,false,500)=="STOP_CONNECTION_IDENTITY_MISMATCH");
            else if(c=="snapshot_unknown")Check(g.Snapshot(true,true,false,true,true,false,500)=="STOP_UNKNOWN_CONNECTION_STATE");
            else if(c=="snapshot_unstable")Check(g.Snapshot(true,true,true,false,true,true,500)=="STOP_UNSTABLE_CONNECTION_STATE");
            else if(c=="snapshot_price_not_connected")Check(g.Snapshot(false,true,true,true,true,false,500)=="STOP_UNSTABLE_CONNECTION_STATE");
            else {
                double second=c=="snapshot_too_soon"?100:c=="snapshot_too_late"?1500:500;
                string expected=(second>=250 && second<=1000)?"CONTINUE":"WAIT_STARTUP_ALIGNMENT";
                Check(g.Snapshot(true,true,true,true,true,true,second)==expected);
                if(expected!="CONTINUE")Check(g.Snapshot(true,true,true,true,true,true,second+500)=="CONTINUE");
                Check(g.AlignmentProvenance=="STARTUP_ALIGNMENT_STABLE_SNAPSHOT");
                Check(g.Poll(true,second+500));Check(g.State=="READY");
            }
            return;
        }
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
        if(safe)Check(g.AlignmentProvenance=="STARTUP_ALIGNMENT_CALLBACK");
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


@pytest.mark.parametrize("case", [
    "snapshot_single", "snapshot_stable", "snapshot_too_soon",
    "snapshot_too_late", "snapshot_source_change", "snapshot_provider_change",
    "snapshot_unknown", "snapshot_unstable", "snapshot_price_not_connected",
])
def test_stable_snapshot_alignment_invariants(readiness_harness, case):
    result = subprocess.run(
        [str(readiness_harness), case], capture_output=True, text=True)
    assert result.returncode == 0, "Snapshot alignment invariant failed"
