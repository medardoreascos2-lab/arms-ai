"""One real-data integration witness; no HTTP server, external network or broker."""
from dataclasses import asdict
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.backtesting.historical_eligibility_v31 import HistoricalEligibilityV31
from backend.backtesting.paper_research_v1 import PaperResearchConfigV1, PaperResearchSessionV1
from backend.config.api_settings import APISettings
from backend.dashboard.widgets.account_overview_widget_v2 import AccountOverviewWidgetV2
from backend.tests.research_fresh_validation_v31 import EVIDENCE, read, write, load_segment, digest
from backend.tests.research_historical_accounting_sprint07r import OUT


def certify():
    declaration=read(EVIDENCE/"predeclared_experiment.json")
    segment=next(s for s in declaration["segments"] if s["contract"]=="JUN22")
    policy=HistoricalEligibilityV31(declaration["calendar"])
    config=PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json")
    assert digest(OUT/"realism_results.json")==config.research_evidence_sha256
    service=PaperResearchSessionV1(config=config,settings=APISettings(),policy=policy,
        observations=load_segment(policy,segment),contract="JUN22")
    result=service.run()
    expected=read(OUT/"JUN22_80_5_C3_fee5_0.json")
    assert len(result.trades)==expected["completed_trades"]
    assert sum(t.pnl for t in result.trades)==expected["net_pnl"]
    assert service.runtime.account.get_state()==expected["account"]
    fields=("entry_index","exit_index","direction","quantity","planned_entry","executed_entry",
            "stop","target","exit_trigger","executed_exit","gross_pnl","fees","net_pnl",
            "balance_after","daily_pnl_after","drawdown_after")
    assert [{k:t[k] for k in fields} for t in service.runtime.completed]==[
        {k:t[k] for k in fields} for t in expected["trades"]]
    app=create_app(settings=APISettings(),paper_research_provider_v1=service)
    before=service.get_snapshot()
    fill_count=len(service.runtime.lifecycle.broker_connector_v2.get_fills())
    with TestClient(app) as client:
        payloads=[client.get("/api/v2/backtesting/dashboard").json()["paper_research"] for _ in range(3)]
    assert payloads[0]==payloads[1]==payloads[2]
    assert service.get_snapshot()==before
    assert len(service.runtime.lifecycle.broker_connector_v2.get_fills())==fill_count
    widget=AccountOverviewWidgetV2(dashboard_live_data_service_v2=service).render()
    assert widget["data"]==before["account_overview"]
    write(OUT/"paper_mvp_evidence.json",{
        "status":"PASS","configuration":asdict(config),"contract":"JUN22",
        "candles":service.runtime.index,"completed_trades":len(result.trades),
        "net_pnl":sum(t.pnl for t in result.trades),"canonical_cost_replay_equivalence":"EXACT",
        "api_read_side_effects":0,"paper_entry_fills":fill_count,
        "journal_completed":len(service.runtime.journal.get_closed_trades()),
        "snapshot":payloads[0],"account_widget":widget,
        "limitations":"Explicit in-memory offline replay; optional existing dashboard API binding. No streaming broker feed, live orders or durable operational recovery."})
    print("PASS: real JUN22 replay -> canonical account/journal -> existing dashboard API/widget; exact cost replay parity")


if __name__=="__main__":
    certify()
