from backend.intelligence.confluence_engine import ConfluenceResult
from backend.intelligence.probability_engine import ProbabilityResult
from backend.models.decision_council_result import DecisionCouncilResult
from backend.models.reasoning_result import ReasoningResult


class DecisionCouncil:
    """
    Coordina los motores de ARMS AI y emite una única decisión final.

    Aunque una operación sea bloqueada por riesgo o sesión,
    conserva los diagnósticos técnicos para explicar la decisión.
    """

    def evaluate(
        self,
        confluence: ConfluenceResult,
        probability: ProbabilityResult,
        reasoning: ReasoningResult,
        risk_allowed: bool,
        session_allowed: bool,
    ) -> DecisionCouncilResult:
        result = DecisionCouncilResult(
            probability=probability.probability,
            confidence=probability.confidence,
            confluence_score=confluence.score,
            reasoning_score=reasoning.quality_score,
        )

        # ==============================
        # CONSERVAR DIAGNÓSTICOS
        # ==============================
        self._extend_unique(
            result.reasons,
            confluence.confirmations,
        )
        self._extend_unique(
            result.reasons,
            probability.positive_factors,
        )
        self._extend_unique(
            result.reasons,
            reasoning.reasons,
        )

        self._extend_unique(
            result.warnings,
            confluence.warnings,
        )
        self._extend_unique(
            result.warnings,
            probability.negative_factors,
        )

        self._extend_unique(
            result.blockers,
            reasoning.blockers,
        )

        # ==============================
        # BLOQUEOS OBLIGATORIOS
        # ==============================
        if not risk_allowed:
            self._append_unique(
                result.blockers,
                "Riesgo no autorizado.",
            )

        if not session_allowed:
            self._append_unique(
                result.blockers,
                "Sesión no autorizada.",
            )

        if not risk_allowed or not session_allowed:
            result.votes_against = max(
                1,
                len(result.blockers),
            )
            return result

        # ==============================
        # NORMALIZAR DIRECCIONES
        # ==============================
        confluence_direction = self._normalize_direction(
            confluence.direction
        )
        probability_direction = self._normalize_direction(
            probability.recommendation
        )
        reasoning_direction = self._normalize_direction(
            reasoning.direction
        )

        directions = {
            direction
            for direction in (
                confluence_direction,
                probability_direction,
                reasoning_direction,
            )
            if direction != "NEUTRAL"
        }

        # ==============================
        # CONFLICTO DE DIRECCIÓN
        # ==============================
        if len(directions) > 1:
            self._append_unique(
                result.blockers,
                "Conflicto de dirección entre motores.",
            )
            result.votes_against += 1
            return result

        if not directions:
            self._append_unique(
                result.blockers,
                "No existe una dirección operativa clara.",
            )
            result.votes_against += 1
            return result

        direction = directions.pop()
        result.direction = direction

        # ==============================
        # VOTACIÓN DE LOS MOTORES
        # ==============================
        if confluence.approved:
            result.votes_for += 1
        else:
            result.votes_against += 1

        if probability.approved:
            result.votes_for += 1
        else:
            result.votes_against += 1

        if reasoning.authorized:
            result.votes_for += 1
        else:
            result.votes_against += 1

        approved = (
            result.votes_for == 3
            and result.votes_against == 0
            and confluence.approved
            and probability.approved
            and reasoning.authorized
        )

        if not approved:
            return result

        # ==============================
        # DECISIÓN FINAL
        # ==============================
        result.approved = True
        result.action = direction
        result.grade = self._calculate_grade(
            confluence_grade=confluence.grade,
            reasoning_grade=reasoning.grade,
            probability=probability.probability,
        )

        return result

    def _append_unique(
        self,
        target: list[str],
        item: str,
    ) -> None:
        if item and item not in target:
            target.append(item)

    def _extend_unique(
        self,
        target: list[str],
        items: list[str],
    ) -> None:
        for item in items:
            self._append_unique(target, item)

    def _normalize_direction(self, value: str) -> str:
        normalized = str(value).strip().upper()

        if normalized in {
            "BUY",
            "COMPRA",
            "COMPRAR",
            "LONG",
            "ALCISTA",
        }:
            return "BUY"

        if normalized in {
            "SELL",
            "VENTA",
            "VENDER",
            "SHORT",
            "BAJISTA",
        }:
            return "SELL"

        return "NEUTRAL"

    def _calculate_grade(
        self,
        confluence_grade: str,
        reasoning_grade: str,
        probability: float,
    ) -> str:
        if (
            confluence_grade == "A+"
            and reasoning_grade == "A+"
            and probability >= 80.0
        ):
            return "A+"

        if (
            confluence_grade in {"A+", "A"}
            and reasoning_grade in {"A+", "A"}
            and probability >= 70.0
        ):
            return "A"

        return "B"
