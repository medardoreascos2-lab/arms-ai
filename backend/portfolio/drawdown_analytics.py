from __future__ import annotations

import numpy as np


class DrawdownAnalytics:
    """
    Calcula la curva de capital y las métricas
    principales de drawdown.
    """

    def calculate(
        self,
        *,
        returns: list[float],
    ) -> dict[str, object]:
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        values = np.asarray(
            returns,
            dtype=float,
        )

        if not np.isfinite(values).all():
            raise ValueError(
                "returns contiene valores inválidos."
            )

        equity_curve = np.concatenate(
            (
                np.array([1.0]),
                np.cumprod(
                    1.0 + values
                ),
            )
        )

        running_maximum = np.maximum.accumulate(
            equity_curve
        )

        drawdown_curve = (
            equity_curve
            / running_maximum
        ) - 1.0

        trough_index = int(
            np.argmin(
                drawdown_curve
            )
        )

        peak_index = int(
            np.argmax(
                equity_curve[
                    : trough_index + 1
                ]
            )
        )

        maximum_drawdown = float(
            drawdown_curve[
                trough_index
            ]
        )

        maximum_duration = 0
        current_duration = 0

        for drawdown in drawdown_curve:
            if drawdown < 0.0:
                current_duration += 1
                maximum_duration = max(
                    maximum_duration,
                    current_duration,
                )
            else:
                current_duration = 0

        return {
            "equity_curve": [
                float(value)
                for value in equity_curve
            ],
            "drawdown_curve": [
                float(value)
                for value in drawdown_curve
            ],
            "maximum_drawdown": (
                maximum_drawdown
            ),
            "maximum_drawdown_duration": (
                maximum_duration
            ),
            "peak_index": peak_index,
            "trough_index": trough_index,
        }
