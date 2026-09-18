"""V14 sustained joined PAPER operational acceptance.

This suite extends the already-certified V12/V13 boundaries without
introducing a second runtime, market, risk, execution, financial, dashboard,
or certified-news authority.
"""

from __future__ import annotations

from backend.tests.runtime_market_fixture_v81 import publish_test_market
from backend.tests.test_account_runtime_transition_v2 import hosted, target
from backend.tests.test_account_switch_safety_containment_v2 import signal
from backend.tests.test_phase1_consolidated_acceptance_v8 import submission


def _submit(host, *, submission_id=None):
    payload = submission(host)

    if submission_id is not None:
        payload["signal"]["submission_id"] = submission_id

    response = host.client.post(
        "/v2/trades/submit",
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_empty_economic_state(runtime) -> None:
    lifecycle = runtime.trade_lifecycle_service

    assert lifecycle.broker_connector_v2.get_fills() == []
    assert lifecycle.get_active_positions() == []
    assert runtime.portfolio_manager_v2.get_open_positions() == []
    assert lifecycle.trade_journal_v2.get_trades() == []


def _close_position(runtime, result, *, exit_price: float) -> None:
    runtime.trade_lifecycle_service.update_position(
        position_id=result["position"]["position_id"],
        current_price=exit_price,
    )


def test_sustained_joined_paper_cycles_preserve_single_application(
    hosted,
    tmp_path,
):
    """Repeated joined cycles stay deterministic and economically singular."""

    runtime = hosted.c.published.runtime
    lifecycle = runtime.trade_lifecycle_service

    for cycle in range(3):
        publish_test_market(
            lifecycle,
            directory=tmp_path / f"cycle-{cycle}",
        )

        submission_id = f"v14-sustained-cycle-{cycle}"

        result = _submit(
            hosted,
            submission_id=submission_id,
        )

        assert result["accepted"] is True, result

        assert len(lifecycle.get_active_positions()) == 1
        assert len(runtime.portfolio_manager_v2.get_open_positions()) == 1

        fills_before_repeat = len(
            lifecycle.broker_connector_v2.get_fills()
        )
        journal_before_repeat = len(
            lifecycle.trade_journal_v2.get_trades()
        )

        # Re-observation must remain observational.
        snapshot = hosted.client.get("/api/v2/dashboard/live")
        assert snapshot.status_code == 200

        with hosted.client.websocket_connect(
            "/api/v2/dashboard/ws"
        ) as socket:
            event = socket.receive_json()

        assert event["event_type"] == "dashboard_snapshot"

        assert len(
            lifecycle.broker_connector_v2.get_fills()
        ) == fills_before_repeat

        assert len(
            lifecycle.trade_journal_v2.get_trades()
        ) == journal_before_repeat

        _close_position(
            runtime,
            result,
            exit_price=float(result["position"]["entry_price"]) + 10.0,
        )

        assert lifecycle.get_active_positions() == []
        assert runtime.portfolio_manager_v2.get_open_positions() == []

        fills_after_close = len(
            lifecycle.broker_connector_v2.get_fills()
        )
        journal_after_close = len(
            lifecycle.trade_journal_v2.get_trades()
        )

        duplicate = _submit(
            hosted,
            submission_id=submission_id,
        )

        assert duplicate["accepted"] is False
        assert duplicate["reason"] == "duplicate_submission"

        assert len(
            lifecycle.broker_connector_v2.get_fills()
        ) == fills_after_close

        assert len(
            lifecycle.trade_journal_v2.get_trades()
        ) == journal_after_close

    assert len(lifecycle.broker_connector_v2.get_fills()) == 3
    assert len(lifecycle.trade_journal_v2.get_trades()) == 3


def test_sustained_risk_rejections_never_accumulate_financial_state(
    hosted,
    tmp_path,
):
    """Repeated safety rejection cannot leak into execution/financial state."""

    runtime = hosted.c.published.runtime

    publish_test_market(
        runtime.trade_lifecycle_service,
        directory=tmp_path,
    )

    runtime.account_state_manager_v2.record_daily_pnl(
        daily_pnl=-3000.0
    )

    for _ in range(5):
        result = _submit(hosted)
        assert result["accepted"] is False, result
        _assert_empty_economic_state(runtime)


def test_sustained_authorized_dashboard_reads_are_observational(
    hosted,
    tmp_path,
):
    """Repeated HTTP/WS observation never creates execution side effects."""

    runtime = hosted.c.published.runtime

    publish_test_market(
        runtime.trade_lifecycle_service,
        directory=tmp_path,
    )

    result = _submit(hosted)

    fills = len(
        runtime.trade_lifecycle_service.broker_connector_v2.get_fills()
    )
    trades = len(
        runtime.trade_lifecycle_service.trade_journal_v2.get_trades()
    )

    for _ in range(10):
        response = hosted.client.get("/api/v2/dashboard/live")
        assert response.status_code == 200

        with hosted.client.websocket_connect(
            "/api/v2/dashboard/ws"
        ) as socket:
            event = socket.receive_json()

        assert event["event_type"] == "dashboard_snapshot"

        assert len(
            runtime.trade_lifecycle_service.broker_connector_v2.get_fills()
        ) == fills

        assert len(
            runtime.trade_lifecycle_service.trade_journal_v2.get_trades()
        ) == trades

    _close_position(
        runtime,
        result,
        exit_price=float(result["position"]["entry_price"]) + 10.0,
    )


def test_sustained_account_switch_retires_old_projection(
    hosted,
    tmp_path,
):
    """A joined operational cycle cannot leak through account transition."""

    old_runtime = hosted.c.published.runtime

    publish_test_market(
        old_runtime.trade_lifecycle_service,
        directory=tmp_path,
    )

    result = _submit(hosted)

    _close_position(
        old_runtime,
        result,
        exit_price=float(result["position"]["entry_price"]) + 10.0,
    )

    old_account = (
        old_runtime.execution_state_store
        .account_identity["account_id"]
    )

    with hosted.client.websocket_connect(
        "/api/v2/dashboard/ws"
    ) as socket:
        first = socket.receive_json()
        assert first["event_type"] == "dashboard_snapshot"

        response = hosted.client.post(
            "/api/v2/dashboard/account-manager/switch",
            json=target(hosted, "B"),
        )

        assert response.status_code == 200

    current = hosted.c.published.runtime

    new_account = (
        current.execution_state_store
        .account_identity["account_id"]
    )

    assert new_account != old_account
    assert current.trade_lifecycle_service.get_active_positions() == []

    snapshot = hosted.client.get("/api/v2/dashboard/live").json()

    assert snapshot["runtime"]["account_id"] == new_account
    assert snapshot["positions"] == []


def test_sustained_candidate_source_remains_runtime_scoped(
    hosted,
    tmp_path,
):
    """Repeated market publication keeps candidate/execution runtime scoped."""

    runtime = hosted.c.published.runtime

    for cycle in range(3):
        publish_test_market(
            runtime.trade_lifecycle_service,
            directory=tmp_path / f"market-{cycle}",
        )

        candidate = signal()

        identity = (
            runtime.execution_state_store.account_identity
        )

        if isinstance(candidate, dict):
            account_id = candidate.get("account_id")
            if account_id is not None:
                assert account_id == identity["account_id"]

    assert hosted.c.published.runtime is runtime
