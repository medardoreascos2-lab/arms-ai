import csv
from datetime import datetime

from backend.backtesting.trade_journal_exporter import (
    TradeJournalExporter,
)


class SimulatedTradeStub:
    def __init__(
        self,
        *,
        symbol="TEST",
        timeframe="1m",
        direction="BUSCAR COMPRAS",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        exit_price=104.0,
        result="TAKE PROFIT",
        contracts=2,
        point_value=2.0,
        pnl=16.0,
        opened_at=None,
        closed_at=None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.exit_price = exit_price
        self.result = result
        self.contracts = contracts
        self.point_value = point_value
        self.pnl = pnl
        self.opened_at = opened_at or datetime(
            2026,
            1,
            1,
            9,
            30,
        )
        self.closed_at = closed_at or datetime(
            2026,
            1,
            1,
            9,
            31,
        )


def test_trade_journal_exporter_writes_csv(tmp_path):
    file_path = tmp_path / "trade_journal.csv"

    trades = [
        SimulatedTradeStub(),
        SimulatedTradeStub(
            direction="BUSCAR VENTAS",
            entry_price=105.0,
            stop_loss=107.0,
            take_profit=101.0,
            exit_price=107.0,
            result="STOP LOSS",
            pnl=-8.0,
        ),
    ]

    exporter = TradeJournalExporter()

    exporter.export_csv(
        trades=trades,
        file_path=file_path,
    )

    assert file_path.exists()

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    assert len(rows) == 2

    first = rows[0]

    assert first["symbol"] == "TEST"
    assert first["timeframe"] == "1m"
    assert first["direction"] == "BUSCAR COMPRAS"
    assert first["result"] == "TAKE PROFIT"
    assert float(first["pnl"]) == 16.0


def test_trade_journal_exporter_writes_expected_columns(
    tmp_path,
):
    file_path = tmp_path / "trade_journal.csv"

    TradeJournalExporter().export_csv(
        trades=[SimulatedTradeStub()],
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames == [
            "opened_at",
            "closed_at",
            "symbol",
            "timeframe",
            "direction",
            "entry_price",
            "stop_loss",
            "take_profit",
            "exit_price",
            "result",
            "contracts",
            "point_value",
            "pnl",
            "duration_seconds",
        ]


def test_trade_journal_exporter_handles_empty_trades(
    tmp_path,
):
    file_path = tmp_path / "empty_journal.csv"

    TradeJournalExporter().export_csv(
        trades=[],
        file_path=file_path,
    )

    assert file_path.exists()

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    assert rows == []


def test_trade_journal_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "trade_journal.csv"
    )

    TradeJournalExporter().export_csv(
        trades=[SimulatedTradeStub()],
        file_path=file_path,
    )

    assert file_path.exists()
