from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ParameterEvaluation:
    parameters: dict[str, Any]
    net_profit: float
    profit_factor: float | None
    max_drawdown: float
    win_rate: float
    result: Any


class ParameterEvaluator:
    """
    Ejecuta un backtest con una combinación de parámetros
    y normaliza sus métricas principales.
    """

    def __init__(
        self,
        engine_factory: Callable[
            [dict[str, Any]],
            Any,
        ],
    ) -> None:
        if not callable(engine_factory):
            raise TypeError(
                "engine_factory debe ser callable."
            )

        self.engine_factory = engine_factory

    def evaluate(
        self,
        parameters: dict[str, Any],
        candles: list[Any],
        warmup_count: int = 0,
    ) -> ParameterEvaluation:
        if not candles:
            raise ValueError(
                "ParameterEvaluator requiere candles."
            )

        if (
            not isinstance(
                warmup_count,
                int,
            )
            or isinstance(
                warmup_count,
                bool,
            )
        ):
            raise TypeError(
                "warmup_count debe ser int."
            )

        if warmup_count < 0:
            raise ValueError(
                "warmup_count no puede ser negativo."
            )

        if warmup_count >= len(candles):
            raise ValueError(
                "warmup_count debe dejar al menos "
                "una candle OOS."
            )

        parameters_copy = dict(parameters)

        engine = self.engine_factory(
            parameters_copy
        )

        run_single_pass = getattr(
            engine,
            "run_single_pass",
            None,
        )

        if not callable(
            run_single_pass
        ):
            raise TypeError(
                "El engine debe implementar "
                "run_single_pass() para evaluación "
                "causal de candles."
            )

        if warmup_count > 0:
            result = run_single_pass(
                candles,
                minimum_candles=(
                    warmup_count + 1
                ),
            )
        else:
            result = run_single_pass(
                candles
            )

        statistics = getattr(
            result,
            "statistics",
            None,
        )

        if statistics is None:
            raise ValueError(
                "El resultado requiere statistics."
            )

        return ParameterEvaluation(
            parameters=parameters_copy,
            net_profit=float(
                getattr(
                    statistics,
                    "net_profit",
                    0.0,
                )
            ),
            profit_factor=self._optional_float(
                getattr(
                    statistics,
                    "profit_factor",
                    None,
                )
            ),
            max_drawdown=float(
                getattr(
                    statistics,
                    "max_drawdown",
                    0.0,
                )
            ),
            win_rate=float(
                getattr(
                    statistics,
                    "win_rate",
                    0.0,
                )
            ),
            result=result,
        )

    def _optional_float(
        self,
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        return float(value)
