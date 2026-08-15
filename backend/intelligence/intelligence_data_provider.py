from dataclasses import dataclass
from typing import List



@dataclass
class IntelligenceData:

    technical_score: float

    probability_score: float

    structure_score: float

    risk_score: float

    memory_score: float

    risk_allowed: bool

    sources: List[str]

    explanations: List[str]




class IntelligenceDataProvider:


    def __init__(self):

        pass



    def collect(

        self,

        technical_report=None,

        structure_report=None,

        risk_report=None,

        probability_score: float = 0,

        memory_score: float = 0,

    ) -> IntelligenceData:



        sources = []

        explanations = []



        # TECHNICAL INTELLIGENCE

        if technical_report:

            technical_score = (

                technical_report.technical_score

            )

            sources.append(

                "Technical Intelligence"

            )

            explanations.extend(

                technical_report.reasoning

            )


        else:

            technical_score = 0





        # MARKET STRUCTURE INTELLIGENCE

        if structure_report:

            structure_score = (

                structure_report.structure_score

            )

            sources.append(

                "Market Structure Intelligence"

            )

            explanations.extend(

                structure_report.reasoning

            )


        else:

            structure_score = 0





        # RISK INTELLIGENCE

        if risk_report:

            risk_score = (

                risk_report.risk_score

            )

            risk_allowed = (

                risk_report.position_allowed

            )

            sources.append(

                "Risk Intelligence"

            )

            explanations.extend(

                risk_report.reasoning

            )


        else:

            risk_score = 0

            risk_allowed = False





        if probability_score:

            sources.append(

                "Probability Intelligence"

            )





        if memory_score:

            sources.append(

                "Trading Memory Intelligence"

            )





        return IntelligenceData(

            technical_score=technical_score,

            probability_score=probability_score,

            structure_score=structure_score,

            risk_score=risk_score,

            memory_score=memory_score,

            risk_allowed=risk_allowed,

            sources=sources,

            explanations=explanations,

        )
