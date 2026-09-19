"""New RC soak evidence; reads frozen Sprint07R ledgers, never rewrites them."""
from backend.tests.private_evidence_paths_v1 import private_runtime_manifest
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from time import perf_counter

from backend.api.paper_rc_app_v1 import load_certified_replay
from backend.backtesting.paper_research_v1 import PaperResearchConfigV1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1
from backend.config.api_settings import APISettings


def certify(output):
    manifest = Path("backend/tests/research_v31/sprint05/predeclared_experiment.json")
    policy, rows = load_certified_replay(manifest_path=private_runtime_manifest(manifest), contract="JUN22")
    config = PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json")
    baseline_path = Path("backend/tests/research_sprint07r/JUN22_80_5_C3_fee5_0.json")
    expected = json.loads(baseline_path.read_text())
    fields = ("entry_index","exit_index","direction","quantity","planned_entry","executed_entry",
              "stop","target","exit_trigger","executed_exit","gross_pnl","fees","net_pnl",
              "balance_after","daily_pnl_after","drawdown_after")
    start = perf_counter()
    with tempfile.TemporaryDirectory(prefix="arms-sprint08-") as folder:
        arguments = dict(mode="PAPER_RESEARCH",config=config,settings=APISettings(),policy=policy,
            observations=rows,contract="JUN22",state_path=Path(folder)/"paper.sqlite",
            initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
        service = PaperRuntimeV1(**arguments)
        service.control("enable")
        days = set()
        max_history = max_diagnostics = 0
        max_drawdown = 0
        risk_blocks = 0
        for index, row in enumerate(rows,1):
            snap = service.ingest(row,received_at=row.available_at)
            r = service._paper.runtime
            if row.trading_date: days.add(row.trading_date)
            max_history = max(max_history,len(r.session.candle_history))
            max_diagnostics = max(max_diagnostics,len(r.states),len(r.session.decisions),len(r.risk_evaluations))
            max_drawdown = max(max_drawdown,snap["account_overview"]["drawdown"])
            risk_blocks += int(snap["account_overview"]["trading_blocked"])
            if index % 1000 == 0:
                assert service.ingest(row,received_at=row.available_at) == snap
                assert service.get_snapshot() == snap
            if index % 10000 == 0: print(f"RC soak {index}/{len(rows)}",flush=True)
        actual = [{k:t[k] for k in fields} for t in r.completed]
        expected_trades = [{k:t[k] for k in fields} for t in expected["trades"]]
        assert actual == expected_trades, "UNEXPLAINED canonical execution difference"
        assert r.account.get_state() == expected["account"], "UNEXPLAINED account difference"
        assert len({t["position_id"] for t in r.completed}) == len(r.completed)
        assert len(r.journal.get_closed_trades()) == len(r.completed)
        assert sum(t["net_pnl"] for t in r.completed) == r.account.get_state()["realized_pnl"]
        assert max_history <= 50 and max_diagnostics == 0
        assert len(r.lifecycle.broker_connector_v2.get_fills()) == len(r.entries)
        snapshot = service.get_snapshot()
        database_bytes = Path(arguments["state_path"]).stat().st_size
        service.shutdown()
        recovery = PaperRuntimeV1(**arguments)
        assert recovery.get_snapshot()["account_overview"] == snapshot["account_overview"]
        assert recovery.get_snapshot()["dashboard_status"] == "RECOVERY_REQUIRED"
        evidence = {"status":"PASS", "contract":"JUN22", "source_sha256":rows[0].source_sha256,
            "manifest_sha256":sha256(manifest.read_bytes()).hexdigest(),
            "baseline_sha256":sha256(baseline_path.read_bytes()).hexdigest(),
            "observations":len(rows),"eligible_candles":r.index,"trading_days":len(days),
            "completed_trades":len(r.completed),"outcomes":dict(Counter("WIN" if t["net_pnl"]>0 else "LOSS" for t in r.completed)),
            "net_pnl":r.account.get_state()["realized_pnl"],"peak_drawdown":max_drawdown,
            "risk_blocked_observations":risk_blocks,"max_analysis_history":max_history,
            "max_diagnostic_history":max_diagnostics,"database_bytes":database_bytes,
            "canonical_ledger_parity":"EXACT","account_parity":"EXACT",
            "duplicates":0,"account_drift":0,"journal_mismatch":0,"unexplained_differences":0,
            "recovery":"RECOVERY_REQUIRED; committed account evidence preserved; no operational resume",
            "elapsed_seconds":round(perf_counter()-start,3),"snapshot":snapshot}
        with Path(output).open("x",encoding="utf-8") as stream:
            json.dump(evidence,stream,indent=2,allow_nan=False)
            stream.write("\n")
        print(f"PASS: {r.index} candles, {len(r.completed)} trades, exact canonical parity",flush=True)


if __name__ == "__main__":
    import sys
    certify(sys.argv[1])
