from backend.backtesting.equity_curve import EquityCurve


def test_equity_curve_starts_with_initial_balance():
    curve = EquityCurve(initial_balance=17000)

    assert curve.balance == 17000
    assert curve.peak_balance == 17000
    assert curve.max_drawdown == 0
    assert curve.points == []


def test_equity_curve_updates_balance():
    curve = EquityCurve(initial_balance=17000)

    curve.add_trade(100)
    curve.add_trade(-50)
    curve.add_trade(25)

    assert curve.balance == 17075

    assert [
        point.balance
        for point in curve.points
    ] == [
        17100,
        17050,
        17075,
    ]


def test_equity_curve_tracks_peak_balance():
    curve = EquityCurve(initial_balance=1000)

    curve.add_trade(100)
    curve.add_trade(-50)
    curve.add_trade(200)

    assert curve.peak_balance == 1250


def test_equity_curve_tracks_drawdown():
    curve = EquityCurve(initial_balance=1000)

    curve.add_trade(100)
    curve.add_trade(-150)

    assert curve.max_drawdown == 150


def test_equity_curve_recovery_after_new_peak():
    curve = EquityCurve(initial_balance=1000)

    curve.add_trade(100)
    curve.add_trade(-50)
    curve.add_trade(200)

    assert curve.peak_balance == 1250
    assert curve.max_drawdown == 50
