from backend.api.app import create_app


def test_dashboard_dependencies_share_same_instances():
    app = create_app()

    lifecycle = (
        app.state
        .trade_lifecycle_service_v2
    )

    dashboard_engine = (
        app.state
        .performance_dashboard_engine_v2
    )

    account_state = (
        app.state
        .account_state_manager_v2
    )

    portfolio = (
        app.state
        .portfolio_manager_v2
    )

    journal = (
        app.state
        .trade_journal_v2
    )

    assert account_state is not None
    assert portfolio is not None
    assert journal is not None

    assert (
        lifecycle.portfolio_manager_v2
        is portfolio
    )

    assert (
        lifecycle.trade_journal_v2
        is journal
    )

    assert (
        portfolio.account_state_manager_v2
        is account_state
    )

    assert (
        dashboard_engine
        .account_state_manager_v2
        is account_state
    )

    assert (
        dashboard_engine
        .portfolio_manager_v2
        is portfolio
    )

    assert (
        dashboard_engine
        .trade_journal_v2
        is journal
    )


def test_dashboard_starts_ready_with_account_state():
    app = create_app()

    snapshot = (
        app.state
        .dashboard_live_data_service_v2
        .get_snapshot()
    )

    assert (
        snapshot["dashboard_status"]
        == "READY"
    )

    assert (
        snapshot["account_state"]
        is not None
    )

    assert (
        snapshot["account_overview"]
        is not None
    )

    assert (
        snapshot["portfolio_summary"]
        is not None
    )

    assert (
        snapshot["trade_journal_summary"]
        is not None
    )

    assert (
        snapshot["account_overview"][
            "balance"
        ]
        == 50000.0
    )

    assert (
        snapshot["account_overview"][
            "equity"
        ]
        == 50000.0
    )

    assert (
        snapshot["risk_status"][
            "trading_blocked"
        ]
        is False
    )
