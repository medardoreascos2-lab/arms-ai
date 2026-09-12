"""One JSON contract for both account-switch routes."""
from pydantic import BaseModel, ConfigDict, Field


class AccountSwitchRequestV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    account_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    profile_name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Z][A-Z0-9_]*$")
