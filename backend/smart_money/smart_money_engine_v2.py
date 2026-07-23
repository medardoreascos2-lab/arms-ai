from __future__ import annotations


class SmartMoneyEngineV2:
    """
    Detecta eventos básicos de Smart Money:

    - BOS
    - CHOCH
    - Liquidity Sweep
    - RANGE
    """

    VALID_DIRECTIONS = {
        "BULLISH",
        "BEARISH",
    }

    def detect_mitigation_block(
        self,
        *,
        direction: str,
        zone_low: float,
        zone_high: float,
        current_low: float,
        current_high: float,
        current_close: float,
    ) -> dict[str, object]:
        normalized_direction = (
            str(
                direction
            )
            .strip()
            .upper()
        )

        if (
            normalized_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction debe ser "
                "BULLISH o BEARISH."
            )

        normalized_zone_low = float(
            zone_low
        )

        normalized_zone_high = float(
            zone_high
        )

        normalized_current_low = float(
            current_low
        )

        normalized_current_high = float(
            current_high
        )

        normalized_current_close = float(
            current_close
        )

        prices = {
            "zone_low": (
                normalized_zone_low
            ),
            "zone_high": (
                normalized_zone_high
            ),
            "current_low": (
                normalized_current_low
            ),
            "current_high": (
                normalized_current_high
            ),
            "current_close": (
                normalized_current_close
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if (
            normalized_zone_high
            <= normalized_zone_low
        ):
            raise ValueError(
                "zone_high debe ser mayor "
                "que zone_low."
            )

        if (
            normalized_current_high
            <= normalized_current_low
        ):
            raise ValueError(
                "current_high debe ser mayor "
                "que current_low."
            )

        if not (
            normalized_current_low
            <= normalized_current_close
            <= normalized_current_high
        ):
            raise ValueError(
                "current_close debe estar dentro "
                "del rango de la vela actual."
            )

        touched = (
            normalized_current_low
            <= normalized_zone_high
            and normalized_current_high
            >= normalized_zone_low
        )

        if normalized_direction == "BULLISH":
            respected = (
                touched
                and normalized_current_close
                > normalized_zone_high
            )
        else:
            respected = (
                touched
                and normalized_current_close
                < normalized_zone_low
            )

        mitigation_block = touched

        return {
            "mitigation_block": (
                mitigation_block
            ),
            "direction": (
                normalized_direction
            ),
            "zone_low": (
                normalized_zone_low
            ),
            "zone_high": (
                normalized_zone_high
            ),
            "current_low": (
                normalized_current_low
            ),
            "current_high": (
                normalized_current_high
            ),
            "current_close": (
                normalized_current_close
            ),
            "touched": touched,
            "respected": respected,
        }


    def detect_breaker_block(
        self,
        *,
        original_direction: str,
        zone_low: float,
        zone_high: float,
        break_close: float,
        retest_price: float,
    ) -> dict[str, object]:
        normalized_direction = (
            str(
                original_direction
            )
            .strip()
            .upper()
        )

        if (
            normalized_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "original_direction debe ser "
                "BULLISH o BEARISH."
            )

        normalized_zone_low = float(
            zone_low
        )

        normalized_zone_high = float(
            zone_high
        )

        normalized_break_close = float(
            break_close
        )

        normalized_retest_price = float(
            retest_price
        )

        prices = {
            "zone_low": (
                normalized_zone_low
            ),
            "zone_high": (
                normalized_zone_high
            ),
            "break_close": (
                normalized_break_close
            ),
            "retest_price": (
                normalized_retest_price
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if (
            normalized_zone_high
            <= normalized_zone_low
        ):
            raise ValueError(
                "zone_high debe ser mayor "
                "que zone_low."
            )

        bullish_breaker = (
            normalized_direction
            == "BEARISH"
            and normalized_break_close
            > normalized_zone_high
        )

        bearish_breaker = (
            normalized_direction
            == "BULLISH"
            and normalized_break_close
            < normalized_zone_low
        )

        breaker_block = (
            bullish_breaker
            or bearish_breaker
        )

        if bullish_breaker:
            direction = "BULLISH"

        elif bearish_breaker:
            direction = "BEARISH"

        else:
            direction = "NONE"

        retested = (
            breaker_block
            and normalized_zone_low
            <= normalized_retest_price
            <= normalized_zone_high
        )

        return {
            "breaker_block": (
                breaker_block
            ),
            "direction": direction,
            "original_direction": (
                normalized_direction
            ),
            "zone_low": (
                normalized_zone_low
            ),
            "zone_high": (
                normalized_zone_high
            ),
            "break_close": (
                normalized_break_close
            ),
            "retest_price": (
                normalized_retest_price
            ),
            "retested": retested,
        }


    def detect_equal_levels(
        self,
        *,
        first_high: float,
        second_high: float,
        first_low: float,
        second_low: float,
        tolerance: float,
    ) -> dict[str, object]:
        prices = {
            "first_high": float(
                first_high
            ),
            "second_high": float(
                second_high
            ),
            "first_low": float(
                first_low
            ),
            "second_low": float(
                second_low
            ),
        }

        normalized_tolerance = float(
            tolerance
        )

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if normalized_tolerance < 0:
            raise ValueError(
                "tolerance no puede ser negativo."
            )

        high_difference = round(
            abs(
                prices["first_high"]
                - prices["second_high"]
            ),
            10,
        )

        low_difference = round(
            abs(
                prices["first_low"]
                - prices["second_low"]
            ),
            10,
        )

        equal_highs = (
            high_difference
            <= normalized_tolerance
        )

        equal_lows = (
            low_difference
            <= normalized_tolerance
        )

        if (
            equal_highs
            and equal_lows
        ):
            liquidity_type = "BOTH"

        elif equal_highs:
            liquidity_type = "BUY_SIDE"

        elif equal_lows:
            liquidity_type = "SELL_SIDE"

        else:
            liquidity_type = "NONE"

        return {
            "equal_highs": equal_highs,
            "equal_lows": equal_lows,
            "liquidity_type": (
                liquidity_type
            ),
            "high_difference": (
                high_difference
            ),
            "low_difference": (
                low_difference
            ),
            "tolerance": (
                normalized_tolerance
            ),
            "first_high": (
                prices["first_high"]
            ),
            "second_high": (
                prices["second_high"]
            ),
            "first_low": (
                prices["first_low"]
            ),
            "second_low": (
                prices["second_low"]
            ),
        }


    def evaluate_price_zone(
        self,
        *,
        range_high: float,
        range_low: float,
        current_price: float,
    ) -> dict[str, object]:
        normalized_high = float(
            range_high
        )

        normalized_low = float(
            range_low
        )

        normalized_price = float(
            current_price
        )

        prices = {
            "range_high": (
                normalized_high
            ),
            "range_low": (
                normalized_low
            ),
            "current_price": (
                normalized_price
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if normalized_high <= normalized_low:
            raise ValueError(
                "range_high debe ser mayor "
                "que range_low."
            )

        if not (
            normalized_low
            <= normalized_price
            <= normalized_high
        ):
            raise ValueError(
                "current_price debe estar dentro "
                "del rango."
            )

        range_size = (
            normalized_high
            - normalized_low
        )

        equilibrium = (
            normalized_low
            + range_size / 2.0
        )

        position_percent = round(
            (
                normalized_price
                - normalized_low
            )
            / range_size
            * 100.0,
            2,
        )

        if position_percent < 50.0:
            zone = "DISCOUNT"
        elif position_percent > 50.0:
            zone = "PREMIUM"
        else:
            zone = "EQUILIBRIUM"

        return {
            "zone": zone,
            "equilibrium": round(
                equilibrium,
                10,
            ),
            "position_percent": (
                position_percent
            ),
            "range_high": (
                normalized_high
            ),
            "range_low": (
                normalized_low
            ),
            "current_price": (
                normalized_price
            ),
            "range_size": round(
                range_size,
                10,
            ),
        }


    def detect_order_block(
        self,
        *,
        candle_open: float,
        candle_high: float,
        candle_low: float,
        candle_close: float,
        impulse_direction: str,
    ) -> dict[str, object]:
        normalized_open = float(
            candle_open
        )
        normalized_high = float(
            candle_high
        )
        normalized_low = float(
            candle_low
        )
        normalized_close = float(
            candle_close
        )

        normalized_impulse_direction = (
            str(
                impulse_direction
            )
            .strip()
            .upper()
        )

        if (
            normalized_impulse_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "impulse_direction debe ser "
                "BULLISH o BEARISH."
            )

        prices = {
            "candle_open": (
                normalized_open
            ),
            "candle_high": (
                normalized_high
            ),
            "candle_low": (
                normalized_low
            ),
            "candle_close": (
                normalized_close
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if normalized_high <= normalized_low:
            raise ValueError(
                "candle_high debe ser mayor "
                "que candle_low."
            )

        if not (
            normalized_low
            <= normalized_open
            <= normalized_high
        ):
            raise ValueError(
                "candle_open debe estar dentro "
                "del rango de la vela."
            )

        if not (
            normalized_low
            <= normalized_close
            <= normalized_high
        ):
            raise ValueError(
                "candle_close debe estar dentro "
                "del rango de la vela."
            )

        if normalized_close < normalized_open:
            source_candle = "BEARISH"
        elif normalized_close > normalized_open:
            source_candle = "BULLISH"
        else:
            source_candle = "DOJI"

        bullish_order_block = (
            normalized_impulse_direction
            == "BULLISH"
            and source_candle
            == "BEARISH"
        )

        bearish_order_block = (
            normalized_impulse_direction
            == "BEARISH"
            and source_candle
            == "BULLISH"
        )

        if bullish_order_block:
            order_block = True
            direction = "BULLISH"
            zone_low = normalized_low
            zone_high = normalized_open

        elif bearish_order_block:
            order_block = True
            direction = "BEARISH"
            zone_low = normalized_open
            zone_high = normalized_high

        else:
            order_block = False
            direction = "NONE"
            zone_low = None
            zone_high = None

        zone_size = (
            round(
                float(
                    zone_high
                    - zone_low
                ),
                10,
            )
            if (
                zone_low is not None
                and zone_high is not None
            )
            else 0.0
        )

        return {
            "order_block": order_block,
            "direction": direction,
            "source_candle": (
                source_candle
            ),
            "zone_low": zone_low,
            "zone_high": zone_high,
            "zone_size": zone_size,
            "impulse_direction": (
                normalized_impulse_direction
            ),
            "candle_open": normalized_open,
            "candle_high": normalized_high,
            "candle_low": normalized_low,
            "candle_close": (
                normalized_close
            ),
        }


    def detect_fvg(
        self,
        *,
        first_high: float,
        first_low: float,
        second_high: float,
        second_low: float,
        third_high: float,
        third_low: float,
    ) -> dict[str, object]:
        prices = {
            "first_high": float(
                first_high
            ),
            "first_low": float(
                first_low
            ),
            "second_high": float(
                second_high
            ),
            "second_low": float(
                second_low
            ),
            "third_high": float(
                third_high
            ),
            "third_low": float(
                third_low
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        candle_ranges = [
            (
                "first_high",
                prices["first_high"],
                "first_low",
                prices["first_low"],
            ),
            (
                "second_high",
                prices["second_high"],
                "second_low",
                prices["second_low"],
            ),
            (
                "third_high",
                prices["third_high"],
                "third_low",
                prices["third_low"],
            ),
        ]

        for (
            high_name,
            high_value,
            low_name,
            low_value,
        ) in candle_ranges:
            if high_value <= low_value:
                raise ValueError(
                    f"{high_name} debe ser mayor "
                    f"que {low_name}."
                )

        bullish_fvg = (
            prices["third_low"]
            > prices["first_high"]
        )

        bearish_fvg = (
            prices["third_high"]
            < prices["first_low"]
        )

        if bullish_fvg:
            direction = "BULLISH"
            gap_low = prices["first_high"]
            gap_high = prices["third_low"]

        elif bearish_fvg:
            direction = "BEARISH"
            gap_low = prices["third_high"]
            gap_high = prices["first_low"]

        else:
            direction = "NONE"
            gap_low = None
            gap_high = None

        gap_size = (
            round(
                float(
                    gap_high
                    - gap_low
                ),
                10,
            )
            if (
                gap_low is not None
                and gap_high is not None
            )
            else 0.0
        )

        return {
            "fvg": (
                bullish_fvg
                or bearish_fvg
            ),
            "direction": direction,
            "gap_low": gap_low,
            "gap_high": gap_high,
            "gap_size": gap_size,
            "first_high": (
                prices["first_high"]
            ),
            "first_low": (
                prices["first_low"]
            ),
            "second_high": (
                prices["second_high"]
            ),
            "second_low": (
                prices["second_low"]
            ),
            "third_high": (
                prices["third_high"]
            ),
            "third_low": (
                prices["third_low"]
            ),
        }


    def evaluate(
        self,
        *,
        previous_high: float,
        previous_low: float,
        current_high: float,
        current_low: float,
        close_price: float,
        previous_direction: str
        | None = None,
    ) -> dict[str, object]:
        normalized_previous_high = float(
            previous_high
        )

        normalized_previous_low = float(
            previous_low
        )

        normalized_current_high = float(
            current_high
        )

        normalized_current_low = float(
            current_low
        )

        normalized_close = float(
            close_price
        )

        normalized_previous_direction = None

        if previous_direction is not None:
            normalized_previous_direction = (
                str(
                    previous_direction
                )
                .strip()
                .upper()
            )

            if (
                normalized_previous_direction
                not in self.VALID_DIRECTIONS
            ):
                raise ValueError(
                    "previous_direction debe ser "
                    "BULLISH o BEARISH."
                )

        prices = {
            "previous_high": (
                normalized_previous_high
            ),
            "previous_low": (
                normalized_previous_low
            ),
            "current_high": (
                normalized_current_high
            ),
            "current_low": (
                normalized_current_low
            ),
            "close_price": (
                normalized_close
            ),
        }

        for field_name, value in prices.items():
            if value <= 0:
                raise ValueError(
                    f"{field_name} debe ser "
                    "mayor que cero."
                )

        if (
            normalized_previous_high
            <= normalized_previous_low
        ):
            raise ValueError(
                "previous_high debe ser mayor "
                "que previous_low."
            )

        if (
            normalized_current_high
            <= normalized_current_low
        ):
            raise ValueError(
                "current_high debe ser mayor "
                "que current_low."
            )

        if not (
            normalized_current_low
            <= normalized_close
            <= normalized_current_high
        ):
            raise ValueError(
                "close_price debe estar dentro "
                "del rango de la vela actual."
            )

        bullish_break = (
            normalized_current_high
            > normalized_previous_high
            and normalized_close
            > normalized_previous_high
        )

        bearish_break = (
            normalized_current_low
            < normalized_previous_low
            and normalized_close
            < normalized_previous_low
        )

        buy_side_sweep = (
            normalized_current_high
            > normalized_previous_high
            and normalized_close
            <= normalized_previous_high
        )

        sell_side_sweep = (
            normalized_current_low
            < normalized_previous_low
            and normalized_close
            >= normalized_previous_low
        )

        bos = False
        choch = False
        liquidity_sweep = False
        sweep_side = None
        broken_level = None
        event = "RANGE"
        direction = "RANGE"

        if bullish_break:
            direction = "BULLISH"
            broken_level = (
                normalized_previous_high
            )

            if (
                normalized_previous_direction
                == "BEARISH"
            ):
                choch = True
                event = "CHOCH"
            else:
                bos = True
                event = "BOS"

        elif bearish_break:
            direction = "BEARISH"
            broken_level = (
                normalized_previous_low
            )

            if (
                normalized_previous_direction
                == "BULLISH"
            ):
                choch = True
                event = "CHOCH"
            else:
                bos = True
                event = "BOS"

        elif buy_side_sweep:
            liquidity_sweep = True
            sweep_side = "BUY_SIDE"
            direction = "RANGE"
            event = "LIQUIDITY_SWEEP"
            broken_level = (
                normalized_previous_high
            )

        elif sell_side_sweep:
            liquidity_sweep = True
            sweep_side = "SELL_SIDE"
            direction = "RANGE"
            event = "LIQUIDITY_SWEEP"
            broken_level = (
                normalized_previous_low
            )

        return {
            "bos": bos,
            "choch": choch,
            "liquidity_sweep": (
                liquidity_sweep
            ),
            "sweep_side": sweep_side,
            "event": event,
            "direction": direction,
            "broken_level": (
                broken_level
            ),
            "previous_direction": (
                normalized_previous_direction
            ),
            "previous_high": (
                normalized_previous_high
            ),
            "previous_low": (
                normalized_previous_low
            ),
            "current_high": (
                normalized_current_high
            ),
            "current_low": (
                normalized_current_low
            ),
            "close_price": (
                normalized_close
            ),
        }
