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
        def __init__(
            self,
            pipeline,
            minimum_candles,
        ):
            self.pipeline = pipeline
            self.minimum_candles = minimum_candles

        def run_from_csv(self, file_path):
            assert Path(file_path).exists()
            assert self.minimum_candles == 50
            return DummyResult()

    monkeypatch.setattr(
        "backend.backtesting.run_backtest.BacktestEngine",
        DummyEngine,
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
        def show(self):
            pass

    class DummyEngine:
        def __init__(
            self,
            pipeline,
            minimum_candles,
        ):
            captured["pipeline"] = pipeline
            captured["minimum_candles"] = minimum_candles

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

    main([str(file_path)])

    assert captured["collector"] is None
    assert captured["mode"] is PipelineMode.BACKTEST
    assert captured["minimum_candles"] == 50
