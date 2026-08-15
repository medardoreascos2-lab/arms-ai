from dataclasses import dataclass
from typing import List



@dataclass
class DecisionMemoryReport:

    technical_confidence: float

    memory_confidence: float

    final_confidence: float

    memory_reliability: str

    decision: str

    explanation: List[str]

    recommendations: List[str]



class DecisionMemoryAdapter:


    def __init__(self):
        pass



    def evaluate(

        self,

        technical_confidence: float,

        memory_report

    ) -> DecisionMemoryReport:



        adjustment = getattr(

            memory_report,

            "adjustment",

            0

        )


        reliability = getattr(

            memory_report,

            "reliability",

            "NO DATA"

        )



        memory_confidence = getattr(

            memory_report,

            "historical_score",

            0

        )



        final_confidence = (

            technical_confidence

            +

            adjustment

        )



        if final_confidence > 100:

            final_confidence = 100



        if final_confidence < 0:

            final_confidence = 0





        if final_confidence >= 85:

            decision = "APPROVED"


        elif final_confidence >= 60:

            decision = "REVIEW"


        else:

            decision = "REJECTED"





        explanation = [

            f"Confianza técnica: {technical_confidence}%",

            f"Memoria histórica: {memory_confidence}%",

            f"Ajuste aplicado: {adjustment}%",

            f"Confianza final: {final_confidence}%",

            f"Confiabilidad memoria: {reliability}",

        ]





        recommendations = []



        if decision == "APPROVED":

            recommendations.append(

                "Setup validado por análisis técnico y memoria histórica."

            )


        elif decision == "REVIEW":

            recommendations.append(

                "Esperar confirmación adicional antes de ejecutar."

            )


        else:

            recommendations.append(

                "Evitar operación hasta mejorar condiciones."

            )





        return DecisionMemoryReport(

            technical_confidence=technical_confidence,

            memory_confidence=memory_confidence,

            final_confidence=final_confidence,

            memory_reliability=reliability,

            decision=decision,

            explanation=explanation,

            recommendations=recommendations,

        )
