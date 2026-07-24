from __future__ import annotations


class TradeValidatorV2:
    """
    Último filtro de seguridad antes
    de permitir la ejecución de un plan.

    Verifica:

    - aprobación del Trade Planner;
    - reward/risk;
    - distancia del stop;
    - spread;
    - ATR;
    - sesión;
    - noticias;
    - posición abierta;
    - límite diario;
    - antigüedad de la señal.
    """

    def __init__(
        self,
        *,
        minimum_reward_risk_ratio: float,
        minimum_stop_points: float,
        maximum_stop_points: float,
        maximum_spread_points: float,
        minimum_atr_points: float,
        maximum_signal_age_seconds: int,
    ) -> None:
        normalized_minimum_rr = float(
            minimum_reward_risk_ratio
        )

        normalized_minimum_stop = float(
            minimum_stop_points
        )

        normalized_maximum_stop = float(
            maximum_stop_points
        )

        normalized_maximum_spread = float(
            maximum_spread_points
        )

        normalized_minimum_atr = float(
            minimum_atr_points
        )

        normalized_maximum_age = int(
            maximum_signal_age_seconds
        )

        if normalized_minimum_rr <= 0:
            raise ValueError(
                "minimum_reward_risk_ratio "
                "debe ser mayor que cero."
            )

        if normalized_minimum_stop <= 0:
            raise ValueError(
                "minimum_stop_points debe ser "
                "mayor que cero."
            )

        if normalized_maximum_stop <= 0:
            raise ValueError(
                "maximum_stop_points debe ser "
                "mayor que cero."
            )

        if (
            normalized_minimum_stop
            >= normalized_maximum_stop
        ):
            raise ValueError(
                "Los límites de stop están "
                "en un orden inválido."
            )

        if normalized_maximum_spread <= 0:
            raise ValueError(
                "maximum_spread_points debe ser "
                "mayor que cero."
            )

        if normalized_minimum_atr < 0:
            raise ValueError(
                "minimum_atr_points no puede "
                "ser negativo."
            )

        if normalized_maximum_age < 0:
            raise ValueError(
                "maximum_signal_age_seconds no "
                "puede ser negativo."
            )

        self.minimum_reward_risk_ratio = (
            normalized_minimum_rr
        )

        self.minimum_stop_points = (
            normalized_minimum_stop
        )

        self.maximum_stop_points = (
            normalized_maximum_stop
        )

        self.maximum_spread_points = (
            normalized_maximum_spread
        )

        self.minimum_atr_points = (
            normalized_minimum_atr
        )

        self.maximum_signal_age_seconds = (
            normalized_maximum_age
        )

    def validate(
        self,
        *,
        trade_plan: dict[str, object],
        spread_points: float,
        atr_points: float,
        session_allowed: bool,
        news_blocked: bool,
        has_open_position: bool,
        daily_limit_reached: bool,
        signal_age_seconds: int,
    ) -> dict[str, object]:
        if not isinstance(
            trade_plan,
            dict,
        ):
            raise TypeError(
                "trade_plan debe ser un dict."
            )

        normalized_spread = float(
            spread_points
        )

        normalized_atr = float(
            atr_points
        )

        normalized_signal_age = int(
            signal_age_seconds
        )

        if normalized_spread < 0:
            raise ValueError(
                "spread_points no puede ser "
                "negativo."
            )

        if normalized_atr < 0:
            raise ValueError(
                "atr_points no puede ser "
                "negativo."
            )

        if normalized_signal_age < 0:
            raise ValueError(
                "signal_age_seconds no puede "
                "ser negativo."
            )

        reward_risk_ratio = float(
            trade_plan.get(
                "reward_risk_ratio",
                0.0,
            )
        )

        risk_points = float(
            trade_plan.get(
                "risk_points",
                0.0,
            )
        )

        plan_approved = bool(
            trade_plan.get(
                "approved",
                False,
            )
        )

        plan_status = (
            str(
                trade_plan.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        blocking_reasons: list[str] = []
        warnings: list[str] = []

        if (
            not plan_approved
            or plan_status != "ACTIVE"
        ):
            blocking_reasons.append(
                "trade_plan_not_approved"
            )

        if (
            reward_risk_ratio
            < self.minimum_reward_risk_ratio
        ):
            blocking_reasons.append(
                "reward_risk_below_minimum"
            )

        if (
            risk_points
            < self.minimum_stop_points
        ):
            blocking_reasons.append(
                "stop_distance_too_small"
            )

        if (
            risk_points
            > self.maximum_stop_points
        ):
            blocking_reasons.append(
                "stop_distance_too_large"
            )

        if (
            normalized_spread
            > self.maximum_spread_points
        ):
            blocking_reasons.append(
                "spread_too_high"
            )

        elif (
            normalized_spread
            >= self.maximum_spread_points
            * 0.90
        ):
            warnings.append(
                "spread_near_limit"
            )

        if (
            normalized_atr
            < self.minimum_atr_points
        ):
            blocking_reasons.append(
                "atr_below_minimum"
            )

        if not bool(
            session_allowed
        ):
            blocking_reasons.append(
                "session_not_allowed"
            )

        if bool(
            news_blocked
        ):
            blocking_reasons.append(
                "high_impact_news"
            )

        if bool(
            has_open_position
        ):
            blocking_reasons.append(
                "position_already_open"
            )

        if bool(
            daily_limit_reached
        ):
            blocking_reasons.append(
                "daily_limit_reached"
            )

        if (
            normalized_signal_age
            > self.maximum_signal_age_seconds
        ):
            blocking_reasons.append(
                "signal_expired"
            )

        if blocking_reasons:
            approved = False
            status = "INVALID"
            decision = "BLOCK"
        else:
            approved = True
            status = "VALID"
            decision = "ALLOW_EXECUTION"

        return {
            "approved": approved,
            "status": status,
            "decision": decision,
            "blocking_reasons": (
                blocking_reasons
            ),
            "warnings": warnings,
            "inputs": {
                "spread_points": (
                    normalized_spread
                ),
                "atr_points": (
                    normalized_atr
                ),
                "session_allowed": bool(
                    session_allowed
                ),
                "news_blocked": bool(
                    news_blocked
                ),
                "has_open_position": bool(
                    has_open_position
                ),
                "daily_limit_reached": bool(
                    daily_limit_reached
                ),
                "signal_age_seconds": (
                    normalized_signal_age
                ),
                "reward_risk_ratio": (
                    reward_risk_ratio
                ),
                "risk_points": (
                    risk_points
                ),
            },
            "limits": {
                "minimum_reward_risk_ratio": (
                    self.minimum_reward_risk_ratio
                ),
                "minimum_stop_points": (
                    self.minimum_stop_points
                ),
                "maximum_stop_points": (
                    self.maximum_stop_points
                ),
                "maximum_spread_points": (
                    self.maximum_spread_points
                ),
                "minimum_atr_points": (
                    self.minimum_atr_points
                ),
                "maximum_signal_age_seconds": (
                    self.maximum_signal_age_seconds
                ),
            },
        }
