from __future__ import annotations

import math


class SpreadAuthorityV2:
    """Resolve spread points from a validated runtime bid/ask quote."""

    def resolve_spread_points(
        self,
        *,
        symbol: str,
        bid: float | None,
        ask: float | None,
    ) -> float:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        if bid is None or ask is None:
            raise RuntimeError(
                "complete runtime bid/ask quote is required"
            )

        bid_value = float(bid)
        ask_value = float(ask)

        if (
            not math.isfinite(bid_value)
            or not math.isfinite(ask_value)
            or bid_value <= 0.0
            or ask_value <= 0.0
        ):
            raise ValueError(
                "bid and ask must be finite positive values"
            )

        if ask_value < bid_value:
            raise ValueError(
                "crossed quote is not a valid spread authority input"
            )

        return ask_value - bid_value
