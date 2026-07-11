import json
from dataclasses import asdict
from pathlib import Path

from backend.models.simulated_trade import SimulatedTrade


class SimulatedTradeLogger:
    def __init__(
        self,
        file_path: str = "data/simulated_trades.jsonl",
    ):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(self, trade: SimulatedTrade) -> None:
        record = asdict(trade)

        record["opened_at"] = trade.opened_at.isoformat()
        record["closed_at"] = trade.closed_at.isoformat()

        with self.file_path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    def show_confirmation(self) -> None:
        print("------ SIMULATED TRADE LOGGER ------")
        print(
            f"Operación guardada en: "
            f"{self.file_path}"
        )