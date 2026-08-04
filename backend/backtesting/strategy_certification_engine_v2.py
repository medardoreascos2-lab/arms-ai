from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StrategyCertificationResultV2:
    """
    Resultado final de certificación de una estrategia.
    """

    validation_score: float
    validation_grade: str
    status: str
    reason: str

    def __post_init__(self) -> None:

        self.validation_score = round(
            float(
                self.validation_score
            ),
            2,
        )

        self.validation_grade = str(
            self.validation_grade
        )

        self.status = str(
            self.status
        )

        self.reason = str(
            self.reason
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:

        return {
            "validation_score": (
                self.validation_score
            ),
            "validation_grade": (
                self.validation_grade
            ),
            "status": self.status,
            "reason": self.reason,
        }


class StrategyCertificationEngineV2:
    """
    Certifica una estrategia según score y grade.
    """

    CERTIFIED_GRADES = {
        "A+",
        "A",
        "A-",
    }

    PROVISIONAL_GRADES = {
        "B+",
        "B",
        "B-",
        "C+",
        "C",
    }

    VALID_GRADES = (
        CERTIFIED_GRADES
        | PROVISIONAL_GRADES
        | {
            "D",
            "F",
        }
    )

    def certify(
        self,
        *,
        validation_score,
        validation_grade,
    ) -> StrategyCertificationResultV2:

        normalized_score = (
            self._normalize_score(
                validation_score
            )
        )

        normalized_grade = (
            self._normalize_grade(
                validation_grade
            )
        )

        if (
            normalized_score >= 90.0
            and normalized_grade
            in self.CERTIFIED_GRADES
        ):
            status = "CERTIFIED"
            reason = (
                "Strategy satisfies all "
                "certification requirements."
            )

        elif (
            normalized_score >= 70.0
            and normalized_grade
            in self.PROVISIONAL_GRADES
        ):
            status = "PROVISIONAL"
            reason = (
                "Strategy requires additional "
                "validation."
            )

        else:
            status = "REJECTED"
            reason = (
                "Strategy does not satisfy "
                "minimum requirements."
            )

        return StrategyCertificationResultV2(
            validation_score=(
                normalized_score
            ),
            validation_grade=(
                normalized_grade
            ),
            status=status,
            reason=reason,
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
    def _normalize_grade(
        cls,
        value,
    ) -> str:

        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                "validation_grade debe ser str."
            )

        normalized = value.strip().upper()

        if not normalized:
            raise ValueError(
                "validation_grade no puede estar vacío."
            )

        if normalized not in cls.VALID_GRADES:
            raise ValueError(
                "validation_grade no es válido."
            )

        return normalized
