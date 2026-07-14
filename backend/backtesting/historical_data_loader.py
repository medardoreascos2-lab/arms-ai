import csv
from datetime import datetime
from pathlib import Path

from backend.models.candle import Candle


class HistoricalDataLoader:
    """
    Carga velas históricas desde archivos CSV
    y las convierte en objetos Candle.
    """

    REQUIRED_COLUMNS = {
        "timestamp",
        "symbol",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    def load_csv(
        self,
        file_path: str | Path,
    ) -> list[Candle]:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe el archivo: {path}"
            )

        candles: list[Candle] = []

        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            fieldnames = set(
                reader.fieldnames or []
            )

            missing_columns = (
                self.REQUIRED_COLUMNS - fieldnames
            )

            if missing_columns:
                missing = ", ".join(
                    sorted(missing_columns)
                )

                raise ValueError(
                    f"Faltan columnas requeridas: {missing}"
                )

            for line_number, row in enumerate(
                reader,
                start=2,
            ):
                try:
                    candle = Candle(
                        symbol=row["symbol"].strip(),
                        timeframe=row["timeframe"].strip(),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        timestamp=datetime.fromisoformat(
                            row["timestamp"].strip()
                        ),
                    )
                except (
                    TypeError,
                    ValueError,
                    KeyError,
                ) as error:
                    raise ValueError(
                        f"Registro inválido en la línea "
                        f"{line_number}: {error}"
                    ) from error

                candles.append(candle)

        if not candles:
            raise ValueError(
                "El archivo no contiene velas."
            )

        candles.sort(
            key=lambda candle: candle.timestamp
        )

        return candles
