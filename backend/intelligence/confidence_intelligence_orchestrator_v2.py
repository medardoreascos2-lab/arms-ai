from dataclasses import dataclass
from typing import List



@dataclass
class IntelligenceDecisionReportV2:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    technical_score: float

    structure_score: float

    probability_score: float

    risk_score: float

    memory_score: float

    final_confidence: float

    quality: str

    decision: str

    sources: List[str]

    reasoning: List[str]

    recommendations: List[str]




class ConfidenceIntelligenceOrchestratorV2:



    def __init__(self):

        pass



    def analyze(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        intelligence_data,

    ) -> IntelligenceDecisionReportV2:



        technical_score = intelligence_data.technical_score

        structure_score = intelligence_data.structure_score

        probability_score = intelligence_data.probability_score

        risk_score = intelligence_data.risk_score

        memory_score = intelligence_data.memory_score



        confidence = (

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



        confidence = round(

            confidence,

            2

        )




        if confidence >= 90:

            quality = "A+"

            decision = "APPROVED"


        elif confidence >= 75:

            quality = "A"

            decision = "REVIEW"


        else:

            quality = "B"

            decision = "REJECTED"




        reasoning = []



        if hasattr(

            intelligence_data,

            "explanations"

        ):

            reasoning.extend(

                intelligence_data.explanations

            )



        reasoning.append(

            f"Final confidence: {confidence}%"

        )




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

                "Evitar ejecución."

            )



        return IntelligenceDecisionReportV2(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            technical_score=technical_score,

            structure_score=structure_score,

            probability_score=probability_score,

            risk_score=risk_score,

            memory_score=memory_score,

            final_confidence=confidence,

            quality=quality,

            decision=decision,

            sources=intelligence_data.sources,

            reasoning=reasoning,

            recommendations=recommendations,

        )
