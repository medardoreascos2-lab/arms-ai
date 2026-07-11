import json
from collections import Counter
from pathlib import Path


class PlanHistoryAnalyzer:
    def __init__(self, file_path: str = "data/trade_plans.jsonl"):
        self.file_path = Path(file_path)

        self.total_plans = 0
        self.authorized_plans = 0
        self.blocked_plans = 0

        self.decisions: Counter[str] = Counter()
        self.confidences: Counter[str] = Counter()
        self.block_reasons: Counter[str] = Counter()

    def analyze(self) -> None:
        self._reset()

        if not self.file_path.exists():
            print(
                f"No existe historial en: {self.file_path}"
            )
            return

        with self.file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        f"Registro inválido ignorado "
                        f"en la línea {line_number}."
                    )
                    continue

                self.total_plans += 1

                decision = record.get(
                    "decision",
                    "DESCONOCIDA",
                )

                confidence = record.get(
                    "confidence",
                    "DESCONOCIDA",
                )

                authorized = bool(
                    record.get("authorized", False)
                )

                reasons = record.get("reasons", [])

                self.decisions[decision] += 1
                self.confidences[confidence] += 1

                if authorized:
                    self.authorized_plans += 1
                else:
                    self.blocked_plans += 1

                    for reason in reasons:
                        self.block_reasons[reason] += 1

    def _reset(self) -> None:
        self.total_plans = 0
        self.authorized_plans = 0
        self.blocked_plans = 0

        self.decisions.clear()
        self.confidences.clear()
        self.block_reasons.clear()

    def show(self) -> None:
        print("------ PLAN HISTORY ANALYZER ------")
        print(f"Planes analizados: {self.total_plans}")
        print(f"Planes autorizados: {self.authorized_plans}")
        print(f"Planes bloqueados: {self.blocked_plans}")

        if self.total_plans == 0:
            print("Todavía no hay datos suficientes.")
            return

        authorization_rate = (
            self.authorized_plans
            / self.total_plans
            * 100
        )

        print(
            f"Tasa de autorización: "
            f"{authorization_rate:.2f}%"
        )

        print("Decisiones:")
        for decision, total in self.decisions.most_common():
            print(f"- {decision}: {total}")

        print("Confianza:")
        for confidence, total in self.confidences.most_common():
            print(f"- {confidence}: {total}")

        if self.block_reasons:
            print("Motivos principales de bloqueo:")

            for reason, total in self.block_reasons.most_common():
                print(f"- {reason}: {total}")