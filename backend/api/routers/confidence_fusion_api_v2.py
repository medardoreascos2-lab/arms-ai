from fastapi import APIRouter


from backend.intelligence.confidence_fusion_engine import (
    ConfidenceFusionEngine,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Confidence Fusion Intelligence"

    ],

)



engine = ConfidenceFusionEngine()



@router.get(
    "/confidence-fusion"
)
def confidence_fusion_dashboard():


    report = engine.calculate(

        technical_score=93,

        probability_score=90,

        structure_score=95,

        risk_score=100,

        memory_score=100,

    )


    return {


        "technical_score":

            report.technical_score,


        "probability_score":

            report.probability_score,


        "structure_score":

            report.structure_score,


        "risk_score":

            report.risk_score,


        "memory_score":

            report.memory_score,


        "final_confidence":

            report.final_confidence,


        "quality":

            report.quality,


        "decision":

            report.decision,


        "explanation":

            report.explanation,


        "recommendations":

            report.recommendations,


    }
