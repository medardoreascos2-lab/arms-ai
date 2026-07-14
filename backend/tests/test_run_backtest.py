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
        def show(self):
            print("BACKTEST OK")

    class DummyEngine:
        def __init__(self, pipeline):
            self.pipeline = pipeline

        def run_from_csv(self, file_path):
            assert Path(file_path).exists()
            return DummyResult()

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
    )

    main([str(file_path)])
