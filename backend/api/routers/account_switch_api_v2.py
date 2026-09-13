"""Legacy URL with the same authorization, JSON contract, and safety coordinator."""
from fastapi import APIRouter, Depends

from backend.api.admin_authorization_dependency_v2 import (
    require_admin_authorization_v2,
)
from backend.api.routers.account_manager_api_v2 import switch_account


router = APIRouter(
    prefix="/api/v2/dashboard/account",
    tags=["account"],
    dependencies=[Depends(require_admin_authorization_v2)],
)

router.add_api_route("/switch", switch_account, methods=["POST"])
