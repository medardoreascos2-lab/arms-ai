from fastapi import APIRouter


router = APIRouter(
    prefix="/api/v2/learning",
    tags=["Learning Intelligence"]
)


@router.get("/summary")
def learning_summary():

    return {

        "total_trades": 1,

        "win_rate": 100.0,

        "dominant_direction": "BUY",

        "best_pattern": "EMA50 Smart Money",

        "recommendation":
            "Mantener estrategia actual.",

    }
