from fastapi import APIRouter, Request


router = APIRouter(
    prefix="/api/v2/learning",
    tags=["Learning Intelligence"],
)


@router.get("/summary")
def learning_summary(request: Request):

    learning_service = (
        request.app.state.trade_learning_service_v2
    )

    report = learning_service.get_learning_report()

    return {
        "total_trades": report.total_trades,
        "winning_trades": report.winning_trades,
        "losing_trades": report.losing_trades,
        "win_rate": report.win_rate,
        "dominant_direction": report.dominant_direction,
        "best_pattern": report.best_pattern,
        "recommendation": report.recommendation,
        "insights": report.insights,
    }
