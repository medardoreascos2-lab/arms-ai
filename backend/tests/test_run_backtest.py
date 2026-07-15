from pathlib import Path

import pytest

from backend.backtesting.run_backtest import main


def test_run_backtest_requires_csv_argument():
    with pytest.raises(
        SystemExit,
        match="Uso",
    ):
        main([])


def test_run_backtest_rejects_missing_file(tmp_path):
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(
        FileNotFoundError,
    ):
        main([str(missing_file)])


def test_run_backtest_accepts_existing_file(tmp_path, monkeypatch):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    class DummyResult:
        trades = []
        equity_curve = object()

        def show(self):
            print("BACKTEST OK")

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            self.pipeline = pipeline
            self.minimum_candles = minimum_candles
            self.initial_balance = initial_balance

        def run_from_csv(self, file_path):
            assert Path(file_path).exists()
            assert self.minimum_candles == 50
            return DummyResult()

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            pass

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main([str(file_path)])


from backend.pipeline.pipeline_mode import PipelineMode


def test_run_backtest_builds_backtest_pipeline(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyFactory:
        def __init__(self, settings, collector):
            captured["collector"] = collector

        def create(self, mode):
            captured["mode"] = mode
            return object()

    class DummyResult:
        trades = []
        equity_curve = object()

        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            captured["pipeline"] = pipeline
            captured["minimum_candles"] = minimum_candles
            captured["initial_balance"] = initial_balance

        def run_from_csv(self, file_path):
            return DummyResult()

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.PipelineFactory",
        DummyFactory,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            pass

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main([str(file_path)])

    assert captured["collector"] is None
    assert captured["mode"] is PipelineMode.BACKTEST
    assert captured["minimum_candles"] == 50


def test_run_backtest_exports_trade_journal(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"
    journal_path = tmp_path / "reports" / "journal.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyResult:
        trades = [object()]
        equity_curve = object()

        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            pass

        def run_from_csv(self, file_path):
            return DummyResult()

    class DummyExporter:
        def export_csv(self, trades, file_path):
            captured["trades"] = trades
            captured["file_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.TradeJournalExporter",
        DummyExporter,
    )

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            pass

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main(
        [
            str(file_path),
            "--journal",
            str(journal_path),
        ]
    )

    assert captured["trades"] == DummyResult.trades
    assert captured["file_path"] == journal_path


def test_run_backtest_uses_default_journal_path(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyResult:
        trades = []
        equity_curve = object()

        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            pass

        def run_from_csv(self, file_path):
            return DummyResult()

    class DummyExporter:
        def export_csv(self, trades, file_path):
            captured["file_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.TradeJournalExporter",
        DummyExporter,
    )

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            pass

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main([str(file_path)])

    assert str(captured["file_path"]).replace("\\", "/") == (
        "data/reports/trade_journal.csv"
    )


def test_run_backtest_exports_equity_curve(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"
    equity_path = tmp_path / "reports" / "equity.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyResult:
        trades = []
        equity_curve = object()

        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            pass

        def run_from_csv(self, file_path):
            return DummyResult()

    class DummyJournalExporter:
        def export_csv(self, trades, file_path):
            pass

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            captured["equity_curve"] = equity_curve
            captured["file_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.TradeJournalExporter",
        DummyJournalExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main(
        [
            str(file_path),
            "--equity",
            str(equity_path),
        ]
    )

    assert captured["equity_curve"] is DummyResult.equity_curve
    assert captured["file_path"] == equity_path


def test_run_backtest_uses_default_equity_path(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        "\n".join(
            [
                (
                    "timestamp,symbol,timeframe,open,high,"
                    "low,close,volume"
                ),
                (
                    "2026-01-01T09:30:00,TEST,1m,"
                    "100.0,101.0,99.5,100.5,1000"
                ),
            ]
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyResult:
        trades = []
        equity_curve = object()

        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
            initial_balance,
        ):
            pass

        def run_from_csv(self, file_path):
            return DummyResult()

    class DummyJournalExporter:
        def export_csv(self, trades, file_path):
            pass

    class DummyEquityExporter:
        def export_csv(
            self,
            equity_curve,
            file_path,
        ):
            captured["file_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.TradeJournalExporter",
        DummyJournalExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_backtest.EquityCurveExporter",
        DummyEquityExporter,
    )

    main([str(file_path)])

    assert str(captured["file_path"]).replace("\\", "/") == (
        "data/reports/equity_curve.csv"
    )
