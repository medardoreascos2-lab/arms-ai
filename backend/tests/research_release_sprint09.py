"""Clean CLI-process acceptance driver; no alternate strategy or execution path.

Run from the repository root. Requires the certified local JUN22 sources, an
unused loopback port 8000, and the existing API settings environment. The token
is randomly generated for each child process and never written to evidence.
The optional stdin pause supports read-only browser acceptance before shutdown.
"""
from backend.tests.private_evidence_paths_v1 import private_runtime_manifest
from contextlib import closing
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

MANIFEST = "backend/tests/research_v31/sprint05/predeclared_experiment.json"
CONFIG = "backend/config/paper_research_sprint07r.json"
BASELINE = "backend/tests/research_sprint07r/JUN22_80_5_C3_fee5_0.json"


def cli_child():
    """Invoke the documented CLI unchanged; stdin replaces operator Ctrl+C."""
    import signal
    from backend.api.paper_rc_app_v1 import main

    def stop_on_stdin():
        if sys.stdin.readline().strip() == "stop":
            signal.raise_signal(signal.SIGINT)

    threading.Thread(target=stop_on_stdin, daemon=True).start()
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    try:
        main()
    except KeyboardInterrupt:
        pass  # Uvicorn re-raises the captured operator signal after lifespan exit.


class CliProcess:
    def __init__(self, state, log):
        self.token = secrets.token_urlsafe(32)
        env = dict(os.environ, ARMS_ADMIN_TOKEN=self.token)
        self.log = log.open("w", encoding="utf-8")
        self.process = subprocess.Popen([
            sys.executable, "-m", "backend.tests.research_release_sprint09", "child",
            "--manifest", str(private_runtime_manifest(MANIFEST)), "--contract", "JUN22", "--config", CONFIG,
            "--state", str(state), "--initialization-policy", "NEW_ISOLATED_PAPER_ACCOUNT",
        ], stdin=subprocess.PIPE, stdout=self.log, stderr=self.log, text=True,
            env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10)
        try:
            for _ in range(120):
                if self.process.poll() is not None:
                    raise AssertionError("CLI exited before health became available")
                try:
                    if self.request("GET", "/health")[0] == 200:
                        break
                except OSError:
                    self.connection.close()
                    time.sleep(.25)
            else:
                raise AssertionError("CLI startup timeout")
        except BaseException:
            self.close()
            raise

    def request(self, method, path):
        headers = {"X-ARMS-ADMIN-TOKEN": self.token} if method == "POST" else {}
        self.connection.request(method, path, headers=headers)
        response = self.connection.getresponse()
        return response.status, json.loads(response.read())

    def get(self):
        status, body = self.request("GET", "/api/v2/backtesting/dashboard")
        assert status == 200
        return body["paper_research"]

    def command(self, name, status=200):
        code, result = self.request("POST", "/api/v2/paper/" + name)
        assert code == status, (name, code, result)
        return result

    def close(self):
        self.connection.close()
        if self.process.poll() is None:
            self.process.stdin.write("stop\n")
            self.process.stdin.flush()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.terminate()  # Only our owned child; never an external server.
                self.process.wait(timeout=10)
                raise AssertionError("CLI did not shut down gracefully")
            finally:
                self.process.stdin.close()
                self.log.close()
        else:
            self.process.stdin.close()
            self.log.close()
        assert self.process.returncode == 0, self.process.returncode


def durable(state):
    with closing(sqlite3.connect(state.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        payload, digest = db.execute("SELECT payload,digest FROM checkpoint WHERE id=1").fetchone()
        assert sha256(payload.encode()).hexdigest() == digest
        return {"checkpoint": json.loads(payload),
                "events": db.execute("SELECT count(*) FROM events").fetchone()[0],
                "pending": db.execute("SELECT count(*) FROM events WHERE phase='INFLIGHT'").fetchone()[0],
                "journal": [json.loads(x[0]) for x in db.execute("SELECT payload FROM journal")]}


def certify_frontend_shutdown():
    """Exercise the installed Next CLI's graceful signal handler on Windows.

    Node's signal event is delivered through an owned stdin pipe because this
    agent has no interactive console. Next 16's documented implementation exits
    143 after SIGTERM cleanup (130 after SIGINT), rather than normal exit 0.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 3000))
    script = """process.argv = [process.execPath, require.resolve('next/dist/bin/next'),
                'start', '--hostname', '127.0.0.1', '--port', '3000'];
process.stdin.once('data', () => {
  if (!process.listenerCount('SIGTERM')) process.exit(2);
  process.emit('SIGTERM', 'SIGTERM');
});
require('next/dist/bin/next');
"""
    process = subprocess.Popen(["node", "-e", script], cwd="frontend", text=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    connection = http.client.HTTPConnection("127.0.0.1", 3000, timeout=5)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError("Next CLI exited before startup")
            try:
                connection.request("GET", "/paper-rc")
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                assert response.status == 200 and "ARMS AI MVP 1.0" in body
                break
            except OSError:
                connection.close()
                time.sleep(.25)
        else:
            raise AssertionError("Next startup timeout")
        connection.close()
        process.communicate(input="stop\n", timeout=20)
        assert process.returncode == 143, process.returncode
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 3000))
        evidence = {"status": "PASS", "process_exit_code": 143,
                    "signal": "SIGTERM", "next_graceful_cleanup": True,
                    "http_status": 200, "release_heading_present": True,
                    "port_released": True}
        print(json.dumps(evidence), flush=True)
        return evidence
    finally:
        connection.close()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def certify(output, *, browser_pause=False):
    # Refuse to touch or accidentally certify an existing unrelated server.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8000))
    expected = json.loads(Path(BASELINE).read_text())["trades"][0]
    evidence = {"release": "ARMS AI MVP 1.0", "transport": "real loopback HTTP / unchanged production CLI",
                "baseline_sha256": sha256(Path(BASELINE).read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="arms-sprint09-") as directory:
        root = Path(directory)
        state = root / "paper.sqlite"
        app = CliProcess(state, root / "first.log")
        try:
            initial = app.get()
            assert initial["mode"] == "PAPER_RESEARCH" and not initial["paper_ready"]
            assert not initial["live_execution_allowed"]
            assert initial["configuration"]["boundary"] == 80.5
            assert initial["configuration"]["quality"] == 85
            assert len(initial["config_hash"]) == 64
            assert initial["account_overview"]["balance"] == 150000
            assert app.request("GET", "/health")[1]["status"] == "PROCESS_HEALTHY"
            app.command("enable")
            first = app.command("step")
            # Source row 1 is a certified out-of-session observation. It cannot
            # establish a market clock or readiness; row 2 is the first eligible bar.
            assert first["anomalies_excluded"] == 1 and not first["paper_ready"]
            assert first["processed_candles"] == 0
            first = app.command("step")
            assert first["paper_ready"]
            assert app.request("GET", "/api/v2/paper/readiness")[1]["paper_ready"]
            evidence["clean_start"] = {"status": "PASS", "initial": initial,
                                       "ready_config_hash": first["config_hash"]}
            # A real flat shutdown/restart, before any strategy trade.
            app.command("shutdown")
            stopped = app.get()
            app.command("step", 409)
            app.command("enable", 409)
            app.command("shutdown")
            assert app.get() == stopped
        finally:
            app.close()
        flat = durable(state)
        restarted = CliProcess(state, root / "flat_restart.log")
        try:
            snap = restarted.get()
            assert snap["dashboard_status"] == "RECOVERY_REQUIRED" and not snap["paper_ready"]
            assert snap["account_overview"] == stopped["account_overview"]
            restarted.command("enable", 409)
            restarted.command("step", 409)
        finally:
            restarted.close()
        assert durable(state) == flat
        evidence["flat_restart"] = "PASS; no operational reconstruction or reset"

        # A separate, explicitly new account is NOT recovery of the first account.
        state = root / "independent_smoke.sqlite"
        app = CliProcess(state, root / "smoke.log")
        try:
            app.command("enable")
            accepted = []
            for index in range(10000):
                snap = app.command("step")
                if (snap.get("submission") or {}).get("accepted") is True:
                    accepted.append(snap)
                if snap["completed_trades"]:
                    break
                if (index + 1) % 1000 == 0:
                    print(f"HTTP real-strategy smoke: {index+1} observations", flush=True)
            else:
                raise AssertionError("Expected first real trade did not complete")
            assert len(accepted) == 1
            assert snap["completed_trades"] == snap["journal_completed"] == snap["journal_total"] == 1
            trade = snap["latest_canonical_trade"]
            fields = ("entry_index", "exit_index", "direction", "quantity", "planned_entry",
                      "executed_entry", "stop", "target", "exit_trigger", "executed_exit",
                      "gross_pnl", "fees", "net_pnl", "balance_after", "daily_pnl_after", "drawdown_after")
            assert {k: trade[k] for k in fields} == {k: expected[k] for k in fields}
            account = snap["account_overview"]
            assert account["realized_pnl"] == -630 and account["balance"] == 149370
            assert not snap["active_simulated_positions"]
            disk_before = durable(state)
            assert disk_before["pending"] == 0 and len(disk_before["journal"]) == 1
            for _ in range(25):
                assert app.get() == snap
                assert app.request("GET", "/health")[0] == 200
                assert app.request("GET", "/api/v2/paper/readiness")[0] == 200
            if browser_pause:
                app.connection.close()  # Do not retain an idle keep-alive across manual inspection.
                print("BROWSER_ACCEPTANCE_READY: http://localhost:3000/paper-rc; press Enter after read-only inspection", flush=True)
                input()
            assert app.get() == snap and durable(state) == disk_before
            evidence["positive_smoke"] = {"status": "PASS", "accepted": accepted[0],
                "completed": snap, "expected_trade": expected, "read_only_rounds": 25,
                "durable_journal_count": 1, "pending_events": 0,
                "browser_pause_used": browser_pause}
            app.command("shutdown")
            stopped = app.get()
            app.command("step", 409)
            app.command("enable", 409)
            app.command("shutdown")
            assert app.get() == stopped
        finally:
            app.close()
        before = durable(state)
        assert before["checkpoint"]["account_overview"] == account
        restarted = CliProcess(state, root / "completed_restart.log")
        try:
            recovered = restarted.get()
            assert recovered["dashboard_status"] == "RECOVERY_REQUIRED" and not recovered["paper_ready"]
            assert recovered["account_overview"] == account
            assert recovered["journal_completed"] == 1
            assert not recovered["operational_state_restored"]
            restarted.command("enable", 409)
            restarted.command("step", 409)
            evidence["completed_restart"] = recovered
        finally:
            restarted.close()
        assert durable(state) == before
        evidence.update(status="PASS", shutdown="graceful CLI process exits: 0; duplicate shutdown no-op",
                        duplicates=0, duplicate_pnl=0, account_drift=0, journal_mismatch=0,
                        unexplained_differences=0)
    with Path(output).open("x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("PASS: clean CLI startup, real-strategy HTTP trade, reads, shutdown, flat/completed restart", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "child":
        cli_child()
    elif sys.argv[1] == "frontend-shutdown":
        certify_frontend_shutdown()
    else:
        certify(sys.argv[1], browser_pause="--browser-pause" in sys.argv[2:])
