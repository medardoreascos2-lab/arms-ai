"""Behavioral proof of the operational market/risk admission boundary."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock

import pytest

from backend.tests.test_account_runtime_transition_v2 import hosted, switch
from backend.tests.test_phase1_consolidated_acceptance_v8 import submission
from backend.tests.runtime_market_fixture_v81 import NOW, publish_test_market
from backend.services.durable_execution_state_v2 import AccountAdmissionRejected


def economic_state(runtime):
    state = deepcopy(runtime.execution_state_store.capture_state())
    state.pop("captured_at", None)
    return state


def invoke(host, runtime, entry, body):
    if entry == "http":
        response = host.client.post("/v2/trades/submit", json=body)
        assert response.status_code in {200, 409, 422, 503}, response.text
        return response.json()
    try:
        return runtime.trade_lifecycle_service.submit_signal(**body)
    except (AccountAdmissionRejected, RuntimeError, ValueError):
        return {"accepted": False}


@pytest.mark.parametrize("entry", ["http", "direct"])
@pytest.mark.parametrize("condition", ["missing", "stale", "future", "spread", "hours", "news",
    "news_coverage", "risk", "account", "failed", "switching", "guard", "foreign",
    "exposure", "portfolio", "order", "caller_veto", "caller_ambiguous", "expires_during_risk", "stale_generation", "invalid_generation", "admission"])
def test_rejections_never_prepare_fill_or_change_financial_state(hosted, tmp_path, monkeypatch, entry, condition):
    assert switch(hosted, "B").status_code == 200
    runtime = hosted.c.published.runtime
    lifecycle = runtime.trade_lifecycle_service
    body = submission(hosted)
    if condition != "missing":
        admission = publish_test_market(lifecycle, directory=tmp_path,
            quote_age=31 if condition == "stale" else -1 if condition == "future" else 0,
            closed=condition == "hours", news_blocked=condition == "news",
            spread=6 if condition == "spread" else .25)
        if condition == "news_coverage":
            admission.clock = lambda: NOW+timedelta(hours=2)
            admission.quote_authority.publish_quote(symbol="MNQ", bid=9999.875, ask=10000.125,
                timestamp=NOW+timedelta(hours=2))
    if condition == "risk":
        runtime.account_state_manager_v2.record_daily_pnl(daily_pnl=-950)
        assert not runtime.account_state_manager_v2.get_state()["trading_blocked"]
    elif condition == "account":
        runtime.account_state_manager_v2.record_daily_pnl(daily_pnl=-1000)
    elif condition in {"failed", "switching"}:
        monkeypatch.setattr(hosted.c, condition, True)
    elif condition == "admission":
        monkeypatch.setattr(lifecycle, "runtime_admission_v2", None)
    elif condition == "guard":
        monkeypatch.setattr(lifecycle, "order_validation_engine_v2", None)
    elif condition == "foreign":
        body["risk_context"]["account_id"] = "WRONG_ACCOUNT"
    elif condition in {"stale_generation", "invalid_generation"}:
        body["risk_context"]["runtime_generation"] = (
            hosted.c.published.generation-1 if condition == "stale_generation" else True)
    elif condition == "exposure":
        lifecycle.exposure_manager_v2.maximum_total_open_risk = 1
    elif condition == "portfolio":
        lifecycle.portfolio_risk_engine_v2.maximum_total_open_risk = 1
    elif condition == "order":
        body["signal"]["take_profit"] = 10001.
    elif condition in {"caller_veto", "caller_ambiguous"}:
        body["order_context"] = {"market_is_open": False if condition == "caller_veto" else None}
    elif condition == "expires_during_risk":
        original = runtime.risk_manager_v2.evaluate
        def expire(**kwargs):
            result = original(**kwargs)
            admission.clock = lambda: NOW+timedelta(seconds=31)
            return result
        monkeypatch.setattr(runtime.risk_manager_v2, "evaluate", expire)
    before = economic_state(runtime)
    broker_before = deepcopy(lifecycle.broker_connector_v2.get_fills())
    guards = []
    for owner, name in [(runtime.execution_manager, "prepare_order"),
                        (lifecycle.broker_connector_v2, "submit_order"),
                        (runtime.paper_execution_engine, "execute")]:
        guard = Mock(side_effect=AssertionError("Rejected request reached execution"))
        monkeypatch.setattr(owner, name, guard)
        guards.append(guard)
    result = invoke(hosted, runtime, entry, body)
    assert result.get("accepted") is not True, result
    assert result.get("prepared_order") is None
    if condition == "risk":
        assert result["reason"] == "risk_blocked", result
    assert economic_state(runtime) == before
    assert lifecycle.broker_connector_v2.get_fills() == broker_before
    for guard in guards:
        guard.assert_not_called()


@pytest.mark.parametrize("entry", ["http", "direct"])
def test_valid_admission_fills_once_and_synchronizes(hosted, tmp_path, entry):
    assert switch(hosted, "B").status_code == 200
    runtime = hosted.c.published.runtime
    lifecycle = runtime.trade_lifecycle_service
    publish_test_market(lifecycle, directory=tmp_path)
    body = submission(hosted)
    result = invoke(hosted, runtime, entry, body)
    assert result["accepted"] is True, result
    assert len(lifecycle.broker_connector_v2.get_fills()) == 1
    assert len(runtime.portfolio_manager_v2.get_open_positions()) == 1
    assert len(lifecycle.trade_journal_v2.get_trades()) == 1
    assert len(lifecycle.get_active_positions()) == 1
    before = economic_state(runtime)
    assert invoke(hosted, runtime, entry, body).get("accepted") is not True
    assert economic_state(runtime) == before


def test_retired_generation_and_lower_level_submission_cannot_bypass_admission(hosted, tmp_path):
    assert switch(hosted, "B").status_code == 200
    source = hosted.c.published.runtime
    publish_test_market(source.trade_lifecycle_service, directory=tmp_path)
    body = submission(hosted)
    for operation in (
        lambda: source.execution_manager.prepare_order(signal=body["signal"], order_type="MARKET"),
        lambda: source.paper_execution_engine.execute(prepared_order={}),
        lambda: source.trade_lifecycle_service.broker_connector_v2.submit_order(prepared_order={}),
    ):
        with pytest.raises(AccountAdmissionRejected, match="canonical_runtime_admission_required"):
            operation()
    assert switch(hosted, "A").status_code == 200
    target = hosted.c.published.runtime
    before = economic_state(target)
    rejected = source.trade_lifecycle_service.submit_signal(**body)
    assert rejected["accepted"] is False
    assert economic_state(target) == before
    assert target.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_refresh_revokes_market_permission_for_http_and_direct(hosted, tmp_path):
    assert switch(hosted, "B").status_code == 200
    runtime = hosted.c.published.runtime
    admission = publish_test_market(runtime.trade_lifecycle_service, directory=tmp_path)
    app = hosted.c.published.application
    assert app.state.runtime_quote_authority_v2 is admission.quote_authority
    path = tmp_path / "closed.json"
    path.write_text('{"covered_dates":["2026-09-08"],"closed_dates":["2026-09-08"],"special_hours":[]}', encoding="utf-8")
    app.state.market_hours_runtime_refresh_service_v2.refresh_from_file(file_path=path)
    for entry in ("http", "direct"):
        result = invoke(hosted, runtime, entry, submission(hosted))
        assert result["accepted"] is False
        assert "hours" in result["admission_reason"]
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []


@pytest.mark.parametrize("entry", ["http", "direct"])
def test_returning_account_requires_new_quote_before_execution(hosted, tmp_path, entry):
    assert switch(hosted, "B").status_code == 200
    old = hosted.c.published.runtime
    publish_test_market(old.trade_lifecycle_service, directory=tmp_path)
    assert switch(hosted, "A").status_code == 200
    assert switch(hosted, "B").status_code == 200
    current = hosted.c.published.runtime
    assert current.trade_lifecycle_service.runtime_admission_v2.quote_authority.get_quote(symbol="MNQ") is None
    result = invoke(hosted, current, entry, submission(hosted))
    assert result["accepted"] is False
    assert current.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_bound_compatibility_facade_cannot_record_an_unadmitted_trade(runtime, tmp_path):
    from backend.api.app import create_app
    app = create_app(account_config_manager_v2=runtime.safety._managers[0],
                     risk_event_store_path_v2=tmp_path / "risk.json")
    pipeline = app.state.execution_pipeline_v3
    with pytest.raises(AccountAdmissionRejected, match="canonical_runtime_admission_required"):
        pipeline.execute(symbol="MNQ", direction="LONG", entry=10000., stop_loss=9995.,
                         take_profit=10010., contracts=1, risk_amount=10., approved=True)
    assert pipeline.counter == 0
    assert app.state.trade_journal_v2.get_trades() == []
    assert app.state.broker_connector_v2.get_fills() == []
