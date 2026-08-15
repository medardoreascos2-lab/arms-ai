from dataclasses import dataclass
from typing import List



@dataclass
class MemoryConfidenceReport:

    base_confidence: float

    memory_adjustment: float

    final_confidence: float

    reliability: str

    decision: str

    insights: List[str]

    recommendations: List[str]



class MemoryConfidenceLayer:


    def __init__(self):
        pass



    def apply(

        self,

        base_confidence: float,

        memory_score

    ) -> MemoryConfidenceReport:



        adjustment = getattr(

            memory_score,

            "adjustment",

            0

        )


        reliability = getattr(

            memory_score,

            "reliability",

            "NO DATA"

        )



        final_confidence = (

            base_confidence

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





        insights = [

            f"Confianza base: {base_confidence}%",

            f"Ajuste memoria: {adjustment}%",

            f"Confianza final: {final_confidence}%",

            f"Memoria histórica: {reliability}",

        ]



        recommendations = []



        if decision == "APPROVED":

            recommendations.append(

                "La memoria histórica aumenta la confianza del setup."

            )

        elif decision == "REVIEW":

            recommendations.append(

                "Revisar condiciones antes de ejecutar."

            )

        else:

            recommendations.append(

                "Evitar ejecución hasta mejorar la confianza."

            )





        return MemoryConfidenceReport(

            base_confidence=base_confidence,

            memory_adjustment=adjustment,

            final_confidence=final_confidence,

            reliability=reliability,

            decision=decision,

            insights=insights,

            recommendations=recommendations,

        )
