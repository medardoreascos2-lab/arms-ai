from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from backend.models.candle import Candle


class CsvCandleLoaderV2:
    """
    Carga velas históricas desde un archivo CSV
    y las convierte en instancias de Candle.
    """

    REQUIRED_COLUMNS = (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    def __init__(
        self,
        *,
        csv_path,
        symbol: str,
        timeframe: str,
    ) -> None:

        normalized_symbol = str(
            symbol
        ).strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        normalized_timeframe = str(
            timeframe
        ).strip().lower()

        if not normalized_timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        self.csv_path = Path(
            csv_path
        )

        self.symbol = normalized_symbol
        self.timeframe = normalized_timeframe

    def load(self) -> list[Candle]:

        if not self.csv_path.exists():
            raise FileNotFoundError(
                self.csv_path
            )

        if not self.csv_path.is_file():
            raise FileNotFoundError(
                self.csv_path
            )

        if self.csv_path.stat().st_size == 0:
            raise ValueError(
                "El archivo CSV está vacío."
            )

        try:
            with self.csv_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as file:
                reader = csv.DictReader(
                    file
                )

                fieldnames = reader.fieldnames

                if not fieldnames:
                    raise ValueError(
                        "El archivo CSV está vacío."
                    )

                normalized_columns = {
                    str(column).strip().lower()
                    for column in fieldnames
                    if column is not None
                }

                for column in self.REQUIRED_COLUMNS:
                    if column not in normalized_columns:
                        raise ValueError(
                            f"Falta la columna requerida: {column}."
                        )

                candles: list[Candle] = []

                for row_number, row in enumerate(
                    reader,
                    start=2,
                ):
                    normalized_row = {
                        str(key).strip().lower(): value
                        for key, value in row.items()
                        if key is not None
                    }

                    if not any(
                        str(value or "").strip()
                        for value in normalized_row.values()
                    ):
                        continue

                    timestamp = self._parse_timestamp(
                        normalized_row.get(
                            "timestamp"
                        ),
                        row_number=row_number,
                    )

                    open_price = self._parse_number(
                        normalized_row.get(
                            "open"
                        ),
                        field_name="open",
                        row_number=row_number,
                    )

                    high_price = self._parse_number(
                        normalized_row.get(
                            "high"
                        ),
                        field_name="high",
                        row_number=row_number,
                    )

                    low_price = self._parse_number(
                        normalized_row.get(
                            "low"
                        ),
                        field_name="low",
                        row_number=row_number,
                    )

                    close_price = self._parse_number(
                        normalized_row.get(
                            "close"
                        ),
                        field_name="close",
                        row_number=row_number,
                    )

                    volume = self._parse_number(
                        normalized_row.get(
                            "volume"
                        ),
                        field_name="volume",
                        row_number=row_number,
                    )

                    self._validate_ohlc(
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        row_number=row_number,
                    )

                    candle = Candle(
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
                        timestamp=timestamp,
                    )

                    candles.append(
                        candle
                    )

        except UnicodeDecodeError as exc:
            raise ValueError(
                "No se pudo leer el archivo CSV con codificación UTF-8."
            ) from exc

        if not candles:
            raise ValueError(
                "El archivo CSV está vacío."
            )

        candles.sort(
            key=lambda candle: candle.timestamp
        )

        return candles

    @staticmethod
    def _parse_timestamp(
        value,
        *,
        row_number: int,
    ) -> datetime:

        normalized_value = str(
            value or ""
        ).strip()

        if not normalized_value:
            raise ValueError(
                f"timestamp inválido en la fila {row_number}."
            )

        try:
            return datetime.fromisoformat(
                normalized_value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError as exc:
            raise ValueError(
                f"timestamp inválido en la fila {row_number}."
            ) from exc

    @staticmethod
    def _parse_number(
        value,
        *,
        field_name: str,
        row_number: int,
    ) -> float:

        normalized_value = str(
            value or ""
        ).strip()

        try:
            return float(
                normalized_value
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} inválido en la fila {row_number}."
            ) from exc

    @staticmethod
    def _validate_ohlc(
        *,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        row_number: int,
    ) -> None:

        highest_body_price = max(
            open_price,
            close_price,
        )

        lowest_body_price = min(
            open_price,
            close_price,
        )

        if (
            high_price < highest_body_price
            or low_price > lowest_body_price
            or high_price < low_price
        ):
            raise ValueError(
                f"Relación OHLC inválida en la fila {row_number}."
            )
