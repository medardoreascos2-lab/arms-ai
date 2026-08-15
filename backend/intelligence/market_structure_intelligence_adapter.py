from dataclasses import dataclass
from typing import List



@dataclass
class MarketStructureReport:

    structure_score: float

    trend: str

    bos: bool

    choch: bool

    fvg: bool

    session_alignment: bool

    reasoning: List[str]




class MarketStructureIntelligenceAdapter:


    def __init__(self):

        pass



    def analyze(

        self,

        bos_confirmed: bool,

        choch_confirmed: bool,

        fvg_present: bool,

        session_aligned: bool,

        trend: str,

    ) -> MarketStructureReport:



        score = 0

        reasoning = []



        # BOS

        if bos_confirmed:

            score += 40

            reasoning.append(

                "BOS confirmado: estructura rota."

            )

        else:

            reasoning.append(

                "Sin BOS confirmado."

            )



        # CHOCH

        if choch_confirmed:

            score += 30

            reasoning.append(

                "CHOCH detectado: cambio de carácter."

            )

        else:

            reasoning.append(

                "Sin CHOCH confirmado."

            )



        # FVG

        if fvg_present:

            score += 20

            reasoning.append(

                "FVG identificado como zona de interés."

            )

        else:

            reasoning.append(

                "Sin FVG relevante."

            )



        # SESSION

        if session_aligned:

            score += 10

            reasoning.append(

                "Sesión alineada con la estructura."

            )

        else:

            reasoning.append(

                "Sesión sin confirmación."

            )



        return MarketStructureReport(

            structure_score=score,

            trend=trend,

            bos=bos_confirmed,

            choch=choch_confirmed,

            fvg=fvg_present,

            session_alignment=session_aligned,

            reasoning=reasoning,

        )
