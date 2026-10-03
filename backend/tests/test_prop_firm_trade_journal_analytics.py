"""Decimal-safe, read-only trade journal analytics tests."""

from dataclasses import FrozenInstanceError
from decimal import Decimal as D

import pytest

from backend.analytics.prop_firm_trade_journal_analytics import (
    ClosedJournalTrade,
    ProfitFactorState,
    analyze_trade_journal,
)


def trade(
    trade_id: str,
    pnl: str,
    risk: str | None,
    *,
    instrument: str = "NQ",
    session: str = "NEW_YORK",
    account_id: str = "account-1",
    firm_id: str = "topstep",
) -> ClosedJournalTrade:
    return ClosedJournalTrade(
        trade_id=trade_id,
        realized_pnl=D(pnl),
        initial_risk=None if risk is None else D(risk),
        instrument=instrument,
        session=session,
        account_id=account_id,
        firm_id=firm_id,
    )


def test_core_metrics_r_distribution_and_tag_distributions():
    trades = (
        trade("t1", "200", "100"),
        trade("t2", "100", "200", instrument="ES", session="LONDON"),
        trade(
            "t3", "-100", "100", account_id="account-2", firm_id="apex",
        ),
        trade(
            "t4", "0", "50", instrument="ES", session="LONDON",
            account_id="account-2", firm_id="apex",
        ),
    )
    report = analyze_trade_journal(trades)
    metrics = report.performance

    assert metrics.total_trades == 4
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.breakeven_trades == 1
    assert metrics.gross_profit == D("300")
    assert metrics.gross_loss == D("100")
    assert metrics.net_pnl == D("200")
    assert metrics.win_rate == D("0.5")
    assert metrics.average_win == D("150")
    assert metrics.average_loss == D("100")
    assert metrics.expectancy == D("50")
    assert metrics.profit_factor == D("3")
    assert metrics.profit_factor_state == ProfitFactorState.AVAILABLE

    distribution = report.r_distribution
    assert distribution.complete
    assert distribution.observed_trades == 4
    assert distribution.mean_r == D("0.375")
    assert distribution.median_r == D("0.25")
    assert distribution.minimum_r == D("-1")
    assert distribution.maximum_r == D("2")
    assert dict(distribution.buckets) == {
        "LOSS_2R_OR_WORSE": 0,
        "LOSS_1_TO_2R": 1,
        "LOSS_UNDER_1R": 0,
        "BREAKEVEN": 1,
        "WIN_UNDER_1R": 1,
        "WIN_1_TO_2R": 0,
        "WIN_2R_OR_BETTER": 1,
    }
    assert distribution.values == (
        ("t1", D("2")), ("t2", D("0.5")),
        ("t3", D("-1")), ("t4", D("0")),
    )

    sessions = {item.key: item.performance for item in report.session_distribution}
    instruments = {
        item.key: item.performance for item in report.instrument_distribution
    }
    accounts = {item.key: item.performance for item in report.account_distribution}
    firms = {item.key: item.performance for item in report.firm_distribution}
    assert sessions["NEW_YORK"].total_trades == 2
    assert sessions["LONDON"].net_pnl == D("100")
    assert instruments["ES"].total_trades == 2
    assert accounts["account-2"].net_pnl == D("-100")
    assert firms["apex"].losing_trades == 1
    assert not report.execution_authorized


def test_empty_journal_has_stable_zero_metrics_and_undefined_ratios():
    report = analyze_trade_journal(())
    metrics = report.performance
    assert metrics.total_trades == 0
    assert metrics.gross_profit == D("0")
    assert metrics.gross_loss == D("0")
    assert metrics.net_pnl == D("0")
    assert metrics.win_rate == D("0")
    assert metrics.average_win == D("0")
    assert metrics.average_loss == D("0")
    assert metrics.expectancy == D("0")
    assert metrics.profit_factor is None
    assert metrics.profit_factor_state == ProfitFactorState.NO_PROFIT_OR_LOSS
    assert report.r_distribution.observed_trades == 0
    assert report.r_distribution.mean_r is None
    assert report.r_distribution.median_r is None
    assert report.r_distribution.minimum_r is None
    assert report.r_distribution.maximum_r is None
    assert report.session_distribution == ()
    assert report.instrument_distribution == ()
    assert report.account_distribution == ()
    assert report.firm_distribution == ()


def test_profit_factor_handles_no_losses_and_no_wins_without_division_errors():
    all_wins = analyze_trade_journal((trade("w1", "25", "10"),)).performance
    assert all_wins.profit_factor is None
    assert all_wins.profit_factor_state == ProfitFactorState.NO_GROSS_LOSS

    all_losses = analyze_trade_journal((trade("l1", "-25", "10"),)).performance
    assert all_losses.profit_factor == D("0")
    assert all_losses.profit_factor_state == ProfitFactorState.AVAILABLE

    breakeven = analyze_trade_journal((trade("b1", "0", "10"),)).performance
    assert breakeven.profit_factor is None
    assert breakeven.profit_factor_state == ProfitFactorState.NO_PROFIT_OR_LOSS


def test_missing_risk_is_reported_and_does_not_invent_an_r_multiple():
    report = analyze_trade_journal((
        trade("known", "100", "50"),
        trade("missing", "75", None),
    ))
    distribution = report.r_distribution
    assert distribution.observed_trades == 1
    assert distribution.missing_risk_trade_ids == ("missing",)
    assert not distribution.complete
    assert distribution.values == (("known", D("2")),)
    assert distribution.mean_r == D("2")
    assert report.performance.net_pnl == D("175")


@pytest.mark.parametrize("changes", [
    {"trade_id": ""},
    {"instrument": " "},
    {"session": ""},
    {"account_id": ""},
    {"firm_id": ""},
    {"realized_pnl": D("NaN")},
    {"realized_pnl": 10.0},
    {"initial_risk": D("0")},
    {"initial_risk": D("-1")},
    {"initial_risk": 10.0},
])
def test_invalid_or_lossy_trade_data_is_rejected(changes):
    values = dict(
        trade_id="t1", realized_pnl=D("10"), initial_risk=D("5"),
        instrument="NQ", session="NEW_YORK", account_id="a1", firm_id="topstep",
    )
    values.update(changes)
    with pytest.raises(ValueError):
        ClosedJournalTrade(**values)


def test_duplicate_ids_and_mutable_input_containers_are_rejected():
    item = trade("t1", "10", "5")
    with pytest.raises(ValueError, match="unique"):
        analyze_trade_journal((item, item))
    with pytest.raises(ValueError, match="immutable tuple"):
        analyze_trade_journal([item])
    with pytest.raises(ValueError, match="ClosedJournalTrade"):
        analyze_trade_journal((object(),))


def test_analysis_and_input_records_are_immutable_and_side_effect_free():
    item = trade("t1", "10", "5")
    report = analyze_trade_journal((item,))
    assert item.realized_pnl == D("10")
    assert item.r_multiple == D("2")
    assert not report.execution_authorized
    with pytest.raises(FrozenInstanceError):
        item.realized_pnl = D("999")
    with pytest.raises(FrozenInstanceError):
        report.performance.net_pnl = D("999")
