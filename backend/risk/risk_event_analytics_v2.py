from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable


class RiskEventAnalyticsV2:
    """
    Read-only analytics over execution risk events.

    The analytics layer deliberately does not mutate the event store.
    It consumes event dictionaries and produces deterministic summaries.
    """

    def summarize(
        self,
        events: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized_events = [
            deepcopy(event)
            for event in events
            if isinstance(event, dict)
        ]

        total = len(normalized_events)

        event_type_counts: Counter[str] = Counter()
        symbol_counts: Counter[str] = Counter()
        reason_counts: Counter[str] = Counter()

        approved = 0
        blocked = 0
        unknown_decision = 0

        for event in normalized_events:
            event_type = self._clean_string(
                event.get("event_type")
            )
            if event_type is not None:
                event_type_counts[event_type] += 1

            symbol = self._extract_symbol(event)
            if symbol is not None:
                symbol_counts[symbol] += 1

            reasons = self._extract_reasons(event)
            reason_counts.update(reasons)

            decision = self._extract_approved(event)

            if decision is True:
                approved += 1
            elif decision is False:
                blocked += 1
            else:
                unknown_decision += 1

        decision_total = approved + blocked

        approval_rate = (
            round(
                approved / decision_total * 100.0,
                2,
            )
            if decision_total
            else None
        )

        block_rate = (
            round(
                blocked / decision_total * 100.0,
                2,
            )
            if decision_total
            else None
        )

        return {
            "total_events": total,
            "decision_summary": {
                "approved": approved,
                "blocked": blocked,
                "unknown": unknown_decision,
                "decision_total": decision_total,
                "approval_rate_percent": approval_rate,
                "block_rate_percent": block_rate,
            },
            "by_event_type": self._sorted_counts(
                event_type_counts
            ),
            "by_symbol": self._sorted_counts(
                symbol_counts
            ),
            "by_reason": self._sorted_counts(
                reason_counts
            ),
        }

    @staticmethod
    def _clean_string(
        value: Any,
    ) -> str | None:
        if not isinstance(value, str):
            return None

        normalized = value.strip()

        if not normalized:
            return None

        return normalized

    def _extract_symbol(
        self,
        event: dict[str, Any],
    ) -> str | None:
        candidates = [
            event.get("symbol"),
            self._nested_get(
                event,
                "signal",
                "symbol",
            ),
            self._nested_get(
                event,
                "risk_context",
                "symbol",
            ),
            self._nested_get(
                event,
                "payload",
                "symbol",
            ),
        ]

        for candidate in candidates:
            normalized = self._clean_string(
                candidate
            )

            if normalized is not None:
                return normalized

        return None

    def _extract_approved(
        self,
        event: dict[str, Any],
    ) -> bool | None:
        candidates = [
            event.get("approved"),
            self._nested_get(
                event,
                "risk_evaluation",
                "approved",
            ),
            self._nested_get(
                event,
                "exposure_evaluation",
                "approved",
            ),
            self._nested_get(
                event,
                "payload",
                "approved",
            ),
        ]

        for candidate in candidates:
            if isinstance(candidate, bool):
                return candidate

        event_type = self._clean_string(
            event.get("event_type")
        )

        if event_type is not None:
            lowered = event_type.lower()

            if "blocked" in lowered or "rejected" in lowered:
                return False

            if "approved" in lowered or "accepted" in lowered:
                return True

        return None

    def _extract_reasons(
        self,
        event: dict[str, Any],
    ) -> list[str]:
        candidates: list[Any] = [
            event.get("reason"),
            event.get("reasons"),
            event.get("blocking_reasons"),
            self._nested_get(
                event,
                "risk_evaluation",
                "reason",
            ),
            self._nested_get(
                event,
                "risk_evaluation",
                "reasons",
            ),
            self._nested_get(
                event,
                "risk_evaluation",
                "blocking_reasons",
            ),
            self._nested_get(
                event,
                "exposure_evaluation",
                "reason",
            ),
            self._nested_get(
                event,
                "exposure_evaluation",
                "blocking_reasons",
            ),
            self._nested_get(
                event,
                "payload",
                "reason",
            ),
            self._nested_get(
                event,
                "payload",
                "blocking_reasons",
            ),
        ]

        result: list[str] = []

        for candidate in candidates:
            if isinstance(candidate, str):
                normalized = self._clean_string(
                    candidate
                )
                if normalized is not None:
                    result.append(normalized)

            elif isinstance(candidate, (list, tuple, set)):
                for item in candidate:
                    normalized = self._clean_string(
                        item
                    )
                    if normalized is not None:
                        result.append(normalized)

        # Avoid counting the same reason twice inside
        # a single event while preserving deterministic order.
        return list(dict.fromkeys(result))

    @staticmethod
    def _nested_get(
        payload: dict[str, Any],
        *keys: str,
    ) -> Any:
        current: Any = payload

        for key in keys:
            if not isinstance(current, dict):
                return None

            current = current.get(key)

        return current

    @staticmethod
    def _sorted_counts(
        counts: Counter[str],
    ) -> dict[str, int]:
        return {
            key: counts[key]
            for key in sorted(
                counts,
                key=lambda item: (
                    -counts[item],
                    item,
                ),
            )
        }
