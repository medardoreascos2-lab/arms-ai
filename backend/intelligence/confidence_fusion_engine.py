from dataclasses import dataclass
from typing import List


@dataclass
class ConfidenceFusionReport:

    technical_score: float

    probability_score: float

    structure_score: float

    risk_score: float

    memory_score: float

    final_confidence: float

    quality: str

    decision: str

    explanation: List[str]

    recommendations: List[str]



class ConfidenceFusionEngine:


    def __init__(self):
        pass



    def calculate(

        self,

        technical_score: float,

        probability_score: float,

        structure_score: float,

        risk_score: float,

        memory_score: float,

    ) -> ConfidenceFusionReport:



        final_confidence = (

            technical_score * 0.30

            +

            probability_score * 0.25

            +

            structure_score * 0.20

            +

            risk_score * 0.15

            +

            memory_score * 0.10

        )



        if final_confidence >= 90:

            quality = "A+"

            decision = "APPROVED"


        elif final_confidence >= 75:

            quality = "A"

            decision = "REVIEW"


        else:

            quality = "B"

            decision = "REJECTED"



        explanation = [

            f"Technical score: {technical_score}%",

            f"Probability score: {probability_score}%",

            f"Structure score: {structure_score}%",

            f"Risk score: {risk_score}%",

            f"Memory score: {memory_score}%",

            f"Final confidence: {round(final_confidence,2)}%",

        ]



        recommendations = []


        if decision == "APPROVED":

            recommendations.append(

                "Setup aprobado por convergencia de inteligencia."

            )

        elif decision == "REVIEW":

            recommendations.append(

                "Esperar confirmación adicional."

            )

        else:

            recommendations.append(

                "Evitar operación."

            )



        return ConfidenceFusionReport(

            technical_score=technical_score,

            probability_score=probability_score,

            structure_score=structure_score,

            risk_score=risk_score,

            memory_score=memory_score,

            final_confidence=round(

                final_confidence,

                2

            ),

            quality=quality,

            decision=decision,

            explanation=explanation,

            recommendations=recommendations,

        )
