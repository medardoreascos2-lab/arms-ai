from dataclasses import dataclass
from typing import List



@dataclass
class IntelligenceDecisionReportV3:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    final_confidence: float

    quality: str

    decision: str

    execution_status: str

    risk_allowed: bool

    risk_score: float

    sources: List[str]

    reasoning: List[str]

    recommendations: List[str]




class ConfidenceIntelligenceOrchestratorV3:


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

    ) -> IntelligenceDecisionReportV3:



        technical_score = intelligence_data.technical_score

        probability_score = intelligence_data.probability_score

        structure_score = intelligence_data.structure_score

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

        elif confidence >= 75:

            quality = "A"

        else:

            quality = "B"





        risk_allowed = (

            intelligence_data.risk_allowed

        )





        reasoning = []



        reasoning.extend(

            intelligence_data.explanations

        )



        reasoning.append(

            f"Final confidence: {confidence}%"

        )





        recommendations = []





        if not risk_allowed:


            decision = "BLOCKED"

            execution_status = "STOP"


            reasoning.append(

                "Operación bloqueada por validación de riesgo."

            )


            recommendations.append(

                "Reducir riesgo antes de ejecutar."

            )





        elif confidence >= 90:


            decision = "APPROVED"

            execution_status = "READY"


            recommendations.append(

                "Setup aprobado para ejecución."

            )





        elif confidence >= 75:


            decision = "REVIEW"

            execution_status = "WAIT"


            recommendations.append(

                "Esperar confirmación adicional."

            )





        else:


            decision = "REJECTED"

            execution_status = "STOP"


            recommendations.append(

                "Evitar operación."

            )





        return IntelligenceDecisionReportV3(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            final_confidence=confidence,

            quality=quality,

            decision=decision,

            execution_status=execution_status,

            risk_allowed=risk_allowed,

            risk_score=risk_score,

            sources=intelligence_data.sources,

            reasoning=reasoning,

            recommendations=recommendations,

        )
