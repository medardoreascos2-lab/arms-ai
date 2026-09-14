from __future__ import annotations

from copy import deepcopy

import pytest

from backend.account.account_state_manager_v2 import AccountStateManagerV2
from backend.analytics.performance_analytics_v2 import PerformanceAnalyticsV2
from backend.analytics.trade_history_manager_v2 import TradeHistoryManagerV2
from backend.dashboard.risk_dashboard_event_publisher_v2 import (
    RiskDashboardEventPublisherV2,
)
from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import (
    TradeLifecycleDashboardEventPublisherV2,
)
from backend.execution.execution_manager_v2 import ExecutionManagerV2
from backend.execution.execution_risk_gate_v1 import ExecutionRiskGateV1
from backend.execution.paper_execution_engine_v2 import PaperExecutionEngineV2
from backend.execution.position_manager_v2 import PositionManagerV2
from backend.execution.position_sizing_engine_v2 import PositionSizingEngineV2
from backend.execution.risk_manager_v2 import RiskManagerV2
from backend.execution.oco_manager_v2 import OCOManagerV2
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.instruments.instrument_profile_engine import InstrumentProfileEngine
from backend.journal.trade_journal_v2 import TradeJournalV2
from backend.portfolio.portfolio_manager_v2 import PortfolioManagerV2
from backend.risk.risk_event_logger_v1 import RiskEventLoggerV1
from backend.services.trade_lifecycle_service_v2 import TradeLifecycleServiceV2
from backend.services.execution_state_store_v2 import ExecutionStateStoreV2


class ApprovedRiskValidator:
    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ) -> dict[str, object]:
        return {
            "status": "APPROVED",
            "account": "PHASE1-ATOMICITY-TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
            "symbol": symbol,
        }


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "MNQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "MNQ LONG ENTRY 100.0 SL 95.0 TP 110.0",
    }


def build_service() -> TradeLifecycleServiceV2:
    account_state = AccountStateManagerV2(
        starting_balance=17_000.0,
        maximum_daily_loss=3_000.0,
        maximum_total_drawdown=4_500.0,
    )

    event_bus = type("EventBus", (), {})()
    event_bus.publish = (
        lambda event_type=None, payload=None, **kwargs: {
            "published": True,
            "event_type": event_type,
            "payload": payload,
            **kwargs,
        }
    )

    portfolio = PortfolioManagerV2(
        starting_balance=17_000.0,
        account_state_manager_v2=account_state,
    )

    paper_engine = PaperExecutionEngineV2(
        fill_market_orders_immediately=True,
        slippage_points=0.25,
    )

    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=paper_engine,
        position_manager=PositionManagerV2(
            point_value=2.0,
        ),
        instrument_profile_engine=InstrumentProfileEngine(),
        trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=252,
        ),
        starting_balance=17_000.0,
        risk_manager_v2=RiskManagerV2(
            position_sizing_engine=PositionSizingEngineV2(),
            maximum_daily_loss=3_000.0,
            maximum_total_drawdown=4_500.0,
            maximum_contracts=20,
            maximum_open_positions=1,
        ),
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=ApprovedRiskValidator(),
            logger=RiskEventLoggerV1(),
        ),
        portfolio_manager_v2=portfolio,
        trade_journal_v2=TradeJournalV2(),
        dashboard_event_publisher_v2=(
            TradeLifecycleDashboardEventPublisherV2(
                event_bus_v2=event_bus,
            )
        ),
        risk_dashboard_event_publisher_v2=(
            RiskDashboardEventPublisherV2(
                event_bus_v2=event_bus,
            )
        ),
        oco_manager_v2=OCOManagerV2(),
        protective_order_registry_v2=ProtectiveOrderRegistryV2(),
    )


def build_durable_service(tmp_path):
    service = build_service()

    store = ExecutionStateStoreV2(
        trade_lifecycle_service=service,
        protective_order_registry=(
            service.protective_order_registry_v2
        ),
        oco_manager=service.oco_manager_v2,
    )

    store._durability.acquire(
        tmp_path / "phase1-fill-atomicity.json"
    )
    store._durability.enable()

    return service, store




def capture_financial_surfaces(
    service: TradeLifecycleServiceV2,
) -> dict[str, object]:
    portfolio = service.portfolio_manager_v2
    account = portfolio.account_state_manager_v2
    broker = service.broker_connector_v2

    return deepcopy(
        {
            "orders": broker.get_orders(),
            "fills": broker.get_fills(),
            "broker_positions": broker.get_positions(),
            "broker_account": broker.get_account(),
            "active_positions": service.get_active_positions(),
            "portfolio_open": portfolio.get_open_positions(),
            "portfolio_closed": portfolio.get_closed_positions(),
            "portfolio_summary": portfolio.get_summary(),
            "account_state": account.get_state(),
            "journal": service.trade_journal_v2.get_trades(),
            "protections": (
                service.protective_order_registry_v2.list_protections()
            ),
            "oco_groups": service.oco_manager_v2.list_groups(),
        }
    )


def submit_valid_signal(
    service: TradeLifecycleServiceV2,
) -> dict[str, object]:
    return service.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17_000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
    )


def test_accepted_paper_fill_synchronizes_all_financial_surfaces(tmp_path):
    service, store = build_durable_service(tmp_path)

    result = submit_valid_signal(service)

    assert result["accepted"] is True
    assert result["execution"]["accepted"] is True
    assert result["execution"]["status"] == "FILLED"
    assert result["execution"]["execution_mode"] == "PAPER"

    execution = result["execution"]
    position = result["position"]
    position_id = result["active_position_id"]

    assert position_id == position["position_id"]
    assert position["status"] == "OPEN"
    assert position["execution_mode"] == "PAPER"
    assert position["symbol"] == execution["symbol"]
    assert position["order_id"] == execution["order_id"]
    assert position["broker_position_id"] is not None
    assert position["entry_price"] == execution["filled_price"]
    assert position["current_price"] == execution["filled_price"]
    assert position["quantity"] == execution["quantity"]
    assert position["realized_pnl"] == 0.0
    assert position["unrealized_pnl"] == 0.0

    broker = service.broker_connector_v2
    orders = broker.get_orders()
    fills = broker.get_fills()
    broker_positions = broker.get_positions()

    assert len(orders) == 1
    assert len(fills) == 1
    assert len(broker_positions) == 1

    order = orders[0]
    fill = fills[0]
    broker_position = broker_positions[0]

    assert order["order_id"] == execution["order_id"]
    assert fill["order_id"] == execution["order_id"]
    assert fill["execution_mode"] == "PAPER"
    assert broker_position["position_id"] == position["broker_position_id"]
    assert broker_position["order_id"] == execution["order_id"]
    assert broker_position["quantity"] == position["quantity"]

    portfolio = service.portfolio_manager_v2
    portfolio_positions = portfolio.get_open_positions()
    assert len(portfolio_positions) == 1
    assert portfolio_positions[0]["position_id"] == position_id
    assert portfolio_positions[0]["order_id"] == execution["order_id"]
    assert portfolio_positions[0]["symbol"] == position["symbol"]
    assert portfolio_positions[0]["quantity"] == position["quantity"]
    assert portfolio_positions[0]["realized_pnl"] == 0.0

    account_state = portfolio.account_state_manager_v2.get_state()
    assert account_state["open_positions"] == 1
    assert account_state["closed_positions"] == 0
    assert account_state["realized_pnl"] == 0.0
    assert account_state["unrealized_pnl"] == 0.0
    assert account_state["total_pnl"] == 0.0
    assert account_state["daily_pnl"] == 0.0
    assert account_state["daily_loss_used"] == 0.0
    assert account_state["trading_blocked"] is False

    journal_trades = service.trade_journal_v2.get_trades()
    assert len(journal_trades) == 1
    assert journal_trades[0].position_id == position_id
    assert journal_trades[0].status == "OPEN"
    assert journal_trades[0].contracts == position["quantity"]
    assert journal_trades[0].entry == position["entry_price"]
    assert journal_trades[0].pnl == 0.0

    protections = service.protective_order_registry_v2.list_protections()
    oco_groups = service.oco_manager_v2.list_groups()

    assert len(protections) == 1
    assert len(oco_groups) == 1
    assert protections[0]["position_id"] == position_id
    assert protections[0]["status"] == "ACTIVE"
    assert oco_groups[0]["position_id"] == position_id
    assert oco_groups[0]["status"] == "ACTIVE"

    assert result["portfolio_summary"]["open_positions"] == 1
    assert result["portfolio_summary"]["closed_positions"] == 0
    assert result["portfolio_summary"]["total_realized_pnl"] == 0.0
    assert result["portfolio_summary"]["total_unrealized_pnl"] == 0.0
    assert result["portfolio_summary"]["total_pnl"] == 0.0


def test_accepted_fill_preserves_pnl_and_daily_pnl_after_close(tmp_path):
    service, store = build_durable_service(tmp_path)

    submitted = submit_valid_signal(service)
    position_id = submitted["active_position_id"]

    result = service.update_position(
        position_id=position_id,
        current_price=110.25,
    )

    assert result["updated"] is True
    assert result["position"]["status"] == "CLOSED"
    assert result["position"]["close_reason"] == "TAKE_PROFIT"

    expected_pnl = round(
        (110.25 - 100.25) * 2.0 * 2,
        10,
    )

    assert result["position"]["realized_pnl"] == expected_pnl
    assert result["position"]["unrealized_pnl"] == 0.0

    portfolio = service.portfolio_manager_v2
    summary = portfolio.get_summary()
    account_state = portfolio.account_state_manager_v2.get_state()

    assert summary["open_positions"] == 0
    assert summary["closed_positions"] == 1
    assert summary["total_realized_pnl"] == expected_pnl
    assert summary["total_unrealized_pnl"] == 0.0
    assert summary["total_pnl"] == expected_pnl
    assert summary["account_equity"] == 17_000.0 + expected_pnl

    assert account_state["open_positions"] == 0
    assert account_state["closed_positions"] == 1
    assert account_state["realized_pnl"] == expected_pnl
    assert account_state["unrealized_pnl"] == 0.0
    assert account_state["total_pnl"] == expected_pnl
    assert account_state["daily_pnl"] == expected_pnl
    assert account_state["daily_loss_used"] == 0.0
    assert account_state["trading_blocked"] is False

    history = service.get_trade_history()
    journal_trades = service.trade_journal_v2.get_trades()

    assert len(history) == 1
    assert history[0]["position_id"] == position_id
    assert history[0]["realized_pnl"] == expected_pnl

    assert len(journal_trades) == 1
    assert journal_trades[0].position_id == position_id
    assert journal_trades[0].status == "CLOSED"
    assert journal_trades[0].pnl == expected_pnl
    assert journal_trades[0].remaining_quantity == 0.0

    protections = service.protective_order_registry_v2.list_protections()
    oco_groups = service.oco_manager_v2.list_groups()

    assert len(protections) == 1
    assert protections[0]["status"] == "COMPLETED"
    assert len(oco_groups) == 1
    assert oco_groups[0]["status"] == "COMPLETED"


def test_failed_journal_mutation_does_not_leave_half_applied_fill_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    service, store = build_durable_service(tmp_path)
    before = capture_financial_surfaces(service)

    def fail_after_portfolio_sync(*args, **kwargs):
        raise RuntimeError("injected journal failure")

    monkeypatch.setattr(
        service.trade_journal_v2,
        "record_open_trade",
        fail_after_portfolio_sync,
    )

    with pytest.raises(
        RuntimeError,
        match="injected journal failure",
    ):
        submit_valid_signal(service)

    after = capture_financial_surfaces(service)

    assert after == before
    assert service.get_active_positions() == []
    assert service.portfolio_manager_v2.get_open_positions() == []
    assert service.portfolio_manager_v2.get_closed_positions() == []
    assert service.trade_journal_v2.get_trades() == []
    assert service.broker_connector_v2.get_orders() == []
    assert service.broker_connector_v2.get_fills() == []
    assert service.broker_connector_v2.get_positions() == []

    account_state = (
        service.portfolio_manager_v2
        .account_state_manager_v2
        .get_state()
    )
    assert account_state["open_positions"] == 0
    assert account_state["closed_positions"] == 0
    assert account_state["realized_pnl"] == 0.0
    assert account_state["unrealized_pnl"] == 0.0
    assert account_state["daily_pnl"] == 0.0
    assert account_state["trading_blocked"] is False
