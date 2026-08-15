from dataclasses import dataclass
from typing import List



@dataclass
class IntelligenceDecisionReport:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    confidence: float

    quality: str

    decision: str

    reasoning: List[str]

    recommendations: List[str]




class ConfidenceIntelligenceOrchestrator:


    def __init__(self):

        pass



    def analyze(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        technical_score: float,

        probability_score: float,

        structure_score: float,

        risk_score: float,

        memory_score: float,

    ) -> IntelligenceDecisionReport:



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




        reasoning = [

            f"Technical intelligence: {technical_score}%",

            f"Probability analysis: {probability_score}%",

            f"Market structure: {structure_score}%",

            f"Risk validation: {risk_score}%",

            f"Historical memory: {memory_score}%",

            f"Final confidence: {confidence}%",

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

                "Evitar ejecución."

            )




        return IntelligenceDecisionReport(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            confidence=confidence,

            quality=quality,

            decision=decision,

            reasoning=reasoning,

            recommendations=recommendations,

        )
