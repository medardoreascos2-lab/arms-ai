from backend.api.app import create_app
from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)


def test_app_exposes_live_position_monitor_v2():
    app = create_app()

    assert hasattr(
        app.state,
        "live_position_monitor_v2",
    )

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    assert isinstance(
        monitor,
        LivePositionMonitorV2,
    )


def test_monitor_uses_shared_trade_lifecycle_service():
    app = create_app()

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    assert (
        monitor.trade_lifecycle_service
        is app.state.trade_lifecycle_service_v2
    )


def test_monitor_uses_shared_portfolio_manager():
    app = create_app()

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    lifecycle_portfolio_manager = getattr(
        app.state.trade_lifecycle_service_v2,
        "portfolio_manager_v2",
        None,
    )

    assert (
        monitor.portfolio_manager_v2
        is lifecycle_portfolio_manager
    )


def test_monitor_has_management_engines():
    app = create_app()

    monitor = (
        app.state
        .live_position_monitor_v2
    )

    assert (
        monitor.partial_take_profit_engine
        is not None
    )

    assert (
        monitor.realized_pnl_engine
        is not None
    )

    assert (
        monitor.break_even_engine
        is not None
    )

    assert (
        monitor.trailing_stop_engine
        is not None
    )


def test_monitor_processes_price_without_positions():
    app = create_app()

    result = (
        app.state
        .live_position_monitor_v2
        .process_price(
            symbol="NQ",
            current_price=22000.0,
        )
    )

    assert result["processed"] is True
    assert result["symbol"] == "NQ"
    assert result["current_price"] == 22000.0
    assert result["matched_positions"] == 0
    assert result["updated_positions"] == []
    assert result["closed_positions"] == 0
