from __future__ import annotations

from copy import deepcopy


class LiveAnalysisStore:
    """
    Mantiene el último análisis disponible
    por (symbol, timeframe).
    """

    REQUIRED_FIELDS = (
        "symbol",
        "timeframe",
        "current_price",
        "trend",
        "decision",
        "probability",
        "risk",
        "analyzed_at",
    )

    def __init__(self) -> None:
        self._storage: dict[
            tuple[str, str],
            dict[str, object],
        ] = {}

    def save(
        self,
        analysis: dict[str, object],
    ) -> None:
        for field in self.REQUIRED_FIELDS:
            if field not in analysis:
                raise KeyError(field)

        symbol = str(
            analysis["symbol"]
        ).strip()

        timeframe = str(
            analysis["timeframe"]
        ).strip()

        if not symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        self._storage[
            (symbol, timeframe)
        ] = deepcopy(analysis)

    def get_latest(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object] | None:

        key = (
            str(symbol).strip(),
            str(timeframe).strip(),
        )

        result = self._storage.get(key)

        if result is None:
            return None

        return deepcopy(result)

    def clear(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> None:
        key = (
            str(symbol).strip(),
            str(timeframe).strip(),
        )

        self._storage.pop(
            key,
            None,
        )
