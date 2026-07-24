from __future__ import annotations


class ExecutionDecisionEngineV2:

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    VALID_SMART_MONEY = {
        "BULLISH",
        "BEARISH",
    }

    VALID_REGIMES = {
        "TREND_UP",
        "TREND_DOWN",
        "RANGE",
        "NO_TRADE",
    }

    def __init__(
        self,
        *,
        minimum_probability: float,
        minimum_confluence_score: float,
    ) -> None:

        minimum_probability = float(
            minimum_probability
        )

        minimum_confluence_score = float(
            minimum_confluence_score
        )

        if not (
            0.0 <= minimum_probability <= 1.0
        ):
            raise ValueError(
                "minimum_probability inválido."
            )

        if not (
            0.0 <= minimum_confluence_score <= 1.0
        ):
            raise ValueError(
                "minimum_confluence_score inválido."
            )

        self.minimum_probability = (
            minimum_probability
        )

        self.minimum_confluence_score = (
            minimum_confluence_score
        )

    def evaluate(
        self,
        *,
        signal_direction,
        probability,
        confluence_score,
        smart_money_direction,
        market_regime,
        market_tradable,
        risk_approved,
        sizing_approved,
        contracts,
        has_open_position,
        daily_limit_reached,
        news_blocked,
    ):

        signal_direction = (
            str(signal_direction)
            .strip()
            .upper()
        )

        smart_money_direction = (
            str(smart_money_direction)
            .strip()
            .upper()
        )

        market_regime = (
            str(market_regime)
            .strip()
            .upper()
        )

        probability = float(
            probability
        )

        confluence_score = float(
            confluence_score
        )

        contracts = int(
            contracts
        )

        if (
            signal_direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "signal_direction inválido."
            )

        if not (
            0.0 <= probability <= 1.0
        ):
            raise ValueError(
                "probability inválido."
            )

        if not (
            0.0 <= confluence_score <= 1.0
        ):
            raise ValueError(
                "confluence_score inválido."
            )

        if contracts < 0:
            raise ValueError(
                "contracts inválido."
            )

        blocking = []
        waiting = []

        if not market_tradable:
            blocking.append(
                "market_not_tradable"
            )

        if not risk_approved:
            blocking.append(
                "account_risk_rejected"
            )

        if not sizing_approved:
            blocking.append(
                "position_sizing_rejected"
            )

        if contracts == 0:
            blocking.append(
                "invalid_contracts"
            )

        if has_open_position:
            blocking.append(
                "position_already_open"
            )

        if daily_limit_reached:
            blocking.append(
                "daily_limit_reached"
            )

        if news_blocked:
            blocking.append(
                "high_impact_news"
            )

        if (
            probability
            < self.minimum_probability
        ):
            waiting.append(
                "probability_below_threshold"
            )

        if (
            confluence_score
            < self.minimum_confluence_score
        ):
            waiting.append(
                "confluence_below_threshold"
            )

        if (
            signal_direction == "LONG"
            and smart_money_direction
            != "BULLISH"
        ):
            waiting.append(
                "smart_money_direction_conflict"
            )

        if (
            signal_direction == "SHORT"
            and smart_money_direction
            != "BEARISH"
        ):
            waiting.append(
                "smart_money_direction_conflict"
            )

        if (
            signal_direction == "LONG"
            and market_regime
            != "TREND_UP"
        ):
            waiting.append(
                "market_regime_direction_conflict"
            )

        if (
            signal_direction == "SHORT"
            and market_regime
            != "TREND_DOWN"
        ):
            waiting.append(
                "market_regime_direction_conflict"
            )

        if blocking:
            approved = False
            decision = "BLOCK"

        elif waiting:
            approved = False
            decision = "WAIT"

        else:
            approved = True

            if signal_direction == "LONG":
                decision = "EXECUTE_LONG"
            else:
                decision = "EXECUTE_SHORT"

        return {
            "approved": approved,
            "decision": decision,
            "direction": signal_direction,
            "contracts": contracts,
            "blocking_reasons": blocking,
            "waiting_reasons": waiting,
        }
