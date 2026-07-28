from __future__ import annotations

from math import isfinite
from typing import Any


class DecisionCouncilV2:
    """
    Consolida las decisiones de los motores V2 de ARMS AI.

    El consejo recibe las evaluaciones de:

    - Trend Engine V2
    - Market Regime Engine
    - Probability Engine V2
    - Confluence Engine V2
    - Execution Manager V2

    Además aplica gates obligatorios:

    - riesgo autorizado;
    - sesión autorizada;
    - ausencia de bloqueos de ejecución.

    El resultado final puede ser:

    - EXECUTE_LONG
    - EXECUTE_SHORT
    - WAIT
    - BLOCK
    - REJECT
    """

    DIRECTIONAL_MEMBERS = (
        "trend",
        "market_regime",
        "probability",
        "confluence",
        "execution",
    )

    CONFIDENCE_WEIGHTS: dict[str, float] = {
        "trend": 0.20,
        "market_regime": 0.15,
        "probability": 0.25,
        "confluence": 0.30,
        "execution": 0.10,
    }

    MINIMUM_DIRECTIONAL_VOTES = 3
    MINIMUM_CONFIDENCE = 70.0

    def evaluate(
        self,
        *,
        trend_result: dict[str, Any],
        market_regime_result: dict[str, Any],
        probability_result: dict[str, Any],
        confluence_result: dict[str, Any],
        execution_result: dict[str, Any],
        risk_approved: bool,
        session_allowed: bool,
    ) -> dict[str, Any]:
        self._validate_result(
            name="trend_result",
            value=trend_result,
        )
        self._validate_result(
            name="market_regime_result",
            value=market_regime_result,
        )
        self._validate_result(
            name="probability_result",
            value=probability_result,
        )
        self._validate_result(
            name="confluence_result",
            value=confluence_result,
        )
        self._validate_result(
            name="execution_result",
            value=execution_result,
        )

        source_results = {
            "trend": trend_result,
            "market_regime": market_regime_result,
            "probability": probability_result,
            "confluence": confluence_result,
            "execution": execution_result,
        }

        votes = {
            member: self._extract_vote(
                member=member,
                result=result,
            )
            for member, result
            in source_results.items()
        }

        vote_summary = {
            "BUY": 0,
            "SELL": 0,
            "WAIT": 0,
            "BLOCK": 0,
        }

        for vote in votes.values():
            vote_summary[vote] += 1

        blocking_reasons: list[str] = []
        confirmations: list[str] = []
        warnings: list[str] = []

        if not bool(risk_approved):
            blocking_reasons.append(
                "risk_not_approved"
            )

        if not bool(session_allowed):
            blocking_reasons.append(
                "session_not_allowed"
            )

        execution_blockers = self._extract_string_list(
            execution_result.get(
                "blocking_reasons"
            )
        )

        self._extend_unique(
            blocking_reasons,
            execution_blockers,
        )

        if votes["execution"] == "BLOCK":
            self._append_unique(
                blocking_reasons,
                "execution_blocked",
            )

        confluence_blockers = self._extract_string_list(
            confluence_result.get(
                "blocking_reasons"
            )
        )

        self._extend_unique(
            blocking_reasons,
            confluence_blockers,
        )

        for member, vote in votes.items():
            if vote in {
                "BUY",
                "SELL",
            }:
                confirmations.append(
                    f"{member}:{vote}"
                )
            elif vote == "WAIT":
                warnings.append(
                    f"{member}:WAIT"
                )
            elif vote == "BLOCK":
                warnings.append(
                    f"{member}:BLOCK"
                )

        confidence_components = {
            member: self._extract_confidence(
                member=member,
                result=result,
            )
            for member, result
            in source_results.items()
        }

        confidence = self._weighted_confidence(
            confidence_components
        )

        buy_votes = vote_summary["BUY"]
        sell_votes = vote_summary["SELL"]

        if buy_votes > sell_votes:
            direction = "BUY"
            directional_votes = buy_votes
        elif sell_votes > buy_votes:
            direction = "SELL"
            directional_votes = sell_votes
        else:
            direction = "NEUTRAL"
            directional_votes = 0

        direction_conflict = (
            buy_votes > 0
            and sell_votes > 0
        )

        if direction_conflict:
            warnings.append(
                "direction_conflict"
            )

        if blocking_reasons:
            approved = False
            status = "BLOCKED"
            decision = "BLOCK"

        elif (
            direction in {
                "BUY",
                "SELL",
            }
            and directional_votes
            >= self.MINIMUM_DIRECTIONAL_VOTES
            and confidence
            >= self.MINIMUM_CONFIDENCE
        ):
            approved = True
            status = "APPROVED"

            if direction == "BUY":
                decision = "EXECUTE_LONG"
            else:
                decision = "EXECUTE_SHORT"

        elif (
            direction in {
                "BUY",
                "SELL",
            }
            and directional_votes > 0
        ):
            approved = False
            status = "WAITING"
            decision = "WAIT"

            warnings.append(
                "insufficient_consensus"
            )

        else:
            approved = False
            status = "REJECTED"
            decision = "REJECT"

            warnings.append(
                "no_directional_consensus"
            )

        return {
            "approved": approved,
            "status": status,
            "decision": decision,
            "direction": direction,
            "confidence": confidence,
            "votes": votes,
            "vote_summary": vote_summary,
            "directional_votes": directional_votes,
            "minimum_directional_votes": (
                self.MINIMUM_DIRECTIONAL_VOTES
            ),
            "minimum_confidence": (
                self.MINIMUM_CONFIDENCE
            ),
            "confidence_components": (
                confidence_components
            ),
            "confidence_weights": dict(
                self.CONFIDENCE_WEIGHTS
            ),
            "blocking_reasons": (
                blocking_reasons
            ),
            "confirmations": confirmations,
            "warnings": warnings,
        }

    def _extract_vote(
        self,
        *,
        member: str,
        result: dict[str, Any],
    ) -> str:
        blocking_reasons = (
            self._extract_string_list(
                result.get(
                    "blocking_reasons"
                )
            )
        )

        status = self._normalize_text(
            result.get(
                "status"
            )
        )

        decision = self._normalize_text(
            result.get(
                "decision"
            )
        )

        action = self._normalize_text(
            result.get(
                "action"
            )
        )

        direction = self._normalize_text(
            result.get(
                "direction"
            )
        )

        recommendation = self._normalize_text(
            result.get(
                "recommendation"
            )
        )

        approved = result.get(
            "approved"
        )

        if (
            blocking_reasons
            or status == "BLOCKED"
            or decision == "BLOCK"
            or action == "BLOCK"
        ):
            return "BLOCK"

        candidates = (
            decision,
            action,
            direction,
            recommendation,
            status,
        )

        for candidate in candidates:
            normalized_vote = (
                self._normalize_vote(
                    candidate
                )
            )

            if normalized_vote is not None:
                if (
                    approved is False
                    and normalized_vote
                    in {
                        "BUY",
                        "SELL",
                    }
                    and member
                    in {
                        "confluence",
                        "probability",
                        "execution",
                    }
                ):
                    return "WAIT"

                return normalized_vote

        if approved is False:
            return "WAIT"

        return "WAIT"

    def _extract_confidence(
        self,
        *,
        member: str,
        result: dict[str, Any],
    ) -> float:
        keys_by_member = {
            "trend": (
                "confidence",
                "score",
            ),
            "market_regime": (
                "confidence",
                "score",
            ),
            "probability": (
                "probability",
                "confidence",
                "score",
            ),
            "confluence": (
                "score",
                "confidence",
            ),
            "execution": (
                "confidence",
                "score",
            ),
        }

        keys = keys_by_member[
            member
        ]

        for key in keys:
            value = result.get(
                key
            )

            numeric = self._to_percentage(
                value
            )

            if numeric is not None:
                return numeric

        return 0.0

    def _weighted_confidence(
        self,
        components: dict[str, float],
    ) -> float:
        total = 0.0

        for member, value in (
            components.items()
        ):
            total += (
                value
                * self.CONFIDENCE_WEIGHTS[
                    member
                ]
            )

        return round(
            max(
                0.0,
                min(
                    total,
                    100.0,
                ),
            ),
            2,
        )

    def _normalize_vote(
        self,
        value: str,
    ) -> str | None:
        if not value:
            return None

        buy_values = {
            "BUY",
            "LONG",
            "BULLISH",
            "ALCISTA",
            "COMPRA",
            "COMPRAR",
            "BUSCAR COMPRAS",
            "EXECUTE LONG",
            "EXECUTE_LONG",
        }

        sell_values = {
            "SELL",
            "SHORT",
            "BEARISH",
            "BAJISTA",
            "VENTA",
            "VENDER",
            "BUSCAR VENTAS",
            "EXECUTE SHORT",
            "EXECUTE_SHORT",
        }

        wait_values = {
            "WAIT",
            "WAITING",
            "NEUTRAL",
            "SIDEWAYS",
            "ESPERAR",
            "NO TRADE",
            "NO_TRADE",
            "REJECT",
            "REJECTED",
            "INSUFFICIENT DATA",
            "INSUFFICIENT_DATA",
        }

        block_values = {
            "BLOCK",
            "BLOCKED",
            "BLOQUEAR",
            "BLOQUEADO",
        }

        if value in buy_values:
            return "BUY"

        if value in sell_values:
            return "SELL"

        if value in block_values:
            return "BLOCK"

        if value in wait_values:
            return "WAIT"

        return None

    def _to_percentage(
        self,
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        if isinstance(
            value,
            bool,
        ):
            return (
                100.0
                if value
                else 0.0
            )

        if isinstance(
            value,
            str,
        ):
            normalized = (
                self._normalize_text(
                    value
                )
            )

            labels = {
                "VERY HIGH": 95.0,
                "MUY ALTA": 95.0,
                "HIGH": 85.0,
                "ALTA": 85.0,
                "MEDIUM": 65.0,
                "MEDIA": 65.0,
                "LOW": 35.0,
                "BAJA": 35.0,
                "VERY LOW": 15.0,
                "MUY BAJA": 15.0,
            }

            if normalized in labels:
                return labels[
                    normalized
                ]

            value = (
                value
                .strip()
                .replace(
                    "%",
                    "",
                )
            )

        try:
            numeric = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not isfinite(
            numeric
        ):
            return None

        if (
            0.0
            <= numeric
            <= 1.0
        ):
            numeric *= 100.0

        return max(
            0.0,
            min(
                numeric,
                100.0,
            ),
        )

    def _normalize_text(
        self,
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return (
            str(
                value
            )
            .strip()
            .upper()
            .replace(
                "-",
                " ",
            )
        )

    def _extract_string_list(
        self,
        value: Any,
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(
            value,
            str,
        ):
            normalized = value.strip()

            return (
                [normalized]
                if normalized
                else []
            )

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            result: list[str] = []

            for item in value:
                normalized = (
                    str(
                        item
                    )
                    .strip()
                )

                if normalized:
                    self._append_unique(
                        result,
                        normalized,
                    )

            return result

        normalized = (
            str(
                value
            )
            .strip()
        )

        return (
            [normalized]
            if normalized
            else []
        )

    def _validate_result(
        self,
        *,
        name: str,
        value: Any,
    ) -> None:
        if not isinstance(
            value,
            dict,
        ):
            raise TypeError(
                f"{name} debe ser un diccionario."
            )

    def _extend_unique(
        self,
        target: list[str],
        values: list[str],
    ) -> None:
        for value in values:
            self._append_unique(
                target,
                value,
            )

    def _append_unique(
        self,
        target: list[str],
        value: str,
    ) -> None:
        if (
            value
            and value not in target
        ):
            target.append(
                value
            )
