from backend.intelligence.confluence_engine import ConfluenceResult
from backend.intelligence.probability_engine import ProbabilityResult
from backend.models.decision_council_result import DecisionCouncilResult
from backend.models.reasoning_result import ReasoningResult


class DecisionCouncil:
    """
    Coordina los motores de ARMS AI y emite una única decisión final.
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

        if not risk_allowed:
            result.blockers.append("Riesgo no autorizado.")

        if not session_allowed:
            result.blockers.append("Sesión no autorizada.")

        if result.blockers:
            result.votes_against += len(result.blockers)
            return result

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

        if len(directions) > 1:
            result.blockers.append(
                "Conflicto de dirección entre motores."
            )
            result.votes_against += 1
            return result

        if not directions:
            result.blockers.append(
                "No existe una dirección operativa clara."
            )
            result.votes_against += 1
            return result

        direction = directions.pop()
        result.direction = direction

        if confluence.approved:
            result.votes_for += 1
            result.reasons.extend(confluence.confirmations)
        else:
            result.votes_against += 1
            result.warnings.extend(confluence.warnings)

        if probability.approved:
            result.votes_for += 1
            result.reasons.extend(probability.positive_factors)
        else:
            result.votes_against += 1
            result.warnings.extend(probability.negative_factors)

        if reasoning.authorized:
            result.votes_for += 1
            result.reasons.extend(reasoning.reasons)
        else:
            result.votes_against += 1
            result.blockers.extend(reasoning.blockers)

        approved = (
            result.votes_for == 3
            and result.votes_against == 0
            and confluence.approved
            and probability.approved
            and reasoning.authorized
        )

        if not approved:
            return result

        result.approved = True
        result.action = direction
        result.grade = self._calculate_grade(
            confluence_grade=confluence.grade,
            reasoning_grade=reasoning.grade,
            probability=probability.probability,
        )

        return result

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
