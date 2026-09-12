"""Legacy URL, identical JSON contract and safety coordinator."""
from fastapi import APIRouter
from backend.api.routers.account_manager_api_v2 import switch_account

router = APIRouter(prefix="/api/v2/dashboard/account", tags=["account"])
router.add_api_route("/switch", switch_account, methods=["POST"])
