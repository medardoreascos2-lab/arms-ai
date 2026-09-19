from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.backtesting.paper_research_v1 import PaperResearchConfigV1, PaperResearchSessionV1, _ResearchConfluenceV1
from backend.config.api_settings import APISettings
from backend.dashboard.widgets.account_overview_widget_v2 import AccountOverviewWidgetV2
from backend.intelligence.confluence_engine_v2 import ConfluenceEngineV2
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.research_calibration_v30 import classify_hypothetically
from backend.tests.test_historical_accounting_sprint07r import observations
from backend.tests.test_historical_eligibility_v31 import policy
from backend.tests.test_production_certified_outcome_v17 import api_settings


def config():
    return PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json")


@pytest.mark.parametrize("changes", [{"boundary":80},{"boundary":90},{"quality":80},
    {"stop_loss":25},{"live_execution_allowed":True},{"mode":"LIVE"},
    {"research_evidence_sha256":"0"*64}])
def test_uncertified_or_live_configuration_is_rejected(changes):
    with pytest.raises(ValueError,match="certified"):
        replace(config(),**changes)


@pytest.mark.parametrize("score", [.79,.80,.805,.8133,.90])
@pytest.mark.parametrize("risk_approved", [False,True])
def test_research_grade_matches_frozen_experiment_without_score_or_veto_change(score,risk_approved):
    production=ConfluenceEngineV2()
    kwargs={k+"_score":score for k in ("trend","structure","liquidity","fvg","ema_alignment","market_regime","probability","volume")}
    kwargs.update(risk_approved=risk_approved,sizing_approved=True,market_tradable=True)
    actual=_ResearchConfluenceV1(production,config().boundary).evaluate(**kwargs)
    assert actual==classify_hypothetically(production.evaluate,80.5)(**kwargs)
    untouched=production.evaluate(**kwargs)
    assert actual["score"]==untouched["score"]
    assert actual["approved"]==untouched["approved"]
    assert actual["blocking_reasons"]==untouched["blocking_reasons"]
    if .80<=score<.90:
        assert untouched["grade"]=="A"


def test_explicit_paper_run_publishes_canonical_account_and_read_only_dashboard(policy,api_settings,tmp_path,monkeypatch):
    prices=[(10000,10000,10000,10000)]*8
    prices[5]=(10000,10060,10000,10000)
    service=PaperResearchSessionV1(config=config(),settings=APISettings(),policy=policy,
        observations=observations(policy,prices),contract="JUN25")
    def fixture_strategy(context):
        if context["signal_index"]!=5:
            return TradingDecisionV2(TradingActionV2.HOLD,.5,"synthetic HOLD")
        return TradingDecisionV2(TradingActionV2.BUY,.95,"synthetic execution witness",
            {"stop_loss":9970,"take_profit":10060,"confluence_score":.95,"grade":"A+","reasons":[]})
    service.runtime.session.strategy_runner_v2.run=fixture_strategy
    app=create_app(settings=APISettings(),risk_event_store_path_v2=tmp_path/"events.json",
        paper_research_provider_v1=service)
    client=TestClient(app)
    url="/api/v2/backtesting/dashboard"
    assert client.get(url).json()["paper_research"]["dashboard_status"]=="READY"
    assert not service.runtime.lifecycle.broker_connector_v2.get_fills()
    result=service.run()
    assert len(result.trades)==1 and result.trades[0].pnl==1170
    before=service.get_snapshot()
    assert before["completed_trades"]==before["journal_completed"]==1
    assert before["account_overview"]["balance"]==151170
    assert before["latest_canonical_trade"]["net_pnl"]==1170
    assert before["latest_decision"]["action"]=="HOLD"
    assert before["active_simulated_positions"]==[]
    with pytest.raises(RuntimeError,match="one explicit"):
        service.run()
    guards=[]
    for owner,name in ((service,"run"),(service.runtime,"run"),(service.runtime.lifecycle,"submit_signal"),
                       (service.runtime.lifecycle,"update_position"),(service.runtime.account,"update_from_portfolio")):
        guard=Mock(side_effect=AssertionError("GET must not mutate execution/account state"))
        monkeypatch.setattr(owner,name,guard);guards.append(guard)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:client.get(url).json()["paper_research"],range(8)))
    assert all(x==results[0] for x in results)
    assert service.get_snapshot()==before
    altered=service.get_snapshot();altered["account_overview"]["balance"]=0
    assert service.get_snapshot()==before
    widget=AccountOverviewWidgetV2(dashboard_live_data_service_v2=service).render()
    assert widget["data"]==before["account_overview"]
    for guard in guards:guard.assert_not_called()
    client.close()
