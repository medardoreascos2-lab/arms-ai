from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ValidationGradeResultV2:
    """
    Resultado de la clasificación ejecutiva
    de una estrategia validada.
    """

    validation_score: float
    grade: str
    recommendation: str

    def __post_init__(self) -> None:

        self.validation_score = round(
            float(
                self.validation_score
            ),
            2,
        )

        self.grade = str(
            self.grade
        )

        self.recommendation = str(
            self.recommendation
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "validation_score": (
                self.validation_score
            ),
            "grade": self.grade,
            "recommendation": (
                self.recommendation
            ),
        }


class ValidationGradeEngineV2:
    """
    Convierte un validation score de 0 a 100
    en grade y recomendación ejecutiva.
    """

    GRADE_THRESHOLDS = (
        (97.0, "A+"),
        (93.0, "A"),
        (90.0, "A-"),
        (87.0, "B+"),
        (83.0, "B"),
        (80.0, "B-"),
        (75.0, "C+"),
        (70.0, "C"),
        (60.0, "D"),
        (0.0, "F"),
    )

    def calculate(
        self,
        *,
        validation_score,
    ) -> ValidationGradeResultV2:

        normalized_score = (
            self._normalize_score(
                validation_score
            )
        )

        grade = self._resolve_grade(
            normalized_score
        )

        recommendation = (
            self._resolve_recommendation(
                normalized_score
            )
        )

        return ValidationGradeResultV2(
            validation_score=(
                normalized_score
            ),
            grade=grade,
            recommendation=(
                recommendation
            ),
        )

    @staticmethod
    def _normalize_score(
        value,
    ) -> float:

        if (
            not isinstance(
                value,
                (
                    int,
                    float,
                ),
            )
            or isinstance(
                value,
                bool,
            )
        ):
            raise TypeError(
                "validation_score debe ser numérico."
            )

        normalized = float(
            value
        )

        return min(
            100.0,
            max(
                0.0,
                normalized,
            ),
        )

    @classmethod
    def _resolve_grade(
        cls,
        score: float,
    ) -> str:

        for threshold, grade in (
            cls.GRADE_THRESHOLDS
        ):
            if score >= threshold:
                return grade

        return "F"

    @staticmethod
    def _resolve_recommendation(
        score: float,
    ) -> str:

        if score >= 93.0:
            return (
                "READY FOR LIVE DEPLOYMENT"
            )

        if score >= 70.0:
            return (
                "NEEDS IMPROVEMENT"
            )

        return "REJECT STRATEGY"
