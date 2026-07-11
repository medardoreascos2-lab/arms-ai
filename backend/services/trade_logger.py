import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from backend.models.trade_plan import TradePlan


class TradeLogger:
    def __init__(self, file_path: str = "data/trade_plans.jsonl"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, trade_plan: TradePlan) -> None:
        record = asdict(trade_plan)
        record["created_at"] = datetime.now().isoformat()

        with self.file_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def show_confirmation(self) -> None:
        print("------ TRADE LOGGER ------")
        print(f"Plan guardado en: {self.file_path}")