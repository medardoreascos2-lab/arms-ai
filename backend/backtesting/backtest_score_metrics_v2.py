from __future__ import annotations

from math import inf
from typing import Any


def normalize_backtest_win_rate_v2(
    value,
) -> float:
    """
    Normaliza win rate al contrato 0..1 esperado
    por BacktestCompositeScoreV2.

    Acepta tanto 0.70 como 70.0.
    """

    normalized = float(
        value
    )

    if normalized > 1.0:
        normalized = (
            normalized / 100.0
        )

    return max(
        0.0,
        min(
            1.0,
            normalized,
        ),
    )


def scoring_profit_factor_v2(
    statistics,
) -> float:
    """
    Traduce la representación estadística de PF
    al dominio específico del scorer.

    StatisticsEngine conserva None cuando gross_loss
    es cero. Para scoring:

    - muestra rentable sin pérdidas -> +infinity;
    - muestra vacía/breakeven sin PF -> 0;
    - PF definido -> se conserva.
    """

    profit_factor = getattr(
        statistics,
        "profit_factor",
        None,
    )

    if profit_factor is not None:
        return float(
            profit_factor
        )

    total_trades = int(
        getattr(
            statistics,
            "total_trades",
            0,
        )
    )

    gross_profit = float(
        getattr(
            statistics,
            "gross_profit",
            0.0,
        )
    )

    gross_loss = abs(
        float(
            getattr(
                statistics,
                "gross_loss",
                0.0,
            )
        )
    )

    if (
        total_trades > 0
        and gross_profit > 0.0
        and gross_loss == 0.0
    ):
        return inf

    return 0.0


def build_backtest_score_metrics_v2(
    statistics,
) -> dict[str, Any]:
    """
    Construye el contrato canónico de métricas
    consumido por BacktestCompositeScoreV2.

    No modifica el objeto statistics ni altera
    sus semánticas públicas/reportables.
    """

    if statistics is None:
        raise ValueError(
            "statistics es requerido."
        )

    return {
        "net_pnl": float(
            getattr(
                statistics,
                "net_profit",
                0.0,
            )
        ),
        "win_rate": (
            normalize_backtest_win_rate_v2(
                getattr(
                    statistics,
                    "win_rate",
                    0.0,
                )
            )
        ),
        "profit_factor": (
            scoring_profit_factor_v2(
                statistics
            )
        ),
        "expectancy": float(
            getattr(
                statistics,
                "expectancy",
                0.0,
            )
        ),
        "maximum_drawdown": abs(
            float(
                getattr(
                    statistics,
                    "max_drawdown",
                    0.0,
                )
            )
        ),
        "total_trades": int(
            getattr(
                statistics,
                "total_trades",
                0,
            )
        ),
    }
