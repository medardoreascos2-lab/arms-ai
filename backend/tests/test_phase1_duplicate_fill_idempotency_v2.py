from __future__ import annotations

from copy import deepcopy

from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)
from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)
from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)
from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.tests.test_trade_lifecycle_service_v2 import (
    build_service,
    build_valid_signal,
)


def _build_durable_runtime(tmp_path):
    account = AccountStateManagerV2(
        starting_balance=17000.0,
        maximum_daily_loss=3000.0,
        maximum_total_drawdown=4500.0,
    )

    portfolio = PortfolioManagerV2(
        starting_balance=17000.0,
        account_state_manager_v2=account,
    )

    journal = TradeJournalV2()

    lifecycle = build_service(
        portfolio_manager_v2=portfolio,
        trade_journal_v2=journal,
    )

    assert isinstance(lifecycle, TradeLifecycleServiceV2)

    store = ExecutionStateStoreV2(
        trade_lifecycle_service=lifecycle,
        protective_order_registry=(
            lifecycle.protective_order_registry_v2
        ),
        oco_manager=lifecycle.oco_manager_v2,
    )

    path = tmp_path / "duplicate-fill-state.json"
    store._durability.acquire(path)
    store._durability.enable()

    return lifecycle, account, portfolio, journal, store


def _submit_position(lifecycle: TradeLifecycleServiceV2):
    result = lifecycle.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
    )

    assert result["accepted"] is True, result
    assert result["position"] is not None
    return result["position"]


def _partial_fill_replay_payload(position: dict[str, object]):
    replay = deepcopy(position)

    entry_price = float(position["entry_price"])
    point_value = float(position["point_value"])
    original_quantity = float(position["quantity"])
    remaining_quantity = 1.0
    partial_closed_quantity = original_quantity - remaining_quantity

    assert partial_closed_quantity > 0.0

    partial_exit_price = 110.0
    realized_pnl = round(
        (partial_exit_price - entry_price)
        * partial_closed_quantity
        * point_value,
        10,
    )

    replay.update(
        {
            "quantity": remaining_quantity,
            "current_price": partial_exit_price,
            "partial_exit_price": partial_exit_price,
            "partial_taken": True,
            "partial_pnl_recorded": True,
            "partial_closed_quantity": partial_closed_quantity,
            "realized_pnl": realized_pnl,
            "last_partial_reason": "PARTIAL_TAKE_PROFIT",
        }
    )
    return replay


def _economic_state(
    lifecycle: TradeLifecycleServiceV2,
    account: AccountStateManagerV2,
    portfolio: PortfolioManagerV2,
    journal: TradeJournalV2,
    store: ExecutionStateStoreV2,
):
    active_positions = lifecycle.get_active_positions()
    trade_history = lifecycle.get_trade_history()

    open_portfolio_positions = portfolio.get_open_positions()
    closed_portfolio_positions = portfolio.get_closed_positions()

    assert len(active_positions) + len(trade_history) == 1
    assert (
        len(open_portfolio_positions)
        + len(closed_portfolio_positions)
        == 1
    )
    assert len(journal.trades) == 1

    if active_positions:
        lifecycle_position = deepcopy(active_positions[0])
    else:
        lifecycle_position = deepcopy(trade_history[0])
        lifecycle_position["status"] = "CLOSED"

    portfolio_position = (
        open_portfolio_positions[0]
        if open_portfolio_positions
        else closed_portfolio_positions[0]
    )

    return {
        "lifecycle_position": deepcopy(lifecycle_position),
        "portfolio_position": deepcopy(portfolio_position),
        "account_state": account.get_state(),
        "journal_trade": deepcopy(journal.trades[0].__dict__),
        "broker_fills": store.trade_lifecycle_service.broker_connector_v2.get_fills(),
        "durable_state": deepcopy(store.capture_state()),
    }


def test_replayed_partial_fill_does_not_double_apply_state(tmp_path):
    (
        lifecycle,
        account,
        portfolio,
        journal,
        store,
    ) = _build_durable_runtime(tmp_path)

    try:
        position = _submit_position(lifecycle)
        replay_payload = _partial_fill_replay_payload(position)
        expected_realized_pnl = replay_payload["realized_pnl"]

        lifecycle.replace_active_position(
            position=replay_payload,
        )

        first_state = _economic_state(
            lifecycle,
            account,
            portfolio,
            journal,
            store,
        )

        lifecycle.replace_active_position(
            position=deepcopy(replay_payload),
        )

        second_state = _economic_state(
            lifecycle,
            account,
            portfolio,
            journal,
            store,
        )

        assert (
            second_state["lifecycle_position"]["quantity"]
            == replay_payload["quantity"]
        )
        assert (
            second_state["portfolio_position"]["quantity"]
            == replay_payload["quantity"]
        )

        assert (
            second_state["lifecycle_position"]["realized_pnl"]
            == expected_realized_pnl
        )
        assert (
            second_state["portfolio_position"]["realized_pnl"]
            == expected_realized_pnl
        )

        assert (
            second_state["account_state"]["daily_pnl"]
            == expected_realized_pnl
        )
        assert (
            second_state["account_state"]["realized_pnl"]
            == expected_realized_pnl
        )

        assert (
            second_state["journal_trade"]["pnl"]
            == expected_realized_pnl
        )
        assert (
            second_state["journal_trade"]["remaining_quantity"]
            == replay_payload["quantity"]
        )

        assert (
            second_state["lifecycle_position"]["status"]
            == "OPEN"
        )
        assert (
            second_state["portfolio_position"]["status"]
            == "OPEN"
        )
        assert (
            second_state["journal_trade"]["status"]
            == "OPEN"
        )

        assert len(first_state["broker_fills"]) == 2
        assert len(second_state["broker_fills"]) == 2

        assert (
            second_state["durable_state"]["active_positions"]
            == first_state["durable_state"]["active_positions"]
        )
        assert (
            second_state["durable_state"]["account_portfolio"]
            == first_state["durable_state"]["account_portfolio"]
        )
        assert (
            second_state["durable_state"]["execution_records"]["paper"][
                "fills"
            ]
            == first_state["durable_state"]["execution_records"]["paper"][
                "fills"
            ]
        )
        assert (
            second_state["durable_state"]["execution_records"]["history"]
            == first_state["durable_state"]["execution_records"]["history"]
        )
        assert (
            second_state["durable_state"]["execution_records"]["journal"]
            == first_state["durable_state"]["execution_records"]["journal"]
        )
    finally:
        store._durability.release()


def test_replayed_closed_fill_does_not_change_lifecycle_or_durable_state(
    tmp_path,
):
    (
        lifecycle,
        account,
        portfolio,
        journal,
        store,
    ) = _build_durable_runtime(tmp_path)

    try:
        position = _submit_position(lifecycle)

        close_price = 110.0
        expected_realized_pnl = round(
            (
                close_price
                - float(position["entry_price"])
            )
            * float(position["quantity"])
            * float(position["point_value"]),
            10,
        )

        lifecycle.update_position(
            position_id=position["position_id"],
            current_price=close_price,
        )

        first_state = _economic_state(
            lifecycle,
            account,
            portfolio,
            journal,
            store,
        )

        assert first_state["lifecycle_position"]["status"] == "CLOSED"
        assert (
            first_state["account_state"]["daily_pnl"]
            == expected_realized_pnl
        )
        assert (
            first_state["account_state"]["realized_pnl"]
            == expected_realized_pnl
        )
        assert len(first_state["broker_fills"]) == 1
        assert len(first_state["durable_state"]["execution_records"]["history"]) == 1

        try:
            lifecycle.update_position(
                position_id=position["position_id"],
                current_price=110.0,
            )
        except ValueError as exc:
            assert "position_id" in str(exc)

        second_state = _economic_state(
            lifecycle,
            account,
            portfolio,
            journal,
            store,
        )

        assert (
            second_state["account_state"]["daily_pnl"]
            == expected_realized_pnl
        )
        assert (
            second_state["account_state"]["realized_pnl"]
            == expected_realized_pnl
        )
        assert len(second_state["broker_fills"]) == 1
        assert len(second_state["journal_trade"]) > 0
        assert len(second_state["durable_state"]["execution_records"]["history"]) == 1
        assert (
            second_state["durable_state"]["account_portfolio"]
            == first_state["durable_state"]["account_portfolio"]
        )
        assert (
            second_state["durable_state"]["execution_records"]["paper"]["fills"]
            == first_state["durable_state"]["execution_records"]["paper"]["fills"]
        )
        assert (
            second_state["durable_state"]["execution_records"]["history"]
            == first_state["durable_state"]["execution_records"]["history"]
        )
    finally:
        store._durability.release()
