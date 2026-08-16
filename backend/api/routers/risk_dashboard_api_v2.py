from fastapi import APIRouter

from backend.api.dashboard.risk_dashboard_api_v1 import (
    RiskDashboardAPIv1,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["risk-dashboard"],
)


risk_api = RiskDashboardAPIv1()


@router.get("/risk")
def get_risk_dashboard():

    return (
        risk_api
        .get_risk_dashboard()
    )
