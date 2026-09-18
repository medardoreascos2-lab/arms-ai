"""Cross-contract acceptance at published account HTTP and direct boundaries."""
from copy import deepcopy
from datetime import datetime, timezone
import ast
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.tests.test_account_runtime_transition_v2 import hosted, target
from backend.tests.test_account_switch_safety_containment_v2 import signal


def submission(host):
    context = host.c.published.runtime
    account = context.account_state_manager_v2.get_state()
    return {
        "signal": {**signal(), "submission_id": "consolidated-v8"},
        "order_type": "MARKET",
        "risk_context": {
            **target(host, host.c.identity.profile_name),
            "account_balance": context.portfolio_manager_v2.get_available_balance(),
            "risk_percent": context.account_switch_safety_v2._profile["risk_percent"],
            "point_value": 2., "daily_pnl": account["daily_pnl"],
            "total_drawdown": account["drawdown"],
        },
    }


@pytest.mark.parametrize("entry", ["http", "direct"])
def test_submission_without_market_authority_cannot_reach_paper(hosted, monkeypatch, entry):
    runtime = hosted.c.published.runtime
    app = hosted.c.published.application
    assert app.state.runtime_quote_authority_v2.get_quote(symbol="MNQ") is None
    now = datetime.now(timezone.utc)
    assert not app.state.market_hours_service_v2.is_market_open(symbol="MNQ", timestamp=now)
    assert app.state.economic_news_authority_v2.is_news_blocked(symbol="MNQ", timestamp=now)
    broker = runtime.trade_lifecycle_service.broker_connector_v2
    before = deepcopy(broker.get_fills())
    submit_order = Mock(wraps=broker.submit_order)
    monkeypatch.setattr(broker, "submit_order", submit_order)
    if entry == "http":
        response = hosted.client.post("/v2/trades/submit", json=submission(hosted))
        assert response.status_code in {200, 409, 422, 503}, response.text
        result = response.json()
    else:
        result = runtime.trade_lifecycle_service.submit_signal(**submission(hosted))
    # Collect all observations before asserting: a response-only assertion can hide
    # the broker/fill side effect that makes this an execution safety failure.
    observed = {
        "accepted": result.get("accepted") is True,
        "prepared_order": result.get("prepared_order") is not None,
        "broker_calls": submit_order.call_count,
        "fills_changed": broker.get_fills() != before,
    }
    assert observed == {
        "accepted": False, "prepared_order": False,
        "broker_calls": 0, "fills_changed": False,
    }, observed


def test_all_registered_application_state_is_rebound_on_account_switch(hosted):
    manifest = json.loads(Path(__file__).with_name(
        "phase1_consolidated_acceptance_v8.json").read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / "backend/api/app.py").read_text(encoding="utf-8-sig"))
    assigned = {
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
        and ast.unparse(node.value) == "app.state"
    }
    assert assigned == {row["binding"] for row in manifest["application_state_bindings"]}
    source = hosted.c.published
    response = hosted.client.post(
        "/api/v2/dashboard/account-manager/switch", json=target(hosted, "B"))
    assert response.status_code == 200, response.text
    current = hosted.c.published
    assert current.generation > source.generation
    assert current.runtime.account_switch_safety_v2.identity.account_id != source.runtime.account_switch_safety_v2.identity.account_id
    for name in sorted(assigned):
        old = getattr(source.application.state, name)
        new = getattr(current.application.state, name)
        if name == "account_switch_safety_v2":
            assert old is new is hosted.c
        elif old is not None and not isinstance(old, (str, int, float, bool)):
            assert new is not old, name
    assert source.runtime.execution_state_store._durability.retired
